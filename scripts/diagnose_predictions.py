"""Tiefendiagnose: Warum sind die Predictions schlecht?

Analysiert systematisch:
1. Target-Balance: Ist das Triple Barrier Label sinnvoll?
2. Feature-Qualitaet: Welche Features sind wirklich praediktiv?
3. Regime-Analyse: Funktioniert das Modell nur in bestimmten Maerkten?
4. Modell-Verhalten: Predicted es immer dasselbe?
5. Einfachere Baselines: Schlaegt ein simples Modell LightGBM?
6. Horizont-Vergleich: 1d vs 3d vs 7d
7. Feature-Reduktion: Weniger Features = weniger Overfitting?
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
from src.models.targets import create_target


def load_coin_data(coin: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_parquet(COIN_PREDICTION_PATH / "data" / "features" / f"{coin}_features.parquet")
    ohlcv = pd.read_parquet(COIN_PREDICTION_PATH / "data" / "raw" / f"{coin}_USDT_1d.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    return features, ohlcv


def prepare_data(coin: str, horizon: int = 7, use_triple_barrier: bool = True):
    """Bereitet Daten mit Target vor."""
    features, ohlcv = load_coin_data(coin)

    if use_triple_barrier:
        target = create_target(ohlcv["close"], horizon, ohlcv["high"], ohlcv["low"])
    else:
        # Einfaches binaeres Target: Preis in N Tagen hoeher?
        future_return = ohlcv["close"].shift(-horizon) / ohlcv["close"] - 1
        target = (future_return > 0).astype(float)
        target[future_return.isna()] = float("nan")
        target.name = f"target_{horizon}d"

    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx]
    y = target.loc[common_idx]
    valid = X.notna().all(axis=1) & y.notna()
    return X[valid], y[valid], ohlcv


# =============================================================================
# DIAGNOSE 1: Target-Analyse
# =============================================================================
def diagnose_target(coins: list[str]):
    """Vergleicht Triple Barrier vs einfaches Target."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 1: TARGET-ANALYSE (Triple Barrier vs Einfach)")
    print("=" * 80)

    print(f"\n{'Coin':<8} {'TB Up%':>7} {'Simple Up%':>10} {'TB N':>6} {'Diff':>6}")
    print("-" * 45)

    for coin in coins:
        try:
            _, y_tb, ohlcv = prepare_data(coin, 7, use_triple_barrier=True)
            _, y_simple, _ = prepare_data(coin, 7, use_triple_barrier=False)

            tb_up = y_tb.mean() * 100
            simple_up = y_simple.mean() * 100

            print(f"{coin:<8} {tb_up:>6.1f}% {simple_up:>9.1f}% {len(y_tb):>6} {tb_up - simple_up:>+5.1f}%")
        except Exception as e:
            print(f"{coin:<8} FEHLER: {e}")

    print("\nFazit: TB Up% << 50% heisst der SL wird zu oft getroffen (SL zu eng oder TP zu weit)")


# =============================================================================
# DIAGNOSE 2: Feature-Qualitaet (univariate Praediktivitaet)
# =============================================================================
def diagnose_features(coins: list[str]):
    """Welche Features korrelieren ueberhaupt mit dem Target?"""
    print("\n" + "=" * 80)
    print("DIAGNOSE 2: FEATURE-PRAEDIKTIVITAET")
    print("=" * 80)

    all_correlations = []

    for coin in coins:
        try:
            X, y, _ = prepare_data(coin, 7)
            for col in X.columns:
                corr = X[col].corr(y)
                if not np.isnan(corr):
                    all_correlations.append({
                        "coin": coin, "feature": col, "correlation": corr
                    })
        except Exception:
            pass

    if not all_correlations:
        print("Keine Korrelationen berechnet!")
        return

    corr_df = pd.DataFrame(all_correlations)

    # Durchschnittliche Korrelation pro Feature ueber alle Coins
    avg_corr = (
        corr_df.groupby("feature")["correlation"]
        .agg(["mean", "std", "count"])
        .sort_values("mean", key=abs, ascending=False)
    )

    print(f"\nTop 15 praediktive Features (nach abs. Korrelation mit 7d-Target):")
    print(f"{'Feature':<30} {'Mean Corr':>10} {'Std':>8} {'Coins':>6}")
    print("-" * 60)
    for feat, row in avg_corr.head(15).iterrows():
        print(f"{feat:<30} {row['mean']:>+9.4f} {row['std']:>7.4f} {int(row['count']):>5}")

    print(f"\nSchwächste Features:")
    weakest = avg_corr[avg_corr["mean"].abs() < 0.01]
    print(f"  {len(weakest)} von {len(avg_corr)} Features haben |Korrelation| < 0.01")
    print(f"  → Diese Features sind vermutlich nur Noise")

    return avg_corr


