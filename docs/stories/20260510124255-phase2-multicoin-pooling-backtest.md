# Phase 2 — Multi-Coin-Pooling mit coin_id

## Summary
Backtest mit einem einzigen LightGBM-Modell ueber 5 Coins (BTC, ETH, SOL, BNB,
TRX) und coin_id als kategorischem Feature. Hypothese (G-Research-Crypto-Kaggle):
Pooling steigert effektive Sample-Size 12x und legt echtes Direction-Signal frei.

**Hypothese widerlegt.**

## Context / Problem
Phase 1 zeigte: Single-Coin-BTC-Modell mit sauberer Methodik (1-Jahr-Window,
72h-Embargo) hat Acc 49.59% bei Baseline 50.12% (Alpha -0.52pp). Online-Recherche
empfahl Multi-Coin-Pooling als groesster einzelner Hebel.

## What Changed
- Neu: `scripts/backtest_phase2_multicoin.py`
- Pool-Builder: alle 5 Coins zu einem DataFrame zusammengefasst, coin_id als
  kategorisches Feature, sortiert nach Timestamp
- Walk-Forward auf der Zeit-Achse: alle Coins teilen sich Train/Test-Fenster
- macro-Features mit ffill um Wochenend-Luecken zu schliessen
- 2 TZ-Bugs gefixed (np.concatenate killt UTC-Info)

## Resultate

| Setup                      | Acc%  | Baseline UP% | Alpha   | Trades | CumRet  |
|----------------------------|------:|-------------:|--------:|-------:|--------:|
| Phase 1 (BTC only, alt)    | 49.59 | 50.12        | -0.52   | 1      | -1%     |
| Phase 2 Pool gesamt        | 50.42 | 51.48        | -1.06   | 52     | -53%    |
| Phase 2 BTC subset         | 49.79 | 50.81        | -1.01   | -      | -       |
| Phase 2 ETH subset         | 49.93 | 50.53        | -0.60   | -      | -       |
| Phase 2 SOL subset         | 47.48 | 48.17        | -0.69   | -      | -       |
| Phase 2 BNB subset         | 51.16 | 52.98        | -1.82   | -      | -       |
| Phase 2 TRX subset         | 53.72 | 54.92        | -1.20   | -      | -       |

**Befund**: KEIN Coin schlaegt seine Baseline. BTC ist mit Pooling sogar
schlechter als ohne. Trade-Performance katastrophal: -53% CumReturn auf
52 Trades, Calibration zeigt INVERSE Edge bei p=0.6-0.7 (actual_up 34.6%).

Vermutete Gruende:
- Crypto-Coins haben heterogene Dynamiken
- coin_id als simpler Kategorial-Feature reicht nicht aus, Coin x Feature-
  Interaktionen explizit zu modellieren
- Kaggle-Top-Solutions hatten zusaetzliche Coin-spezifische Engineering

## How to Test
```bash
cd c:/Codes/CryptoTrader_3.0/CryptoTrader
python scripts/backtest_phase2_multicoin.py
```

## Risk / Rollback Notes
Reine Diagnose-Aenderung, kein Live-Bot-Eingriff. Loescht das Skript zum
Rollback. Lehre: vor Implementierung im Bot zwingend Phase 3+4 abwarten.
