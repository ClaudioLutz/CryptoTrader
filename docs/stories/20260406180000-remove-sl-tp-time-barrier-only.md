# SL/TP entfernt — nur Zeitbarriere als Risikomanagement

## Summary

SL/TP komplett deaktiviert. Positionen werden nur noch durch die 72h-Zeitbarriere geschlossen. Confidence bleibt bei 65%.

## Context / Problem

Systematische Backtests (90d + 180d, alle Kombinationen aus Filtern, Confidence-Levels und SL/TP-Konfigurationen) zeigen eindeutig: SL/TP zerstoert den schwachen ML-Edge. Die Stop-Losses schneiden die grossen Gewinner ab, bevor sie sich entwickeln koennen.

- 90d: +11.0% ohne SL/TP vs. +5.8% mit SL/TP (2x/4x ATR)
- 180d: +16.4% ohne SL/TP vs. +2.3% mit SL/TP

Die 72h-Zeitbarriere fungiert als natuerlicher Stop — schlechte Trades werden nach 72h geschlossen, unabhaengig vom Verlust.

## What Changed

- `prediction_pipeline.py`: `sl_pct` und `tp_pct` auf `0.0` gesetzt (1h-Pfad). ATR wird weiterhin berechnet (fuer Logging/Analyse), aber nicht mehr fuer SL/TP verwendet.
- `prediction_strategy.py`:
  - `sl_price`/`tp_price` werden auf `None` gesetzt wenn `sl_pct`/`tp_pct` == 0
  - Keine Binance-Level SL-Order mehr platziert
  - Bot-Level TP-Check uebersprungen (da `take_profit_price` == None)
  - Log-Output zeigt "disabled" statt ungueltige Preise
- Confidence (`min_confidence`) bleibt unveraendert bei 65%

## How to Test

```bash
# Lokal: Bot starten und pruefen ob Positionen ohne SL/TP geoeffnet werden
python scripts/start_prediction_bot.py

# Logs pruefen: sl="disabled", tp="disabled"
# Keine Binance SL-Orders sollten platziert werden
```

## Risk / Rollback Notes

- **Risiko**: Ohne SL/TP koennen einzelne Positionen innerhalb der 72h groessere Verluste erleiden (bis zu ~10-15% pro Coin). Das Gesamtportfolio ist durch `max_total_exposure_pct=60%` und `max_per_coin_pct=10%` begrenzt.
- **Rollback**: SL/TP-Berechnung in `prediction_pipeline.py` wieder aktivieren (ATR-basierte Werte waren: SL=2x ATR, TP=4x ATR).
- **Backtests stuetzen die Entscheidung**: Alle getesteten Kombinationen zeigen "kein SL/TP" als dominant.