# =============================================================================
# DIAGNOSE 3: Regime-Analyse
# =============================================================================
def diagnose_regimes(coins: list[str]):
    """Wie performt das Modell in Bull vs Bear Maerkten?"""
    print("\n" + "=" * 80)
    print("DIAGNOSE 3: REGIME-ANALYSE (Bull vs Bear)")
    print("=" * 80)

    # BTC als Regime-Indikator
    _, btc_ohlcv = load_coin_data("BTC")
    btc_sma200 = btc_ohlcv["close"].rolling(200).mean()
    btc_regime = (btc_ohlcv["close"] > btc_sma200).astype(int)  # 1=Bull, 0=Bear

    for coin in ["TRX", "DOGE", "SOL"]:  # Best, mid, worst
        if coin not in coins:
            continue
        try:
            X, y, _ = prepare_data(coin, 7)
            regime = btc_regime.reindex(X.index).dropna()
            common = X.index.intersection(regime.index)

            if len(common) < 100:
                continue

            X_c = X.loc[common]
            y_c = y.loc[common]
            regime_c = regime.loc[common]

            # Walk-Forward mit Regime-Tracking
            bull_correct, bull_total = 0, 0
            bear_correct, bear_total = 0, 0

            for X_train, y_train, X_test, y_test, info in walk_forward_splits(
                X_c, y_c, train_days=500, test_days=30, step_days=30,
                embargo_days=7, purge_days=7,
            ):
                split = int(len(X_train) * 0.8)
                model = lgb.LGBMClassifier(
                    **{"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
                       "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
                       "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
                       "n_jobs": 4, "random_state": 42}
                )
                fit_kw = {}
                if split < len(X_train):
                    fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                    fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
                model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)

                preds = model.predict(X_test)
                test_regime = regime_c.reindex(X_test.index)

                for idx, (pred, true) in enumerate(zip(preds, y_test.values)):
                    r = test_regime.iloc[idx] if idx < len(test_regime) else np.nan
                    if r == 1:
                        bull_total += 1
                        if pred == true:
                            bull_correct += 1
                    elif r == 0:
                        bear_total += 1
                        if pred == true:
                            bear_correct += 1

            bull_acc = bull_correct / bull_total * 100 if bull_total > 0 else 0
            bear_acc = bear_correct / bear_total * 100 if bear_total > 0 else 0
            print(f"\n{coin}:")
            print(f"  Bull-Markt: {bull_acc:.1f}% Accuracy ({bull_total} Samples)")
            print(f"  Bear-Markt: {bear_acc:.1f}% Accuracy ({bear_total} Samples)")

        except Exception as e:
            print(f"{coin}: Fehler - {e}")


