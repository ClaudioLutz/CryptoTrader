"""Teste jede Verbesserung ISOLIERT um zu sehen was hilft und was schadet."""
import sys, warnings
sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from src.evaluation.walk_forward import walk_forward_splits
from src.models.targets import create_target
from src.models.ensemble import RegimeSplitEnsemble

CP = Path("C:/Codes/coin_prediction")

OLD_P = {"objective": "binary", "learning_rate": 0.03, "max_depth": 5,
         "n_estimators": 500, "num_leaves": 31, "subsample": 0.8,
         "colsample_bytree": 0.8, "min_child_samples": 30, "verbose": -1,
         "n_jobs": 4, "random_state": 42}

NEW_P = {"objective": "binary", "learning_rate": 0.03, "max_depth": 4,
         "n_estimators": 500, "num_leaves": 12, "subsample": 0.7,
         "colsample_bytree": 0.6, "min_child_samples": 50,
         "reg_alpha": 0.1, "reg_lambda": 1.0, "min_split_gain": 0.01,
         "verbose": -1, "n_jobs": 4, "random_state": 42}

def load(coin):
    f = pd.read_parquet(CP / "data/features" / f"{coin}_features.parquet")
    o = pd.read_parquet(CP / "data/raw" / f"{coin}_USDT_1d.parquet")
    if "timestamp" in o.columns:
        o = o.set_index("timestamp").sort_index()
    return f, o

def prep_tb(coin):
    f, o = load(coin)
    t = create_target(o["close"], 7, o["high"], o["low"])
    ci = f.index.intersection(t.dropna().index)
    X, y = f.loc[ci], t.loc[ci]
    v = X.notna().all(axis=1) & y.notna()
    return X[v], y[v]

def prep_simple(coin):
    f, o = load(coin)
    fr = o["close"].shift(-7) / o["close"] - 1
    t = (fr > 0).astype(float)
    t[fr.isna()] = float("nan")
    ci = f.index.intersection(t.dropna().index)
    X, y = f.loc[ci], t.loc[ci]
    v = X.notna().all(axis=1) & y.notna()
    return X[v], y[v]

def train_lgbm(params):
    def fn(Xtr, ytr):
        s = int(len(Xtr) * 0.8)
        m = lgb.LGBMClassifier(**params)
        kw = {}
        if s < len(Xtr):
            kw["eval_set"] = [(Xtr.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr.iloc[:s], ytr.iloc[:s], **kw)
        return m
    return fn

def wf_acc(X, y, model_fn, train_days=500):
    accs = []
    for Xtr, ytr, Xte, yte, _ in walk_forward_splits(
        X, y, train_days=train_days, test_days=30, step_days=30,
        embargo_days=7, purge_days=7,
    ):
        m = model_fn(Xtr, ytr)
        preds = m.predict(Xte) if hasattr(m, "predict") else (m.predict_proba(Xte)[:, 1] > 0.5).astype(int)
        accs.append((preds == yte.values).mean())
    return round(np.mean(accs) * 100, 1) if accs else 0.0

def wf_top15(X, y, params, train_days=500):
    accs = []
    for Xtr, ytr, Xte, yte, _ in walk_forward_splits(
        X, y, train_days=train_days, test_days=30, step_days=30,
        embargo_days=7, purge_days=7,
    ):
        corrs = Xtr.corrwith(ytr).abs().sort_values(ascending=False).dropna()
        top = corrs.head(15).index.tolist()
        Xtr_s, Xte_s = Xtr[top], Xte[top]
        s = int(len(Xtr_s) * 0.8)
        m = lgb.LGBMClassifier(**params)
        kw = {}
        if s < len(Xtr_s):
            kw["eval_set"] = [(Xtr_s.iloc[s:], ytr.iloc[s:])]
            kw["callbacks"] = [lgb.early_stopping(50), lgb.log_evaluation(0)]
        m.fit(Xtr_s.iloc[:s], ytr.iloc[:s], **kw)
        preds = m.predict(Xte_s)
        accs.append((preds == yte.values).mean())
    return round(np.mean(accs) * 100, 1) if accs else 0.0

coins = ["TRX", "XLM", "DOGE", "SOL", "EOS"]

print("ISOLIERTE TESTS - Jede Aenderung einzeln")
print("=" * 75)

# Collect all results
results = {c: {} for c in coins}

for coin in coins:
    print(f"\n{coin}:", flush=True)

    # Baseline
    X, y = prep_tb(coin)
    base = wf_acc(X, y, train_lgbm(OLD_P))
    results[coin]["Baseline"] = base
    print(f"  Baseline (TB, old params, 500d, all feat):  {base}%")

    # A: Simple Target
    X, y = prep_simple(coin)
    a = wf_acc(X, y, train_lgbm(OLD_P))
    results[coin]["A:SimpleTarget"] = a
    print(f"  A: Simple Target:                           {a}% ({a-base:+.1f})")

    # B: Regularized params
    X, y = prep_tb(coin)
    b = wf_acc(X, y, train_lgbm(NEW_P))
    results[coin]["B:RegParams"] = b
    print(f"  B: Regularized LightGBM:                    {b}% ({b-base:+.1f})")

    # C: 250d training
    c = wf_acc(X, y, train_lgbm(OLD_P), train_days=250)
    results[coin]["C:250d"] = c
    print(f"  C: 250d Training:                           {c}% ({c-base:+.1f})")

    # D: Top-15 per fold (kein look-ahead)
    d = wf_top15(X, y, OLD_P)
    results[coin]["D:Top15"] = d
    print(f"  D: Top-15 Features per Fold:                {d}% ({d-base:+.1f})")

    # E: Regime-Split
    def regime_fn(Xtr, ytr):
        m = RegimeSplitEnsemble(seed=42)
        m.fit(Xtr, ytr)
        return m
    e = wf_acc(X, y, regime_fn)
    results[coin]["E:Regime"] = e
    print(f"  E: Regime-Split Ensemble:                   {e}% ({e-base:+.1f})")

    # F: Beste Kombination (A+B+D)
    X, y = prep_simple(coin)
    f_val = wf_top15(X, y, NEW_P)
    results[coin]["F:A+B+D"] = f_val
    print(f"  F: Simple + RegParams + Top15:              {f_val}% ({f_val-base:+.1f})")

# Summary
print("\n" + "=" * 75)
print("ZUSAMMENFASSUNG: Durchschnittliche Aenderung vs Baseline")
print("-" * 75)
tests = ["Baseline", "A:SimpleTarget", "B:RegParams", "C:250d", "D:Top15", "E:Regime", "F:A+B+D"]
for test in tests:
    vals = [results[c][test] for c in coins]
    avg = np.mean(vals)
    if test == "Baseline":
        print(f"  {test:<35} {avg:.1f}%")
    else:
        base_avg = np.mean([results[c]["Baseline"] for c in coins])
        diff = avg - base_avg
        print(f"  {test:<35} {avg:.1f}% ({diff:+.1f}%)")
