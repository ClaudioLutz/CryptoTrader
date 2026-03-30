# Triple Barrier Labeling und Quantil-Regression

## Summary
ML-Modell lernt jetzt "wird der Trade profitabel?" statt nur "steigt der Preis?" (Triple Barrier Labeling).
Zusaetzlich sagt eine Quantil-Regression das erwartete Rendite-Intervall (Q10/Q50/Q90) vorher, was fuer
intelligenteres Position Sizing genutzt wird.

## Context / Problem
Das bisherige binaere Target (Up/Down) hatte eine fundamentale Schwaeche: Ein Coin, der +15% steigt
und dann auf -2% faellt, wurde als "Up" gelabelt — obwohl der Trade mit unserem Stop-Loss ein Verlust
waere. Ausserdem konnte das Modell nicht sagen, wie gross die erwartete Bewegung ist.

## What Changed

### Triple Barrier Labeling (coin_prediction/src/models/targets.py)
- Neues Target-Verfahren nach Lopez de Prado ("Advances in Financial Machine Learning")
- Drei Barrieren: TP (3x ATR), SL (2x ATR), Zeit (7 Tage)
- Label bestimmt durch welche Barriere zuerst beruehrt wird
- Rueckwaerts-kompatibel: Ohne high/low automatischer Fallback auf binaeres Target
- Walk-Forward-Backtest zeigt: Accuracy nahezu identisch (-0.7%), Top-25% Predictions minimal besser

### Quantil-Regression (coin_prediction/src/models/quantile_model.py)
- Drei LightGBM-Regressoren (Q10, Q50, Q90) vorhersagen Rendite-Intervall
- Q10: "Im schlechtesten Fall -9%", Q50: "Erwartet +0.5%", Q90: "Im besten Fall +7.8%"
- Quantile-Crossing-Korrektur eingebaut
- Training laeuft parallel zum Classifier (~15s extra pro Coin)

### ATR + Quantil-gewichtetes Position Sizing (prediction_strategy.py)
- Positionsgroesse basiert auf Confidence x Bewegungsgroesse
- Wenn Quantil-Daten verfuegbar: Q50 bestimmt Groesse, Q10>0 gibt 20% Bonus
- Fallback auf ATR-basierte Gewichtung (tp_pct / median_tp)

### Pipeline-Integration (prediction_pipeline.py)
- OHLCV high/low wird an create_target uebergeben fuer Triple Barrier
- Quantil-Modelle werden nach dem Classifier trainiert
- PredictionResult um q10, q50, q90 Felder erweitert
- Dashboard-Cache persistiert Quantil-Daten

### Threshold-Aenderung
- min_confidence von 55% auf 56% erhoeht (weniger aber bessere Trades)

## How to Test
```bash
# Backtest Triple Barrier vs. Binaer
cd C:/Codes/coin_prediction
python scripts/backtest_triple_barrier.py --coins=BTC,ETH,SOL,ADA,TRX

# Training mit Quantil-Regression via Dashboard
cd C:/Codes/CryptoTrader_3.0/CryptoTrader
python -m dashboard.main
# -> Predictions Tab -> Training starten
# -> Logs pruefen: grep "q10" in Ausgabe

# Bot neu starten
taskkill /PID <bot_pid> /F
python scripts/start_prediction_bot.py
```

## Risk / Rollback Notes
- Triple Barrier ist rueckwaerts-kompatibel (Fallback auf binaer ohne OHLCV)
- Quantil-Regression ist optional (try/except, setzt q10=q50=q90=0 bei Fehler)
- Backtest zeigt keinen signifikanten Accuracy-Gewinn durch Triple Barrier, aber korrektere Labels
- Rollback: In prediction_pipeline.py `high=None, low=None` setzen fuer binaeres Target
- Position Sizing Fallback auf ATR wenn keine Quantile vorhanden