# =============================================================================
# DIAGNOSE 4: Modell-Verhalten (predicted es immer dasselbe?)
# =============================================================================
def diagnose_model_behavior(coins: list[str]):
    """Analysiert die Prediction-Verteilung."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 4: MODELL-VERHALTEN")
    print("=" * 80)

    print(f"\n{'Coin':<8} {'PredUp%':>8} {'TrueUp%':>8} {'AvgProba':>9} {'ProbaStd':>9} {'Bias':>8}")
    print("-" * 55)

    for coin in coins:
        try:
            X, y, _ = prepare_data(coin, 7)
            all_preds, all_proba, all_true = [], [], []

            for X_train, y_train, X_test, y_test, info in walk_forward_splits(
                X, y, train_days=500, test_days=30, step_days=30,
                embargo_days=7, purge_days=7,
            ):
                split = int(len(X_train) * 0.8)
                model = lgb.LGBMClassifier(
                    **{"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
                       "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
                       "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
                       "n_jobs": 4, "random_state": 42}
                )
                fit_kw = {}
                if split < len(X_train):
                    fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                    fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
                model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)

                proba = model.predict_proba(X_test)[:, 1]
                preds = (proba > 0.5).astype(int)

                all_preds.extend(preds)
                all_proba.extend(proba)
                all_true.extend(y_test.values)

            pred_up = np.mean(all_preds) * 100
            true_up = np.mean(all_true) * 100
            avg_proba = np.mean(all_proba)
            proba_std = np.std(all_proba)
            bias = pred_up - true_up

            print(f"{coin:<8} {pred_up:>6.1f}% {true_up:>6.1f}% {avg_proba:>8.3f} {proba_std:>8.3f} {bias:>+6.1f}%")

        except Exception as e:
            print(f"{coin:<8} Fehler: {e}")

    print("\nFazit: ProbaStd < 0.05 = Modell differenziert kaum zwischen Situationen")
    print("       Bias gross = Modell systematisch falsch kalibriert")


# =============================================================================
# DIAGNOSE 5: Horizont-Vergleich
# =============================================================================
def diagnose_horizons(coins: list[str]):
    """Vergleicht 1d, 3d, 7d Horizonte."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 5: HORIZONT-VERGLEICH (1d vs 3d vs 7d)")
    print("=" * 80)

    # Teste nur Top-3 Coins fuer Speed
    test_coins = [c for c in ["TRX", "XLM", "DOGE"] if c in coins]

    for horizon in [1, 3, 7]:
        print(f"\n--- Horizont: {horizon} Tage ---")
        print(f"{'Coin':<8} {'Acc%':>6} {'Trades':>6} {'WinRate':>8} {'Folds':>5}")
        print("-" * 40)

        for coin in test_coins:
            try:
                # Einfaches Target (nicht Triple Barrier) fuer fairen Vergleich
                X, y, _ = prepare_data(coin, horizon, use_triple_barrier=False)

                fold_accs = []
                trade_wins, trade_total = 0, 0

                for X_train, y_train, X_test, y_test, info in walk_forward_splits(
                    X, y, train_days=500, test_days=30, step_days=30,
                    embargo_days=horizon, purge_days=horizon,
                ):
                    split = int(len(X_train) * 0.8)
                    model = lgb.LGBMClassifier(
                        **{"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
                           "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
                           "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
                           "n_jobs": 4, "random_state": 42}
                    )
                    fit_kw = {}
                    if split < len(X_train):
                        fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                        fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
                    model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)

                    preds = model.predict(X_test)
                    proba = model.predict_proba(X_test)[:, 1]
                    acc = (preds == y_test.values).mean()
                    fold_accs.append(acc)

                    # High-confidence trades
                    conf = np.abs(proba - 0.5) + 0.5
                    mask = (conf >= 0.65) & (preds == 1)
                    if mask.sum() > 0:
                        trade_total += mask.sum()
                        trade_wins += (y_test.values[mask] == 1).sum()

                avg_acc = np.mean(fold_accs) * 100 if fold_accs else 0
                wr = trade_wins / trade_total * 100 if trade_total > 0 else 0
                print(f"{coin:<8} {avg_acc:>5.1f}% {trade_total:>5} {wr:>6.1f}% {len(fold_accs):>5}")

            except Exception as e:
                print(f"{coin:<8} Fehler: {e}")


