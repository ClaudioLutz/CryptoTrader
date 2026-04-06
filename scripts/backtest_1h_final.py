"""Realistischer Backtest: BTC 1h mit stuendlichem Retraining.

Vergleicht:
- Alt: SL 2x / TP 2x (symmetrisch)
- Neu: SL 2x / TP 4x (asymmetrisch)
- Referenz: Kein SL/TP (nur Zeitablauf)

Testet 90 und 180 Tage.
"""

import sys
import warnings
import time

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


def get_predictions(coin, horizon_h, train_h, test_days):
    """Stuendliches Training, gibt alle Predictions zurueck."""
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
    last_pct = -1

    for step in range(test_hours):
        i = test_start + step
        pct = int(step / test_hours * 100)
        if pct % 10 == 0 and pct != last_pct:
            last_pct = pct
            print(f"    {pct}%", end=" ", flush=True)

        train_end = i
        train_start_idx = max(0, train_end - train_h)
        Xtr = X.iloc[train_start_idx:train_end]
        ytr = y.iloc[train_start_idx:train_end]

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

        predictions.append({
            "idx": i,
            "timestamp": X.index[i],
            "direction": direction,
            "probability": proba,
            "confidence": confidence,
            "actual_up": int(y.iloc[i]),
        })

    print()
    return close, X, y, predictions


def simulate(close, preds, horizon_h, min_conf, sl_mult, tp_mult, fee_pct=0.2,
             capital=453.0, max_exposure_pct=0.80):
    """Realistische Trade-Simulation mit Kapital und Exposure-Limits."""
    trades = []
    equity_curve = []
    balance = capital
    open_positions = []  # (entry_price, amount, sl, tp, close_idx)

    for p in preds:
        idx = p["idx"]
        price = float(close.iloc[idx])

        # Offene Positionen pruefen
        closed_now = []
        for pos in open_positions:
            e_price, amount, sl_p, tp_p, close_idx = pos
            if idx >= close_idx:
                # Zeitablauf
                exit_p = float(close.iloc[min(close_idx, len(close) - 1)])
                pnl = amount * (exit_p / e_price - 1) - amount * fee_pct / 100
                balance += amount + pnl
                trades.append({"pnl_pct": (exit_p / e_price - 1) * 100 - fee_pct,
                                "pnl_usd": pnl, "reason": "time"})
                closed_now.append(pos)
                continue

            # SL/TP pruefen (vereinfacht: nur aktuellen Preis)
            if sl_p and price <= sl_p:
                pnl = amount * (sl_p / e_price - 1) - amount * fee_pct / 100
                balance += amount + pnl
                trades.append({"pnl_pct": (sl_p / e_price - 1) * 100 - fee_pct,
                                "pnl_usd": pnl, "reason": "sl"})
                closed_now.append(pos)
            elif tp_p and price >= tp_p:
                pnl = amount * (tp_p / e_price - 1) - amount * fee_pct / 100
                balance += amount + pnl
                trades.append({"pnl_pct": (tp_p / e_price - 1) * 100 - fee_pct,
                                "pnl_usd": pnl, "reason": "tp"})
                closed_now.append(pos)

        for pos in closed_now:
            open_positions.remove(pos)

        # Neuer Trade?
        if p["direction"] == "up" and p["confidence"] >= min_conf:
            exposure = sum(pos[1] for pos in open_positions)
            max_exp = capital * max_exposure_pct
            available = min(balance, max_exp - exposure)

            if available > 1:
                # Confidence-gewichtete Groesse
                conf_range = 1.0 - min_conf
                if conf_range > 0:
                    scale = 0.25 + 0.75 * ((p["confidence"] - min_conf) / conf_range)
                else:
                    scale = 1.0
                size = min(available * scale, available)
                if size < 1:
                    continue

                balance -= size
                atr = float(close.iloc[max(0, idx - 14):idx].diff().abs().mean())
                sl_pct = min(sl_mult * atr / price, 0.10) if sl_mult < 50 else None
                tp_pct = min(tp_mult * atr / price, 0.20) if tp_mult < 50 else None
                sl_p = price * (1 - sl_pct) if sl_pct else None
                tp_p = price * (1 + tp_pct) if tp_pct else None

                open_positions.append((price, size, sl_p, tp_p, idx + horizon_h))

        total_equity = balance + sum(pos[1] for pos in open_positions)
        equity_curve.append({"idx": idx, "equity": total_equity})

    # Offene Positionen am Ende schliessen
    for pos in open_positions:
        e_price, amount, _, _, close_idx = pos
        exit_p = float(close.iloc[min(close_idx, len(close) - 1)])
        pnl = amount * (exit_p / e_price - 1) - amount * fee_pct / 100
        balance += amount + pnl
        trades.append({"pnl_pct": (exit_p / e_price - 1) * 100 - fee_pct,
                        "pnl_usd": pnl, "reason": "time"})

    return trades, balance, equity_curve


