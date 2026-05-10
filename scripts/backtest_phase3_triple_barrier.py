"""Phase 3 Backtest — Triple-Barrier mit Vol-Skalierung.

Ersetzt das nackte Vorzeichen-Target durch Lopez-de-Prado Triple-Barrier:
- Upper Barrier (TP) = entry * (1 + 2 * sigma_t)
- Lower Barrier (SL) = entry * (1 - 1 * sigma_t)
- Vertikale Barrier: 72h
- sigma_t = EWMA der hourly returns (span=100)
- Label = 1 wenn TP zuerst getroffen ODER (Time-out mit close>entry)
        = 0 wenn SL zuerst getroffen ODER (Time-out mit close<entry)

Vergleich:
- Phase 2 (simples Vorzeichen-Target, Multi-Coin-Pool)
- Phase 3 (Triple-Barrier-Target, Multi-Coin-Pool)

Methodik (Train 8760h, Embargo 72h, Test 168h, Pool 5 Coins) bleibt identisch.
Berichtet sowohl die TB-Accuracy (passt Prediction zum TB-Label) als auch die
klassische Direction-Accuracy (close[t+72]>close[t]) fuer fairen Vergleich.
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
TRAIN_H = 8760
TEST_H = 168
EMBARGO_H = 72
TP_MULT = 2.0     # asymmetrisch nach de Prado: TP = 2*sigma
SL_MULT = 1.0     # SL = 1*sigma
SIGMA_SPAN = 100  # EWMA span fuer Vol-Schaetzer
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


def build_triple_barrier_target(
    close: pd.Series, high: pd.Series, low: pd.Series,
    horizon: int = HORIZON_H, tp_mult: float = TP_MULT, sl_mult: float = SL_MULT,
    sigma_span: int = SIGMA_SPAN,
) -> tuple[pd.Series, dict]:
    """Triple-Barrier-Label nach de Prado mit EWMA-Vol-Schaetzer.

    Returns:
        labels: Series mit 0/1, NaN am Ende (kein Lookahead moeglich)
        stats: Dict mit Hit-Counts (tp, sl, time_up, time_down)
    """
    n = len(close)
    hourly_ret = close.pct_change()
    sigma = hourly_ret.ewm(span=sigma_span, adjust=False).std()

    close_v = close.values
    high_v = high.values
    low_v = low.values
    sigma_v = sigma.values

    labels = np.full(n, np.nan)
    tp_hit = sl_hit = time_up = time_down = 0

    for i in range(n - horizon):
        s = sigma_v[i]
        if not np.isfinite(s) or s <= 0:
            continue
        entry = close_v[i]
        upper = entry * (1.0 + tp_mult * s)
        lower = entry * (1.0 - sl_mult * s)

        label = None
        for j in range(i + 1, i + 1 + horizon):
            if high_v[j] >= upper:
                label = 1.0
                tp_hit += 1
                break
            if low_v[j] <= lower:
                label = 0.0
                sl_hit += 1
                break
        if label is None:
            # Time-Barriere: Vorzeichen am Ende
            end_close = close_v[i + horizon]
            if end_close > entry:
                label = 1.0
                time_up += 1
            else:
                label = 0.0
                time_down += 1
        labels[i] = label

    total = tp_hit + sl_hit + time_up + time_down
    stats = {
        "tp_hit": tp_hit, "sl_hit": sl_hit,
        "time_up": time_up, "time_down": time_down,
        "tp_hit_pct": (tp_hit / total * 100) if total > 0 else 0.0,
        "sl_hit_pct": (sl_hit / total * 100) if total > 0 else 0.0,
        "label_up_pct": ((tp_hit + time_up) / total * 100) if total > 0 else 0.0,
    }
    return pd.Series(labels, index=close.index), stats


def build_pool() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, dict]:
    all_X = []
    all_y_vals = []
    all_coin_vals = []
    all_ts_vals = []
    closes: dict[str, pd.Series] = {}
    coin_stats: dict[str, dict] = {}
    for idx, coin in enumerate(COINS):
        ohlcv = pd.read_parquet(CP / f"data/raw/{coin}_USDT_1h.parquet")
        if "timestamp" in ohlcv.columns:
            ohlcv = ohlcv.set_index("timestamp").sort_index()
        close = ohlcv["close"].astype(float)
        high = ohlcv["high"].astype(float)
        low = ohlcv["low"].astype(float)
        closes[coin] = close
        feats = build_features(ohlcv, coin)
        tgt, stats = build_triple_barrier_target(close, high, low)
        coin_stats[coin] = stats

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
        print(
            f"  {coin}: {len(X)} valid bars, "
            f"TB-stats: tp={stats['tp_hit_pct']:.1f}% "
            f"sl={stats['sl_hit_pct']:.1f}% "
            f"up={stats['label_up_pct']:.1f}%"
        )

    X_pool = pd.concat(all_X, ignore_index=True)
    y_pool = np.concatenate(all_y_vals)
    coin_pool = np.concatenate(all_coin_vals)
    ts_pool = pd.DatetimeIndex(np.concatenate(all_ts_vals)).tz_localize("UTC")
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
    times_unique = pd.DatetimeIndex(
        np.unique(ts_arr.values)
    ).tz_localize("UTC").sort_values()
    n_t = len(times_unique)
    if n_t < TRAIN_H + EMBARGO_H + TEST_H:
        return {"n_oos": 0}

    all_preds: list[int] = []
    all_proba: list[float] = []
    all_actual_tb: list[int] = []
    all_actual_dir: list[int] = []
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
        yte = y[test_mask]

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
            actual_dir = int(exit_ > entry)
            actual_tb = int(yte[i])
            all_preds.append(int(preds[i]))
            all_proba.append(float(proba[i]))
            all_actual_tb.append(actual_tb)
            all_actual_dir.append(actual_dir)
            all_coin.append(coin)

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
    arr_proba = np.array(all_proba)
    arr_tb = np.array(all_actual_tb)
    arr_dir = np.array(all_actual_dir)
    arr_coin = np.array(all_coin)

    out = {
        "n_oos": len(all_preds),
        "acc_tb_pct": float((arr_pred == arr_tb).mean() * 100),
        "acc_dir_pct": float((arr_pred == arr_dir).mean() * 100),
        "baseline_tb_up_pct": float(arr_tb.mean() * 100),
        "baseline_dir_up_pct": float(arr_dir.mean() * 100),
        "up_pred_pct": float(arr_pred.mean() * 100),
        "brier_tb": float(((arr_proba - arr_tb) ** 2).mean()),
        "brier_dir": float(((arr_proba - arr_dir) ** 2).mean()),
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
            "acc_tb": float((arr_pred[mask] == arr_tb[mask]).mean() * 100),
            "acc_dir": float((arr_pred[mask] == arr_dir[mask]).mean() * 100),
            "base_tb": float(arr_tb[mask].mean() * 100),
            "base_dir": float(arr_dir[mask].mean() * 100),
        }

    bins = np.linspace(0.5, 1.0, 6)
    cal = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (arr_proba >= lo) & (arr_proba < hi)
        if mask.sum() > 5:
            cal.append(
                f"      p={lo:.2f}-{hi:.2f}: n={int(mask.sum()):>5}  "
                f"actual_tb={float(arr_tb[mask].mean() * 100):5.1f}%  "
                f"actual_dir={float(arr_dir[mask].mean() * 100):5.1f}%"
            )

    return {**out, "per_coin": per_coin, "cal": cal}


def build_pool_with(tp_mult: float, sl_mult: float):
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
        high = ohlcv["high"].astype(float)
        low = ohlcv["low"].astype(float)
        closes[coin] = close
        feats = build_features(ohlcv, coin)
        tgt, stats = build_triple_barrier_target(
            close, high, low, tp_mult=tp_mult, sl_mult=sl_mult
        )
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
        print(
            f"  {coin}: tp={stats['tp_hit_pct']:.1f}% sl={stats['sl_hit_pct']:.1f}% "
            f"up={stats['label_up_pct']:.1f}%"
        )
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


def main() -> None:
    print("=" * 80)
    print("PHASE 3 BACKTEST — Triple-Barrier Varianten")
    print("=" * 80)
    print(f"Coins: {COINS}, Train={TRAIN_H}h, Test={TEST_H}h, Embargo={EMBARGO_H}h")
    print(f"SIGMA_SPAN={SIGMA_SPAN}")

    variants = [
        ("ASYMM (TP=2.0sigma, SL=1.0sigma)", 2.0, 1.0),
        ("SYMM  (TP=1.5sigma, SL=1.5sigma)", 1.5, 1.5),
        ("CONSERV (TP=1.0sigma, SL=1.0sigma)", 1.0, 1.0),
    ]

    summary = []
    for label, tp, sl in variants:
        print()
        print(f">>> VARIANT: {label}")
        X, y, coin_arr, ts_arr, closes = build_pool_with(tp, sl)
        print(f"Pool: {len(X)} samples, label up_pct={float(y.mean()*100):.1f}%")
        r = run_pooled_backtest(X, y, coin_arr, ts_arr, closes)
        if r["n_oos"] == 0:
            print("  Keine OOS-Predictions.")
            summary.append((label, None))
            continue
        print(f"  Acc-TB:   {r['acc_tb_pct']:.2f}%  Base-TB: {r['baseline_tb_up_pct']:.2f}%  "
              f"Alpha-TB: {r['acc_tb_pct'] - r['baseline_tb_up_pct']:+.2f}pp")
        print(f"  Acc-Dir:  {r['acc_dir_pct']:.2f}%  Base-Dir:{r['baseline_dir_up_pct']:.2f}%  "
              f"Alpha-Dir:{r['acc_dir_pct'] - r['baseline_dir_up_pct']:+.2f}pp")
        print(f"  UP-Pred%: {r['up_pred_pct']:.2f}%  Brier-TB:{r['brier_tb']:.4f}  Trades:{r['trades']}  CumRet:{r['cum_return_pct']:+.2f}%")
        if r["cal"]:
            print("  Calibration:")
            for line in r["cal"]:
                print(line)
        summary.append((label, r))

    print()
    print("=" * 80)
    print("ZUSAMMENFASSUNG ALLER VARIANTEN")
    print("=" * 80)
    print(f"{'Variant':<38} {'AccTB':>7} {'BaseTB':>7} {'AlphaTB':>7} {'AccDir':>7} {'AlphaD':>7} {'Trades':>6} {'CumRet':>8}")
    print("-" * 100)
    for label, r in summary:
        if r is None:
            print(f"{label:<38} (no OOS)")
            continue
        print(
            f"{label:<38} {r['acc_tb_pct']:>6.2f}% {r['baseline_tb_up_pct']:>6.2f}% "
            f"{r['acc_tb_pct'] - r['baseline_tb_up_pct']:>+6.2f} "
            f"{r['acc_dir_pct']:>6.2f}% "
            f"{r['acc_dir_pct'] - r['baseline_dir_up_pct']:>+6.2f} "
            f"{r['trades']:>6} {r['cum_return_pct']:>+7.2f}%"
        )
    return
    # alter Single-Variant-Code unten unreachable
    X, y, coin_arr, ts_arr, closes = build_pool()
    print(f"\nPool gesamt: {len(X)} samples, {X.shape[1]} features")
    print(f"Time range: {ts_arr.min()} -> {ts_arr.max()}")
    print()

    print(">>> Run: TB-Pool")
    r = run_pooled_backtest(X, y, coin_arr, ts_arr, closes)
    if r["n_oos"] == 0:
        print("Keine OOS-Predictions.")
        return

    print(f"\n=== POOL OVERALL ===")
    print(f"  OOS Predictions:   {r['n_oos']:>6}")
    print(f"  Accuracy (TB):     {r['acc_tb_pct']:>6.2f}%   Baseline UP-TB: {r['baseline_tb_up_pct']:>5.2f}%")
    print(f"  Accuracy (Dir72):  {r['acc_dir_pct']:>6.2f}%   Baseline UP-Dir: {r['baseline_dir_up_pct']:>5.2f}%")
    print(f"  Alpha vs UP-TB:    {r['acc_tb_pct'] - r['baseline_tb_up_pct']:>+6.2f} pp")
    print(f"  Alpha vs UP-Dir:   {r['acc_dir_pct'] - r['baseline_dir_up_pct']:>+6.2f} pp")
    print(f"  UP-Predictions:    {r['up_pred_pct']:>6.2f}%")
    print(f"  Brier (TB):        {r['brier_tb']:>6.4f}")
    print(f"  Brier (Dir):       {r['brier_dir']:>6.4f}")
    print(f"  Trades:            {r['trades']:>6}")
    if r["trades"] > 0:
        print(f"  Winrate:           {r['winrate_pct']:>6.2f}%")
        print(f"  CumReturn (72h):   {r['cum_return_pct']:>+6.2f}%")
    if r["cal"]:
        print("  Calibration (Pred-Proba vs Actual-TB-Rate / Dir-UP-Rate):")
        for line in r["cal"]:
            print(line)

    print(f"\n=== PER-COIN ===")
    print(f"  {'Coin':<6} {'n':>6} {'AccTB%':>7} {'BaseTB%':>8} {'AccDir%':>8} {'BaseDir%':>9}")
    print("  " + "-" * 55)
    for c, pc in r["per_coin"].items():
        print(
            f"  {c:<6} {pc['n']:>6} "
            f"{pc['acc_tb']:>6.2f}% {pc['base_tb']:>7.2f}% "
            f"{pc['acc_dir']:>7.2f}% {pc['base_dir']:>8.2f}%"
        )

    print(f"\n=== VERGLEICH ZU PHASE 1+2 ===")
    print(f"  Phase 1 (BTC, simple)   : Acc 49.59%  Base 50.12%  Alpha -0.52pp  Trades 1   CumRet -1%")
    print(f"  Phase 2 (Pool, simple)  : Acc 50.42%  Base 51.48%  Alpha -1.06pp  Trades 52  CumRet -53%")
    print(f"  Phase 3 (Pool, TB)      : "
          f"Acc {r['acc_tb_pct']:.2f}%  Base {r['baseline_tb_up_pct']:.2f}%  "
          f"Alpha {r['acc_tb_pct'] - r['baseline_tb_up_pct']:+.2f}pp  "
          f"Trades {r['trades']}  CumRet {r['cum_return_pct']:+.2f}%")
    print(f"  Phase 3 Direction-equiv : "
          f"Acc {r['acc_dir_pct']:.2f}%  Base {r['baseline_dir_up_pct']:.2f}%  "
          f"Alpha {r['acc_dir_pct'] - r['baseline_dir_up_pct']:+.2f}pp")


if __name__ == "__main__":
    main()
