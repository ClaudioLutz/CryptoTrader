"""Phase 2 Backtest — Multi-Coin-Pooling mit coin_id als kategorisches Feature.

Hypothese (G-Research-Crypto-Kaggle Top-Solutions): Ein einziges LightGBM
ueber alle 5 Coins (BTC, ETH, SOL, BNB, TRX) trainiert mit coin_id als
kategorischem Feature schlaegt 5 separate Single-Coin-Modelle, weil die
effektive Sample-Size massiv steigt.

Vergleich:
- Single-Coin BTC (Phase 1, Embargo 72h, 1-Jahr-Window) — Baseline
- Multi-Coin Pool (alle 5 Coins, gleiche Methodik, coin_id-Feature)

OOS-Accuracy wird sowohl pro Coin als auch insgesamt gemessen.
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

CP = Path("C:/Codes/coin_prediction")
COINS = ["BTC", "ETH", "SOL", "BNB", "TRX"]
HORIZON_H = 72
TRAIN_H = 8760    # 1 Jahr
TEST_H = 168     # 1 Woche
EMBARGO_H = 72   # 72h Embargo zwischen Train/Val und Train/Test
FEE_RT = 0.001

CLF_P = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.03,
    "max_depth": 5,
    "n_estimators": 500,
    "num_leaves": 31,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 30,
    "verbose": -1,
    "n_jobs": 4,
    "random_state": 42,
}


def build_features(ohlcv: pd.DataFrame, coin: str) -> pd.DataFrame:
    """Identische Feature-Berechnung wie Phase 1."""
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
            # ffill um Wochenend-Luecken in DXY/VIX/SPY zu schliessen
            macro_ff = macro[valid_cols].ffill()
            f = pd.concat([f, macro_ff], axis=1)
    except Exception as e:
        print(f"  macro_features failed for {coin}: {e}")
    return f


def build_target(close: pd.Series) -> pd.Series:
    future_return = close.shift(-HORIZON_H) / close - 1
    target = (future_return > 0).astype(float)
    target[future_return.isna()] = np.nan
    return target


def build_pool() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, dict[str, pd.Series]]:
    """Lade alle Coins, baue Features+Target. Rueckgabe als parallele Arrays
    auf RangeIndex (Duplikate im Timestamp ueber Coins sind ok), Timestamps
    separat. Alle nach Timestamp sortiert."""
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
        X["coin_id"] = idx  # kategorisches Feature

        all_X.append(X.reset_index(drop=True))
        all_y_vals.append(y.values)
        all_coin_vals.append(np.full(len(X), coin, dtype=object))
        all_ts_vals.append(X.index.values)
        print(f"  {coin}: {len(X)} valid bars  {X.index[0]} -> {X.index[-1]}")

    X_pool = pd.concat(all_X, ignore_index=True)
    y_pool = np.concatenate(all_y_vals)
    coin_pool = np.concatenate(all_coin_vals)
    # np.concatenate loescht TZ-Info, daher manuell als UTC re-localisieren
    ts_pool = pd.DatetimeIndex(np.concatenate(all_ts_vals)).tz_localize("UTC")

    # nach Timestamp sortieren (positional)
    order = np.argsort(ts_pool.values)
    X_pool = X_pool.iloc[order].reset_index(drop=True)
    y_pool = y_pool[order]
    coin_pool = coin_pool[order]
    ts_pool = ts_pool[order]
    return X_pool, y_pool, coin_pool, ts_pool, closes


def run_pooled_backtest(
    X: pd.DataFrame, y: np.ndarray, coin_arr: np.ndarray,
    ts_arr: pd.DatetimeIndex, closes: dict[str, pd.Series],
    min_conf: float = 0.65,
) -> dict:
    """Walk-Forward Backtest mit Multi-Coin-Pool.

    Walking forward in der Zeit-Achse: alle Coins, die im Train-Fenster Daten
    haben, gehen zusammen ins Modell. Test-Window: alle Coins parallel.
    Arbeit auf parallelen Arrays mit RangeIndex (Duplikate in ts ok).
    """
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

        # Inneren Train/Val-Split: 80% der Zeit in Train, Rest in Val,
        # mit Embargo dazwischen
        tr_times_unique = pd.DatetimeIndex(
            np.unique(ts_tr.values)
        ).tz_localize("UTC").sort_values()
        if len(tr_times_unique) < 100:
            t_start += TEST_H
            continue
        split_t = tr_times_unique[int(len(tr_times_unique) * 0.8)]
        embargo_cutoff = split_t - pd.Timedelta(hours=EMBARGO_H)
        inner_tr_mask = ts_tr <= embargo_cutoff
        inner_val_mask = ts_tr >= split_t
        Xtr_inner = Xtr_full.iloc[inner_tr_mask]
        ytr_inner = ytr_full[inner_tr_mask]
        Xval_inner = Xtr_full.iloc[inner_val_mask]
        yval_inner = ytr_full[inner_val_mask]

        if (
            len(Xtr_inner) < 200
            or len(np.unique(ytr_inner)) < 2
            or len(np.unique(yval_inner)) < 2
        ):
            t_start += TEST_H
            continue

        m = lgb.LGBMClassifier(**CLF_P)
        m.fit(
            Xtr_inner, ytr_inner,
            eval_set=[(Xval_inner, yval_inner)],
            categorical_feature=["coin_id"],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
        )

        proba = m.predict_proba(Xte)[:, 1]
        preds = (proba > 0.5).astype(int)
        conf = np.abs(proba - 0.5) + 0.5

        # Pro Test-Sample: actuals + Trade-Logik
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
            all_proba.append(float(proba[i]))
            all_actual.append(actual)
            all_coin.append(coin)

            # Trade-Logik pro Coin
            bu = blocked_until_per_coin.get(coin)
            if bu is not None and ts < bu:
                continue
            if preds[i] != 1 or conf[i] < min_conf:
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
    arr_actual = np.array(all_actual)
    arr_proba = np.array(all_proba)
    arr_coin = np.array(all_coin)

    overall = {
        "n_oos": len(all_preds),
        "accuracy_pct": float((arr_pred == arr_actual).mean() * 100),
        "baseline_up_pct": float(arr_actual.mean() * 100),
        "up_pred_pct": float(arr_pred.mean() * 100),
        "brier": float(((arr_proba - arr_actual) ** 2).mean()),
        "trades": tt,
        "winrate_pct": (tw / tt * 100) if tt > 0 else 0.0,
        "cum_return_pct": (
            float((np.prod(1 + np.array(trade_returns)) - 1) * 100) if tt > 0 else 0.0
        ),
    }

    per_coin = {}
    for c in COINS:
        mask = arr_coin == c
        if mask.sum() == 0:
            continue
        per_coin[c] = {
            "n": int(mask.sum()),
            "acc_pct": float((arr_pred[mask] == arr_actual[mask]).mean() * 100),
            "baseline_up_pct": float(arr_actual[mask].mean() * 100),
            "alpha_pp": float(
                (arr_pred[mask] == arr_actual[mask]).mean() * 100
                - arr_actual[mask].mean() * 100
            ),
        }

    # Calibration overall
    bins = np.linspace(0.5, 1.0, 6)
    cal_lines = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (arr_proba >= lo) & (arr_proba < hi)
        if mask.sum() > 5:
            cal_lines.append(
                f"      p={lo:.2f}-{hi:.2f}: n={int(mask.sum()):>5}  "
                f"actual_up={float(arr_actual[mask].mean() * 100):5.1f}%"
            )

    return {**overall, "per_coin": per_coin, "calibration": cal_lines}


def main() -> None:
    print("=" * 80)
    print("PHASE 2 BACKTEST — Multi-Coin-Pooling (coin_id als kategorisches Feature)")
    print("=" * 80)
    print(f"Coins: {COINS}, Train={TRAIN_H}h, Test={TEST_H}h, Embargo={EMBARGO_H}h")
    print()
    print("Lade Pool ...")
    X, y, coin_arr, ts_arr, closes = build_pool()
    print(f"\nPool gesamt: {len(X)} samples, {X.shape[1]} features (inkl. coin_id)")
    print(f"Time range: {ts_arr.min()} -> {ts_arr.max()}")
    print()

    print(">>> Run: Multi-Coin-Pool")
    r = run_pooled_backtest(X, y, coin_arr, ts_arr, closes)

    if r["n_oos"] == 0:
        print("Keine OOS-Predictions.")
        return

    print(f"\n=== POOL OVERALL ===")
    print(f"  OOS Predictions: {r['n_oos']:>6}")
    print(f"  Accuracy:        {r['accuracy_pct']:>6.2f}%")
    print(f"  Baseline UP:     {r['baseline_up_pct']:>6.2f}%")
    print(f"  Alpha vs UP:     {r['accuracy_pct'] - r['baseline_up_pct']:>+6.2f} pp")
    print(f"  UP-Predictions:  {r['up_pred_pct']:>6.2f}%")
    print(f"  Brier-Score:     {r['brier']:>6.4f}")
    print(f"  Trades:          {r['trades']:>6}")
    if r["trades"] > 0:
        print(f"  Winrate:         {r['winrate_pct']:>6.2f}%")
        print(f"  CumReturn:       {r['cum_return_pct']:>+6.2f}%")
    if r["calibration"]:
        print("  Calibration:")
        for line in r["calibration"]:
            print(line)

    print(f"\n=== PER-COIN ACCURACY ===")
    print(f"  {'Coin':<6} {'n':>6} {'Acc%':>7} {'BaseUP%':>8} {'Alpha':>7}")
    print(f"  {'-'*6} {'-'*6} {'-'*7} {'-'*8} {'-'*7}")
    for c, pc in r["per_coin"].items():
        print(
            f"  {c:<6} {pc['n']:>6} "
            f"{pc['acc_pct']:>6.2f}% {pc['baseline_up_pct']:>7.2f}% "
            f"{pc['alpha_pp']:>+6.2f}"
        )

    print(f"\n=== VERGLEICH ZU PHASE 1 ===")
    print(f"  Phase 1 (BTC only):    49.59% Acc, Baseline 50.12%, Alpha -0.52pp")
    print(
        f"  Phase 2 (5-Coin Pool): {r['accuracy_pct']:.2f}% Acc, "
        f"Baseline {r['baseline_up_pct']:.2f}%, "
        f"Alpha {r['accuracy_pct'] - r['baseline_up_pct']:+.2f}pp"
    )
    if "BTC" in r["per_coin"]:
        btc_pc = r["per_coin"]["BTC"]
        print(
            f"  Phase 2 (BTC only):    {btc_pc['acc_pct']:.2f}% Acc, "
            f"Baseline {btc_pc['baseline_up_pct']:.2f}%, "
            f"Alpha {btc_pc['alpha_pp']:+.2f}pp"
        )


if __name__ == "__main__":
    main()
