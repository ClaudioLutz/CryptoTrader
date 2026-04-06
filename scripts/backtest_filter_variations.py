"""Backtest: Filter-Variationen mit verschiedenen SL/TP und Confidence-Schwellen.

Testet die besten Filter aus backtest_new_approaches.py mit:
- Verschiedenen SL/TP-Konfigurationen
- Verschiedenen Confidence-Schwellen
- 90 und 180 Tage
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
from hmmlearn.hmm import GaussianHMM

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


def build_4h_trend(ohlcv_1h):
    ohlcv_4h = ohlcv_1h.resample("4h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna()
    close_4h = ohlcv_4h["close"].astype(float)
    ema8 = close_4h.ewm(span=8, adjust=False).mean()
    ema21 = close_4h.ewm(span=21, adjust=False).mean()
    trend = (ema8 > ema21).astype(float)
    return trend.reindex(ohlcv_1h.index, method="ffill")


def rolling_hmm_regimes(close, train_window=720, n_states=3):
    returns = close.pct_change().dropna()
    vol_24h = returns.rolling(24).std().dropna()
    common = returns.index.intersection(vol_24h.index)
    returns = returns.loc[common]
    vol_24h = vol_24h.loc[common]

    regime_series = pd.Series(np.nan, index=common, name="regime")
    last_hmm = None
    last_mapping = None

    for i in range(train_window, len(common)):
        if i % 24 == 0 or last_hmm is None:
            X_train = np.column_stack([
                returns.values[max(0, i - train_window):i],
                vol_24h.values[max(0, i - train_window):i],
            ])
            try:
                hmm = GaussianHMM(n_components=n_states, covariance_type="full",
                                   n_iter=50, random_state=42, verbose=False)
                hmm.fit(X_train)
                last_hmm = hmm
                states_train = hmm.predict(X_train)
                state_vols = {}
                for s in range(n_states):
                    mask = states_train == s
                    if mask.sum() > 0:
                        state_vols[s] = vol_24h.values[max(0, i - train_window):i][mask].mean()
                    else:
                        state_vols[s] = float("inf")
                sorted_states = sorted(state_vols, key=state_vols.get)
                last_mapping = {state_id: rank for rank, state_id in enumerate(sorted_states)}
            except Exception:
                pass

        if last_hmm is not None:
            X_point = np.array([[returns.values[i], vol_24h.values[i]]])
            try:
                raw_state = last_hmm.predict(X_point)[0]
                regime_series.iloc[i] = last_mapping.get(raw_state, 1)
            except Exception:
                regime_series.iloc[i] = 1

    return regime_series


def get_predictions(close, X, y, test_start, test_hours, train_h=720):
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
            "idx": i, "timestamp": X.index[i], "direction": direction,
            "probability": proba, "confidence": confidence,
            "actual_up": int(y.iloc[i]),
        })
    print()
    return predictions


def simulate_trades(close, predictions, horizon_h, min_conf,
                    sl_mult=2.0, tp_mult=4.0, fee_pct=0.2,
                    capital=453.0, max_exposure_pct=0.80):
    trades = []
    balance = capital
    open_positions = []

    for p in predictions:
        idx = p["idx"]
        if idx >= len(close):
            continue
        price = float(close.iloc[idx])

        closed_now = []
        for pos in open_positions:
            e_price, amount, sl_p, tp_p, close_idx = pos
            if idx >= close_idx:
                exit_p = float(close.iloc[min(close_idx, len(close) - 1)])
                pnl = amount * (exit_p / e_price - 1) - amount * fee_pct / 100
                balance += amount + pnl
                trades.append({"pnl_pct": (exit_p / e_price - 1) * 100 - fee_pct,
                                "pnl_usd": pnl, "reason": "time"})
                closed_now.append(pos)
                continue
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

        if p["direction"] == "up" and p["confidence"] >= min_conf:
            exposure = sum(pos[1] for pos in open_positions)
            max_exp = capital * max_exposure_pct
            available = min(balance, max_exp - exposure)
            if available > 1:
                conf_range = 1.0 - min_conf
                scale = (0.25 + 0.75 * ((p["confidence"] - min_conf) / conf_range)) if conf_range > 0 else 1.0
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

    for pos in open_positions:
        e_price, amount, _, _, close_idx = pos
        exit_p = float(close.iloc[min(close_idx, len(close) - 1)])
        pnl = amount * (exit_p / e_price - 1) - amount * fee_pct / 100
        balance += amount + pnl
        trades.append({"pnl_pct": (exit_p / e_price - 1) * 100 - fee_pct,
                        "pnl_usd": pnl, "reason": "time"})

    return trades, balance


def main():
    capital = 453.0
    horizon_h = 72
    train_h = 720

    print("=" * 90)
    print("FILTER-VARIATIONEN: SL/TP + Confidence + Zeitraum")
    print("=" * 90)

    ohlcv = pd.read_parquet(CP / "data/raw/BTC_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    close = ohlcv["close"].astype(float)

    future_return = close.shift(-horizon_h) / close - 1
    target = (future_return > 0).astype(float)
    target[future_return.isna()] = float("nan")

    features = build_1h_features(ohlcv)
    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    # HMM + 4h-Trend
    print("\n[1] HMM Regimes berechnen...")
    t0 = time.time()
    regimes = rolling_hmm_regimes(close, train_window=train_h, n_states=3)
    print(f"  Fertig in {time.time() - t0:.0f}s")

    print("[2] 4h-Trend berechnen...")
    trend_4h = build_4h_trend(ohlcv)

    for test_days in [90, 180]:
        print(f"\n{'=' * 90}")
        print(f"  ZEITRAUM: {test_days} Tage")
        print(f"{'=' * 90}")

        n = len(X)
        test_hours = test_days * 24
        test_start = n - test_hours - horizon_h

        print(f"\n[3] Predictions berechnen ({test_days}d)...")
        t0 = time.time()
        preds = get_predictions(close, X, y, test_start, test_hours, train_h)
        print(f"  {len(preds)} Predictions in {time.time() - t0:.0f}s")

        correct = sum(1 for p in preds if (p["direction"] == "up") == (p["actual_up"] == 1))
        print(f"  Accuracy: {correct / len(preds) * 100:.1f}%\n")

        # Filter-Varianten
        def apply_filter(preds, filter_type):
            if filter_type == "none":
                return preds
            elif filter_type == "4h_trend":
                return [p for p in preds if trend_4h.get(p["timestamp"], 0) == 1.0]
            elif filter_type == "hmm_01":
                return [p for p in preds if regimes.get(p["timestamp"], 1) in [0, 1]]
            elif filter_type == "hmm_01_trend":
                return [p for p in preds
                        if regimes.get(p["timestamp"], 1) in [0, 1]
                        and trend_4h.get(p["timestamp"], 0) == 1.0]
            elif filter_type == "hmm_0_trend":
                return [p for p in preds
                        if regimes.get(p["timestamp"], 1) == 0
                        and trend_4h.get(p["timestamp"], 0) == 1.0]
            return preds

        # Ergebnis-Tabelle
        print(f"  {'Filter':<25} {'Conf':>4} {'SL/TP':>8} {'Trades':>6} {'WR':>6} "
              f"{'Avg':>8} {'Total':>7} {'Kapital':>9}")
        print(f"  {'-' * 83}")

        filters = [
            ("none", "Kein Filter"),
            ("4h_trend", "4h-Trend"),
            ("hmm_01_trend", "HMM(0+1)+Trend"),
            ("hmm_0_trend", "HMM(0)+Trend"),
        ]

        sltp_configs = [
            (2.0, 4.0, "2x/4x"),
            (2.0, 3.0, "2x/3x"),
            (3.0, 4.0, "3x/4x"),
            (99.0, 99.0, "kein"),
        ]

        conf_levels = [0.60, 0.65, 0.70, 0.75]

        best_result = None
        best_pnl = -999

        for filter_type, filter_name in filters:
            for min_conf in conf_levels:
                for sl, tp, sltp_name in sltp_configs:
                    filtered = apply_filter(preds, filter_type)
                    trades, bal = simulate_trades(
                        close, filtered, horizon_h, min_conf,
                        sl_mult=sl, tp_mult=tp, capital=capital
                    )

                    if not trades:
                        continue

                    df_t = pd.DataFrame(trades)
                    n_trades = len(df_t)
                    wins = (df_t["pnl_usd"] > 0).sum()
                    wr = wins / n_trades * 100
                    avg_pnl = df_t["pnl_pct"].mean()
                    total_pnl_pct = (bal - capital) / capital * 100

                    if n_trades >= 5:  # Min 5 Trades fuer Relevanz
                        print(f"  {filter_name:<25} {min_conf:>3.0%} {sltp_name:>8} "
                              f"{n_trades:>6} {wr:>5.1f}% {avg_pnl:>+7.3f}% "
                              f"{total_pnl_pct:>+6.1f}% ${bal:>8.2f}")

                        if total_pnl_pct > best_pnl:
                            best_pnl = total_pnl_pct
                            best_result = {
                                "filter": filter_name, "conf": min_conf,
                                "sltp": sltp_name, "trades": n_trades,
                                "wr": wr, "avg_pnl": avg_pnl,
                                "total_pnl_pct": total_pnl_pct, "bal": bal,
                            }

        if best_result:
            print(f"\n  BESTER ({test_days}d): {best_result['filter']} | "
                  f"Conf {best_result['conf']:.0%} | SL/TP {best_result['sltp']} | "
                  f"{best_result['trades']} Trades | WR {best_result['wr']:.1f}% | "
                  f"{best_result['total_pnl_pct']:+.1f}%")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nGesamtlaufzeit: {(time.time() - t0) / 60:.1f} Minuten")
