"""Systematische Untersuchung: Was koennte funktionieren?

Hypothesen:
1. SL/TP-Verhaeltnis ist das Problem, nicht das Modell
2. Signal invertieren (Contrarian) — wenn alle Down sagen, kaufen
3. Nur in bestimmten Regimes handeln (hohe Volatilitaet)
4. Kuerzerer Horizont (24h statt 72h)
5. Laengerer Horizont (168h statt 72h)
6. Confidence-Threshold hoeher setzen (75%+)
7. Nur die staerksten Features verwenden
"""

import sys
import warnings

sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

CP = Path("C:/Codes/coin_prediction")

CLF_P = {
    "objective": "binary",
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


def simulate_trades(close, X, y, predictions, horizon_h, min_conf,
                    sl_mult=2.0, tp_mult=2.0, invert=False, fee_pct=0.2):
    """Simuliert Trades mit konfigurierbarem SL/TP."""
    trades = []

    for p in predictions:
        direction = p["direction"]
        confidence = p["confidence"]
        idx = p["idx"]

        # Invert-Modus: kaufen wenn Modell Down sagt
        if invert:
            direction = "down" if direction == "up" else "up"
            # Confidence bleibt gleich (Staerke des Signals)

        if direction != "up" or confidence < min_conf:
            continue

        entry_price = float(close.iloc[idx])
        atr_14 = float(close.iloc[max(0, idx - 14):idx].diff().abs().mean())
        sl_pct = min(sl_mult * atr_14 / entry_price, 0.10)
        tp_pct = min(tp_mult * atr_14 / entry_price, 0.10)

        exit_idx = idx + horizon_h
        if exit_idx >= len(close):
            continue

        holding = close.iloc[idx:exit_idx + 1].astype(float)
        sl_price = entry_price * (1 - sl_pct)
        tp_price = entry_price * (1 + tp_pct)

        hit_sl = holding.min() <= sl_price
        hit_tp = holding.max() >= tp_price

        if hit_sl and hit_tp:
            sl_i = (holding <= sl_price).idxmax()
            tp_i = (holding >= tp_price).idxmax()
            if sl_i <= tp_i:
                actual_exit, reason = sl_price, "sl"
            else:
                actual_exit, reason = tp_price, "tp"
        elif hit_sl:
            actual_exit, reason = sl_price, "sl"
        elif hit_tp:
            actual_exit, reason = tp_price, "tp"
        else:
            actual_exit, reason = float(close.iloc[exit_idx]), "time"

        pnl = (actual_exit / entry_price - 1) * 100 - fee_pct
        trades.append({"pnl": pnl, "reason": reason, "confidence": confidence})

    return trades


def run_backtest_core(coin="BTC", horizon_h=72, train_h=720, test_days=90):
    """Kern-Backtest: gibt Predictions zurueck fuer verschiedene Strategien."""
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
    test_hours = test_days * 24
    test_start = n - test_hours - horizon_h

    predictions = []
    print(f"  Training {test_hours} Modelle (Horizont {horizon_h}h)...", end=" ", flush=True)

    for step in range(test_hours):
        i = test_start + step
        train_end = i
        train_start = max(0, train_end - train_h)

        Xtr = X.iloc[train_start:train_end]
        ytr = y.iloc[train_start:train_end]

        if len(Xtr) < 200:
            continue

        s = int(len(Xtr) * 0.8)
        m = lgb.LGBMClassifier(**CLF_P)
        kw = {}
        if s < len(Xtr):
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)

        Xte = X.iloc[i:i + 1]
        proba = m.predict_proba(Xte)[:, 1][0]
        direction = "up" if proba > 0.5 else "down"
        confidence = abs(proba - 0.5) + 0.5
        actual_up = int(y.iloc[i])

        predictions.append({
            "idx": i,
            "direction": direction,
            "probability": proba,
            "confidence": confidence,
            "actual_up": actual_up,
        })

    print(f"{len(predictions)} Predictions")
    return close, X, y, predictions


def summarize_trades(trades, label=""):
    if not trades:
        return f"  {label:<35} {'KEINE TRADES':>10}"

    df = pd.DataFrame(trades)
    n = len(df)
    wins = (df["pnl"] > 0).sum()
    wr = wins / n * 100
    avg = df["pnl"].mean()
    total = df["pnl"].sum()
    return f"  {label:<35} {n:>4} Trades  WR {wr:>5.1f}%  Avg {avg:>+7.3f}%  Total {total:>+8.2f}%"


