# Prediction Quality Deep Analysis

## Summary
Umfassende Analyse der Prediction-Qualität mit 9 Diagnosen, Internet-Recherche,
23 getesteten Varianten und Integration neuer Datenquellen (Funding Rates,
Derivate-Daten). Ergebnis: ~50-53% Accuracy ist das Maximum mit aktuellen
Standard-TA-Features bei täglicher Auflösung.

## Context / Problem
Die Walk-Forward Backtest-Ergebnisse zeigten, dass die Prediction-Accuracy
bei durchschnittlich 50.8% liegt — praktisch Münzwurf. Die ursprünglichen
Accuracy-Zahlen in `prediction_config.py` (53-58%) basierten auf einem
einfachen 80/20-Split, der die Performance überschätzt.

## What Changed

### Diagnose-Skripte (neu)
- `scripts/backtest_predictions.py` — Walk-Forward Backtest für alle Coins
- `scripts/diagnose_predictions.py` — 9-teilige Tiefendiagnose
- `scripts/test_regression.py` — Regression vs Classification Vergleich
- `scripts/backtest_improved.py` — Vergleich Alt vs Neu
- `scripts/test_isolated.py` — Isolierte Tests jeder einzelnen Änderung

### Neue Datenquellen
- `coin_prediction/src/ingestion/funding_fetcher.py` — Binance Funding Rates
  (historisch ab 2020, ~6800 Einträge pro Coin)
- `coin_prediction/src/ingestion/derivatives_fetcher.py` — Long/Short Ratio,
  Taker Volume, Open Interest (nur 30 Tage historisch, tägliches Sammeln)

### Feature-Pipeline erweitert
- `coin_prediction/src/features/pipeline.py` — Funding Rate Features integriert
- `coin_prediction/src/features/feature_selection.py` — Neue `correlation`-Methode
  für dynamische Top-N Feature-Selektion pro Coin

### Prediction Pipeline
- `prediction_pipeline.py` — Simple Target statt Triple Barrier,
  Funding Rates und Derivate-Daten werden täglich geholt,
  korrelationsbasierte Feature-Selektion (Top-15 pro Coin)

### Diagnose-Ergebnisse (Kernerkenntnisse)
1. **Target-Bias**: Triple Barrier erzeugt verzerrte Labels (44-48% Up bei 10/12 Coins)
2. **Feature-Schwäche**: Stärkste Korrelation nur 0.045 — praktisch Noise
3. **Modell-Bias**: TRX predicted 77% Up (AlwaysUp schlägt ML), XLM nur 16.7% Up
4. **Regime-Split schadet**: Halbiert die ohnehin knappen Trainingsdaten
5. **Funding Rates**: Nicht signifikant besser als bestehende Features
6. **Regression**: Hilft bei schwachen Coins, schadet bei starken
7. **1h-Daten**: Vielversprechend (BTC 55.5% WR auf 22k Trades), braucht Architektur-Änderung

### Getestete Varianten (23 insgesamt)
| Ansatz | Ø Accuracy | vs Baseline |
|--------|-----------|-------------|
| Baseline (TB, alle Features, 500d) | 50.3% | — |
| Simple Target | 50.5% | +0.2% |
| Regularisierte Params | 50.0% | -0.3% |
| 250d Training | 49.9% | -0.4% |
| Top-15 Features/Fold | 50.4% | +0.1% |
| Regime-Split | 49.4% | -0.9% |
| Kombination A+B+D | 50.8% | +0.5% |
| Funding Rate Features | 49.4% | -0.9% |
| Regression (Huber) | 48.9% | -1.4% |
| 1h-Daten (BTC, 7d) | 52.6% | +2.3% |

## How to Test
```bash
# Walk-Forward Backtest (alle Coins)
python scripts/backtest_predictions.py

# Tiefendiagnose
python scripts/diagnose_predictions.py

# Regression vs Classification
python scripts/test_regression.py

# Isolierte Tests
python scripts/test_isolated.py
```

## Risk / Rollback Notes
- LightGBM DEFAULT_PARAMS wurden zurückgesetzt auf Original-Werte
- Pipeline verwendet jetzt Simple Target statt Triple Barrier — Rollback:
  `_create_target(close, horizon, high=high, low=low)` zurücksetzen
- Funding/Derivate-Fetcher sind additiv (keine bestehende Funktionalität geändert)
- Feature-Selektion `method="correlation"` ist abwärtskompatibel mit `method="core"`
