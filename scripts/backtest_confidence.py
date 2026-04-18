"""Backtest: Welche Confidence-Schwelle bringt den meisten Profit?

Walk-Forward mit non-overlapping Trades (realistisch!).
Testet min_conf Schwellen 0.55 / 0.60 / 0.65 / 0.70 / 0.75 / 0.80.
Inkl. Macro-Features (Fix vom 18.04.2026).
"""

import sys
import warnings
from pathlib import Path

sys.path.insert(0, "C:/Codes/coin_prediction")
sys.path.insert(0, "C:/Codes/CryptoTrader_3.0/CryptoTrader/src")
warnings.filterwarnings("ignore")

import lightgbm as lgb
import numpy as np
import pandas as pd

CP = Path("C:/Codes/coin_prediction")

FEE_RT = 0.001  # 0.1% round-trip (Binance Spot taker)
HORIZON_H = 72
TRAIN_H = 720
TEST_H = 168

CLF_P = {
    "objective": "binary", "learning_rate": 0.03, "max_depth": 5,
    "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
    "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
    "n_jobs": 4, "random_state": 42,
}


def build_features(ohlcv, coin="BTC", include_macro=True):
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
    vol_24 = volume.rolling(24).mean()
    vol_168 = volume.rolling(168).mean()
    f["vol_ratio_24_168"] = vol_24 / vol_168.replace(0, np.nan)
    f["hl_range_24h"] = (high.rolling(24).max() - low.rolling(24).min()) / close
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    f["macd"] = ema12 - ema26
    f["macd_signal"] = f["macd"].ewm(span=9, adjust=False).mean()
    f["macd_hist"] = f["macd"] - f["macd_signal"]
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    f["bb_position"] = (close - sma20) / (2 * std20).replace(0, np.nan)

    # Funding
    fp = CP / f"data/raw/{coin}_funding.parquet"
    if fp.exists():
        funding = pd.read_parquet(fp)
        if "timestamp" in funding.columns:
            funding = funding.set_index("timestamp").sort_index()
        fr = funding["funding_rate"].reindex(f.index, method="ffill")
        f["funding_rate"] = fr
        f["funding_3d_ma"] = fr.rolling(72).mean()

    # Macro (Fix vom 18.04.)
    if include_macro:
        from src.ingestion.macro_fetcher import build_macro_features
        macro = build_macro_features(close, CP / "data", interval="1h")
        if not macro.empty:
            if hasattr(f.index, "tz") and f.index.tz is not None and macro.index.tz is None:
                macro.index = macro.index.tz_localize("UTC")
            elif macro.index.tz is not None and (not hasattr(f.index, "tz") or f.index.tz is None):
                macro.index = macro.index.tz_localize(None)
            valid_cols = macro.columns[macro.notna().any()]
            f = pd.concat([f, macro[valid_cols]], axis=1)

    return f


