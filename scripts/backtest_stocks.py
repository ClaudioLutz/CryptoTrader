"""Backtest: Aktien-ML-Strategie mit dem bestehenden LightGBM-Stack.

Nutzt die gleiche Walk-Forward-Methodik wie backtest_1h_btc.py, aber:
- Daten: yfinance (AAPL, MSFT, NVDA, ...)
- Timeframe: 1d (Aktien-Standard)
- Horizon: 5 Tage (~1 Woche)
- Target: next_5d_return > 0
- Benchmark: SPY Buy&Hold

Features aus dem Krypto-Projekt die uebertragbar sind:
- Returns (1d, 5d, 20d, 60d)
- Volatilitaet (20d, 60d)
- RSI(14), MACD, Bollinger
- Volume-Ratio
- Macro: VIX, DXY, US10Y (bereits im Projekt via yfinance)

Zusaetzliche Aktien-spezifische Features:
- SPY-Relative-Strength (Aktie vs. Markt)
- Sector-Relative (vs. Sector-ETF)

Output: Sharpe, MaxDD, Win-Rate, CumRet pro Ticker und aggregiert.
"""

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import lightgbm as lgb
import numpy as np
import pandas as pd
import yfinance as yf

CACHE_DIR = Path("data/stocks_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# S&P500 Mega-Caps (liquid, reiche Historie, fuer Cross-Sectional sinnvoll)
TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "AVGO", "JPM", "V",
    "UNH", "XOM", "MA", "HD", "PG",
]

BENCHMARK = "SPY"
MACRO = {
    "^VIX": "vix",
    "DX-Y.NYB": "dxy",
    "^TNX": "us10y",
}

CLF_P = {
    "objective": "binary", "learning_rate": 0.03, "max_depth": 5,
    "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
    "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
    "n_jobs": 4, "random_state": 42,
}

FEE_BPS = 0.001  # 10 bps Round-Trip (IBKR ~0.05%/Side + Slippage)
HORIZON_D = 5
TRAIN_D = 504  # 2 Jahre
TEST_D = 63    # 3 Monate


def fetch_cached(ticker: str, period: str = "10y") -> pd.DataFrame:
    cache_file = CACHE_DIR / f"{ticker.replace('^', '').replace('.', '_')}.parquet"
    if cache_file.exists():
        age_days = (pd.Timestamp.now() - pd.Timestamp(cache_file.stat().st_mtime, unit="s")).days
        if age_days < 1:
            return pd.read_parquet(cache_file)
    print(f"  Fetching {ticker}...", flush=True)
    df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
    if df.empty:
        return df
    df.index = df.index.tz_localize(None) if df.index.tz else df.index
    df.columns = [c.lower() for c in df.columns]
    df.to_parquet(cache_file)
    return df


def build_features(df: pd.DataFrame, spy_close: pd.Series, macro: dict[str, pd.Series]) -> pd.DataFrame:
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    f = pd.DataFrame(index=df.index)

    for p in [1, 5, 20, 60]:
        f[f"ret_{p}d"] = close.pct_change(p)

    daily_ret = close.pct_change()
    for w in [20, 60]:
        f[f"vol_{w}d"] = daily_ret.rolling(w).std()

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    f["rsi_14"] = 100 - (100 / (1 + rs))

    vol_20 = volume.rolling(20).mean()
    vol_60 = volume.rolling(60).mean()
    f["vol_ratio"] = vol_20 / vol_60.replace(0, np.nan)

    f["hl_range_20"] = (high.rolling(20).max() - low.rolling(20).min()) / close

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    f["macd"] = ema12 - ema26
    f["macd_signal"] = f["macd"].ewm(span=9, adjust=False).mean()
    f["macd_hist"] = f["macd"] - f["macd_signal"]

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    f["bb_position"] = (close - sma20) / (2 * std20).replace(0, np.nan)

    # Distanz von 52w-High (Momentum-Proxy)
    f["dist_52w_high"] = close / close.rolling(252).max() - 1

    # SPY Relative Strength — Aktie vs. Markt
    spy_aligned = spy_close.reindex(df.index, method="ffill")
    spy_ret_20 = spy_aligned.pct_change(20)
    f["rel_strength_20d"] = f["ret_20d"] - spy_ret_20
    f["spy_ret_20d"] = spy_ret_20

    # Macro
    for name, ser in macro.items():
        s = ser.reindex(df.index, method="ffill")
        f[f"macro_{name}_level"] = s
        f[f"macro_{name}_ret_5d"] = s.pct_change(5)

    return f


