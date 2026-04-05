# Dashboard-Umbau fuer BTC 1h Prediction-Strategie

## Summary

Dashboard komplett umgebaut von Grid-Trading-Multi-Pair auf BTC 1h Prediction-Strategie.
Neue Tabs: BTC Prediction (Hauptview), Trade History, Performance. Alte leere Dashboard-
und Configuration-Tabs entfernt.

## Context / Problem

Das Dashboard war fuer die alte Grid-Trading-Strategie gebaut (Multi-Pair, Grid-Levels,
Buy/Sell-Orders). Nach dem Wechsel auf die BTC 1h Prediction-Strategie waren die meisten
Views irrelevant (Grid-Visualization, Multi-Pair-Tabelle, Grid-Config). Der Dashboard-Tab
war leer, der Configuration-Tab nicht gepflegt.

## What Changed

### Bot-seitig (Backend)
- **prediction_strategy.py**: Prediction-History-Speicher hinzugefuegt (`_prediction_history`).
  Jede stuendliche Prediction wird mit Timestamp, Richtung, Confidence gespeichert (max 336
  Eintraege = 2 Wochen). Retraining-Dauer wird gemessen. State-Serialisierung erweitert.
- **health.py**: Neuer API-Endpunkt `GET /api/prediction-history` — liefert History,
  Model-Info (Retraining-Status, Config), aktuelle Prediction, offene + geschlossene Positionen.

### Dashboard (Frontend)
- **main.py**: 3 Tabs statt 4 (BTC Prediction, Trade History, Performance). Imports bereinigt.
  Prediction-Daten werden alle 30s gepollt.
- **header.py**: Angepasst fuer BTC-only — zeigt aktuelle Prediction (Richtung + Confidence),
  P&L, Uptime statt Pair/Order-Counts.
- **predictions_view.py**: Komplett neu geschrieben:
  - Model-Status Cards (aktuelle Prediction, letztes/naechstes Retraining, Strategie-Config)
  - BTC-Preis-Chart (1h Candlestick) mit Confidence-Subplot und Trade-Markern (Entry/Exit)
  - SL/TP-Linien fuer offene Positionen
  - Offene Positionen mit verbleibender Zeit bis Schliessung
  - Prediction-Timeline (letzte 48h, filterbar, mit Handelbar-Indikator)
- **performance_view.py**: Neu erstellt:
  - Trading-Statistiken (Win-Rate, Avg P&L, Best/Worst Trade, Close-Reason-Breakdown)
  - Equity-Kurve (kumulativer P&L ueber Zeit, Plotly)
  - Geschlossene Positionen (Tabelle mit P&L-Farbe und Reason-Badge)
- **state.py**: Erweitert um prediction_history, model_info, current_prediction,
  open_positions, closed_positions + refresh_prediction_data() Methode.
- **api_client.py**: Neue Methode `get_prediction_history()`.

### Entfernte Referenzen
- Dashboard-Tab (war leer)
- Configuration-Tab (nicht gepflegt)
- Alte Component-Dateien bleiben als Dateien bestehen, werden aber nicht mehr importiert.

## How to Test

1. Bot lokal starten: `python scripts/start_prediction_bot.py`
2. Dashboard starten: `python -m dashboard.main`
3. Browser: http://localhost:8081
4. Pruefen:
   - Tab "BTC Prediction": Model-Status, Chart, Positionen, Timeline
   - Tab "Trade History": Filter funktionieren
   - Tab "Performance": Stats, Equity-Kurve, geschlossene Positionen
5. Warten auf erstes Retraining (1h) — danach sollten Prediction-History-Eintraege erscheinen.

## Risk / Rollback Notes

- **Kein Risiko fuer den Bot**: Aenderungen am Bot sind rein additiv (History-Speicher,
  neuer API-Endpunkt). Bestehende Logik bleibt unveraendert.
- **Dashboard-Rollback**: Git revert der Dashboard-Dateien stellt altes Dashboard wieder her.
- **Alte Components**: Dateien wie `pairs_table.py`, `configuration_view.py`,
  `grid_visualization.py` wurden nicht geloescht — bei Bedarf wieder aktivierbar.