def run_backtest(features, close, min_conf: float):
    future_ret = close.shift(-HORIZON_H) / close - 1
    target = (future_ret > 0).astype(float)
    target[future_ret.isna()] = np.nan
    common = features.index.intersection(target.dropna().index)
    X = features.loc[common]
    y = target.loc[common]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    n = len(X)
    trade_returns = []
    tt, tw = 0, 0
    start = 0
    blocked_until = None

    while start + TRAIN_H + TEST_H <= n:
        Xtr = X.iloc[start:start + TRAIN_H]
        ytr = y.iloc[start:start + TRAIN_H]
        Xte = X.iloc[start + TRAIN_H:start + TRAIN_H + TEST_H]

        s = int(len(Xtr) * 0.8)
        if ytr.iloc[:s].nunique() < 2 or ytr.iloc[s:].nunique() < 2:
            start += TEST_H
            continue

        m = lgb.LGBMClassifier(**CLF_P)
        m.fit(
            Xtr.iloc[:s], ytr.iloc[:s],
            eval_set=[(Xtr.iloc[s:], ytr.iloc[s:])],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
        )

        proba = m.predict_proba(Xte)[:, 1]
        preds = (proba > 0.5).astype(int)
        conf = np.abs(proba - 0.5) + 0.5

        test_close = close.loc[Xte.index]
        test_idx = test_close.index

        for i in range(len(Xte)):
            now_ts = test_idx[i]
            if blocked_until is not None and now_ts < blocked_until:
                continue
            if preds[i] != 1 or conf[i] < min_conf:
                continue
            if i + HORIZON_H >= len(test_close):
                break
            entry = float(test_close.iloc[i])
            exit_ = float(test_close.iloc[i + HORIZON_H])
            gross = (exit_ - entry) / entry
            net = gross - FEE_RT
            trade_returns.append(net)
            tt += 1
            if exit_ > entry:
                tw += 1
            blocked_until = test_idx[i + HORIZON_H]

        start += TEST_H

    if not trade_returns:
        return None

    arr = np.array(trade_returns)
    wr = tw / tt * 100
    cum = float(np.prod(1 + arr) - 1)
    trades_per_year = (365 * 24) / HORIZON_H
    sharpe = (arr.mean() / arr.std() * np.sqrt(trades_per_year)) if arr.std() > 0 else 0
    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min())
    return {
        "trades": tt, "wr": wr, "avg": float(arr.mean() * 100),
        "cum": cum * 100, "sharpe": float(sharpe), "maxdd": max_dd * 100,
    }


def main():
    print("=" * 100)
    print("CONFIDENCE-SWEEP BACKTEST — BTC 1h, 72h Horizon, MIT Macro-Features")
    print(f"Fee: {FEE_RT*100:.2f}% RT  |  Train: 30d  |  Test: 7d  |  Non-overlapping Trades")
    print("=" * 100)

    ohlcv = pd.read_parquet(CP / "data/raw/BTC_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    close = ohlcv["close"].astype(float)

    print("\nLade Features (mit Macro)...")
    features = build_features(ohlcv, "BTC", include_macro=True)
    n_macro = sum(1 for c in features.columns if c.startswith("macro_"))
    print(f"  Total Features: {features.shape[1]}  |  davon Macro: {n_macro}")

    results = []
    for conf in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        print(f"\nRunning conf>={conf}...", flush=True)
        r = run_backtest(features, close, conf)
        if r:
            r["conf"] = conf
            results.append(r)
            print(f"  trades={r['trades']}  WR={r['wr']:.1f}%  "
                  f"avg={r['avg']:+.2f}%  cum={r['cum']:+.1f}%  "
                  f"sharpe={r['sharpe']:+.2f}  maxdd={r['maxdd']:.1f}%")

    print("\n" + "=" * 100)
    print("ERGEBNISSE (sortiert nach Sharpe):")
    print("-" * 100)
    print(f"{'MinConf':>8} {'Trades':>7} {'WR':>6} {'AvgTrade':>10} {'CumRet':>10} {'Sharpe':>8} {'MaxDD':>8}")
    print("-" * 100)
    for r in sorted(results, key=lambda x: -x["sharpe"]):
        print(f"{r['conf']:>7.2f} {r['trades']:>7} "
              f"{r['wr']:>5.1f}% {r['avg']:>+8.2f}% "
              f"{r['cum']:>+8.1f}% {r['sharpe']:>+7.2f} "
              f"{r['maxdd']:>+7.1f}%")
    print("=" * 100)

    if results:
        best_sharpe = max(results, key=lambda x: x["sharpe"])
        best_cum = max(results, key=lambda x: x["cum"])
        print(f"\nBester Sharpe: conf={best_sharpe['conf']} (Sharpe={best_sharpe['sharpe']:.2f}, CumRet={best_sharpe['cum']:+.1f}%)")
        print(f"Bester CumRet: conf={best_cum['conf']} (CumRet={best_cum['cum']:+.1f}%, Sharpe={best_cum['sharpe']:.2f})")


if __name__ == "__main__":
    main()
