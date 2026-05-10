# Phase 4 — Platt-Scaling-Calibration + Threshold-Tuning

## Summary
Backtest mit manuellem Platt-Scaling (LogisticRegression auf raw proba) und
max-EV Threshold-Tuning auf separatem Cal-Hold-Out und Val-Set.
Alle 4 Konfigurationen testen. **Resultat katastrophal**: Calibration macht
Modell SCHLECHTER, Threshold-Tuning overfittet auf Val-Set, FULL-Setup
verliert -98.77% CumReturn auf 638 Trades.

## Context / Problem
Phasen 1-3 zeigten kein Direction-Edge. Online-Recherche-Hypothese: das
Modell hat zwar wenig Information, aber Calibration + Threshold-Tuning
koennten zumindest die wenigen wahren Signale herauspicken. Inverse-Edge
bei p=0.7-0.9 (actual_up nur 5-25%) sollte durch Sigmoid-Calibration
gefixt werden.

## What Changed
- Neu: `scripts/backtest_phase4_calibration.py`
- 3-Way-Split: Inner-Train (60%) -> Cal-Hold-Out (20%) -> Val (20%)
  mit Embargo zwischen jedem Sub-Split
- Manuelles Platt-Scaling via LogisticRegression(C=1.0) auf Cal-Set
  (sklearn CalibratedClassifierCV cv='prefit' deprecated)
- Max-EV Threshold-Tuning auf Val (range 0.40-0.80, step 0.02)
- 4 Varianten: Baseline, Cal-only, Thresh-only, FULL

## Resultate

| Setup                                  | Acc%  | Alpha   | Brier  | Trades | Winrate | CumRet   |
|----------------------------------------|------:|--------:|-------:|-------:|--------:|---------:|
| BASELINE (no cal, fixed t=0.65)        | 50.68 | -0.80   | 0.252  | 54     | 40.7%   | -55.24%  |
| CAL-ONLY (Platt, fixed t=0.65)         | 48.33 | -3.15   | 0.260  | 7      | 28.6%   | -20.87%  |
| THRESH-ONLY (no cal, max-EV)           | 50.68 | -0.80   | 0.252  | 467    | 49.5%   | -91.20%  |
| FULL Phase 4 (Cal + max-EV)            | 48.33 | -3.15   | 0.260  | 638    | 51.4%   | -98.77%  |

**Befund**: Jede Verbesserung verschlechtert das Resultat.
- Calibration: Acc -2.35pp, Brier +0.008 (verschlechtert Calibration sogar)
- Threshold-Tuning: 12-90x mehr Trades, alle verlieren
- Mean tuned Threshold 0.47-0.54 → Tuning overfittet auf Val-Set, Distribution
  auf Test instabil

## Gesamtbild Phase 1-4

| Phase | Hebel                        | Alpha   | Trades | CumRet  |
|-------|------------------------------|--------:|-------:|--------:|
| 1     | Embargo + 1-Jahr             | -0.52   | 1      | -1%     |
| 2     | Multi-Coin-Pool              | -1.06   | 52     | -53%    |
| 3 SYMM| Triple-Barrier 1.5sigma     | -1.19   | 4      | +40%*   |
| 4 FULL| Calibration + Threshold      | -3.15   | 638    | -99%    |

*) statistisches Rauschen bei n=4

**Schlussfolgerung**: Direction-Prediction fuer 1h/72h-Crypto mit aktuellem
Feature-Set (TA + Funding + Macro) funktioniert nicht. Modell zeigt durchweg
inverse Edge bei hoher Confidence — vermutet: Overfitting auf strukturell
instabile Marktregime.

## How to Test
```bash
cd c:/Codes/CryptoTrader_3.0/CryptoTrader
python scripts/backtest_phase4_calibration.py
```

## Risk / Rollback Notes
Reine Diagnose-Aenderung, kein Live-Bot-Eingriff. Loescht das Skript zum
Rollback.

**Strategische Konsequenz**: Bot sollte gestoppt werden bis ein Setup mit
echtem Edge gefunden ist. Aktuelle Erwartung pro Trade ist leicht negativ
plus 0.2% Round-Trip-Fees.
