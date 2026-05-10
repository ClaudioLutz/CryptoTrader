"""Phase 4 Backtest — Platt-Scaling-Calibration + Threshold-Tuning auf max-EV.

Auf der Phase-2-Basis (Multi-Coin-Pool, simples Vorzeichen-Target):
- Train-Split: Inner-Train (60%) -> Cal-Hold-Out (20%) -> Val (20%)
- Calibration: CalibratedClassifierCV(method='sigmoid', cv='prefit') auf Cal
- Threshold-Tuning: auf Val-Set Threshold finden, der max Expected Value
  pro selektiertem Trade liefert (Forward-Return nach Fees)
- Test: kalibriertes Modell + getunter Threshold

Vergleich:
- Baseline (Phase 2 setup, threshold=0.65, keine Calibration)
- Phase 4 (Calibration + tuned Threshold)
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

CP = Path("C:/Codes/coin_prediction")
COINS = ["BTC", "ETH", "SOL", "BNB", "TRX"]
HORIZON_H = 72
TRAIN_H = 8760
TEST_H = 168
EMBARGO_H = 72
FEE_RT = 0.001

CLF_P = {
    "objective": "binary", "metric": "binary_logloss",
    "learning_rate": 0.03, "max_depth": 5, "n_estimators": 500,
    "num_leaves": 31, "subsample": 0.8, "colsample_bytree": 0.8,
    "min_child_samples": 30, "verbose": -1, "n_jobs": 4, "random_state": 42,
}


def build_features(ohlcv: pd.DataFrame, coin: str) -> pd.DataFrame:
    close = ohlcv["close"].astype(float)
    volume = ohlcv["volume"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    f = pd.DataFrame(index=ohlcv.index)
    for p in [1, 4, 12, 24, 72, 168]:
        f[f"ret_{p}h"] = close.pct_change(p)
    hourly_ret = close.pct_change()
    for w in [12, 24, 72, 168]:
        f[f"vol_{w}h"] = hourly_ret.rolling(w).std()
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    f["rsi_14h"] = 100 - (100 / (1 + rs))
    f["vol_ratio_24_168"] = (
        volume.rolling(24).mean() / volume.rolling(168).mean().replace(0, np.nan)
    )
    f["hl_range_24h"] = (high.rolling(24).max() - low.rolling(24).min()) / close
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    f["macd"] = ema12 - ema26
    f["macd_signal"] = f["macd"].ewm(span=9, adjust=False).mean()
    f["macd_hist"] = f["macd"] - f["macd_signal"]
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    f["bb_position"] = (close - sma20) / (2 * std20).replace(0, np.nan)

    fp = CP / f"data/raw/{coin}_funding.parquet"
    if fp.exists():
        funding = pd.read_parquet(fp)
        if "timestamp" in funding.columns:
            funding = funding.set_index("timestamp").sort_index()
        fr = funding["funding_rate"].reindex(f.index, method="ffill")
        f["funding_rate"] = fr
        f["funding_3d_ma"] = fr.rolling(72).mean()
    else:
        f["funding_rate"] = 0.0
        f["funding_3d_ma"] = 0.0

    try:
        from src.ingestion.macro_fetcher import build_macro_features
        macro = build_macro_features(close, CP / "data", interval="1h")
        if not macro.empty:
            if hasattr(f.index, "tz") and f.index.tz is not None and macro.index.tz is None:
                macro.index = macro.index.tz_localize("UTC")
            valid_cols = macro.columns[macro.notna().any()]
            macro_ff = macro[valid_cols].ffill()
            f = pd.concat([f, macro_ff], axis=1)
    except Exception as e:
        print(f"  macro_features failed for {coin}: {e}")
    return f


def build_target(close: pd.Series) -> pd.Series:
    fr = close.shift(-HORIZON_H) / close - 1
    t = (fr > 0).astype(float)
    t[fr.isna()] = np.nan
    return t


def build_pool() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, dict]:
    all_X = []
    all_y_vals = []
    all_coin_vals = []
    all_ts_vals = []
    closes: dict[str, pd.Series] = {}
    for idx, coin in enumerate(COINS):
        ohlcv = pd.read_parquet(CP / f"data/raw/{coin}_USDT_1h.parquet")
        if "timestamp" in ohlcv.columns:
            ohlcv = ohlcv.set_index("timestamp").sort_index()
        close = ohlcv["close"].astype(float)
        closes[coin] = close
        feats = build_features(ohlcv, coin)
        tgt = build_target(close)
        common = feats.index.intersection(tgt.dropna().index)
        X = feats.loc[common].copy()
        y = tgt.loc[common].copy()
        valid = X.notna().all(axis=1) & y.notna()
        X, y = X[valid], y[valid]
        X["coin_id"] = idx
        all_X.append(X.reset_index(drop=True))
        all_y_vals.append(y.values)
        all_coin_vals.append(np.full(len(X), coin, dtype=object))
        all_ts_vals.append(X.index.values)
    X_pool = pd.concat(all_X, ignore_index=True)
    y_pool = np.concatenate(all_y_vals)
    coin_pool = np.concatenate(all_coin_vals)
    ts_pool = pd.DatetimeIndex(np.concatenate(all_ts_vals)).tz_localize("UTC")
    order = np.argsort(ts_pool.values)
    return (
        X_pool.iloc[order].reset_index(drop=True),
        y_pool[order],
        coin_pool[order],
        ts_pool[order],
        closes,
    )


def find_max_ev_threshold(
    proba: np.ndarray, future_ret: np.ndarray, fee: float = FEE_RT,
    min_n: int = 5,
) -> tuple[float, float]:
    """Findet den Threshold mit max mean Net-Return pro selektiertem Trade.

    Tested thresholds in [0.40, 0.80] step 0.02. Gibt (best_thresh, best_ev)
    zurueck. Falls fuer jeden Threshold n < min_n Trades, fallback auf 0.5.
    """
    best_t = 0.5
    best_ev = -np.inf
    for t in np.arange(0.40, 0.81, 0.02):
        sel = proba >= t
        n_sel = int(sel.sum())
        if n_sel < min_n:
            continue
        ev = float((future_ret[sel] - fee).mean())
        if ev > best_ev:
            best_ev = ev
            best_t = float(t)
    if best_ev == -np.inf:
        return 0.5, 0.0
    return best_t, best_ev


def run_calibrated_backtest(
    X: pd.DataFrame, y: np.ndarray, coin_arr: np.ndarray,
    ts_arr: pd.DatetimeIndex, closes: dict[str, pd.Series],
    use_calibration: bool = True, use_threshold_tuning: bool = True,
    fixed_threshold: float = 0.65,
) -> dict:
    times_unique = pd.DatetimeIndex(
        np.unique(ts_arr.values)
    ).tz_localize("UTC").sort_values()
    n_t = len(times_unique)
    if n_t < TRAIN_H + EMBARGO_H + TEST_H:
        return {"n_oos": 0}

    all_preds: list[int] = []
    all_proba: list[float] = []
    all_actual: list[int] = []
    all_coin: list[str] = []
    trade_returns: list[float] = []
    chosen_thresholds: list[float] = []
    blocked_until_per_coin: dict[str, pd.Timestamp | None] = {c: None for c in COINS}
    tt = 0
    tw = 0

    t_start = 0
    while t_start + TRAIN_H + EMBARGO_H + TEST_H <= n_t:
        train_start_t = times_unique[t_start]
        train_end_t = times_unique[t_start + TRAIN_H - 1]
        test_start_t = times_unique[t_start + TRAIN_H + EMBARGO_H]
        test_end_t = times_unique[min(t_start + TRAIN_H + EMBARGO_H + TEST_H - 1, n_t - 1)]
        train_mask = (ts_arr >= train_start_t) & (ts_arr <= train_end_t)
        test_mask = (ts_arr >= test_start_t) & (ts_arr <= test_end_t)

        Xtr_full = X.iloc[train_mask]
        ytr_full = y[train_mask]
        ts_tr = ts_arr[train_mask]
        Xte = X.iloc[test_mask]
        coin_te = coin_arr[test_mask]
        ts_te = ts_arr[test_mask]

        # 3-Way-Split der Train-Zeit: 60% Inner-Train, 20% Cal, 20% Val
        # mit Embargo zwischen aufeinanderfolgenden Sub-Splits
        tr_times_u = pd.DatetimeIndex(
            np.unique(ts_tr.values)
        ).tz_localize("UTC").sort_values()
        if len(tr_times_u) < 200:
            t_start += TEST_H
            continue
        n_tr_t = len(tr_times_u)
        cal_split_t = tr_times_u[int(n_tr_t * 0.6)]
        val_split_t = tr_times_u[int(n_tr_t * 0.8)]

        emb1 = cal_split_t - pd.Timedelta(hours=EMBARGO_H)
        emb2 = val_split_t - pd.Timedelta(hours=EMBARGO_H)

        inner_mask = ts_tr <= emb1
        cal_mask = (ts_tr >= cal_split_t) & (ts_tr <= emb2)
        val_mask = ts_tr >= val_split_t

        Xtr_inner = Xtr_full.iloc[inner_mask]
        ytr_inner = ytr_full[inner_mask]
        Xcal = Xtr_full.iloc[cal_mask]
        ycal = ytr_full[cal_mask]
        Xval = Xtr_full.iloc[val_mask]
        yval = ytr_full[val_mask]
        ts_val = ts_tr[val_mask]
        coin_val = coin_arr[train_mask][val_mask]

        if (
            len(Xtr_inner) < 200 or len(Xcal) < 100 or len(Xval) < 100
            or len(np.unique(ytr_inner)) < 2
            or len(np.unique(ycal)) < 2
            or len(np.unique(yval)) < 2
        ):
            t_start += TEST_H
            continue

        # 1) Modell auf Inner mit Early-Stopping auf Val
        m = lgb.LGBMClassifier(**CLF_P)
        m.fit(
            Xtr_inner, ytr_inner,
            eval_set=[(Xval, yval)],
            categorical_feature=["coin_id"],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
        )

        # 2) Calibration auf Cal-Hold-Out (manuelles Platt-Scaling via LogReg
        # auf raw proba). Aequivalent zu CalibratedClassifierCV(method='sigmoid')
        # ohne sklearn-API-Probleme (cv='prefit' deprecated).
        raw_test = m.predict_proba(Xte)[:, 1]
        raw_val = m.predict_proba(Xval)[:, 1]
        if use_calibration:
            raw_cal = m.predict_proba(Xcal)[:, 1]
            try:
                lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
                lr.fit(raw_cal.reshape(-1, 1), ycal)
                proba_test = lr.predict_proba(raw_test.reshape(-1, 1))[:, 1]
                proba_val = lr.predict_proba(raw_val.reshape(-1, 1))[:, 1]
            except Exception:
                proba_test = raw_test
                proba_val = raw_val
        else:
            proba_test = raw_test
            proba_val = raw_val

        # 3) Threshold-Tuning auf Val: max-EV pro selektiertem Trade
        if use_threshold_tuning:
            # Future-Returns auf Val ausrechnen (fuer EV-Schaetzung)
            ret_val = np.empty(len(Xval))
            ret_val[:] = np.nan
            for i in range(len(Xval)):
                ts_v = ts_val[i]
                cv = coin_val[i]
                cc = closes[cv]
                if ts_v not in cc.index:
                    continue
                p_v = cc.index.get_loc(ts_v)
                if p_v + HORIZON_H >= len(cc):
                    continue
                ret_val[i] = float(cc.iloc[p_v + HORIZON_H] / cc.iloc[p_v] - 1.0)
            valid_v = ~np.isnan(ret_val)
            if valid_v.sum() < 20:
                threshold = fixed_threshold
            else:
                threshold, _ = find_max_ev_threshold(
                    proba_val[valid_v], ret_val[valid_v], fee=FEE_RT
                )
        else:
            threshold = fixed_threshold

        chosen_thresholds.append(threshold)

        preds = (proba_test > 0.5).astype(int)
        for i in range(len(Xte)):
            ts = ts_te[i]
            coin = coin_te[i]
            close_coin = closes[coin]
            if ts not in close_coin.index:
                continue
            t_pos = close_coin.index.get_loc(ts)
            if t_pos + HORIZON_H >= len(close_coin):
                continue
            entry = float(close_coin.iloc[t_pos])
            exit_ = float(close_coin.iloc[t_pos + HORIZON_H])
            actual = int(exit_ > entry)
            all_preds.append(int(preds[i]))
            all_proba.append(float(proba_test[i]))
            all_actual.append(actual)
            all_coin.append(coin)

            bu = blocked_until_per_coin.get(coin)
            if bu is not None and ts < bu:
                continue
            # Trade ausloesen, wenn calibrated proba >= threshold
            if proba_test[i] < threshold:
                continue
            gross = (exit_ - entry) / entry
            net = gross - FEE_RT
            trade_returns.append(net)
            tt += 1
            if exit_ > entry:
                tw += 1
            blocked_until_per_coin[coin] = close_coin.index[t_pos + HORIZON_H]

        t_start += TEST_H

    if not all_preds:
        return {"n_oos": 0}

    arr_pred = np.array(all_preds)
    arr_proba = np.array(all_proba)
    arr_actual = np.array(all_actual)
    arr_coin = np.array(all_coin)

    out = {
        "n_oos": len(all_preds),
        "acc_pct": float((arr_pred == arr_actual).mean() * 100),
        "baseline_up_pct": float(arr_actual.mean() * 100),
        "up_pred_pct": float(arr_pred.mean() * 100),
        "brier": float(((arr_proba - arr_actual) ** 2).mean()),
        "trades": tt,
        "winrate_pct": (tw / tt * 100) if tt > 0 else 0.0,
        "cum_return_pct": (
            float((np.prod(1 + np.array(trade_returns)) - 1) * 100) if tt > 0 else 0.0
        ),
        "thresholds": chosen_thresholds,
    }

    bins = np.linspace(0.30, 1.00, 8)
    cal = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (arr_proba >= lo) & (arr_proba < hi)
        if mask.sum() > 5:
            cal.append(
                f"      p={lo:.2f}-{hi:.2f}: n={int(mask.sum()):>5}  "
                f"actual_up={float(arr_actual[mask].mean() * 100):5.1f}%"
            )
    out["cal"] = cal
    return out


def main() -> None:
    print("=" * 80)
    print("PHASE 4 BACKTEST — Calibration + Threshold-Tuning")
    print("=" * 80)
    print(f"Coins: {COINS}, Train={TRAIN_H}h (60% Inner / 20% Cal / 20% Val)")
    print(f"Test={TEST_H}h, Embargo={EMBARGO_H}h")
    print()
    print("Lade Pool ...")
    X, y, coin_arr, ts_arr, closes = build_pool()
    print(f"Pool: {len(X)} samples, {X.shape[1]} features")
    print(f"Time range: {ts_arr.min()} -> {ts_arr.max()}")
    print()

    runs = [
        ("BASELINE  (no cal, fixed thresh=0.65)", False, False, 0.65),
        ("CAL-ONLY  (Platt cal, fixed thresh=0.65)", True, False, 0.65),
        ("THRESH-ONLY (no cal, tuned thresh)", False, True, 0.65),
        ("FULL Phase4 (Platt cal + tuned thresh)", True, True, 0.65),
    ]

    summary = []
    for label, cal, thr, fixed in runs:
        print(f">>> {label}")
        r = run_calibrated_backtest(
            X, y, coin_arr, ts_arr, closes,
            use_calibration=cal, use_threshold_tuning=thr,
            fixed_threshold=fixed,
        )
        if r["n_oos"] == 0:
            print("  no OOS")
            summary.append((label, None))
            continue
        ths = r["thresholds"]
        ths_summary = (
            f"thresh range {min(ths):.2f}-{max(ths):.2f}, mean {np.mean(ths):.2f}"
            if ths else "no threshold tuning"
        )
        print(f"  Acc:           {r['acc_pct']:.2f}%  Base UP: {r['baseline_up_pct']:.2f}%  "
              f"Alpha {r['acc_pct'] - r['baseline_up_pct']:+.2f}pp")
        print(f"  Brier:         {r['brier']:.4f}")
        print(f"  Trades:        {r['trades']}  Winrate: {r['winrate_pct']:.2f}%  "
              f"CumRet: {r['cum_return_pct']:+.2f}%")
        print(f"  Thresholds:    {ths_summary}")
        if r["cal"]:
            print("  Calibration (post):")
            for line in r["cal"]:
                print(line)
        summary.append((label, r))
        print()

    print("=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    print(f"{'Setup':<42} {'Acc%':>7} {'Alpha':>7} {'Brier':>7} {'Trades':>7} {'WR%':>6} {'CumRet':>9}")
    print("-" * 95)
    for label, r in summary:
        if r is None:
            print(f"{label:<42} (no OOS)")
            continue
        print(
            f"{label:<42} {r['acc_pct']:>6.2f}% "
            f"{r['acc_pct'] - r['baseline_up_pct']:>+6.2f} "
            f"{r['brier']:>7.4f} {r['trades']:>7} "
            f"{r['winrate_pct']:>5.1f}% {r['cum_return_pct']:>+8.2f}%"
        )


if __name__ == "__main__":
    main()