# =============================================================================
# DIAGNOSE 6: Feature-Reduktion (Top-N Features only)
# =============================================================================
def diagnose_feature_reduction(coins: list[str]):
    """Testet ob weniger Features besser sind."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 6: FEATURE-REDUKTION")
    print("=" * 80)

    test_coins = [c for c in ["TRX", "XLM", "DOGE", "SOL"] if c in coins]
    feature_counts = [5, 10, 20, "all"]

    for coin in test_coins:
        print(f"\n{coin}:")
        X, y, _ = prepare_data(coin, 7)

        # Bestimme Feature-Ranking via Korrelation mit Target
        correlations = X.corrwith(y).abs().sort_values(ascending=False)
        correlations = correlations[correlations.notna()]

        print(f"  Top-5 Features: {', '.join(correlations.head(5).index.tolist())}")

        for n_feat in feature_counts:
            if n_feat == "all":
                X_sub = X
                label = f"Alle ({X.shape[1]})"
            else:
                top_features = correlations.head(n_feat).index.tolist()
                X_sub = X[top_features]
                label = f"Top-{n_feat}"

            fold_accs = []
            for X_train, y_train, X_test, y_test, info in walk_forward_splits(
                X_sub, y, train_days=500, test_days=30, step_days=30,
                embargo_days=7, purge_days=7,
            ):
                split = int(len(X_train) * 0.8)
                model = lgb.LGBMClassifier(
                    **{"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
                       "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
                       "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
                       "n_jobs": 4, "random_state": 42}
                )
                fit_kw = {}
                if split < len(X_train):
                    fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                    fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
                model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)

                preds = model.predict(X_test)
                fold_accs.append((preds == y_test.values).mean())

            avg = np.mean(fold_accs) * 100 if fold_accs else 0
            std = np.std(fold_accs) * 100 if fold_accs else 0
            print(f"  {label:<12} → Acc: {avg:.1f}% ±{std:.1f}%")


# =============================================================================
# DIAGNOSE 7: Baseline-Vergleich
# =============================================================================
def diagnose_baselines(coins: list[str]):
    """Vergleicht LightGBM mit simplen Baselines."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 7: BASELINE-VERGLEICH")
    print("=" * 80)

    test_coins = [c for c in ["TRX", "XLM", "DOGE", "SOL"] if c in coins]

    print(f"\n{'Coin':<8} {'AlwaysUp':>9} {'Momentum':>9} {'MeanRev':>8} {'LGBM':>6}")
    print("-" * 50)

    for coin in test_coins:
        X, y, ohlcv = prepare_data(coin, 7)

        # Momentum-Baseline: wenn 7d-Return > 0 → Up
        mom_col = "ret_momentum_7d" if "ret_momentum_7d" in X.columns else None
        # Mean-Reversion: wenn 7d-Return > 0 → Down (Gegentrend)
        # Always-Up: immer Up predicted

        always_up_accs, mom_accs, mr_accs, lgbm_accs = [], [], [], []

        for X_train, y_train, X_test, y_test, info in walk_forward_splits(
            X, y, train_days=500, test_days=30, step_days=30,
            embargo_days=7, purge_days=7,
        ):
            # Always Up
            always_up = np.ones(len(y_test))
            always_up_accs.append((always_up == y_test.values).mean())

            # Momentum
            if mom_col:
                mom_pred = (X_test[mom_col] > 0).astype(int).values
                mom_accs.append((mom_pred == y_test.values).mean())

            # Mean Reversion
            if mom_col:
                mr_pred = (X_test[mom_col] < 0).astype(int).values
                mr_accs.append((mr_pred == y_test.values).mean())

            # LightGBM
            split = int(len(X_train) * 0.8)
            model = lgb.LGBMClassifier(
                **{"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
                   "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
                   "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
                   "n_jobs": 4, "random_state": 42}
            )
            fit_kw = {}
            if split < len(X_train):
                fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
            model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)
            preds = model.predict(X_test)
            lgbm_accs.append((preds == y_test.values).mean())

        au = np.mean(always_up_accs) * 100
        mo = np.mean(mom_accs) * 100 if mom_accs else 0
        mr = np.mean(mr_accs) * 100 if mr_accs else 0
        lg = np.mean(lgbm_accs) * 100

        print(f"{coin:<8} {au:>7.1f}% {mo:>7.1f}% {mr:>6.1f}% {lg:>5.1f}%")

    print("\nFazit: LGBM muss jede Baseline deutlich schlagen, sonst lohnt sich ML nicht")


