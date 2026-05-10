# Phase 3 — Triple-Barrier mit Vol-Skalierung (3 Varianten)

## Summary
Drei Triple-Barrier-Varianten getestet: ASYMM (TP=2sigma, SL=1sigma — de-Prado-
Default), SYMM (1.5sigma/1.5sigma) und CONSERV (1sigma/1sigma). Alle mit
Multi-Coin-Pool aus Phase 2. Hypothese: Vol-skaliertes TB-Target reduziert
Label-Rauschen. **Hypothese widerlegt — alle 3 Varianten zeigen 0 Edge.**

## Context / Problem
Phase 1+2 zeigten: Modell hat keinen Direction-Edge mit nacktem Vorzeichen-
Target. Online-Recherche und de-Prado-Default empfehlen Triple-Barrier mit
asymmetrischen Schwellen. Bot-Code-Kommentar sagte "asymm performt schlechter"
aber symmetrische Variante wurde nie getestet.

## What Changed
- Neu: `scripts/backtest_phase3_triple_barrier.py`
- Triple-Barrier-Implementierung mit EWMA-Vol-Schaetzer (span=100)
- 3 Schwellen-Varianten in einem Run getestet
- Reportet sowohl TB-Accuracy als auch Direction-equivalent-Accuracy

## Resultate

| Variant            | up%  | AccTB% | BaseTB | AlphaTB | AccDir% | AlphaD | Trades | CumRet  |
|--------------------|-----:|-------:|-------:|--------:|--------:|-------:|-------:|--------:|
| ASYMM (2.0/1.0)    | 34.9 | 65.53  | 34.47  | +31.05* | 48.52   | -2.96  | 0      | +0.00%  |
| SYMM  (1.5/1.5)    | 50.9 | 49.95  | 50.31  | -0.36   | 50.29   | -1.19  | 4      | +39.77% |
| CONSERV (1.0/1.0)  | 51.8 | 51.16  | 51.38  | -0.22   | 50.91   | -0.57  | 0      | +0.00%  |

*) Mathematik-Artefakt: ASYMM-Modell predicted 0% UP (immer Mehrheitsklasse).

**Befund**: Direction-Acc liegt in allen Varianten unter Baseline. Kein Setup
extrahiert echte Information. SYMM hat Class-Balance 50/50 aber liefert dennoch
keinen Edge (-0.36pp Alpha). 4 Trades bei SYMM mit +39% CumReturn sind
statistisches Rauschen (n=4).

## How to Test
```bash
cd c:/Codes/CryptoTrader_3.0/CryptoTrader
python scripts/backtest_phase3_triple_barrier.py
```

## Risk / Rollback Notes
Reine Diagnose-Aenderung, kein Live-Bot-Eingriff. Loescht das Skript zum
Rollback. Lehre: das Target ist nicht der primaere Engpass — das Underlying-
Signal fehlt. Phase 4 (Calibration + Threshold-Tuning) ist letzter methodischer
Hebel; wenn auch das nichts bringt, ist Direction-Prediction fuer dieses
Setup nicht machbar.
