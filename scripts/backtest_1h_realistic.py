"""Realistischer Backtest: BTC 1h mit stuendlichem Retraining.

Simuliert exakt die Produktion:
- Jede Stunde neues Training (720h Window)
- 72h Prediction-Horizont
- Min-Confidence 65%
- ATR-basiertes SL/TP
"""

import sys
import warnings

sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from datetime import timedelta

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


def run_realistic_backtest(
    coin="BTC",
    horizon_h=72,
    train_h=720,
    min_conf=0.65,
    test_days=90,
):
    """Stuendliches Retraining wie in Produktion."""
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

    # Nur die letzten test_days Tage testen
    n = len(X)
    test_hours = test_days * 24
    test_start = n - test_hours - horizon_h  # Genug Platz fuer letzten Horizont

    if test_start < train_h:
        print(f"FEHLER: Nicht genug Daten. Brauche {train_h + test_hours} h, habe {n} h")
        return None

    predictions = []
    trades = []
    total_steps = test_hours
    last_pct = -1

    print(f"\nStarte Backtest: {test_days} Tage, {total_steps} stuendliche Trainings")
    print(f"Train-Window: {train_h}h, Horizont: {horizon_h}h, Min-Confidence: {min_conf:.0%}")
    print()

    for step in range(total_steps):
        i = test_start + step  # Index im Gesamt-Array

        # Fortschritt
        pct = int(step / total_steps * 100)
        if pct % 5 == 0 and pct != last_pct:
            last_pct = pct
            print(f"  {pct:>3}% ({step}/{total_steps}) ...", flush=True)

        # Training: letzte train_h Stunden VOR diesem Zeitpunkt
        train_end = i
        train_start = max(0, train_end - train_h)

        Xtr = X.iloc[train_start:train_end]
        ytr = y.iloc[train_start:train_end]

        if len(Xtr) < 200:
            continue

        # 80/20 Split fuer Early Stopping
        s = int(len(Xtr) * 0.8)
        m = lgb.LGBMClassifier(**CLF_P)
        kw = {}
        if s < len(Xtr):
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)

        # Prediction fuer DIESEN Zeitpunkt
        Xte = X.iloc[i:i + 1]
        proba = m.predict_proba(Xte)[:, 1][0]
        direction = "up" if proba > 0.5 else "down"
        confidence = abs(proba - 0.5) + 0.5
        actual_up = int(y.iloc[i])
        correct = (direction == "up") == (actual_up == 1)

        predictions.append({
            "timestamp": X.index[i],
            "direction": direction,
            "probability": round(proba, 4),
            "confidence": round(confidence, 4),
            "actual_up": actual_up,
            "correct": correct,
            "close": float(close.iloc[i]) if i < len(close) else None,
        })

        # Trade-Logik: nur Up mit hoher Confidence
        if direction == "up" and confidence >= min_conf:
            entry_price = float(close.iloc[i])
            # ATR fuer SL/TP
            atr_14 = float(close.iloc[max(0, i - 14):i].diff().abs().mean())
            sl_pct = min(2 * atr_14 / entry_price, 0.10)
            tp_pct = min(2 * atr_14 / entry_price, 0.10)

            # Ergebnis nach horizon_h Stunden
            exit_idx = i + horizon_h
            if exit_idx < len(close):
                exit_price = float(close.iloc[exit_idx])

                # SL/TP waehrend der Haltedauer pruefen
                holding_prices = close.iloc[i:exit_idx + 1].astype(float)
                sl_price = entry_price * (1 - sl_pct)
                tp_price = entry_price * (1 + tp_pct)

                hit_sl = holding_prices.min() <= sl_price
                hit_tp = holding_prices.max() >= tp_price

                if hit_sl and hit_tp:
                    # Beide getroffen — welches zuerst?
                    sl_idx = (holding_prices <= sl_price).idxmax()
                    tp_idx = (holding_prices >= tp_price).idxmax()
                    if sl_idx <= tp_idx:
                        actual_exit = sl_price
                        reason = "sl"
                    else:
                        actual_exit = tp_price
                        reason = "tp"
                elif hit_sl:
                    actual_exit = sl_price
                    reason = "sl"
                elif hit_tp:
                    actual_exit = tp_price
                    reason = "tp"
                else:
                    actual_exit = exit_price
                    reason = "time"

                pnl_pct = (actual_exit / entry_price - 1) * 100
                fee_pct = 0.2  # 0.1% je Seite
                net_pnl = pnl_pct - fee_pct

                trades.append({
                    "timestamp": X.index[i],
                    "entry": entry_price,
                    "exit": actual_exit,
                    "reason": reason,
                    "pnl_pct": round(pnl_pct, 3),
                    "net_pnl": round(net_pnl, 3),
                    "confidence": round(confidence, 4),
                })

    # === AUSWERTUNG ===
    print(f"\n{'=' * 70}")
    print(f"ERGEBNIS: BTC 1h Backtest ({test_days} Tage, stuendl. Training)")
    print(f"{'=' * 70}")

    df_pred = pd.DataFrame(predictions)
    df_trades = pd.DataFrame(trades)

    # Prediction-Qualitaet
    total = len(df_pred)
    correct = df_pred["correct"].sum()
    accuracy = correct / total * 100 if total > 0 else 0
    up_preds = (df_pred["direction"] == "up").sum()
    down_preds = (df_pred["direction"] == "down").sum()
    avg_conf = df_pred["confidence"].mean() * 100

    print(f"\nPrediction-Qualitaet:")
    print(f"  Total Predictions:  {total}")
    print(f"  Accuracy:           {accuracy:.1f}%")
    print(f"  Up / Down:          {up_preds} / {down_preds}")
    print(f"  Avg Confidence:     {avg_conf:.1f}%")

    # Confidence-Verteilung
    print(f"\n  Confidence-Verteilung:")
    for thresh in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]:
        above = (df_pred["confidence"] >= thresh).sum()
        if above > 0:
            acc_above = df_pred[df_pred["confidence"] >= thresh]["correct"].mean() * 100
            print(f"    >= {thresh:.0%}: {above:>5} Predictions, Accuracy {acc_above:.1f}%")

    # Trade-Ergebnisse
    print(f"\nTrade-Ergebnisse (Min-Confidence {min_conf:.0%}):")
    if len(df_trades) > 0:
        wins = (df_trades["net_pnl"] > 0).sum()
        losses = (df_trades["net_pnl"] <= 0).sum()
        wr = wins / len(df_trades) * 100
        avg_pnl = df_trades["net_pnl"].mean()
        median_pnl = df_trades["net_pnl"].median()
        total_pnl = df_trades["net_pnl"].sum()
        best = df_trades["net_pnl"].max()
        worst = df_trades["net_pnl"].min()

        # Reason Breakdown
        reasons = df_trades["reason"].value_counts()

        print(f"  Total Trades:       {len(df_trades)}")
        print(f"  Wins / Losses:      {wins} / {losses}")
        print(f"  Win-Rate:           {wr:.1f}%")
        print(f"  Avg P&L:            {avg_pnl:+.3f}%")
        print(f"  Median P&L:         {median_pnl:+.3f}%")
        print(f"  Total P&L:          {total_pnl:+.2f}%")
        print(f"  Bester Trade:       {best:+.3f}%")
        print(f"  Schlechtester:      {worst:+.3f}%")
        print(f"\n  Close-Reasons:")
        for reason, count in reasons.items():
            reason_trades = df_trades[df_trades["reason"] == reason]
            r_wr = (reason_trades["net_pnl"] > 0).mean() * 100
            r_avg = reason_trades["net_pnl"].mean()
            label = {"sl": "Stop-Loss", "tp": "Take-Profit", "time": "Zeitablauf"}.get(reason, reason)
            print(f"    {label:<14} {count:>4} Trades, WR {r_wr:.0f}%, Avg {r_avg:+.3f}%")
    else:
        print(f"  KEINE TRADES! Confidence nie ueber {min_conf:.0%} bei Up-Signal.")

    # Verschiedene Confidence-Thresholds testen
    print(f"\n{'=' * 70}")
    print(f"CONFIDENCE-THRESHOLD ANALYSE")
    print(f"{'=' * 70}")
    print(f"{'Threshold':>10} {'Trades':>7} {'WR':>6} {'Avg P&L':>8} {'Total P&L':>10}")
    print(f"{'-' * 45}")

    for conf_test in [0.50, 0.55, 0.60, 0.65, 0.70]:
        # Re-filter trades from predictions
        t = []
        for _, p in df_pred.iterrows():
            if p["direction"] == "up" and p["confidence"] >= conf_test and p["close"]:
                idx_in_close = close.index.get_loc(p["timestamp"])
                entry = p["close"]
                exit_idx = idx_in_close + horizon_h
                if exit_idx < len(close):
                    exit_p = float(close.iloc[exit_idx])
                    pnl = (exit_p / entry - 1) * 100 - 0.2
                    t.append(pnl)

        if t:
            wr = sum(1 for x in t if x > 0) / len(t) * 100
            avg = np.mean(t)
            total = sum(t)
            print(f"  {conf_test:>7.0%} {len(t):>7} {wr:>5.1f}% {avg:>+7.3f}% {total:>+9.2f}%")
        else:
            print(f"  {conf_test:>7.0%}       0     -        -          -")

    return df_pred, df_trades


if __name__ == "__main__":
    import time
    t0 = time.time()
    run_realistic_backtest(test_days=90)
    elapsed = time.time() - t0
    print(f"\nLaufzeit: {elapsed / 60:.1f} Minuten")
