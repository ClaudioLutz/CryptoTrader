"""Backtest: BTC 1h-Strategie mit den exakt implementierten Features.

Testet die PredictionPipeline._build_1h_features() Methode
mit Walk-Forward Validation.
"""

import sys, warnings
sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

CP = Path("C:/Codes/coin_prediction")

CLF_P = {"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
         "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
         "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
         "n_jobs": 4, "random_state": 42}


def build_1h_features(ohlcv, coin="BTC"):
    """Exakt gleiche Features wie PredictionPipeline._build_1h_features()."""
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

    # Funding Rate
    fp = CP / f"data/raw/{coin}_funding.parquet"
    if fp.exists():
        funding = pd.read_parquet(fp)
        if "timestamp" in funding.columns:
            funding = funding.set_index("timestamp").sort_index()
        fr = funding["funding_rate"].reindex(features.index, method="ffill")
        features["funding_rate"] = fr
        features["funding_3d_ma"] = fr.rolling(72).mean()

    return features


def run_wf_backtest(coin, horizon_h, train_h=720, test_h=168, min_conf=0.60):
    """Walk-Forward Backtest mit nicht-ueberlappenden Test-Fenstern."""
    ohlcv = pd.read_parquet(CP / f"data/raw/{coin}_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
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
    accs, tw, tt = [], 0, 0
    pnl_pcts = []  # Simulierte P&L pro Trade
    start = 0

    while start + train_h + test_h <= n:
        Xtr = X.iloc[start:start + train_h]
        ytr = y.iloc[start:start + train_h]
        Xte = X.iloc[start + train_h:start + train_h + test_h]
        yte = y.iloc[start + train_h:start + train_h + test_h]

        s = int(len(Xtr) * 0.8)
        m = lgb.LGBMClassifier(**CLF_P)
        kw = {}
        if s < len(Xtr):
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)

        proba = m.predict_proba(Xte)[:, 1]
        preds = (proba > 0.5).astype(int)
        accs.append((preds == yte.values).mean())

        # Trade-Simulation (nur High-Confidence Up-Signals)
        conf = np.abs(proba - 0.5) + 0.5
        trade_mask = (conf >= min_conf) & (preds == 1)
        if trade_mask.sum() > 0:
            tt += int(trade_mask.sum())
            tw += int((yte.values[trade_mask] == 1).sum())

            # P&L: tatsaechliche Returns fuer Trades
            test_close = close.iloc[start + train_h:start + train_h + test_h]
            for idx in np.where(trade_mask)[0]:
                if idx + horizon_h < len(test_close):
                    actual_ret = float(test_close.iloc[idx + horizon_h] / test_close.iloc[idx] - 1)
                    pnl_pcts.append(actual_ret)

        start += test_h

    wr = tw / tt * 100 if tt > 0 else 0
    avg_pnl = np.mean(pnl_pcts) * 100 if pnl_pcts else 0
    med_pnl = np.median(pnl_pcts) * 100 if pnl_pcts else 0
    cum_pnl = (np.prod([1 + r for r in pnl_pcts]) - 1) * 100 if pnl_pcts else 0

    return {
        "coin": coin,
        "horizon_h": horizon_h,
        "train_h": train_h,
        "accuracy": round(np.mean(accs) * 100, 1) if accs else 0,
        "folds": len(accs),
        "trades": tt,
        "wins": tw,
        "win_rate": round(wr, 1),
        "avg_pnl_pct": round(avg_pnl, 2),
        "median_pnl_pct": round(med_pnl, 2),
        "cumulative_pnl_pct": round(cum_pnl, 1),
    }


def main():
    print("=" * 85)
    print("BTC 1h BACKTEST — Walk-Forward Validation")
    print("=" * 85)

    # Test verschiedene Horizonte und Train-Windows
    configs = [
        ("24h Horizont, 30d Train", 24, 720),
        ("72h Horizont, 30d Train", 72, 720),
        ("168h Horizont, 30d Train", 168, 720),
        ("72h Horizont, 14d Train", 72, 336),
        ("72h Horizont, 60d Train", 72, 1440),
    ]

    print(f"\n{'Config':<30} {'Acc':>5} {'Folds':>5} {'Trades':>6} {'WR':>5} "
          f"{'AvgPnL':>7} {'MedPnL':>7} {'CumPnL':>8}")
    print("-" * 85)

    for name, horizon_h, train_h in configs:
        r = run_wf_backtest("BTC", horizon_h, train_h)
        print(f"{name:<30} {r['accuracy']:>4.1f}% {r['folds']:>5} {r['trades']:>5} "
              f"{r['win_rate']:>4.1f}% {r['avg_pnl_pct']:>+6.2f}% "
              f"{r['median_pnl_pct']:>+6.2f}% {r['cumulative_pnl_pct']:>+7.1f}%")

    # Confidence-Threshold Analyse fuer beste Config
    print(f"\n{'='*85}")
    print("CONFIDENCE-THRESHOLD (72h Horizont, 30d Train)")
    print("-" * 85)
    print(f"{'MinConf':>7} {'Trades':>6} {'WR':>5} {'AvgPnL':>7} {'MedPnL':>7} {'CumPnL':>8}")
    print("-" * 50)

    for conf in [0.50, 0.55, 0.60, 0.65, 0.70]:
        r = run_wf_backtest("BTC", 72, 720, min_conf=conf)
        print(f"{conf:>6.0%} {r['trades']:>6} {r['win_rate']:>4.1f}% "
              f"{r['avg_pnl_pct']:>+6.2f}% {r['median_pnl_pct']:>+6.2f}% "
              f"{r['cumulative_pnl_pct']:>+7.1f}%")


if __name__ == "__main__":
    main()