def walk_forward_backtest(
    ticker: str, features: pd.DataFrame, close: pd.Series, min_conf: float = 0.55
):
    future_ret = close.shift(-HORIZON_D) / close - 1
    target = (future_ret > 0).astype(float)
    target[future_ret.isna()] = np.nan

    common = features.index.intersection(target.dropna().index)
    X = features.loc[common]
    y = target.loc[common]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    n = len(X)
    if n < TRAIN_D + TEST_D:
        return None

    trade_returns = []
    tt, tw = 0, 0
    start = 0
    blocked_until = None

    while start + TRAIN_D + TEST_D <= n:
        Xtr = X.iloc[start:start + TRAIN_D]
        ytr = y.iloc[start:start + TRAIN_D]
        Xte = X.iloc[start + TRAIN_D:start + TRAIN_D + TEST_D]

        s = int(len(Xtr) * 0.8)
        if ytr.iloc[:s].nunique() < 2:
            start += TEST_D
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

        test_close = close.loc[Xte.index]
        test_idx = test_close.index

        for i in range(len(Xte)):
            now_ts = test_idx[i]
            if blocked_until is not None and now_ts < blocked_until:
                continue
            if preds[i] != 1 or conf[i] < min_conf:
                continue
            if i + HORIZON_D >= len(test_close):
                break
            entry = float(test_close.iloc[i])
            exit_ = float(test_close.iloc[i + HORIZON_D])
            gross = (exit_ - entry) / entry
            net = gross - FEE_BPS
            trade_returns.append(net)
            tt += 1
            if exit_ > entry:
                tw += 1
            blocked_until = test_idx[i + HORIZON_D]

        start += TEST_D

    if not trade_returns:
        return None

    arr = np.array(trade_returns)
    wr = tw / tt * 100
    cum = float(np.prod(1 + arr) - 1)
    trades_per_year = 252 / HORIZON_D
    sharpe = (arr.mean() / arr.std() * np.sqrt(trades_per_year)) if arr.std() > 0 else 0
    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min())

    return {
        "ticker": ticker, "trades": tt, "wr": wr,
        "avg": float(arr.mean() * 100),
        "cum": cum * 100, "sharpe": float(sharpe),
        "maxdd": max_dd * 100,
    }


def main():
    print("=" * 110)
    print("STOCKS BACKTEST — LightGBM Walk-Forward")
    print(f"Ticker: {len(TICKERS)} | Horizon: {HORIZON_D}d | Train: {TRAIN_D}d (2y) | Test: {TEST_D}d (3m)")
    print(f"Fee: {FEE_BPS*100:.2f}% RT | Period: 10 Jahre (max yfinance)")
    print("=" * 110)

    # 1) Macro + Benchmark laden
    print("\n[1/3] Lade Benchmark und Macro-Daten...")
    spy_df = fetch_cached(BENCHMARK)
    spy_close = spy_df["close"]

    macro_data = {}
    for tick, slug in MACRO.items():
        df_m = fetch_cached(tick)
        if not df_m.empty:
            macro_data[slug] = df_m["close"]

    # SPY Buy & Hold Benchmark
    spy_bh_5y = (spy_close.iloc[-1] / spy_close.iloc[-min(252*5, len(spy_close))] - 1) * 100
    spy_bh_all = (spy_close.iloc[-1] / spy_close.iloc[0] - 1) * 100
    print(f"  SPY B&H 5y: {spy_bh_5y:+.1f}% | gesamt: {spy_bh_all:+.1f}%")

    # 2) Pro Ticker laden + Features + Backtest
    print("\n[2/3] Lade Tickers und baue Features...")
    results = []
    for ticker in TICKERS:
        df = fetch_cached(ticker)
        if df.empty or len(df) < TRAIN_D + TEST_D + 60:
            print(f"  {ticker}: insufficient data")
            continue
        features = build_features(df, spy_close, macro_data)
        r = walk_forward_backtest(ticker, features, df["close"])
        if r is None:
            print(f"  {ticker}: no trades")
            continue
        results.append(r)

    # 3) Ergebnisse
    print("\n[3/3] Ergebnisse:")
    print("=" * 110)
    print(f"{'Ticker':<8} {'Trades':>7} {'WR':>6} {'AvgTrade':>10} {'CumRet':>10} {'Sharpe':>8} {'MaxDD':>8}")
    print("-" * 110)
    for r in sorted(results, key=lambda x: -x["sharpe"]):
        print(
            f"{r['ticker']:<8} {r['trades']:>7} {r['wr']:>5.1f}% "
            f"{r['avg']:>+8.2f}% {r['cum']:>+8.1f}% "
            f"{r['sharpe']:>+7.2f} {r['maxdd']:>+7.1f}%"
        )

    if results:
        print("-" * 110)
        avg_sharpe = np.mean([r["sharpe"] for r in results])
        avg_cum = np.mean([r["cum"] for r in results])
        med_wr = np.median([r["wr"] for r in results])
        med_dd = np.median([r["maxdd"] for r in results])
        n_positive = sum(1 for r in results if r["cum"] > 0)
        n_profitable_vs_spy = sum(1 for r in results if r["cum"] > spy_bh_all)
        print(
            f"{'MEAN':<8} {'':>7} {med_wr:>5.1f}% "
            f"{'':>9} {avg_cum:>+8.1f}% "
            f"{avg_sharpe:>+7.2f} {med_dd:>+7.1f}%"
        )
        print("\n" + "=" * 110)
        print("ZUSAMMENFASSUNG:")
        print(f"  Positive Ticker: {n_positive}/{len(results)}")
        print(f"  Schlagen SPY B&H: {n_profitable_vs_spy}/{len(results)}")
        print(f"  Mean Sharpe: {avg_sharpe:+.2f}")
        print(f"  Median Max DD: {med_dd:+.1f}%")
        print(f"  SPY Benchmark (gesamte Periode): {spy_bh_all:+.1f}%")
        print("=" * 110)
        print("\nBEWERTUNG:")
        if avg_sharpe > 0.8 and n_profitable_vs_spy > len(results) // 2:
            print("  POSITIV — Edge vorhanden, weiter mit Paper-Trading")
        elif avg_sharpe > 0.3:
            print("  MIXED — Schwacher Edge, braucht Verbesserung")
        else:
            print("  NEGATIV — kein robuster Edge, Qlib/Cross-Sectional testen")


if __name__ == "__main__":
    main()
