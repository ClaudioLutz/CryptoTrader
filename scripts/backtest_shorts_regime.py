"""Backtest: Short-Only MIT Regime-Filter.

Shorts nur in bestaetigten Bear-Phasen, gefiltert durch:
  - SMA200 (Close < 200d-SMA)
  - SMA200 + Slope (zusaetzlich SMA200 fallend)
  - SMA50<SMA200 (Death Cross)
  - RSI<45 (Momentum)
  - SMA200 + RSI (kombiniert)

Vergleich: unfiltered vs. jeder Filter.
"""

import sys
import warnings

sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

CP = Path("C:/Codes/coin_prediction")

FEE_RT = 0.0008
FUNDING_PER_HOUR = 0.0001 / 8

CLF_P = {
    "objective": "binary", "learning_rate": 0.03, "max_depth": 5,
    "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
    "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
    "n_jobs": 4, "random_state": 42,
}


def build_1h_features(ohlcv, coin="BTC"):
    close = ohlcv["close"].astype(float)
    volume = ohlcv["volume"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)

    features = pd.DataFrame(index=ohlcv.index)

    for p in [1, 4, 12, 24, 72, 168]:
        features[f"ret_{p}h"] = close.pct_change(p)

    hourly_ret = close.pct_change()
    for w in [12, 24, 72, 168]:
        features[f"vol_{w}h"] = hourly_ret.rolling(w).std()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    features["rsi_14h"] = 100 - (100 / (1 + rs))

    vol_24 = volume.rolling(24).mean()
    vol_168 = volume.rolling(168).mean()
    features["vol_ratio_24_168"] = vol_24 / vol_168.replace(0, np.nan)

    features["hl_range_24h"] = (high.rolling(24).max() - low.rolling(24).min()) / close

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    features["macd"] = ema12 - ema26
    features["macd_signal"] = features["macd"].ewm(span=9, adjust=False).mean()
    features["macd_hist"] = features["macd"] - features["macd_signal"]

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    features["bb_position"] = (close - sma20) / (2 * std20).replace(0, np.nan)

    fp = CP / f"data/raw/{coin}_funding.parquet"
    if fp.exists():
        funding = pd.read_parquet(fp)
        if "timestamp" in funding.columns:
            funding = funding.set_index("timestamp").sort_index()
        fr = funding["funding_rate"].reindex(features.index, method="ffill")
        features["funding_rate"] = fr
        features["funding_3d_ma"] = fr.rolling(72).mean()

    return features


def build_regime_masks(close: pd.Series) -> dict[str, pd.Series]:
    """Berechnet Regime-Filter-Masken (True = 'Shorts erlaubt')."""
    sma50 = close.rolling(50 * 24).mean()   # 50 Tage
    sma200 = close.rolling(200 * 24).mean()  # 200 Tage
    sma200_slope = sma200.diff(24)  # Aenderung ueber 1 Tag

    # RSI auf 14 Tage (336h)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14 * 24).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14 * 24).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_14d = 100 - (100 / (1 + rs))

    masks = {
        "none": pd.Series(True, index=close.index),
        "sma200": close < sma200,
        "sma200_slope": (close < sma200) & (sma200_slope < 0),
        "death_cross": sma50 < sma200,
        "rsi<45": rsi_14d < 45,
        "sma200+rsi": (close < sma200) & (rsi_14d < 45),
    }
    return masks


