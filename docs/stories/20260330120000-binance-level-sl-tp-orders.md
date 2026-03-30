# Binance-Level Stop-Loss und Take-Profit Orders

## Summary

SL/TP werden jetzt direkt auf Binance als separate Orders platziert statt nur durch den Bot geprueft (60s-Polling). Schutz ist damit auch bei Bot-Ausfall aktiv.

## Context / Problem

Bisher wurden SL/TP nur im Bot-Speicher gehalten und alle 60 Sekunden per Preis-Polling geprueft. Bei Bot-Crash oder Netzwerkausfall gab es keinen Schutz. Binance selbst wusste nichts von unseren SL/TP-Levels.

## What Changed

- **`base_exchange.py`**: `create_order()` akzeptiert optionalen `params: dict` fuer Exchange-spezifische Parameter
- **`ccxt_wrapper.py`**: Leitet `params` an CCXT `create_order()` weiter (z.B. `stopLossPrice`, `takeProfitPrice`)
- **`binance_adapter.py`**: Reicht `params` durch die Validierungskette
- **`base_strategy.py`**: `ExecutionContext.place_order()` akzeptiert `params`
- **`bot.py`**: Beide Kontexte (Live + DryRun) leiten `params` durch
- **`position_tracker.py`**: `PredictionPosition` hat neue Felder `sl_order_id` und `tp_order_id`
- **`prediction_strategy.py`**:
  - Nach Market Buy: 2 separate Orders (SL + TP) auf Binance platzieren
  - `on_order_filled()`: Bei SL/TP-Fill die Gegenseite automatisch canceln
  - `on_tick()`: Bot-Level SL/TP nur als Fallback wenn keine Binance-Orders existieren
  - `_close_position()`: Bestehende SL/TP Orders canceln vor Market Sell (Zeitbarriere)
  - Migration: Beim Start werden bestehende Positionen automatisch mit Binance-Orders nachgeruestet
- **`daily_prediction_run.py`**: SL/TP Orders nach Buy + Cancel vor Close

## How to Test

1. `python -m pytest tests/unit/ -k "not test_grid" -q` — Unit-Tests
2. `python scripts/daily_prediction_run.py --dry-run` — Dry-Run
3. Live-Test: Bot starten, neuen Trade beobachten, in Binance-App pruefen ob SL/TP-Orders sichtbar sind

## Risk / Rollback Notes

- **Fallback**: Wenn SL/TP-Platzierung fehlschlaegt, greift Bot-Level SL/TP wie bisher
- **Doppel-Sell-Risiko**: Gering — bei SL/TP-Fill wird Gegenseite sofort gecancelt; bei Zeitbarriere werden beide gecancelt vor Market Sell
- **Fee-Beruecksichtigung**: OCO-Menge basiert auf `order.filled` (nach Fee-Abzug)
- **Rollback**: Aenderungen rueckgaengig machen → Bot funktioniert wieder mit Bot-Level SL/TP
