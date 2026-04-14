"""Backtest: BTC Short-Only Strategie via Walk-Forward.

Testet ob 'down'-Predictions profitabel als Futures-Shorts handelbar sind.
- Entry: direction='down' + confidence >= threshold → Market Short
- Exit: nach exit_hours (72h default) — keine SL/TP
- Kosten: 0.08% Round-Trip Fee (Binance Futures Taker) + Funding (~0.03%/8h konservativ)
- Vergleich: Buy&Hold Short (passiv) vs. Strategie
- Metriken: Win-Rate, Sharpe, MaxDD, Total Return

Teste mehrere Zeitraeume: 90d, 180d, 365d, 730d, all.
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

# Binance USD-M Futures
FEE_RT = 0.0008  # 0.04% taker x 2 (entry + exit)
# Funding-Rate konservativ: Shorts *zahlen* bei positivem Funding.
# Langfristig positiv ~0.01%/8h = 0.03%/Tag = 0.09% pro 72h
FUNDING_PER_HOUR = 0.0001 / 8  # 0.00125%/h

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


def load_data(coin: str, days: int | None = None):
    ohlcv = pd.read_parquet(CP / f"data/raw/{coin}_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    if days:
        cutoff = ohlcv.index[-1] - pd.Timedelta(days=days)
        ohlcv = ohlcv.loc[ohlcv.index >= cutoff]
    return ohlcv


def run_short_backtest(
    coin: str,
    days: int | None,
    horizon_h: int = 72,
    train_h: int = 720,
    test_h: int = 168,
    min_conf: float = 0.60,
):
    """Walk-Forward Short-Only Backtest.

    - Signal: Model predicts 0 (price wird fallen) mit confidence >= min_conf
    - Trade: Short Entry, 72h halten, Market Close
    - P&L: (entry - exit) / entry - fees - funding
    """
    ohlcv = load_data(coin, days)
    close = ohlcv["close"].astype(float)

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
    accs = []
    tt, tw = 0, 0
    start = 0
    # Non-overlapping: Absolute Stunde bis wann der naechste Trade frei ist
    blocked_until_ts = None

    while start + train_h + test_h <= n:
        Xtr = X.iloc[start:start + train_h]
        ytr = y.iloc[start:start + train_h]
        Xte = X.iloc[start + train_h:start + train_h + test_h]
        yte = y.iloc[start + train_h:start + train_h + test_h]

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
        accs.append((preds == yte.values).mean())

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
        return None

    arr = np.array(trade_returns)
    wr = tw / tt * 100 if tt > 0 else 0

    # Compound return
    cum = float(np.prod(1 + arr) - 1)

    # Sharpe (annualisiert, 365*24/72 = 121.7 Trades/Jahr wenn durchgaengig)
    trades_per_year = (365 * 24) / horizon_h
    sharpe = (arr.mean() / arr.std() * np.sqrt(trades_per_year)) if arr.std() > 0 else 0

    # Max Drawdown auf Equity-Kurve
    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min())

    # Buy & Hold Short (passiv) als Benchmark
    if len(close) > 0:
        bh_short = (close.iloc[0] - close.iloc[-1]) / close.iloc[0]
    else:
        bh_short = 0

    return {
        "coin": coin,
        "days": days,
        "min_conf": min_conf,
        "accuracy": float(np.mean(accs) * 100) if accs else 0,
        "folds": len(accs),
        "trades": tt,
        "win_rate": wr,
        "avg_trade_pct": float(arr.mean() * 100),
        "median_trade_pct": float(np.median(arr) * 100),
        "cum_return_pct": cum * 100,
        "sharpe": float(sharpe),
        "max_dd_pct": max_dd * 100,
        "bh_short_pct": bh_short * 100,
    }


def print_row(r):
    if r is None:
        print("  (no trades)")
        return
    label = f"{r['days']}d" if r['days'] else "all"
    print(
        f"  {label:<5} conf>={r['min_conf']:.2f} | "
        f"trades={r['trades']:>4} WR={r['win_rate']:>4.1f}% "
        f"AvgTrade={r['avg_trade_pct']:>+6.2f}% "
        f"CumRet={r['cum_return_pct']:>+7.1f}% "
        f"Sharpe={r['sharpe']:>+5.2f} MaxDD={r['max_dd_pct']:>6.1f}% "
        f"(B&H Short: {r['bh_short_pct']:>+6.1f}%)"
    )


def main():
    print("=" * 110)
    print("SHORT-ONLY BACKTEST — BTC Futures (Walk-Forward)")
    print("Kosten: 0.08% Fee/RT + 0.09% Funding/72h | Horizon: 72h | Train: 30d")
    print("=" * 110)

    periods = [90, 180, 365, 730, 1460, None]
    confidences = [0.55, 0.60, 0.65]

    for days in periods:
        label = f"{days} Tage" if days else "Gesamter Zeitraum (seit 2020)"
        print(f"\n--- {label} ---")
        for conf in confidences:
            r = run_short_backtest("BTC", days, min_conf=conf)
            print_row(r)

    print("\n" + "=" * 110)
    print("INTERPRETATION:")
    print("  - Sharpe > 0.8  UND  CumRet > 0  UND  MaxDD > -20%  → live gehen")
    print("  - CumRet < B&H Short → Strategie schlaegt passives Short nicht")
    print("  - MaxDD < -30% → zu riskant")
    print("=" * 110)


if __name__ == "__main__":
    main()
