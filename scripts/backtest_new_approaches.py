"""Backtest: Neue Ansaetze fuer BTC 1h Trading.

Testet schrittweise:
1. Baseline (aktuelles Modell, SL 2x/TP 4x)
2. HMM Regime-Filter (nur in guenstigen Regimes traden)
3. Multi-Timeframe Features (4h-Trend als Filter/Feature)
4. Kombination: HMM + Multi-Timeframe
5. OI-Delta + Fear & Greed als Features
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


# =============================================================================
# Feature Engineering
# =============================================================================

def build_1h_features(ohlcv, coin="BTC"):
    """Standard 1h-Features (Baseline)."""
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


def build_4h_features(ohlcv_1h):
    """4h-Timeframe Features aus 1h-Daten (Resampling)."""
    ohlcv_4h = ohlcv_1h.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    close_4h = ohlcv_4h["close"].astype(float)

    features_4h = pd.DataFrame(index=ohlcv_4h.index)

    # 4h Trend-Features
    ema8 = close_4h.ewm(span=8, adjust=False).mean()
    ema21 = close_4h.ewm(span=21, adjust=False).mean()
    features_4h["trend_4h_ema8_21"] = (ema8 - ema21) / close_4h  # Normalisiert
    features_4h["trend_4h_direction"] = (ema8 > ema21).astype(float)  # 1=bullish

    # 4h Returns
    for p in [1, 3, 6, 12]:  # 4h, 12h, 24h, 48h
        features_4h[f"ret_4h_{p}"] = close_4h.pct_change(p)

    # 4h Momentum
    features_4h["mom_4h_6"] = close_4h / close_4h.shift(6) - 1  # 24h Momentum
    features_4h["mom_4h_18"] = close_4h / close_4h.shift(18) - 1  # 72h Momentum

    # 4h RSI
    delta_4h = close_4h.diff()
    gain_4h = delta_4h.where(delta_4h > 0, 0).rolling(14).mean()
    loss_4h = (-delta_4h.where(delta_4h < 0, 0)).rolling(14).mean()
    rs_4h = gain_4h / loss_4h.replace(0, np.nan)
    features_4h["rsi_4h"] = 100 - (100 / (1 + rs_4h))

    # 4h Volatilitaet
    ret_4h = close_4h.pct_change()
    features_4h["vol_4h_6"] = ret_4h.rolling(6).std()  # 24h Vol auf 4h-Basis

    # 4h ADX (Average Directional Index) - Trendstaerke
    high_4h = ohlcv_4h["high"].astype(float)
    low_4h = ohlcv_4h["low"].astype(float)
    plus_dm = high_4h.diff()
    minus_dm = -low_4h.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    atr_4h = pd.concat([
        high_4h - low_4h,
        (high_4h - close_4h.shift(1)).abs(),
        (low_4h - close_4h.shift(1)).abs()
    ], axis=1).max(axis=1).rolling(14).mean()

    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_4h.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_4h.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    features_4h["adx_4h"] = dx.rolling(14).mean()

    # Auf 1h-Index reindexen (forward-fill)
    features_1h = features_4h.reindex(ohlcv_1h.index, method="ffill")

    return features_1h


def build_oi_features(coin="BTC"):
    """Open Interest Features aus Binance-Daten."""
    oi_path = CP / f"data/raw/{coin}_oi.parquet"
    if not oi_path.exists():
        return None

    oi = pd.read_parquet(oi_path)
    if "timestamp" in oi.columns:
        oi = oi.set_index("timestamp").sort_index()

    if "open_interest" not in oi.columns:
        return None

    features = pd.DataFrame(index=oi.index)
    oi_val = oi["open_interest"].astype(float)

    # OI-Delta (Veraenderungsrate)
    features["oi_delta_1h"] = oi_val.pct_change(1)
    features["oi_delta_4h"] = oi_val.pct_change(4)
    features["oi_delta_24h"] = oi_val.pct_change(24)

    # OI-Momentum
    features["oi_ma_12h"] = oi_val.rolling(12).mean()
    features["oi_ma_72h"] = oi_val.rolling(72).mean()
    features["oi_ratio"] = features["oi_ma_12h"] / features["oi_ma_72h"].replace(0, np.nan)

    return features


def build_fear_greed_features():
    """Fear & Greed Index als Feature."""
    fg_path = CP / "data/raw/fear_greed.parquet"
    if not fg_path.exists():
        return None

    fg = pd.read_parquet(fg_path)
    if "timestamp" in fg.columns:
        fg = fg.set_index("timestamp").sort_index()

    if "value" not in fg.columns:
        return None

    features = pd.DataFrame(index=fg.index)
    val = fg["value"].astype(float)
    features["fear_greed"] = val
    features["fear_greed_ma7"] = val.rolling(7).mean()
    features["fear_greed_extreme_fear"] = (val < 25).astype(float)
    features["fear_greed_extreme_greed"] = (val > 75).astype(float)

    return features


# =============================================================================
# HMM Regime Detection
# =============================================================================

def fit_hmm_regimes(close, n_states=3, lookback=720):
    """Fittet ein HMM auf Returns + Volatilitaet und klassifiziert Regimes.

    Returns:
        regime_series: pd.Series mit Regime-Labels (0, 1, 2)
        regime_names: dict mit Regime-Mapping (z.B. {0: "low_vol", 1: "med_vol", 2: "high_vol"})
    """
    returns = close.pct_change().dropna()
    vol_24h = returns.rolling(24).std().dropna()

    # Gemeinsamer Index
    common = returns.index.intersection(vol_24h.index)
    returns = returns.loc[common]
    vol_24h = vol_24h.loc[common]

    # HMM-Input: Returns und Volatilitaet
    X_hmm = np.column_stack([returns.values, vol_24h.values])

    # HMM fitten (auf den gesamten Lookback-Bereich)
    hmm = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=100,
        random_state=42,
        verbose=False,
    )
    hmm.fit(X_hmm[-lookback:])

    # Regime-Zuweisung fuer alle Daten
    states = hmm.predict(X_hmm)
    regime_series = pd.Series(states, index=common, name="regime")

    # Regime-Mapping: sortiere nach mittlerer Volatilitaet
    state_vols = {}
    for s in range(n_states):
        mask = states == s
        if mask.sum() > 0:
            state_vols[s] = vol_24h.values[mask].mean()
        else:
            state_vols[s] = float("inf")

    sorted_states = sorted(state_vols, key=state_vols.get)
    regime_names = {}
    labels = ["low_vol", "med_vol", "high_vol"]
    for rank, state_id in enumerate(sorted_states):
        regime_names[state_id] = labels[min(rank, len(labels) - 1)]

    return regime_series, regime_names, hmm


def rolling_hmm_regimes(close, train_window=720, n_states=3):
    """Rolling HMM: fuer jeden Zeitpunkt das Regime basierend auf historischen Daten.

    Trainiert das HMM alle 24h neu (Effizienz).
    """
    returns = close.pct_change().dropna()
    vol_24h = returns.rolling(24).std().dropna()
    common = returns.index.intersection(vol_24h.index)
    returns = returns.loc[common]
    vol_24h = vol_24h.loc[common]

    regime_series = pd.Series(np.nan, index=common, name="regime")
    regime_vol = pd.Series(np.nan, index=common, name="regime_vol")

    last_hmm = None
    last_mapping = None

    for i in range(train_window, len(common)):
        # Nur alle 24h neu trainieren
        if i % 24 == 0 or last_hmm is None:
            X_train = np.column_stack([
                returns.values[max(0, i - train_window):i],
                vol_24h.values[max(0, i - train_window):i],
            ])
            try:
                hmm = GaussianHMM(
                    n_components=n_states,
                    covariance_type="full",
                    n_iter=50,
                    random_state=42,
                    verbose=False,
                )
                hmm.fit(X_train)
                last_hmm = hmm

                # Regime-Mapping nach mittlerer Volatilitaet
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
                mapped_state = last_mapping.get(raw_state, 1)
                regime_series.iloc[i] = mapped_state
                regime_vol.iloc[i] = vol_24h.values[i]
            except Exception:
                regime_series.iloc[i] = 1  # Default: medium

    return regime_series, regime_vol


# =============================================================================
# Simulation
# =============================================================================

def simulate_trades(close, predictions, horizon_h, min_conf,
                    sl_mult=2.0, tp_mult=4.0, fee_pct=0.2,
                    capital=453.0, max_exposure_pct=0.80):
    """Realistische Trade-Simulation mit Kapital."""
    trades = []
    balance = capital
    open_positions = []

    for p in predictions:
        idx = p["idx"]
        if idx >= len(close):
            continue
        price = float(close.iloc[idx])

        # Offene Positionen pruefen
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

        # Neuer Trade?
        if p["direction"] == "up" and p["confidence"] >= min_conf:
            exposure = sum(pos[1] for pos in open_positions)
            max_exp = capital * max_exposure_pct
            available = min(balance, max_exp - exposure)

            if available > 1:
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

    # Offene Positionen am Ende schliessen
    for pos in open_positions:
        e_price, amount, _, _, close_idx = pos
        exit_p = float(close.iloc[min(close_idx, len(close) - 1)])
        pnl = amount * (exit_p / e_price - 1) - amount * fee_pct / 100
        balance += amount + pnl
        trades.append({"pnl_pct": (exit_p / e_price - 1) * 100 - fee_pct,
                        "pnl_usd": pnl, "reason": "time"})

    return trades, balance


# =============================================================================
# Core Backtest
# =============================================================================

def get_predictions(close, X, y, test_start, test_hours, train_h=720, label=""):
    """Stuendliches Training, gibt alle Predictions zurueck."""
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
    return predictions


def report(label, trades, start_capital, end_balance):
    if not trades:
        print(f"  {label:<45} KEINE TRADES")
        return {"label": label, "trades": 0, "wr": 0, "avg_pnl": 0, "total_pnl_pct": 0}

    df = pd.DataFrame(trades)
    n = len(df)
    wins = (df["pnl_usd"] > 0).sum()
    wr = wins / n * 100
    total_pnl = end_balance - start_capital
    total_pnl_pct = total_pnl / start_capital * 100
    avg_pnl = df["pnl_pct"].mean()

    reasons = df["reason"].value_counts()
    reason_str = ", ".join(f"{r}:{c}" for r, c in reasons.items())

    print(f"  {label}")
    print(f"    Trades: {n}  |  WR: {wr:.1f}%  |  Avg: {avg_pnl:+.3f}%")
    print(f"    Kapital: ${start_capital:.0f} -> ${end_balance:.2f}  ({total_pnl_pct:+.1f}%)")
    print(f"    Reasons: {reason_str}")
    print()

    return {"label": label, "trades": n, "wr": wr, "avg_pnl": avg_pnl,
            "total_pnl_pct": total_pnl_pct, "end_balance": end_balance}


# =============================================================================
# Main
# =============================================================================

def main():
    capital = 453.0
    min_conf = 0.65
    horizon_h = 72
    train_h = 720
    test_days = 90

    print("=" * 80)
    print("BACKTEST NEUE ANSAETZE: HMM + Multi-Timeframe + OI + Fear&Greed")
    print(f"Kapital: ${capital:.0f}  |  Min-Confidence: {min_conf:.0%}")
    print(f"Horizont: {horizon_h}h  |  Train-Window: {train_h}h  |  Test: {test_days} Tage")
    print("=" * 80)

    # Daten laden
    print("\n[0] Daten laden...")
    ohlcv = pd.read_parquet(CP / "data/raw/BTC_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    close = ohlcv["close"].astype(float)

    # Target
    future_return = close.shift(-horizon_h) / close - 1
    target = (future_return > 0).astype(float)
    target[future_return.isna()] = float("nan")

    # =========================================================================
    # Test 1: BASELINE (aktuelle Features, SL 2x / TP 4x)
    # =========================================================================
    print("\n" + "=" * 80)
    print("[1/5] BASELINE: Aktuelle Features, SL 2x / TP 4x")
    print("=" * 80)

    features_base = build_1h_features(ohlcv)
    common_idx = features_base.index.intersection(target.dropna().index)
    X_base = features_base.loc[common_idx]
    y_base = target.loc[common_idx]
    valid = X_base.notna().all(axis=1) & y_base.notna()
    X_base, y_base = X_base[valid], y_base[valid]

    n = len(X_base)
    test_hours = test_days * 24
    test_start = n - test_hours - horizon_h

    print(f"  Daten: {n} Stunden, Test ab Index {test_start}")
    print(f"  Features: {list(X_base.columns)}")
    print(f"\n  Training Baseline...")

    t0 = time.time()
    preds_base = get_predictions(close, X_base, y_base, test_start, test_hours, train_h,
                                  "Baseline")
    print(f"  {len(preds_base)} Predictions in {time.time() - t0:.0f}s")

    # Accuracy
    correct = sum(1 for p in preds_base if (p["direction"] == "up") == (p["actual_up"] == 1))
    print(f"  Accuracy: {correct / len(preds_base) * 100:.1f}%")

    trades_base, bal_base = simulate_trades(close, preds_base, horizon_h, min_conf,
                                             sl_mult=2.0, tp_mult=4.0, capital=capital)
    r_base = report("Baseline (SL 2x / TP 4x)", trades_base, capital, bal_base)

    # =========================================================================
    # Test 2: HMM REGIME-FILTER
    # =========================================================================
    print("\n" + "=" * 80)
    print("[2/5] HMM REGIME-FILTER: Nur in guenstigen Regimes traden")
    print("=" * 80)

    print("  Rolling HMM fitten (alle 24h neu, 3 States)...")
    t0 = time.time()
    regimes, regime_vol = rolling_hmm_regimes(close, train_window=train_h, n_states=3)
    print(f"  HMM fertig in {time.time() - t0:.0f}s")

    # Regime-Statistik im Testzeitraum
    test_timestamps = [p["timestamp"] for p in preds_base]
    test_regimes = regimes.reindex(test_timestamps)
    for regime_id in [0, 1, 2]:
        count = (test_regimes == regime_id).sum()
        label = ["Niedrige Vol", "Mittlere Vol", "Hohe Vol"][regime_id]
        print(f"    Regime {regime_id} ({label}): {count} Stunden ({count / len(test_regimes) * 100:.0f}%)")

    # Test verschiedene Regime-Filter
    for allowed_regimes, rlabel in [
        ([0], "Nur Regime 0 (niedrige Vol)"),
        ([0, 1], "Regime 0+1 (nicht hohe Vol)"),
        ([1], "Nur Regime 1 (mittlere Vol)"),
    ]:
        filtered_preds = []
        for p in preds_base:
            ts = p["timestamp"]
            regime = regimes.get(ts, 1)
            if regime in allowed_regimes:
                filtered_preds.append(p)

        trades, bal = simulate_trades(close, filtered_preds, horizon_h, min_conf,
                                       sl_mult=2.0, tp_mult=4.0, capital=capital)
        report(f"HMM Filter: {rlabel}", trades, capital, bal)

    # =========================================================================
    # Test 3: MULTI-TIMEFRAME FEATURES
    # =========================================================================
    print("\n" + "=" * 80)
    print("[3/5] MULTI-TIMEFRAME: 4h-Features zum Modell hinzufuegen")
    print("=" * 80)

    print("  4h-Features berechnen...")
    features_4h = build_4h_features(ohlcv)

    # Kombiniere 1h + 4h Features
    features_mtf = pd.concat([features_base, features_4h], axis=1)
    common_idx_mtf = features_mtf.index.intersection(target.dropna().index)
    X_mtf = features_mtf.loc[common_idx_mtf]
    y_mtf = target.loc[common_idx_mtf]
    valid_mtf = X_mtf.notna().all(axis=1) & y_mtf.notna()
    X_mtf, y_mtf = X_mtf[valid_mtf], y_mtf[valid_mtf]

    n_mtf = len(X_mtf)
    test_start_mtf = n_mtf - test_hours - horizon_h

    print(f"  Features: {X_mtf.shape[1]} (Base: {X_base.shape[1]} + 4h: {features_4h.shape[1]})")
    print(f"  Neue Features: {[c for c in X_mtf.columns if c not in X_base.columns]}")

    print(f"\n  Training Multi-Timeframe...")
    t0 = time.time()
    preds_mtf = get_predictions(close, X_mtf, y_mtf, test_start_mtf, test_hours, train_h,
                                 "Multi-TF")
    print(f"  {len(preds_mtf)} Predictions in {time.time() - t0:.0f}s")

    correct_mtf = sum(1 for p in preds_mtf if (p["direction"] == "up") == (p["actual_up"] == 1))
    print(f"  Accuracy: {correct_mtf / len(preds_mtf) * 100:.1f}%")

    trades_mtf, bal_mtf = simulate_trades(close, preds_mtf, horizon_h, min_conf,
                                           sl_mult=2.0, tp_mult=4.0, capital=capital)
    r_mtf = report("Multi-Timeframe (1h + 4h)", trades_mtf, capital, bal_mtf)

    # Multi-TF als 4h-Trend-Richtungsfilter (nur traden wenn 4h bullish)
    print("  Multi-TF als Richtungsfilter...")
    trend_4h = features_4h["trend_4h_direction"].reindex(close.index, method="ffill")

    filtered_preds_trend = []
    for p in preds_base:
        ts = p["timestamp"]
        trend = trend_4h.get(ts, 0)
        if trend == 1.0:  # Nur wenn 4h-Trend bullish
            filtered_preds_trend.append(p)

    trades_tf, bal_tf = simulate_trades(close, filtered_preds_trend, horizon_h, min_conf,
                                         sl_mult=2.0, tp_mult=4.0, capital=capital)
    report("4h-Trend-Filter (nur bullish)", trades_tf, capital, bal_tf)

    # =========================================================================
    # Test 4: KOMBINATION HMM + Multi-Timeframe
    # =========================================================================
    print("\n" + "=" * 80)
    print("[4/5] KOMBINATION: HMM + 4h-Trend-Filter")
    print("=" * 80)

    combined_preds = []
    for p in preds_base:
        ts = p["timestamp"]
        regime = regimes.get(ts, 1)
        trend = trend_4h.get(ts, 0)
        # Nur traden wenn: nicht hohe Vol UND 4h bullish
        if regime in [0, 1] and trend == 1.0:
            combined_preds.append(p)

    print(f"  Gefilterte Predictions: {len(combined_preds)} von {len(preds_base)}")
    trades_comb, bal_comb = simulate_trades(close, combined_preds, horizon_h, min_conf,
                                             sl_mult=2.0, tp_mult=4.0, capital=capital)
    r_comb = report("HMM (0+1) + 4h-Trend", trades_comb, capital, bal_comb)

    # Kombination: HMM Regime 0 only + 4h-Trend
    combined_strict = []
    for p in preds_base:
        ts = p["timestamp"]
        regime = regimes.get(ts, 1)
        trend = trend_4h.get(ts, 0)
        if regime == 0 and trend == 1.0:
            combined_strict.append(p)

    print(f"  Gefilterte Predictions (strikt): {len(combined_strict)} von {len(preds_base)}")
    trades_strict, bal_strict = simulate_trades(close, combined_strict, horizon_h, min_conf,
                                                 sl_mult=2.0, tp_mult=4.0, capital=capital)
    report("HMM (0 only) + 4h-Trend", trades_strict, capital, bal_strict)

    # =========================================================================
    # Test 5: MULTI-TIMEFRAME + HMM als FEATURE (nicht nur Filter)
    # =========================================================================
    print("\n" + "=" * 80)
    print("[5/5] HMM-REGIME als FEATURE (statt nur Filter)")
    print("=" * 80)

    # Regime als Feature zum Modell hinzufuegen
    features_hmm = features_base.copy()
    regime_reindexed = regimes.reindex(features_hmm.index, method="ffill")
    features_hmm["regime"] = regime_reindexed
    features_hmm["regime_vol"] = regime_vol.reindex(features_hmm.index, method="ffill")

    # Plus 4h-Features
    features_all = pd.concat([features_hmm, features_4h], axis=1)
    common_idx_all = features_all.index.intersection(target.dropna().index)
    X_all = features_all.loc[common_idx_all]
    y_all = target.loc[common_idx_all]
    valid_all = X_all.notna().all(axis=1) & y_all.notna()
    X_all, y_all = X_all[valid_all], y_all[valid_all]

    n_all = len(X_all)
    test_start_all = n_all - test_hours - horizon_h

    print(f"  Features: {X_all.shape[1]} (Base + HMM-Regime + 4h)")

    print(f"\n  Training Alle Features...")
    t0 = time.time()
    preds_all = get_predictions(close, X_all, y_all, test_start_all, test_hours, train_h,
                                 "Alle Features")
    print(f"  {len(preds_all)} Predictions in {time.time() - t0:.0f}s")

    correct_all = sum(1 for p in preds_all if (p["direction"] == "up") == (p["actual_up"] == 1))
    print(f"  Accuracy: {correct_all / len(preds_all) * 100:.1f}%")

    trades_all, bal_all = simulate_trades(close, preds_all, horizon_h, min_conf,
                                           sl_mult=2.0, tp_mult=4.0, capital=capital)
    r_all = report("Alle Features (Base+HMM+4h)", trades_all, capital, bal_all)

    # =========================================================================
    # ZUSAMMENFASSUNG
    # =========================================================================
    print("\n" + "=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    print(f"  {'Ansatz':<45} {'Trades':>6} {'WR':>6} {'Avg P&L':>8} {'Total':>8} {'Kapital':>10}")
    print(f"  {'-' * 83}")

    all_results = []
    for r in [r_base, r_mtf, r_comb, r_all]:
        if r and r.get("trades", 0) > 0:
            print(f"  {r['label']:<45} {r['trades']:>6} {r['wr']:>5.1f}% "
                  f"{r['avg_pnl']:>+7.3f}% {r['total_pnl_pct']:>+7.1f}% "
                  f"${r.get('end_balance', capital):>8.2f}")
            all_results.append(r)

    print(f"\n  Bester Ansatz: ", end="")
    if all_results:
        best = max(all_results, key=lambda x: x["total_pnl_pct"])
        print(f"{best['label']} ({best['total_pnl_pct']:+.1f}%)")
    else:
        print("Keine Ergebnisse")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nGesamtlaufzeit: {(time.time() - t0) / 60:.1f} Minuten")