def run_backtest(
    coin: str,
    days: int | None,
    regime_name: str,
    horizon_h: int = 72,
    train_h: int = 720,
    test_h: int = 168,
    min_conf: float = 0.60,
):
    ohlcv = pd.read_parquet(CP / f"data/raw/{coin}_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    if days:
        cutoff = ohlcv.index[-1] - pd.Timedelta(days=days)
        ohlcv = ohlcv.loc[ohlcv.index >= cutoff]
    close = ohlcv["close"].astype(float)

    # Regime-Masken auf VOLLER History berechnen, damit SMA200 verfuegbar ist
    full_ohlcv = pd.read_parquet(CP / f"data/raw/{coin}_USDT_1h.parquet")
    if "timestamp" in full_ohlcv.columns:
        full_ohlcv = full_ohlcv.set_index("timestamp").sort_index()
    full_close = full_ohlcv["close"].astype(float)
    full_masks = build_regime_masks(full_close)
    regime_mask = full_masks[regime_name].reindex(close.index).fillna(False)

    features = build_1h_features(ohlcv, coin)

    future_return = close.shift(-horizon_h) / close - 1
    target = (future_return > 0).astype(float)
    target[future_return.isna()] = float("nan")

    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    n = len(X)
    if n < train_h + test_h:
        return None

    trade_returns = []
    tt, tw = 0, 0
    start = 0
    blocked_until_ts = None
    regime_blocked = 0  # Trades die durch Regime-Filter abgelehnt wurden

    while start + train_h + test_h <= n:
        Xtr = X.iloc[start:start + train_h]
        ytr = y.iloc[start:start + train_h]
        Xte = X.iloc[start + train_h:start + train_h + test_h]

        s = int(len(Xtr) * 0.8)
        if ytr.iloc[:s].nunique() < 2:
            start += test_h
            continue
        m = lgb.LGBMClassifier(**CLF_P)
        kw = {}
        if s < len(Xtr) and ytr.iloc[s:].nunique() > 1:
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)

        proba = m.predict_proba(Xte)[:, 1]
        preds = (proba > 0.5).astype(int)
        conf = np.abs(proba - 0.5) + 0.5

        test_close = close.iloc[start + train_h:start + train_h + test_h]
        test_idx = test_close.index

        for i in range(len(Xte)):
            now_ts = test_idx[i]
            if blocked_until_ts is not None and now_ts < blocked_until_ts:
                continue
            if preds[i] != 0 or conf[i] < min_conf:
                continue
            if i + horizon_h >= len(test_close):
                break

            # Regime-Filter
            if not regime_mask.get(now_ts, False):
                regime_blocked += 1
                continue

            entry = float(test_close.iloc[i])
            exit_ = float(test_close.iloc[i + horizon_h])
            gross = (entry - exit_) / entry
            funding_cost = FUNDING_PER_HOUR * horizon_h
            net = gross - FEE_RT - funding_cost
            trade_returns.append(net)
            tt += 1
            if exit_ < entry:
                tw += 1
            blocked_until_ts = test_idx[i + horizon_h]

        start += test_h

    if not trade_returns:
        return {
            "trades": 0, "wr": 0, "avg": 0, "cum": 0, "sharpe": 0,
            "maxdd": 0, "regime_blocked": regime_blocked,
        }

    arr = np.array(trade_returns)
    wr = tw / tt * 100
    cum = float(np.prod(1 + arr) - 1)
    trades_per_year = (365 * 24) / horizon_h
    sharpe = (arr.mean() / arr.std() * np.sqrt(trades_per_year)) if arr.std() > 0 else 0
    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min())

    return {
        "trades": tt, "wr": wr, "avg": float(arr.mean() * 100),
        "cum": cum * 100, "sharpe": float(sharpe), "maxdd": max_dd * 100,
        "regime_blocked": regime_blocked,
    }


def main():
    print("=" * 115)
    print("SHORT + REGIME-FILTER BACKTEST  (BTC Futures, 72h Horizon, Conf>=0.60)")
    print("Kosten: 0.08% Fee/RT + 0.09% Funding/72h")
    print("=" * 115)

    periods = [90, 180, 365, 730, 1460, None]
    regimes = ["none", "sma200", "sma200_slope", "death_cross", "rsi<45", "sma200+rsi"]

    for days in periods:
        label = f"{days}d" if days else "all"
        print(f"\n--- Periode: {label} ---")
        print(f"  {'Regime':<14} {'Trades':>7} {'Blocked':>8} {'WR':>6} {'AvgT':>7} {'CumRet':>9} {'Sharpe':>7} {'MaxDD':>8}")
        print("  " + "-" * 80)
        for regime in regimes:
            r = run_backtest("BTC", days, regime, min_conf=0.60)
            if r is None:
                print(f"  {regime:<14} (insufficient data)")
                continue
            print(
                f"  {regime:<14} {r['trades']:>7} {r['regime_blocked']:>8} "
                f"{r['wr']:>5.1f}% {r['avg']:>+6.2f}% "
                f"{r['cum']:>+7.1f}% {r['sharpe']:>+6.2f} {r['maxdd']:>+7.1f}%"
            )

    print("\n" + "=" * 115)
    print("LEGENDE:")
    print("  none         = kein Filter (Baseline)")
    print("  sma200       = Close < 200d-SMA")
    print("  sma200_slope = Close < 200d-SMA UND SMA200 fallend")
    print("  death_cross  = 50d-SMA < 200d-SMA")
    print("  rsi<45       = RSI 14d < 45 (Momentum baerisch)")
    print("  sma200+rsi   = SMA200-Filter UND RSI<45")
    print("=" * 115)


if __name__ == "__main__":
    main()
