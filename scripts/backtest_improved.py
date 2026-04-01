"""Walk-Forward Backtest mit ALLEN Verbesserungen.

Vergleicht Alt (Baseline) vs Neu:
1. Feature-Selektion: Top-15 per Correlation statt alle
2. Simple Target statt Triple Barrier
3. LightGBM regularisiert (num_leaves=12, reg_alpha/lambda)
4. Regime-Split Ensemble
5. Funding Rate Features (falls Daten vorhanden)
6. 250 Tage Training-Fenster statt 500

Usage:
    python scripts/backtest_improved.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

COIN_PREDICTION_PATH = Path("C:/Codes/coin_prediction")
sys.path.insert(0, str(COIN_PREDICTION_PATH))

from src.evaluation.walk_forward import walk_forward_splits
from src.models.ensemble import RegimeSplitEnsemble
from src.models.targets import create_target


# --- Alt: Baseline (wie bisher) ---

OLD_PARAMS = {
    "objective": "binary", "learning_rate": 0.03, "max_depth": 5,
    "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
    "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
    "n_jobs": 4, "random_state": 42,
}

# --- Neu: Verbesserte Parameter ---

NEW_PARAMS = {
    "objective": "binary", "learning_rate": 0.03, "max_depth": 4,
    "n_estimators": 500, "num_leaves": 12, "subsample": 0.7,
    "colsample_bytree": 0.6, "min_child_samples": 50,
    "reg_alpha": 0.1, "reg_lambda": 1.0, "min_split_gain": 0.01,
    "verbose": -1, "n_jobs": 4, "random_state": 42,
}


def load_coin_data(coin: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_parquet(COIN_PREDICTION_PATH / "data" / "features" / f"{coin}_features.parquet")
    ohlcv = pd.read_parquet(COIN_PREDICTION_PATH / "data" / "raw" / f"{coin}_USDT_1d.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    return features, ohlcv


def load_funding_features(coin: str, target_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Laedt Funding Rate Features falls verfuegbar."""
    funding_path = COIN_PREDICTION_PATH / "data" / "raw" / f"{coin}_funding.parquet"
    if not funding_path.exists():
        return pd.DataFrame(index=target_index)

    from src.ingestion.funding_fetcher import create_funding_features
    funding_df = pd.read_parquet(funding_path)
    return create_funding_features(funding_df, target_index)


def run_old_backtest(coin: str, horizon: int = 7) -> dict:
    """Alte Methode: Triple Barrier, alle Features, 500d, LGBMClassifier."""
    features, ohlcv = load_coin_data(coin)
    target = create_target(ohlcv["close"], horizon, ohlcv["high"], ohlcv["low"])

    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    if len(X) < 200:
        return {"coin": coin, "method": "ALT", "error": "zu wenig Daten"}

    fold_accs = []
    trade_wins, trade_total = 0, 0

    for X_train, y_train, X_test, y_test, info in walk_forward_splits(
        X, y, train_days=500, test_days=30, step_days=30,
        embargo_days=horizon, purge_days=horizon,
    ):
        split = int(len(X_train) * 0.8)
        model = lgb.LGBMClassifier(**OLD_PARAMS)
        kw = {}
        if split < len(X_train):
            kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        model.fit(X_train.iloc[:split], y_train.iloc[:split], **kw)

        preds = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]
        fold_accs.append((preds == y_test.values).mean())

        conf = np.abs(proba - 0.5) + 0.5
        mask = (conf >= 0.65) & (preds == 1)
        if mask.sum() > 0:
            trade_total += int(mask.sum())
            trade_wins += int((y_test.values[mask] == 1).sum())

    if not fold_accs:
        return {"coin": coin, "method": "ALT", "error": "keine Folds"}

    wr = trade_wins / trade_total * 100 if trade_total > 0 else 0
    return {
        "coin": coin, "method": "ALT",
        "accuracy": round(np.mean(fold_accs) * 100, 1),
        "std": round(np.std(fold_accs) * 100, 1),
        "folds": len(fold_accs),
        "trades": trade_total,
        "win_rate": round(wr, 1),
        "wins": trade_wins,
        "losses": trade_total - trade_wins,
    }


def run_new_backtest(coin: str, horizon: int = 7) -> dict:
    """Neue Methode: Simple Target, Top-15 Features, 250d, Regime-Split."""
    features, ohlcv = load_coin_data(coin)

    # Simple Target statt Triple Barrier
    future_return = ohlcv["close"].shift(-horizon) / ohlcv["close"] - 1
    target = (future_return > 0).astype(float)
    target[future_return.isna()] = float("nan")

    # Funding Features hinzufuegen (falls vorhanden)
    funding_feat = load_funding_features(coin, features.index)
    if not funding_feat.empty:
        features = pd.concat([features, funding_feat], axis=1)

    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]

    if len(X) < 200:
        return {"coin": coin, "method": "NEU", "error": "zu wenig Daten"}

    # Feature-Selektion: Top-15 per Correlation
    correlations = X.corrwith(y).abs().sort_values(ascending=False).dropna()
    top_features = correlations.head(15).index.tolist()
    X = X[top_features]

    fold_accs = []
    trade_wins, trade_total = 0, 0

    for X_train, y_train, X_test, y_test, info in walk_forward_splits(
        X, y, train_days=250, test_days=30, step_days=30,
        embargo_days=horizon, purge_days=horizon,
    ):
        # Regime-Split Ensemble
        ensemble = RegimeSplitEnsemble(seed=42)
        ensemble.fit(X_train, y_train)

        proba = ensemble.predict_proba(X_test)[:, 1]
        preds = (proba > 0.5).astype(int)
        fold_accs.append((preds == y_test.values).mean())

        conf = np.abs(proba - 0.5) + 0.5
        mask = (conf >= 0.65) & (preds == 1)
        if mask.sum() > 0:
            trade_total += int(mask.sum())
            trade_wins += int((y_test.values[mask] == 1).sum())

    if not fold_accs:
        return {"coin": coin, "method": "NEU", "error": "keine Folds"}

    wr = trade_wins / trade_total * 100 if trade_total > 0 else 0
    return {
        "coin": coin, "method": "NEU",
        "accuracy": round(np.mean(fold_accs) * 100, 1),
        "std": round(np.std(fold_accs) * 100, 1),
        "folds": len(fold_accs),
        "trades": trade_total,
        "win_rate": round(wr, 1),
        "wins": trade_wins,
        "losses": trade_total - trade_wins,
    }


