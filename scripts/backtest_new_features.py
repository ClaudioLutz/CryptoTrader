"""Backtest: Vergleich Baseline vs neue Features (Quick-Wins).

Vergleicht:
  A) Baseline:        Feste LightGBM-Params, nur TA-Features
  B) + Optuna:         Optuna-getunte Hyperparameter
  C) + Macro:          Zusaetzliche Macro/Cross-Market Features (DXY, VIX, MSTR, Gold, SPY)
  D) + Optuna+Macro:   Beides kombiniert
  E) + Kelly+DD:       Position-Sizing mit Kelly Criterion + Drawdown Protection

Metriken:
  - Prediction Accuracy, Win-Rate, Avg P&L, Total P&L
  - Kelly: Simulierte Positionsgroessen-Varianz
  - Drawdown-Analyse

Usage:
    python scripts/backtest_new_features.py
    python scripts/backtest_new_features.py --test-days 180
    python scripts/backtest_new_features.py --optuna-trials 10  # schnell
"""

import argparse
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, "C:/Codes/coin_prediction")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "coin_prediction_src"))

import lightgbm as lgb
import numpy as np
import pandas as pd


CP = Path("C:/Codes/coin_prediction")

BASELINE_PARAMS = {
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


# ===========================================================================
# Feature Builder
# ===========================================================================

def build_ta_features(ohlcv, coin="BTC"):
    """Baseline: TA-Features (identisch mit Produktion)."""
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
    loss_s = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss_s.replace(0, np.nan)
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


def build_macro_features(btc_close, data_dir):
    """C6+C11: Macro/Cross-Market Features (DXY, VIX, MSTR, Gold, SPY)."""
    try:
        from src.ingestion.macro_fetcher import build_macro_features as _build
        return _build(btc_close, data_dir, interval="1h")
    except Exception as e:
        print(f"  [WARN] Macro-Features nicht verfuegbar: {e}")
        return pd.DataFrame(index=btc_close.index)


# ===========================================================================
# Training
# ===========================================================================

def train_baseline(X_train, y_train, X_val, y_val):
    """Baseline: feste Hyperparameter."""
    model = lgb.LGBMClassifier(**BASELINE_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )
    return model, BASELINE_PARAMS


def train_optuna(X_train, y_train, X_val, y_val, n_trials=30, timeout=300):
    """B8: Optuna-getunte Hyperparameter."""
    from src.models.optuna_tuner import tune_and_train
    return tune_and_train(X_train, y_train, X_val, y_val, n_trials=n_trials, timeout=timeout)


# ===========================================================================
# Backtest Engine
# ===========================================================================

def run_backtest(
    label,
    features,
    close,
    target,
    train_fn,
    horizon_h=72,
    train_h=720,
    min_conf=0.65,
    test_days=90,
    kelly_enabled=False,
    drawdown_enabled=False,
):
    """Generischer Backtest mit konfigurierbarem Training und Features."""
    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    n = len(X)
    test_hours = test_days * 24
    test_start = n - test_hours - horizon_h

    if test_start < train_h:
        print(f"  [{label}] FEHLER: Nicht genug Daten ({n}h < {train_h + test_hours}h)")
        return None

    predictions = []
    trades = []

    # Kelly/Drawdown Tracking
    capital = 1000.0
    peak_capital = capital
    win_history = []
    pnl_history = []
    kelly_fractions = []

    print(f"\n  [{label}] {test_days}d Backtest, {test_hours} Steps...", end="", flush=True)
    t0 = time.time()

    for step in range(test_hours):
        i = test_start + step

        # Training
        train_end = i
        train_start_idx = max(0, train_end - train_h)
        Xtr = X.iloc[train_start_idx:train_end]
        ytr = y.iloc[train_start_idx:train_end]

        if len(Xtr) < 200:
            continue

        s = int(len(Xtr) * 0.8)
        try:
            model, params = train_fn(Xtr.iloc[:s], ytr.iloc[:s], Xtr.iloc[s:], ytr.iloc[s:])
        except Exception as e:
            continue

        # Prediction
        Xte = X.iloc[i:i + 1]
        proba = model.predict_proba(Xte)[:, 1][0]
        direction = "up" if proba > 0.5 else "down"
        confidence = abs(proba - 0.5) + 0.5
        actual_up = int(y.iloc[i])
        correct = (direction == "up") == (actual_up == 1)

        predictions.append({
            "timestamp": X.index[i],
            "direction": direction,
            "confidence": round(confidence, 4),
            "actual_up": actual_up,
            "correct": correct,
        })

        # Trade-Logik
        if direction == "up" and confidence >= min_conf:
            entry_price = float(close.loc[X.index[i]])
            exit_idx_pos = close.index.get_loc(X.index[i]) + horizon_h

            if exit_idx_pos < len(close):
                exit_price = float(close.iloc[exit_idx_pos])
                pnl_pct = (exit_price / entry_price - 1) * 100
                fee_pct = 0.2
                net_pnl = pnl_pct - fee_pct

                # Kelly Position Sizing
                position_pct = 100.0  # Default: 100%
                kelly_val = None
                dd_scale = 1.0

                if kelly_enabled and len(win_history) >= 20:
                    wins = [p for p in pnl_history if p > 0]
                    losses = [abs(p) for p in pnl_history if p <= 0]
                    if wins and losses:
                        wr = len(wins) / len(win_history)
                        avg_w = np.mean(wins)
                        avg_l = np.mean(losses)
                        if avg_l > 0:
                            kelly_val = wr - (1 - wr) / (avg_w / avg_l)
                            kelly_val = max(0, kelly_val) * 0.25  # Quarter-Kelly
                            kelly_val = min(kelly_val, 0.25)  # Cap 25%
                            position_pct = kelly_val * 100
                            kelly_fractions.append(kelly_val)

                if drawdown_enabled:
                    dd_pct = (peak_capital - capital) / peak_capital if peak_capital > 0 else 0
                    if dd_pct > 0.05:
                        dd_excess = dd_pct - 0.05
                        dd_scale = max(0.25, 1.0 - dd_excess / 0.10 * 0.75)
                        position_pct *= dd_scale

                # P&L berechnen (skaliert nach Position)
                scaled_pnl = net_pnl * (position_pct / 100.0)

                # Kapital aktualisieren
                capital *= (1 + scaled_pnl / 100.0)
                if capital > peak_capital:
                    peak_capital = capital

                win_history.append(1 if net_pnl > 0 else 0)
                pnl_history.append(net_pnl)

                trades.append({
                    "timestamp": X.index[i],
                    "net_pnl": round(net_pnl, 3),
                    "scaled_pnl": round(scaled_pnl, 3),
                    "confidence": round(confidence, 4),
                    "position_pct": round(position_pct, 1),
                    "dd_scale": round(dd_scale, 3),
                    "kelly": round(kelly_val, 4) if kelly_val else None,
                })

    elapsed = time.time() - t0
    print(f" {elapsed:.0f}s")

    # Auswertung
    df_pred = pd.DataFrame(predictions)
    df_trades = pd.DataFrame(trades)

    result = {
        "label": label,
        "predictions": len(df_pred),
        "accuracy": df_pred["correct"].mean() * 100 if len(df_pred) > 0 else 0,
        "trades": len(df_trades),
        "win_rate": (df_trades["net_pnl"] > 0).mean() * 100 if len(df_trades) > 0 else 0,
        "avg_pnl": df_trades["net_pnl"].mean() if len(df_trades) > 0 else 0,
        "total_pnl": df_trades["net_pnl"].sum() if len(df_trades) > 0 else 0,
        "median_pnl": df_trades["net_pnl"].median() if len(df_trades) > 0 else 0,
        "final_capital": round(capital, 2),
        "max_drawdown": round((1 - capital / peak_capital) * 100, 2) if capital < peak_capital else 0,
        "elapsed_s": round(elapsed),
    }

    if kelly_enabled and kelly_fractions:
        result["avg_kelly"] = round(np.mean(kelly_fractions), 4)
        result["avg_position_pct"] = round(df_trades["position_pct"].mean(), 1)

    if len(df_trades) > 0:
        result["best_trade"] = df_trades["net_pnl"].max()
        result["worst_trade"] = df_trades["net_pnl"].min()
        result["sharpe"] = round(
            df_trades["net_pnl"].mean() / df_trades["net_pnl"].std() * np.sqrt(365 * 24 / 72), 2
        ) if df_trades["net_pnl"].std() > 0 else 0

    return result


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Backtest neue Features")
    parser.add_argument("--test-days", type=int, default=90, help="Testzeitraum in Tagen")
    parser.add_argument("--optuna-trials", type=int, default=30, help="Optuna Trials pro Training")
    parser.add_argument("--optuna-timeout", type=int, default=120, help="Optuna Timeout in Sekunden")
    parser.add_argument("--train-h", type=int, default=720, help="Trainingsfenster in Stunden")
    parser.add_argument("--horizon-h", type=int, default=72, help="Prediction-Horizont in Stunden")
    parser.add_argument("--min-conf", type=float, default=0.65, help="Min. Confidence fuer Trades")
    args = parser.parse_args()

    print("=" * 70)
    print("BACKTEST: Baseline vs Quick-Win Features")
    print("=" * 70)
    print(f"Test-Zeitraum:    {args.test_days} Tage")
    print(f"Train-Window:     {args.train_h}h")
    print(f"Horizont:         {args.horizon_h}h")
    print(f"Min-Confidence:   {args.min_conf:.0%}")
    print(f"Optuna-Trials:    {args.optuna_trials}")
    print()

    # 1. Daten laden
    print("Lade BTC 1h Daten...")
    ohlcv = pd.read_parquet(CP / "data/raw/BTC_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    close = ohlcv["close"].astype(float)

    # Target
    future_return = close.shift(-args.horizon_h) / close - 1
    target = (future_return > 0).astype(float)
    target[future_return.isna()] = float("nan")

    # 2. Features bauen
    print("Baue TA-Features...")
    ta_features = build_ta_features(ohlcv, "BTC")
    n_ta = ta_features.shape[1]
    print(f"  TA-Features: {n_ta}")

    print("Baue Macro-Features...")
    # Zuerst Macro-Daten herunterladen falls nicht vorhanden
    macro_dir = CP / "data" / "raw" / "macro"
    if not macro_dir.exists() or len(list(macro_dir.glob("*.parquet"))) == 0:
        print("  Lade Macro-Daten von yfinance...")
        try:
            from src.ingestion.macro_fetcher import fetch_macro_data
            fetch_macro_data(CP / "data", period="730d", interval="1h")
        except Exception as e:
            print(f"  [WARN] Macro-Daten Download fehlgeschlagen: {e}")

    macro_feats = build_macro_features(close, CP / "data")
    if not macro_feats.empty:
        valid_cols = macro_feats.columns[macro_feats.notna().any()]
        macro_feats = macro_feats[valid_cols]
    n_macro = macro_feats.shape[1] if not macro_feats.empty else 0
    print(f"  Macro-Features: {n_macro}")

    # Macro-Features Index an TA-Features anpassen
    if not macro_feats.empty:
        macro_feats.index = ta_features.index[:len(macro_feats)] if len(macro_feats) == len(ta_features) else macro_feats.index
        # Reindex auf gemeinsamen Index
        macro_feats = macro_feats.reindex(ta_features.index)

    # Kombinierte Features
    if not macro_feats.empty:
        combined_features = pd.concat([ta_features, macro_feats], axis=1)
    else:
        combined_features = ta_features.copy()
    print(f"  Kombiniert: {combined_features.shape[1]}")

    # 3. Backtests ausfuehren
    results = []
    common_args = {
        "close": close,
        "target": target,
        "horizon_h": args.horizon_h,
        "train_h": args.train_h,
        "min_conf": args.min_conf,
        "test_days": args.test_days,
    }

    # A) Baseline
    r = run_backtest(
        "A) Baseline", ta_features,
        train_fn=train_baseline,
        **common_args,
    )
    if r:
        results.append(r)

    # B) + Optuna (nur wenn genuegend Trials)
    if args.optuna_trials > 0:
        r = run_backtest(
            "B) + Optuna", ta_features,
            train_fn=lambda Xtr, ytr, Xv, yv: train_optuna(
                Xtr, ytr, Xv, yv,
                n_trials=args.optuna_trials,
                timeout=args.optuna_timeout,
            ),
            **common_args,
        )
        if r:
            results.append(r)

    # C) + Macro Features (Baseline-Params)
    if n_macro > 0:
        r = run_backtest(
            "C) + Macro", combined_features,
            train_fn=train_baseline,
            **common_args,
        )
        if r:
            results.append(r)

        # D) + Optuna + Macro
        if args.optuna_trials > 0:
            r = run_backtest(
                "D) Optuna+Macro", combined_features,
                train_fn=lambda Xtr, ytr, Xv, yv: train_optuna(
                    Xtr, ytr, Xv, yv,
                    n_trials=args.optuna_trials,
                    timeout=args.optuna_timeout,
                ),
                **common_args,
            )
            if r:
                results.append(r)

    # E) + Kelly + Drawdown (Baseline-Params + TA-Features, Position-Sizing simuliert)
    r = run_backtest(
        "E) Kelly+DD", ta_features,
        train_fn=train_baseline,
        kelly_enabled=True,
        drawdown_enabled=True,
        **common_args,
    )
    if r:
        results.append(r)

    # === ERGEBNISVERGLEICH ===
    print(f"\n{'=' * 90}")
    print(f"ERGEBNISVERGLEICH ({args.test_days} Tage)")
    print(f"{'=' * 90}")
    print(f"{'Variante':<22} {'Acc':>5} {'Trades':>7} {'WR':>6} {'Avg P&L':>8} {'Total':>8} "
          f"{'Kapital':>9} {'Sharpe':>7} {'MaxDD':>6}")
    print(f"{'-' * 90}")

    for r in results:
        print(
            f"{r['label']:<22} "
            f"{r['accuracy']:>4.1f}% "
            f"{r['trades']:>7} "
            f"{r['win_rate']:>5.1f}% "
            f"{r.get('avg_pnl', 0):>+7.3f}% "
            f"{r.get('total_pnl', 0):>+7.1f}% "
            f"{r.get('final_capital', 1000):>8.0f}$ "
            f"{r.get('sharpe', 0):>6.2f} "
            f"{r.get('max_drawdown', 0):>5.1f}%"
        )

    # Kelly-Details
    kelly_results = [r for r in results if "avg_kelly" in r]
    if kelly_results:
        print(f"\n{'=' * 50}")
        print(f"KELLY CRITERION DETAILS")
        print(f"{'=' * 50}")
        for r in kelly_results:
            print(f"  Avg Kelly Fraction:  {r['avg_kelly']:.2%}")
            print(f"  Avg Position Size:   {r['avg_position_pct']:.1f}%")
            print(f"  Final Capital:       {r['final_capital']}$ (Start: 1'000$)")

    # Zusammenfassung
    if len(results) >= 2:
        baseline = results[0]
        best = max(results, key=lambda r: r.get("total_pnl", 0))
        print(f"\n{'=' * 50}")
        print(f"ZUSAMMENFASSUNG")
        print(f"{'=' * 50}")
        print(f"  Baseline Total P&L:  {baseline.get('total_pnl', 0):+.1f}%")
        print(f"  Bestes Setup:        {best['label']}")
        print(f"  Bestes Total P&L:    {best.get('total_pnl', 0):+.1f}%")
        delta = best.get("total_pnl", 0) - baseline.get("total_pnl", 0)
        print(f"  Verbesserung:        {delta:+.1f}%")


if __name__ == "__main__":
    t_start = time.time()
    main()
    total = time.time() - t_start
    print(f"\nGesamtlaufzeit: {total / 60:.1f} Minuten")