def report(label, trades, start_capital, end_balance):
    if not trades:
        print(f"  {label:<30} KEINE TRADES")
        return

    df = pd.DataFrame(trades)
    n = len(df)
    wins = (df["pnl_usd"] > 0).sum()
    wr = wins / n * 100
    total_pnl = end_balance - start_capital
    total_pnl_pct = total_pnl / start_capital * 100
    avg_pnl = df["pnl_pct"].mean()
    max_dd = 0  # vereinfacht

    reasons = df["reason"].value_counts()
    reason_str = ", ".join(f"{r}:{c}" for r, c in reasons.items())

    print(f"  {label}")
    print(f"    Trades: {n}  |  WR: {wr:.1f}%  |  Avg: {avg_pnl:+.3f}%")
    print(f"    Kapital: ${start_capital:.0f} -> ${end_balance:.2f}  ({total_pnl_pct:+.1f}%)")
    print(f"    Reasons: {reason_str}")
    print()


def main():
    capital = 453.0
    min_conf = 0.65

    print("=" * 75)
    print("REALISTISCHER BACKTEST: SL/TP-Vergleich mit stuendl. Training")
    print(f"Kapital: ${capital:.0f}  |  Min-Confidence: {min_conf:.0%}")
    print("=" * 75)

    for test_days in [90, 180]:
        print(f"\n{'=' * 75}")
        print(f"  ZEITRAUM: {test_days} Tage")
        print(f"{'=' * 75}")

        t0 = time.time()
        close, X, y, preds = get_predictions("BTC", 72, 720, test_days)
        elapsed = time.time() - t0
        print(f"  {len(preds)} Predictions in {elapsed:.0f}s\n")

        # Accuracy
        correct = sum(1 for p in preds if (p["direction"] == "up") == (p["actual_up"] == 1))
        up = sum(1 for p in preds if p["direction"] == "up")
        high_conf = sum(1 for p in preds if p["confidence"] >= min_conf)
        high_conf_up = sum(1 for p in preds if p["confidence"] >= min_conf and p["direction"] == "up")
        print(f"  Accuracy: {correct / len(preds) * 100:.1f}%")
        print(f"  Up/Down: {up} / {len(preds) - up}")
        print(f"  Conf >= {min_conf:.0%}: {high_conf} ({high_conf_up} Up-Signale)")
        print()

        configs = [
            ("ALT: SL 2x / TP 2x", 2.0, 2.0),
            ("NEU: SL 2x / TP 4x", 2.0, 4.0),
            ("SL 2x / TP 3x", 2.0, 3.0),
            ("SL 3x / TP 4x", 3.0, 4.0),
            ("Kein SL/TP (nur Zeit)", 99.0, 99.0),
        ]

        for label, sl, tp in configs:
            trades, end_bal, equity = simulate(
                close, preds, 72, min_conf, sl, tp, capital=capital
            )
            report(label, trades, capital, end_bal)

    print("=" * 75)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nGesamtlaufzeit: {(time.time() - t0) / 60:.1f} Minuten")