def main():
    coins = ["MATIC", "DOT", "ETC", "ADA", "XLM", "EOS", "ATOM", "TRX", "DOGE",
             "AVAX", "SOL", "NEAR"]

    # Zuerst Funding Rates holen (einmalig)
    print("Funding Rates herunterladen...")
    try:
        from src.ingestion.funding_fetcher import fetch_all_funding_rates
        fetch_all_funding_rates(coins)
        print("  Funding Rates geladen.\n")
    except Exception as e:
        print(f"  Funding Rates nicht verfuegbar (kein API-Key?): {e}\n")

    # Features neu bauen mit Funding
    print("Features neu bauen (inkl. Funding)...")
    try:
        from src.features.pipeline import build_all_features
        build_all_features(coins)
        print("  Features aktualisiert.\n")
    except Exception as e:
        print(f"  Feature-Build fehlgeschlagen: {e}\n")

    print("=" * 90)
    print("VERGLEICH: ALT vs NEU")
    print("=" * 90)
    print(f"{'Coin':<8} {'ALT Acc':>8} {'NEU Acc':>8} {'Diff':>7} "
          f"{'ALT WR':>7} {'NEU WR':>7} {'ALT Tr':>6} {'NEU Tr':>6}")
    print("-" * 90)

    old_results, new_results = [], []
    for i, coin in enumerate(coins, 1):
        print(f"[{i}/{len(coins)}] {coin}...", end=" ", flush=True)

        old = run_old_backtest(coin)
        new = run_new_backtest(coin)
        old_results.append(old)
        new_results.append(new)

        if "error" in old or "error" in new:
            err = old.get("error", new.get("error", ""))
            print(f"FEHLER: {err}")
            continue

        diff = new["accuracy"] - old["accuracy"]
        marker = "+++" if diff > 3 else "++" if diff > 1 else "+" if diff > 0 else "-" if diff > -1 else "--"
        print(f"ALT={old['accuracy']:.1f}% NEU={new['accuracy']:.1f}% ({diff:+.1f}%) {marker}")

    # Zusammenfassung
    print("\n" + "=" * 90)
    print("ZUSAMMENFASSUNG")
    print("=" * 90)

    valid_old = [r for r in old_results if "error" not in r]
    valid_new = [r for r in new_results if "error" not in r]

    if valid_old and valid_new:
        # Tabelle nochmal sauber
        print(f"\n{'Coin':<8} {'ALT Acc':>8} {'NEU Acc':>8} {'Diff':>7} "
              f"{'ALT WR':>7} {'NEU WR':>7} {'ALT Tr':>6} {'NEU Tr':>6}")
        print("-" * 90)

        for old, new in zip(old_results, new_results):
            if "error" in old or "error" in new:
                coin = old.get("coin", new.get("coin", "?"))
                print(f"{coin:<8} {'FEHLER':>8}")
                continue

            diff = new["accuracy"] - old["accuracy"]
            print(f"{old['coin']:<8} {old['accuracy']:>6.1f}% {new['accuracy']:>6.1f}% {diff:>+5.1f}% "
                  f"{old['win_rate']:>5.1f}% {new['win_rate']:>5.1f}% "
                  f"{old['trades']:>5} {new['trades']:>5}")

        avg_old = np.mean([r["accuracy"] for r in valid_old])
        avg_new = np.mean([r["accuracy"] for r in valid_new])
        total_diff = avg_new - avg_old

        total_old_trades = sum(r["trades"] for r in valid_old)
        total_new_trades = sum(r["trades"] for r in valid_new)
        total_old_wins = sum(r["wins"] for r in valid_old)
        total_new_wins = sum(r["wins"] for r in valid_new)
        old_wr = total_old_wins / total_old_trades * 100 if total_old_trades > 0 else 0
        new_wr = total_new_wins / total_new_trades * 100 if total_new_trades > 0 else 0

        improved = sum(1 for o, n in zip(valid_old, valid_new)
                      if n["accuracy"] > o["accuracy"])

        print(f"\nDurchschnitt ALT: {avg_old:.1f}%")
        print(f"Durchschnitt NEU: {avg_new:.1f}% ({total_diff:+.1f}%)")
        print(f"Trade Win-Rate ALT: {old_wr:.1f}% ({total_old_trades} Trades)")
        print(f"Trade Win-Rate NEU: {new_wr:.1f}% ({total_new_trades} Trades)")
        print(f"Verbessert: {improved}/{len(valid_old)} Coins")


if __name__ == "__main__":
    main()