# =============================================================================
# DIAGNOSE 8: Alternatives Target (simple return threshold)
# =============================================================================
def diagnose_alternative_targets(coins: list[str]):
    """Testet alternative Target-Definitionen."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 8: ALTERNATIVE TARGETS")
    print("=" * 80)

    test_coins = [c for c in ["TRX", "XLM", "DOGE"] if c in coins]

    for coin in test_coins:
        features, ohlcv = load_coin_data(coin)
        print(f"\n{coin}:")

        targets_to_test = {
            "Simple (>0%)": lambda: _simple_target(ohlcv, 7, 0.0),
            "Simple (>2%)": lambda: _simple_target(ohlcv, 7, 0.02),
            "Simple (>5%)": lambda: _simple_target(ohlcv, 7, 0.05),
            "Triple Barrier": lambda: create_target(ohlcv["close"], 7, ohlcv["high"], ohlcv["low"]),
            "TB tight (1.5/2)": lambda: create_target(ohlcv["close"], 7, ohlcv["high"], ohlcv["low"],
                                                       atr_sl_mult=1.5, atr_tp_mult=2.0),
            "TB wide (3/4)": lambda: create_target(ohlcv["close"], 7, ohlcv["high"], ohlcv["low"],
                                                    atr_sl_mult=3.0, atr_tp_mult=4.0),
        }

        print(f"  {'Target':<20} {'Acc%':>6} {'Up%':>5} {'Folds':>5}")
        print(f"  {'-' * 40}")

        for name, target_fn in targets_to_test.items():
            try:
                target = target_fn()
                common_idx = features.index.intersection(target.dropna().index)
                X = features.loc[common_idx]
                y = target.loc[common_idx]
                valid = X.notna().all(axis=1) & y.notna()
                X, y = X[valid], y[valid]

                fold_accs = []
                for X_train, y_train, X_test, y_test, info in walk_forward_splits(
                    X, y, train_days=500, test_days=30, step_days=30,
                    embargo_days=7, purge_days=7,
                ):
                    split = int(len(X_train) * 0.8)
                    model = lgb.LGBMClassifier(
                        **{"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
                           "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
                           "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
                           "n_jobs": 4, "random_state": 42}
                    )
                    fit_kw = {}
                    if split < len(X_train):
                        fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                        fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
                    model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)
                    preds = model.predict(X_test)
                    fold_accs.append((preds == y_test.values).mean())

                avg = np.mean(fold_accs) * 100
                up_pct = y.mean() * 100
                print(f"  {name:<20} {avg:>5.1f}% {up_pct:>4.1f}% {len(fold_accs):>5}")
            except Exception as e:
                print(f"  {name:<20} Fehler: {e}")


def _simple_target(ohlcv: pd.DataFrame, horizon: int, threshold: float) -> pd.Series:
    """Einfaches Target: Return > threshold."""
    future_return = ohlcv["close"].shift(-horizon) / ohlcv["close"] - 1
    target = (future_return > threshold).astype(float)
    target[future_return.isna()] = float("nan")
    return target


# =============================================================================
# DIAGNOSE 9: Tuning-Sensitivitaet
# =============================================================================
def diagnose_hyperparams(coins: list[str]):
    """Testet verschiedene LightGBM-Konfigurationen."""
    print("\n" + "=" * 80)
    print("DIAGNOSE 9: HYPERPARAMETER-SENSITIVITAET")
    print("=" * 80)

    test_coins = [c for c in ["TRX", "DOGE"] if c in coins]

    configs = {
        "Default": {"max_depth": 5, "n_estimators": 500, "learning_rate": 0.03,
                     "num_leaves": 31, "min_child_samples": 30},
        "Shallow": {"max_depth": 3, "n_estimators": 300, "learning_rate": 0.05,
                     "num_leaves": 8, "min_child_samples": 50},
        "Deep": {"max_depth": 8, "n_estimators": 1000, "learning_rate": 0.01,
                  "num_leaves": 63, "min_child_samples": 20},
        "Regularized": {"max_depth": 4, "n_estimators": 500, "learning_rate": 0.03,
                         "num_leaves": 15, "min_child_samples": 50,
                         "reg_alpha": 1.0, "reg_lambda": 1.0},
        "Conservative": {"max_depth": 3, "n_estimators": 200, "learning_rate": 0.1,
                           "num_leaves": 8, "min_child_samples": 100},
    }

    for coin in test_coins:
        X, y, _ = prepare_data(coin, 7)
        print(f"\n{coin}:")
        print(f"  {'Config':<16} {'Acc%':>6} {'Std%':>6}")
        print(f"  {'-' * 30}")

        for name, params in configs.items():
            fold_accs = []
            full_params = {
                "objective": "binary", "subsample": 0.8, "colsample_bytree": 0.8,
                "verbose": -1, "n_jobs": 4, "random_state": 42, **params,
            }

            for X_train, y_train, X_test, y_test, info in walk_forward_splits(
                X, y, train_days=500, test_days=30, step_days=30,
                embargo_days=7, purge_days=7,
            ):
                split = int(len(X_train) * 0.8)
                model = lgb.LGBMClassifier(**full_params)
                fit_kw = {}
                if split < len(X_train):
                    fit_kw["eval_set"] = [(X_train.iloc[split:], y_train.iloc[split:])]
                    fit_kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
                model.fit(X_train.iloc[:split], y_train.iloc[:split], **fit_kw)
                preds = model.predict(X_test)
                fold_accs.append((preds == y_test.values).mean())

            avg = np.mean(fold_accs) * 100
            std = np.std(fold_accs) * 100
            print(f"  {name:<16} {avg:>5.1f}% {std:>5.1f}%")


# =============================================================================
# MAIN
# =============================================================================
def main():
    coins = ["MATIC", "DOT", "ETC", "ADA", "XLM", "EOS", "ATOM", "TRX", "DOGE",
             "AVAX", "SOL", "NEAR"]

    # Schnelle Diagnosen zuerst
    diagnose_target(coins)
    feature_ranking = diagnose_features(coins)
    diagnose_model_behavior(coins)
    diagnose_baselines(coins)

    # Tiefere Analysen
    diagnose_regimes(coins)
    diagnose_horizons(coins)
    diagnose_feature_reduction(coins)
    diagnose_alternative_targets(coins)
    diagnose_hyperparams(coins)

    print("\n" + "=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    print("""
Checkliste fuer Verbesserungen:
1. Target: Ist Triple Barrier besser als Simple? SL/TP-Ratio optimal?
2. Features: Gibt es Features die konsistent praediktiv sind?
3. Regime: Funktioniert das Modell nur in Bull/Bear?
4. Horizont: Ist 7d der beste Horizont?
5. Feature-Count: Weniger Features = weniger Overfitting?
6. Baselines: Schlaegt LGBM einfache Heuristiken?
7. Hyperparams: Ist das Modell zu komplex/einfach?
""")


if __name__ == "__main__":
    main()
