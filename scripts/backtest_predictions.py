"""Walk-Forward Backtest fuer alle Prediction-Coins.

Fuehrt eine realistische Walk-Forward Validation durch:
- Sliding Window (500 Tage Training, 30 Tage Test)
- Purging (7 Tage) + Embargo (7 Tage) gegen Look-Ahead-Bias
- Triple Barrier Labeling (2x ATR SL, 3x ATR TP)
- Metriken: Accuracy, IC, Accuracy Top-25% Confidence, simulierter P&L

Usage:
    python scripts/backtest_predictions.py
    python scripts/backtest_predictions.py --coins BTC ETH SOL
    python scripts/backtest_predictions.py --horizon 7 --train-days 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# coin_prediction Pfad
COIN_PREDICTION_PATH = Path("C:/Codes/coin_prediction")
sys.path.insert(0, str(COIN_PREDICTION_PATH))

from src.evaluation.metrics import aggregate_metrics, compute_fold_metrics
from src.evaluation.walk_forward import walk_forward_splits
from src.models.lightgbm_model import predict_with_confidence, train_lightgbm
from src.models.targets import create_target


def load_coin_data(coin: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Laedt Features und OHLCV fuer einen Coin."""
    features_path = COIN_PREDICTION_PATH / "data" / "features" / f"{coin}_features.parquet"
    ohlcv_path = COIN_PREDICTION_PATH / "data" / "raw" / f"{coin}_USDT_1d.parquet"

    features = pd.read_parquet(features_path)
    ohlcv = pd.read_parquet(ohlcv_path)

    if "timestamp" in ohlcv.columns:
        ohlcv = ohlcv.set_index("timestamp").sort_index()

    return features, ohlcv


def run_backtest_for_coin(
    coin: str,
    horizon: int = 7,
    train_days: int = 500,
    test_days: int = 30,
    min_confidence: float = 0.65,
) -> dict:
    """Walk-Forward Backtest fuer einen einzelnen Coin.

    Returns:
        Dict mit aggregierten Metriken und Trade-Simulation.
    """
    features, ohlcv = load_coin_data(coin)

    # Target erstellen (Triple Barrier)
    target = create_target(
        close=ohlcv["close"],
        horizon=horizon,
        high=ohlcv["high"],
        low=ohlcv["low"],
        atr_sl_mult=2.0,
        atr_tp_mult=3.0,
    )

    # Features und Target alignen
    common_idx = features.index.intersection(target.dropna().index)
    X = features.loc[common_idx].copy()
    y = target.loc[common_idx].copy()

    # NaN-Zeilen entfernen
    valid_mask = X.notna().all(axis=1) & y.notna()
    X = X[valid_mask]
    y = y[valid_mask]

    if len(X) < 200:
        return {"coin": coin, "error": f"Zu wenig Daten: {len(X)} Zeilen"}

    # Walk-Forward Validation
    fold_metrics = []
    all_predictions = []

    for X_train, y_train, X_test, y_test, fold_info in walk_forward_splits(
        X, y,
        train_days=train_days,
        test_days=test_days,
        step_days=test_days,  # Nicht-ueberlappende Test-Fenster
        embargo_days=horizon,
        purge_days=horizon,
    ):
        # 80/20 Split innerhalb Training fuer Early Stopping
        split_idx = int(len(X_train) * 0.8)
        X_tr = X_train.iloc[:split_idx]
        y_tr = y_train.iloc[:split_idx]
        X_val = X_train.iloc[split_idx:]
        y_val = y_train.iloc[split_idx:]

        # Trainieren
        model = train_lightgbm(X_tr, y_tr, X_val, y_val)

        # Vorhersagen
        preds, proba = predict_with_confidence(model, X_test)

        # Metriken
        metrics = compute_fold_metrics(y_test.values, preds, proba)
        metrics["fold"] = fold_info.fold_number
        metrics["test_start"] = str(fold_info.test_start.date())
        metrics["test_end"] = str(fold_info.test_end.date())
        fold_metrics.append(metrics)

        # Predictions speichern fuer Trade-Simulation
        for i, (idx, true_val) in enumerate(y_test.items()):
            all_predictions.append({
                "date": idx,
                "y_true": int(true_val),
                "y_pred": int(preds[i]),
                "probability": float(proba[i]),
                "confidence": float(abs(proba[i] - 0.5) + 0.5),
                "fold": fold_info.fold_number,
            })

    if not fold_metrics:
        return {"coin": coin, "error": "Keine Walk-Forward Folds moeglich"}

    # Aggregierte Metriken
    agg = aggregate_metrics(fold_metrics)
    agg["coin"] = coin
    agg["horizon"] = horizon

    # Trade-Simulation (nur Trades mit Confidence >= min_confidence)
    pred_df = pd.DataFrame(all_predictions)
    trade_mask = (pred_df["confidence"] >= min_confidence) & (pred_df["y_pred"] == 1)
    trades = pred_df[trade_mask]

    if len(trades) > 0:
        wins = (trades["y_true"] == 1).sum()
        losses = (trades["y_true"] == 0).sum()
        agg["trade_count"] = len(trades)
        agg["trade_win_rate"] = round(float(wins / len(trades)), 4)
        agg["trade_wins"] = int(wins)
        agg["trade_losses"] = int(losses)
    else:
        agg["trade_count"] = 0
        agg["trade_win_rate"] = 0.0
        agg["trade_wins"] = 0
        agg["trade_losses"] = 0

    # "Down"-Predictions (Markt faellt → kein Trade → richtig wenn tatsaechlich gefallen)
    no_trade_mask = (pred_df["confidence"] >= min_confidence) & (pred_df["y_pred"] == 0)
    no_trades = pred_df[no_trade_mask]
    if len(no_trades) > 0:
        correct_no_trade = (no_trades["y_true"] == 0).sum()
        agg["no_trade_count"] = len(no_trades)
        agg["no_trade_accuracy"] = round(float(correct_no_trade / len(no_trades)), 4)
    else:
        agg["no_trade_count"] = 0
        agg["no_trade_accuracy"] = 0.0

    # Fold-Details
    agg["fold_details"] = fold_metrics

    return agg