def main():
    print("=" * 75)
    print("SYSTEMATISCHE UNTERSUCHUNG: Was koennte funktionieren?")
    print("=" * 75)

    # =====================================================================
    # Test 1: Verschiedene Horizonte (mit stuendl. Training)
    # =====================================================================
    print("\n[1/4] HORIZONT-VERGLEICH (stuendl. Training, 90 Tage)")
    print("-" * 75)

    for horizon in [24, 48, 72, 168]:
        close, X, y, preds = run_backtest_core(horizon_h=horizon, test_days=90)

        # Accuracy
        correct = sum(1 for p in preds if (p["direction"] == "up") == (p["actual_up"] == 1))
        acc = correct / len(preds) * 100

        print(f"\n  Horizont {horizon}h (Accuracy: {acc:.1f}%):")
        for conf in [0.55, 0.60, 0.65, 0.70, 0.75]:
            trades = simulate_trades(close, X, y, preds, horizon, conf)
            print(summarize_trades(trades, f"    Conf >= {conf:.0%}"))

    # =====================================================================
    # Test 2: SL/TP Verhaeltnis
    # =====================================================================
    print(f"\n\n[2/4] SL/TP VERHAELTNIS (72h Horizont)")
    print("-" * 75)

    close, X, y, preds = run_backtest_core(horizon_h=72, test_days=90)

    configs = [
        ("SL 1x / TP 1x (eng)", 1.0, 1.0),
        ("SL 1x / TP 2x (asym.)", 1.0, 2.0),
        ("SL 1x / TP 3x (weit)", 1.0, 3.0),
        ("SL 2x / TP 2x (Standard)", 2.0, 2.0),
        ("SL 2x / TP 3x", 2.0, 3.0),
        ("SL 2x / TP 4x", 2.0, 4.0),
        ("SL 3x / TP 3x", 3.0, 3.0),
        ("Kein SL/TP (nur Zeit)", 99.0, 99.0),
    ]

    for label, sl, tp in configs:
        trades = simulate_trades(close, X, y, preds, 72, 0.65, sl_mult=sl, tp_mult=tp)
        print(summarize_trades(trades, label))

    # =====================================================================
    # Test 3: Contrarian (Signal invertieren)
    # =====================================================================
    print(f"\n\n[3/4] CONTRARIAN: Signal invertieren")
    print("-" * 75)
    print("  (Kaufen wenn Modell Down sagt mit hoher Confidence)")

    for conf in [0.55, 0.60, 0.65, 0.70, 0.75]:
        trades = simulate_trades(close, X, y, preds, 72, conf, invert=True)
        print(summarize_trades(trades, f"  Contrarian Conf >= {conf:.0%}"))

    print("\n  Mit asymmetrischem SL/TP (1x SL / 3x TP):")
    for conf in [0.55, 0.60, 0.65, 0.70]:
        trades = simulate_trades(close, X, y, preds, 72, conf,
                                 sl_mult=1.0, tp_mult=3.0, invert=True)
        print(summarize_trades(trades, f"  Contrarian {conf:.0%} + asym SL/TP"))

    # =====================================================================
    # Test 4: Volatilitaets-Filter
    # =====================================================================
    print(f"\n\n[4/4] VOLATILITAETS-REGIME")
    print("-" * 75)
    print("  (Nur handeln wenn Volatilitaet hoch/niedrig ist)")

    # Berechne Volatilitaets-Quintile
    features = build_1h_features(
        pd.read_parquet(CP / "data/raw/BTC_USDT_1h.parquet").pipe(
            lambda d: d.set_index("timestamp").sort_index() if "timestamp" in d.columns else d
        )
    )
    vol_col = "vol_24h"
    n_total = len(X)

    for regime_label, vol_low, vol_high in [
        ("Niedrige Vol (Q1)", 0.0, 0.25),
        ("Mittlere Vol (Q2-Q3)", 0.25, 0.75),
        ("Hohe Vol (Q4)", 0.75, 1.0),
    ]:
        # Vol-Quantile berechnen
        vol_series = features[vol_col].reindex(X.index)
        vol_quantiles = vol_series.quantile([vol_low, vol_high])
        q_lo, q_hi = vol_quantiles.iloc[0], vol_quantiles.iloc[1]

        # Nur Predictions in diesem Regime
        regime_preds = []
        for p in preds:
            idx = p["idx"]
            vol_val = vol_series.iloc[idx] if idx < len(vol_series) else None
            if vol_val is not None and q_lo <= vol_val <= q_hi:
                regime_preds.append(p)

        trades = simulate_trades(close, X, y, regime_preds, 72, 0.65)
        n_preds = len(regime_preds)
        if regime_preds:
            correct = sum(1 for p in regime_preds
                          if (p["direction"] == "up") == (p["actual_up"] == 1))
            acc = correct / n_preds * 100
            print(f"  {regime_label}: {n_preds} Preds, Acc {acc:.1f}%")
            print(summarize_trades(trades, f"    Trades"))
        else:
            print(f"  {regime_label}: Keine Predictions")

    print(f"\n{'=' * 75}")
    print("FAZIT")
    print("=" * 75)


if __name__ == "__main__":
    import time
    t0 = time.time()
    main()
    elapsed = time.time() - t0
    print(f"\nLaufzeit: {elapsed / 60:.1f} Minuten")
