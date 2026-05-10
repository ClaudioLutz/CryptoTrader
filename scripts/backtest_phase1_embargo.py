"""Phase 1 Backtest — Embargo + 1-Jahr-Train-Window vs naives Setup.

Vergleicht die aktuelle Bot-Methodik (Train 720h, kein Embargo) gegen die
saubere Methodik nach Lopez de Prado (Train 8760h = 1 Jahr, Embargo 72h
zwischen Train/Val sowie zwischen Train/Test).

Ziel: ehrliche OOS-Accuracy fuer BTC 1h/72h. Keine anderen Aenderungen.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, "C:/Codes/coin_prediction")
warnings.filterwarnings("ignore")

import lightgbm as lgb
import numpy as np
import pandas as pd

CP = Path("C:/Codes/coin_prediction")
HORIZON_H = 72
TEST_H = 168
FEE_RT = 0.001  # 0.1% pro Trade-Seite (round-trip 0.2%)

CLF_P = {
    "objective": "binary",
    "metric": "binary_logloss",
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


def build_features(ohlcv: pd.DataFrame, coin: str = "BTC") -> pd.DataFrame:
    close = ohlcv["close"].astype(float)
    volume = ohlcv["volume"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    f = pd.DataFrame(index=ohlcv.index)
    for p in [1, 4, 12, 24, 72, 168]:
        f[f"ret_{p}h"] = close.pct_change(p)
    hourly_ret = close.pct_change()
    for w in [12, 24, 72, 168]:
        f[f"vol_{w}h"] = hourly_ret.rolling(w).std()
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    f["rsi_14h"] = 100 - (100 / (1 + rs))
    f["vol_ratio_24_168"] = (
        volume.rolling(24).mean() / volume.rolling(168).mean().replace(0, np.nan)
    )
    f["hl_range_24h"] = (high.rolling(24).max() - low.rolling(24).min()) / close
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    f["macd"] = ema12 - ema26
    f["macd_signal"] = f["macd"].ewm(span=9, adjust=False).mean()
    f["macd_hist"] = f["macd"] - f["macd_signal"]
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    f["bb_position"] = (close - sma20) / (2 * std20).replace(0, np.nan)

    fp = CP / f"data/raw/{coin}_funding.parquet"
    if fp.exists():
        funding = pd.read_parquet(fp)
        if "timestamp" in funding.columns:
            funding = funding.set_index("timestamp").sort_index()
        fr = funding["funding_rate"].reindex(f.index, method="ffill")
        f["funding_rate"] = fr
        f["funding_3d_ma"] = fr.rolling(72).mean()

    try:
        from src.ingestion.macro_fetcher import build_macro_features
        macro = build_macro_features(close, CP / "data", interval="1h")
        if not macro.empty:
            if hasattr(f.index, "tz") and f.index.tz is not None and macro.index.tz is None:
                macro.index = macro.index.tz_localize("UTC")
            valid_cols = macro.columns[macro.notna().any()]
            f = pd.concat([f, macro[valid_cols]], axis=1)
    except Exception as e:
        print(f"  macro_features failed: {e}")
    return f


def run_backtest(
    features: pd.DataFrame,
    close: pd.Series,
    train_h: int,
    embargo_h: int,
    min_conf: float = 0.65,
    label: str = "",
    year_filter: list[int] | None = None,
) -> dict:
    """Walk-Forward Backtest mit konfigurierbarem Embargo.

    embargo_h=0 reproduziert die alte Bot-Methodik.
    embargo_h=72 implementiert Phase 1 (Embargo zwischen Train/Val UND Train/Test).
    train_h=720 = alt, train_h=8760 = Phase 1.
    """
    future_ret = close.shift(-HORIZON_H) / close - 1
    target = (future_ret > 0).astype(float)
    target[future_ret.isna()] = np.nan

    common = features.index.intersection(target.dropna().index)
    X = features.loc[common]
    y = target.loc[common]
    valid = X.notna().all(axis=1) & y.notna()
    X, y = X[valid], y[valid]
    n = len(X)

    trade_returns: list[float] = []
    all_preds: list[int] = []
    all_proba: list[float] = []
    all_actual: list[int] = []
    all_ts: list[pd.Timestamp] = []
    tt = 0
    tw = 0
    blocked_year = 0
    start = 0
    blocked_until: pd.Timestamp | None = None

    while start + train_h + embargo_h + TEST_H <= n:
        # Train-Block
        Xtr_full = X.iloc[start : start + train_h]
        ytr_full = y.iloc[start : start + train_h]

        # Train/Val-Split mit Embargo dazwischen (fuer Early Stopping)
        s = int(len(Xtr_full) * 0.8)
        if embargo_h > 0:
            # Letzte embargo_h Bars von Train rausschneiden, dann Val starten
            Xtr = Xtr_full.iloc[: max(1, s - embargo_h)]
            ytr = ytr_full.iloc[: max(1, s - embargo_h)]
        else:
            Xtr = Xtr_full.iloc[:s]
            ytr = ytr_full.iloc[:s]
        Xval = Xtr_full.iloc[s:]
        yval = ytr_full.iloc[s:]

        # Test-Block (nach Train + Embargo)
        test_start = start + train_h + embargo_h
        Xte = X.iloc[test_start : test_start + TEST_H]

        if len(Xtr) < 100 or ytr.nunique() < 2 or yval.nunique() < 2:
            start += TEST_H
            continue

        m = lgb.LGBMClassifier(**CLF_P)
        m.fit(
            Xtr, ytr,
            eval_set=[(Xval, yval)],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
        )
        proba = m.predict_proba(Xte)[:, 1]
        preds = (proba > 0.5).astype(int)
        conf = np.abs(proba - 0.5) + 0.5

        test_close = close.loc[Xte.index]
        test_idx = test_close.index

        # Actuals fuer Accuracy-Messung
        for i in range(len(Xte)):
            now_ts = test_idx[i]
            if i + HORIZON_H >= len(test_close):
                break
            actual = int(test_close.iloc[i + HORIZON_H] > test_close.iloc[i])
            all_preds.append(int(preds[i]))
            all_proba.append(float(proba[i]))
            all_actual.append(actual)
            all_ts.append(now_ts)

            # Trade-Logik mit Confidence-Filter
            if blocked_until is not None and now_ts < blocked_until:
                continue
            if preds[i] != 1 or conf[i] < min_conf:
                continue
            if year_filter is not None and now_ts.year not in year_filter:
                blocked_year += 1
                continue
            entry = float(test_close.iloc[i])
            exit_ = float(test_close.iloc[i + HORIZON_H])
            gross = (exit_ - entry) / entry
            net = gross - FEE_RT
            trade_returns.append(net)
            tt += 1
            if exit_ > entry:
                tw += 1
            blocked_until = test_idx[i + HORIZON_H]

        start += TEST_H

    # Accuracy-Metriken auf ALLEN OOS-Predictions (nicht nur Trades)
    if not all_preds:
        return {"label": label, "n_oos": 0, "trades": 0}

    arr_pred = np.array(all_preds)
    arr_actual = np.array(all_actual)
    arr_proba = np.array(all_proba)

    acc = float((arr_pred == arr_actual).mean() * 100)
    up_pred_pct = float(arr_pred.mean() * 100)
    up_actual_pct = float(arr_actual.mean() * 100)
    baseline_always_up = float(arr_actual.mean() * 100)
    # Brier
    brier = float(((arr_proba - arr_actual) ** 2).mean())

    # Calibration: Bin nach Proba
    bins = np.linspace(0.5, 1.0, 6)
    cal_lines = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (arr_proba >= lo) & (arr_proba < hi)
        if mask.sum() > 5:
            actual_rate = float(arr_actual[mask].mean() * 100)
            cal_lines.append(f"      p={lo:.2f}-{hi:.2f}: n={int(mask.sum()):>5}  actual_up={actual_rate:5.1f}%")

    res = {
        "label": label,
        "n_oos": len(all_preds),
        "accuracy_pct": acc,
        "baseline_always_up_pct": baseline_always_up,
        "alpha_vs_baseline_pp": acc - baseline_always_up,
        "up_predicted_pct": up_pred_pct,
        "brier_score": brier,
        "trades": tt,
        "winrate_pct": (tw / tt * 100) if tt > 0 else 0.0,
        "cum_return_pct": (
            float((np.prod(1 + np.array(trade_returns)) - 1) * 100) if tt > 0 else 0.0
        ),
        "calibration": cal_lines,
    }
    return res


def print_result(r: dict) -> None:
    print(f"\n--- {r['label']} ---")
    print(f"  OOS Predictions: {r['n_oos']:>6}")
    if r["n_oos"] == 0:
        print("  (keine OOS-Predictions, Train-Window zu gross fuer Daten?)")
        return
    print(f"  Accuracy:        {r['accuracy_pct']:>6.2f}%")
    print(f"  Baseline UP:     {r['baseline_always_up_pct']:>6.2f}% (always-UP-Strategie)")
    print(f"  Alpha vs UP:     {r['alpha_vs_baseline_pp']:>+6.2f} pp")
    print(f"  UP-Predictions:  {r['up_predicted_pct']:>6.2f}% (vs realistisch {r['baseline_always_up_pct']:.1f}%)")
    print(f"  Brier-Score:     {r['brier_score']:>6.4f} (niedriger = besser)")
    print(f"  Trades:          {r['trades']:>6}")
    if r["trades"] > 0:
        print(f"  Winrate:         {r['winrate_pct']:>6.2f}%")
        print(f"  CumReturn:       {r['cum_return_pct']:>+6.2f}%")
    if r["calibration"]:
        print("  Calibration (Predicted-Proba vs Actual-UP-Rate):")
        for line in r["calibration"]:
            print(line)


def main() -> None:
    print("=" * 80)
    print("PHASE 1 BACKTEST — Embargo + 1-Jahr-Window")
    print("=" * 80)
    ohlcv = pd.read_parquet(CP / "data/raw/BTC_USDT_1h.parquet")
    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()
    close = ohlcv["close"].astype(float)

    print(f"BTC: {len(ohlcv)} bars, {ohlcv.index[0]} -> {ohlcv.index[-1]}")
    print("Lade Features (TA + Funding + Macro) ...")
    features = build_features(ohlcv, "BTC")
    print(f"Features: {features.shape[1]} cols, {len(features)} rows")

    configs = [
        ("BOT-AKTUELL  (train=720h, embargo=0)", 720, 0),
        ("PHASE-1 NEU  (train=8760h, embargo=72h)", 8760, 72),
        ("VARIANT-A    (train=4380h=6mo, embargo=72h)", 4380, 72),
        ("VARIANT-B    (train=17520h=2yr, embargo=72h)", 17520, 72),
    ]

    results = []
    for label, th, eh in configs:
        print(f"\n>>> Run: {label}")
        r = run_backtest(features, close, train_h=th, embargo_h=eh, label=label)
        print_result(r)
        results.append(r)

    print("\n" + "=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    print(f"{'Setup':<48} {'Acc%':>7} {'BaseUP%':>8} {'Alpha':>7} {'Brier':>7} {'Trades':>7}")
    print("-" * 90)
    for r in results:
        if r["n_oos"] == 0:
            print(f"{r['label']:<48} (no OOS)")
            continue
        print(
            f"{r['label']:<48} "
            f"{r['accuracy_pct']:>6.2f}% "
            f"{r['baseline_always_up_pct']:>7.2f}% "
            f"{r['alpha_vs_baseline_pp']:>+6.2f} "
            f"{r['brier_score']:>7.4f} "
            f"{r['trades']:>7}"
        )


if __name__ == "__main__":
    main()