def format_results(results: list[dict]) -> str:
    """Formatiert die Ergebnisse als uebersichtliche Tabelle."""
    lines = []
    lines.append("=" * 110)
    lines.append("WALK-FORWARD BACKTEST ERGEBNISSE")
    lines.append("=" * 110)

    # Header
    lines.append(
        f"{'Coin':<8} {'Acc%':>6} {'±Std':>6} {'IC':>6} "
        f"{'Top25%':>7} {'Folds':>5} {'Samples':>7} "
        f"{'Trades':>6} {'WinRate':>7} {'W/L':>7} "
        f"{'NoTrade':>7} {'NoTrAcc':>7}"
    )
    lines.append("-" * 110)

    # Sortiere nach Accuracy
    valid = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]
    valid.sort(key=lambda x: x.get("accuracy_mean", 0), reverse=True)

    for r in valid:
        acc = r.get("accuracy_mean", 0) * 100
        acc_std = r.get("accuracy_std", 0) * 100
        ic = r.get("ic_mean", 0)
        top25 = r.get("accuracy_top25_mean", 0) * 100
        folds = r.get("n_folds", 0)
        samples = r.get("total_samples", 0)
        trades = r.get("trade_count", 0)
        win_rate = r.get("trade_win_rate", 0) * 100
        wins = r.get("trade_wins", 0)
        losses = r.get("trade_losses", 0)
        no_trades = r.get("no_trade_count", 0)
        no_trade_acc = r.get("no_trade_accuracy", 0) * 100

        lines.append(
            f"{r['coin']:<8} {acc:>5.1f}% {acc_std:>5.1f}% {ic:>6.3f} "
            f"{top25:>5.1f}%  {folds:>4}  {samples:>6} "
            f"{trades:>6} {win_rate:>5.1f}%  {wins:>3}/{losses:<3} "
            f"{no_trades:>6} {no_trade_acc:>5.1f}%"
        )

    lines.append("-" * 110)

    # Zusammenfassung
    if valid:
        avg_acc = np.mean([r.get("accuracy_mean", 0) for r in valid]) * 100
        avg_ic = np.mean([r.get("ic_mean", 0) for r in valid])
        total_trades = sum(r.get("trade_count", 0) for r in valid)
        total_wins = sum(r.get("trade_wins", 0) for r in valid)
        total_losses = sum(r.get("trade_losses", 0) for r in valid)
        overall_wr = total_wins / total_trades * 100 if total_trades > 0 else 0

        lines.append(f"\nGESAMT: {len(valid)} Coins analysiert")
        lines.append(f"  Durchschnittliche Accuracy: {avg_acc:.1f}%")
        lines.append(f"  Durchschnittlicher IC: {avg_ic:.3f}")
        lines.append(f"  Trades gesamt: {total_trades} (Win-Rate: {overall_wr:.1f}%, {total_wins}W/{total_losses}L)")

        # Coins nach Tier sortieren
        strong = [r["coin"] for r in valid if r.get("accuracy_mean", 0) >= 0.58]
        solid = [r["coin"] for r in valid if 0.55 <= r.get("accuracy_mean", 0) < 0.58]
        marginal = [r["coin"] for r in valid if 0.52 <= r.get("accuracy_mean", 0) < 0.55]
        weak = [r["coin"] for r in valid if r.get("accuracy_mean", 0) < 0.52]

        if strong:
            lines.append(f"  Tier 1 (>58%): {', '.join(strong)}")
        if solid:
            lines.append(f"  Tier 2 (55-58%): {', '.join(solid)}")
        if marginal:
            lines.append(f"  Tier 3 (52-55%): {', '.join(marginal)}")
        if weak:
            lines.append(f"  Schwach (<52%): {', '.join(weak)}")

    for r in errors:
        lines.append(f"\n  FEHLER {r['coin']}: {r['error']}")

    lines.append("=" * 110)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-Forward Backtest")
    parser.add_argument("--coins", nargs="+", default=None,
                        help="Coins zum Testen (Default: alle profitablen)")
    parser.add_argument("--all-coins", action="store_true",
                        help="Alle Coins testen (inkl. unprofitable)")
    parser.add_argument("--horizon", type=int, default=7,
                        help="Prediction-Horizont in Tagen (Default: 7)")
    parser.add_argument("--train-days", type=int, default=500,
                        help="Trainings-Fenster in Tagen (Default: 500)")
    parser.add_argument("--min-confidence", type=float, default=0.65,
                        help="Minimale Confidence fuer Trade-Simulation (Default: 0.65)")
    args = parser.parse_args()

    # Coins bestimmen
    if args.coins:
        coins = [c.upper() for c in args.coins]
    elif args.all_coins:
        # Alle Coins mit Features
        features_dir = COIN_PREDICTION_PATH / "data" / "features"
        coins = sorted([
            p.stem.replace("_features", "")
            for p in features_dir.glob("*_features.parquet")
        ])
    else:
        # Nur die profitablen (aktuell gehandelten)
        coins = ["MATIC", "DOT", "ETC", "ADA", "XLM",
                 "EOS", "ATOM", "TRX", "DOGE",
                 "AVAX", "SOL", "NEAR"]

    print(f"\nBacktest: {len(coins)} Coins, Horizont={args.horizon}d, "
          f"Training={args.train_days}d, MinConfidence={args.min_confidence}")
    print(f"Coins: {', '.join(coins)}\n")

    results = []
    for i, coin in enumerate(coins, 1):
        print(f"[{i}/{len(coins)}] {coin}...", end=" ", flush=True)
        try:
            result = run_backtest_for_coin(
                coin,
                horizon=args.horizon,
                train_days=args.train_days,
                min_confidence=args.min_confidence,
            )
            if "error" in result:
                print(f"FEHLER: {result['error']}")
            else:
                acc = result.get("accuracy_mean", 0) * 100
                trades = result.get("trade_count", 0)
                wr = result.get("trade_win_rate", 0) * 100
                print(f"Acc={acc:.1f}%, Trades={trades}, WinRate={wr:.1f}%")
            results.append(result)
        except Exception as e:
            print(f"EXCEPTION: {e}")
            results.append({"coin": coin, "error": str(e)})

    # Ergebnisse ausgeben
    print("\n")
    print(format_results(results))

    # CSV speichern
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    csv_rows = [r for r in results if "error" not in r]
    if csv_rows:
        # fold_details entfernen fuer CSV
        for r in csv_rows:
            r.pop("fold_details", None)
        df = pd.DataFrame(csv_rows)
        csv_path = output_dir / f"backtest_results_{args.horizon}d.csv"
        df.to_csv(csv_path, index=False)
        print(f"\nErgebnisse gespeichert: {csv_path}")


if __name__ == "__main__":
    main()
