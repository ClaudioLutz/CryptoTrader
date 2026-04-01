"""Test: Regression statt Classification fuer Crypto-Prediction.

Statt binaer Up/Down vorherzusagen, wird der Return-Wert predicted.
Trading-Signal: Nur handeln wenn predicted Return > Schwelle.

Vorteile:
- Kein harter Cutoff bei 0% (kleine Returns sind Rauschen)
- Modell lernt die Staerke der Bewegung, nicht nur Richtung
- Position Sizing natuerlich eingebaut (groesserer predicted Return = groessere Position)

Ansaetze:
1. LightGBM Regressor auf 7d-Return
2. Directional Signal: Nur handeln wenn |predicted_return| > threshold
3. Vergleich mit Classification-Baseline
"""

import sys, warnings
sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from src.evaluation.walk_forward import walk_forward_splits
from src.models.targets import create_target

CP = Path("C:/Codes/coin_prediction")


def load(coin):
    f = pd.read_parquet(CP / "data/features" / f"{coin}_features.parquet")
    o = pd.read_parquet(CP / "data/raw" / f"{coin}_USDT_1d.parquet")
    if "timestamp" in o.columns:
        o = o.set_index("timestamp").sort_index()
    return f, o


# Regression Parameters (angepasst fuer Finanzdaten)
REG_PARAMS = {
    "objective": "regression",
    "metric": "mae",
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

# Huber Loss (robust gegen Ausreisser)
HUBER_PARAMS = {
    "objective": "huber",
    "metric": "mae",
    "alpha": 0.9,  # Huber delta
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

CLF_PARAMS = {
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


def test_classification_baseline(X, y_binary, train_days=500, horizon=7):
    """Baseline: Binaere Classification."""
    accs, tw, tt = [], 0, 0
    for Xtr, ytr, Xte, yte, _ in walk_forward_splits(
        X, y_binary, train_days=train_days, test_days=30, step_days=30,
        embargo_days=horizon, purge_days=horizon,
    ):
        s = int(len(Xtr) * 0.8)
        m = lgb.LGBMClassifier(**CLF_PARAMS)
        kw = {}
        if s < len(Xtr):
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)
        proba = m.predict_proba(Xte)[:, 1]
        preds = (proba > 0.5).astype(int)
        accs.append((preds == yte.values).mean())

        conf = np.abs(proba - 0.5) + 0.5
        mask = (conf >= 0.65) & (preds == 1)
        if mask.sum() > 0:
            tt += int(mask.sum())
            tw += int((yte.values[mask] == 1).sum())

    wr = tw / tt * 100 if tt > 0 else 0
    return round(np.mean(accs) * 100, 1), tt, round(wr, 1)


def test_regression(X, y_return, y_binary, params, threshold=0.0, train_days=500, horizon=7):
    """Regression: Predicted Return -> Trading Signal."""
    dir_accs, tw, tt = [], 0, 0
    pred_returns_all, true_returns_all = [], []

    for Xtr, ytr, Xte, yte, _ in walk_forward_splits(
        X, y_return, train_days=train_days, test_days=30, step_days=30,
        embargo_days=horizon, purge_days=horizon,
    ):
        s = int(len(Xtr) * 0.8)
        m = lgb.LGBMRegressor(**params)
        kw = {}
        if s < len(Xtr):
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)

        pred_return = m.predict(Xte)
        true_return = yte.values

        pred_returns_all.extend(pred_return)
        true_returns_all.extend(true_return)

        # Directional Accuracy: predicted Richtung == wahre Richtung
        pred_dir = (pred_return > 0).astype(int)
        true_dir = (true_return > 0).astype(int)
        dir_accs.append((pred_dir == true_dir).mean())

        # Trades: nur wenn predicted return > threshold
        trade_mask = pred_return > threshold
        if trade_mask.sum() > 0:
            tt += int(trade_mask.sum())
            tw += int((true_return[trade_mask] > 0).sum())

    # Korrelation zwischen predicted und true return
    corr = np.corrcoef(pred_returns_all, true_returns_all)[0, 1]
    wr = tw / tt * 100 if tt > 0 else 0

    return round(np.mean(dir_accs) * 100, 1), tt, round(wr, 1), round(corr, 4)


def test_regression_with_feature_selection(X, y_return, y_binary, params, threshold=0.0, train_days=500, horizon=7):
    """Regression mit per-fold Feature-Selektion."""
    dir_accs, tw, tt = [], 0, 0
    pred_returns_all, true_returns_all = [], []

    for Xtr, ytr, Xte, yte, _ in walk_forward_splits(
        X, y_return, train_days=train_days, test_days=30, step_days=30,
        embargo_days=horizon, purge_days=horizon,
    ):
        # Top-15 Features per fold
        corrs = Xtr.corrwith(ytr).abs().sort_values(ascending=False).dropna()
        top = corrs.head(15).index.tolist()
        Xtr_s, Xte_s = Xtr[top], Xte[top]

        s = int(len(Xtr_s) * 0.8)
        m = lgb.LGBMRegressor(**params)
        kw = {}
        if s < len(Xtr_s):
            kw["eval_set"] = [(Xtr_s.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr_s.iloc[:s], ytr.iloc[:s], **kw)

        pred_return = m.predict(Xte_s)
        true_return = yte.values

        pred_returns_all.extend(pred_return)
        true_returns_all.extend(true_return)

        pred_dir = (pred_return > 0).astype(int)
        true_dir = (true_return > 0).astype(int)
        dir_accs.append((pred_dir == true_dir).mean())

        trade_mask = pred_return > threshold
        if trade_mask.sum() > 0:
            tt += int(trade_mask.sum())
            tw += int((true_return[trade_mask] > 0).sum())

    corr = np.corrcoef(pred_returns_all, true_returns_all)[0, 1] if len(pred_returns_all) > 2 else 0
    wr = tw / tt * 100 if tt > 0 else 0
    return round(np.mean(dir_accs) * 100, 1), tt, round(wr, 1), round(corr, 4)


def main():
    coins = ["TRX", "XLM", "DOGE", "SOL", "EOS", "ADA", "AVAX", "NEAR", "ETC", "ATOM", "MATIC"]

    print("=" * 95)
    print("REGRESSION vs CLASSIFICATION — Walk-Forward Backtest")
    print("=" * 95)

    print(f"\n{'Coin':<7} {'CLF Acc':>8} {'REG Acc':>8} {'HUB Acc':>8} {'REG+FS':>7} "
          f"{'Corr':>6} {'CLF WR':>7} {'REG WR':>7} {'HUB WR':>7}")
    print("-" * 95)

    all_results = []

    for coin in coins:
        print(f"{coin}...", end=" ", flush=True)
        features, ohlcv = load(coin)

        # Return target (fuer Regression)
        future_return = ohlcv["close"].shift(-7) / ohlcv["close"] - 1
        y_return = future_return.copy()
        y_return.name = "return_7d"

        # Binary target (fuer Classification Baseline)
        y_binary = (future_return > 0).astype(float)
        y_binary[future_return.isna()] = float("nan")

        # Align
        common_idx = features.index.intersection(y_return.dropna().index)
        X = features.loc[common_idx]
        y_ret = y_return.loc[common_idx]
        y_bin = y_binary.loc[common_idx]
        valid = X.notna().all(axis=1) & y_ret.notna()
        X, y_ret, y_bin = X[valid], y_ret[valid], y_bin[valid]

        if len(X) < 200:
            print("zu wenig Daten")
            continue

        # Classification Baseline
        clf_acc, clf_trades, clf_wr = test_classification_baseline(X, y_bin)

        # Regression (MAE)
        reg_acc, reg_trades, reg_wr, reg_corr = test_regression(
            X, y_ret, y_bin, REG_PARAMS, threshold=0.02)

        # Huber Regression (robust gegen Ausreisser)
        hub_acc, hub_trades, hub_wr, hub_corr = test_regression(
            X, y_ret, y_bin, HUBER_PARAMS, threshold=0.02)

        # Regression + Feature Selection
        regfs_acc, regfs_trades, regfs_wr, regfs_corr = test_regression_with_feature_selection(
            X, y_ret, y_bin, HUBER_PARAMS, threshold=0.02)

        print(f"\r{coin:<7} {clf_acc:>6.1f}% {reg_acc:>6.1f}% {hub_acc:>6.1f}% {regfs_acc:>5.1f}% "
              f"{hub_corr:>+5.3f} {clf_wr:>5.1f}% {reg_wr:>5.1f}% {hub_wr:>5.1f}%")

        all_results.append({
            "coin": coin,
            "clf_acc": clf_acc, "reg_acc": reg_acc, "hub_acc": hub_acc, "regfs_acc": regfs_acc,
            "clf_wr": clf_wr, "reg_wr": reg_wr, "hub_wr": hub_wr,
            "clf_trades": clf_trades, "reg_trades": reg_trades, "hub_trades": hub_trades,
            "corr": hub_corr,
        })

    # Summary
    if all_results:
        print("-" * 95)
        avg_clf = np.mean([r["clf_acc"] for r in all_results])
        avg_reg = np.mean([r["reg_acc"] for r in all_results])
        avg_hub = np.mean([r["hub_acc"] for r in all_results])
        avg_regfs = np.mean([r["regfs_acc"] for r in all_results])
        avg_corr = np.mean([r["corr"] for r in all_results])

        t_clf = sum(r["clf_trades"] for r in all_results)
        t_reg = sum(r["reg_trades"] for r in all_results)
        t_hub = sum(r["hub_trades"] for r in all_results)
        w_clf = sum(r["clf_wr"] * r["clf_trades"] for r in all_results) / t_clf if t_clf > 0 else 0
        w_reg = sum(r["reg_wr"] * r["reg_trades"] for r in all_results) / t_reg if t_reg > 0 else 0
        w_hub = sum(r["hub_wr"] * r["hub_trades"] for r in all_results) / t_hub if t_hub > 0 else 0

        print(f"\n{'DURCHSCHNITT':<7} {avg_clf:>6.1f}% {avg_reg:>6.1f}% {avg_hub:>6.1f}% {avg_regfs:>5.1f}% "
              f"{avg_corr:>+5.3f} {w_clf:>5.1f}% {w_reg:>5.1f}% {w_hub:>5.1f}%")

        # Threshold-Analyse fuer bestes Modell
        print("\n" + "=" * 95)
        print("THRESHOLD-ANALYSE: Huber Regression (nur Trades wenn predicted return > X%)")
        print("=" * 95)
        print(f"{'Coin':<7}", end="")
        for thr in [0.0, 0.01, 0.02, 0.03, 0.05]:
            print(f" {'>' + str(int(thr*100)) + '%':>8}", end="")
        print()
        print("-" * 55)

        for coin in coins:
            features, ohlcv = load(coin)
            future_return = ohlcv["close"].shift(-7) / ohlcv["close"] - 1
            y_return = future_return.copy()
            common_idx = features.index.intersection(y_return.dropna().index)
            X = features.loc[common_idx]
            y_ret = y_return.loc[common_idx]
            y_bin = (y_ret > 0).astype(float)
            valid = X.notna().all(axis=1) & y_ret.notna()
            X, y_ret, y_bin = X[valid], y_ret[valid], y_bin[valid]

            if len(X) < 200:
                continue

            print(f"{coin:<7}", end="")
            for thr in [0.0, 0.01, 0.02, 0.03, 0.05]:
                _, trades, wr, _ = test_regression(X, y_ret, y_bin, HUBER_PARAMS, threshold=thr)
                print(f" {wr:>4.0f}%/{trades:<3}", end="")
            print()


if __name__ == "__main__":
    main()
