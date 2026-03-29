# Add Prediction-Based Trading Strategy

## Summary

Neue Trading-Strategie integriert, die auf 7-Tage ML-Vorhersagen des `coin_prediction`-Projekts basiert. Der Bot trainiert taeglich ein LightGBM-Modell fuer 20 Kryptowaehrungen, oeffnet Positionen bei starken "Up"-Signalen mit Confidence-basierter Positionsgroesse und schliesst sie nach exakt 7 Tagen.

## Context / Problem

Der CryptoTrader hatte bisher nur eine Grid-Trading-Strategie fuer SOL/USDT. Das separate `coin_prediction`-Projekt generiert ML-basierte 7-Tage-Vorhersagen mit 52-56% Accuracy, die bisher nicht fuer Live-Trading genutzt wurden. Ziel ist die Integration dieser Predictions als eigenstaendige, umschaltbare Strategie.

## What Changed

- **Neues Package `src/crypto_bot/prediction/`** mit:
  - `prediction_config.py`: PredictionConfig (Pydantic) mit Parametern fuer Kapital, Confidence-Schwelle, Retrain-Zeitpunkt, Coins
  - `position_tracker.py`: Position-Lifecycle-Management (open/closing/closed) mit 7-Tage-Ablauf und State-Serialisierung
  - `prediction_pipeline.py`: Wrapper um das `coin_prediction`-Projekt (fetch -> features -> train -> predict) mit asyncio.to_thread() Integration
  - `prediction_strategy.py`: Vollstaendige Strategy-Protocol-Implementation mit taegl. Retrain, Confidence-basiertem Sizing, Multi-Symbol-Support

- **`src/crypto_bot/bot.py`** angepasst:
  - Multi-Symbol-Support in `_run_loop()` (Dummy-Ticker fuer MULTI/USDT Sentinel)
  - `_check_order_fills()` unterstuetzt `fetch_open_orders(None)` fuer alle Symbole
  - Konfigurierbares `tick_interval` pro Strategie (60s fuer Predictions statt 1s)

- **`src/crypto_bot/main.py`** angepasst:
  - Neues CLI-Argument `--strategy grid|prediction`
  - `create_prediction_strategy()` Funktion

- **Dashboard Predictions-Tab** (`dashboard/components/predictions_view.py`):
  - Training-Button startet Pipeline direkt aus dem Dashboard
  - Ergebnis-Tabelle mit Richtung, Wahrscheinlichkeit, Confidence, Signal-Qualitaet
  - Summary-Cards (Coins analysiert, Up/Down-Signale, handelbare Signale)
  - Farbcodierte Badges fuer Signal-Staerke (STARK/MODERAT/SCHWACH/NOISE)

- **Pipeline-Bug gefixt** (`prediction_pipeline.py`):
  - NaN in neuester Feature-Zeile werden per forward-fill aufgefuellt statt auf aeltere Zeile zurueckzufallen
  - Verbleibende NaN werden mit Median-Fallback behandelt

- **E2E-Tests** (`tests/e2e/test_predictions_tab.py`):
  - 12 Playwright-Tests fuer Dashboard-Basics, Predictions-Tab, Tab-Navigation

## How to Test

```bash
# 1. Automatisierter Bot (Dry-Run)
python -m crypto_bot.main --strategy prediction --dry-run

# 2. Dashboard mit Training-Button
python -m dashboard.main
# -> Tab "Predictions" -> "Training starten"

# 3. E2E-Tests (Dashboard muss laufen)
python -m pytest tests/e2e/test_predictions_tab.py -v

# 4. Grid-Strategie (unveraendert)
python -m crypto_bot.main --strategy grid --dry-run
```

## Risk / Rollback Notes

- **Echtes Geld**: Die Strategie handelt auf Binance Mainnet! Immer zuerst mit `--dry-run` testen.
- **Exposure-Limits**: Max 60% des Kapitals deployed, max 10% pro Coin, min. Confidence 0.55.
- **Nur Long**: Keine Short-Positionen auf dem Spot-Markt.
- **Rollback**: Einfach `--strategy grid` verwenden, die Grid-Strategie ist unveraendert.
- **Abhaengigkeit**: Benoetigt das `coin_prediction`-Projekt unter `C:/Codes/coin_prediction` mit allen Abhaengigkeiten (lightgbm, ccxt, pandas, etc.).
- **Crash-Recovery**: State wird nach jedem Tick gespeichert; offene Positionen bleiben nach Neustart erhalten.
