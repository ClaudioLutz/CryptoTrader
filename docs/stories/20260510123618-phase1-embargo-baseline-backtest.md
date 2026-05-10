# Phase 1 — Embargo + 1-Jahr-Window Baseline-Backtest

## Summary
Backtest-Skript zum ehrlichen Vergleich der aktuellen Bot-Methodik (720h-Train,
kein Embargo) gegen saubere Lopez-de-Prado-Methodik (1-Jahr-Train, 72h Embargo
zwischen Train/Val und Train/Test). Ziel: ungeschoente OOS-Direction-Accuracy.

## Context / Problem
Der Bot zeigte in vorherigen Backtests +164% CumReturn, aber die Modell-Accuracy
liegt bei 49.5% — schlechter als "always UP" (52%). Verdacht: Label-Leakage
durch fehlendes Embargo zwischen Train- und Validation-Set bei 72h-Target,
und Train-Window von nur 720h (~10 unabhaengige Samples). Ohne Embargo+ehrliches
Window keine valide Aussage ueber echten Edge moeglich.

## What Changed
- Neu: `scripts/backtest_phase1_embargo.py` — Walk-Forward-Backtest mit
  konfigurierbarem Train-Window und Embargo zwischen Train/Val sowie Train/Test
- Vier Konfigurationen verglichen: Bot-Aktuell, Phase-1, Variant-A (6 Monate),
  Variant-B (2 Jahre)
- Reportet OOS-Accuracy, Brier-Score, Calibration-Bins, Trade-Statistik

## Resultate (BTC 1h, Horizont 72h)

| Setup                       | Acc%  | Baseline UP% | Alpha  | Brier  | Trades |
|-----------------------------|------:|-------------:|-------:|-------:|-------:|
| BOT-AKTUELL (720h, 0h emb)  | 49.23 | 54.47        | -5.25  | 0.288  | 70     |
| PHASE-1 (8760h, 72h emb)    | 49.59 | 50.12        | -0.52  | 0.254  | 1      |
| VARIANT-A (4380h, 72h emb)  | 43.13 | 49.95        | -6.82  | 0.263  | 7      |
| VARIANT-B (17520h)          | -     | -            | -      | -      | -      |

**Befund**: Kein Setup schlaegt die jeweilige "always UP"-Baseline. Phase-1
liefert ehrlichste Zahlen (Acc ≈ 50% bei Baseline ≈ 50%) — Modell ist also
nicht besser als Muenzwurf. Die scheinbare Profitabilitaet des Bot-Aktuell-
Setups ist Markt-Beta-Artefakt, kein echter Edge.

VARIANT-B lieferte 0 OOS-Predictions, weil Macro-Features (DXY/VIX/SPY)
Wochenend-Luecken haben und `notna().all()` die Haelfte der Bars entfernt.

## How to Test
```bash
cd c:/Codes/CryptoTrader_3.0/CryptoTrader
python scripts/backtest_phase1_embargo.py
```
Erwartet: Tabelle mit Accuracy/Baseline/Alpha/Brier/Trades pro Konfiguration,
plus Calibration-Bins.

## Risk / Rollback Notes
Reine Diagnose-Aenderung: nur ein neues Skript unter `scripts/`, kein Eingriff
in den Live-Bot. Rollback durch Loeschen des Skripts. Keine Performance- oder
Sicherheits-Auswirkungen auf das Trading.
