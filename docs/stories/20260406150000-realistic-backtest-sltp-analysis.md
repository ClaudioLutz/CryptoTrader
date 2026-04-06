# Realistischer Backtest: SL/TP-Analyse und ehrliche Ergebnisse

## Summary

Realistischer Backtest mit stündlichem Retraining zeigt, dass die ursprünglichen Backtest-Ergebnisse
(57% WR, +0.93% Avg P&L) zu optimistisch waren. Das symmetrische SL/TP (2x/2x ATR) war das
Hauptproblem — es schneidet Gewinne ab. Asymmetrisches SL/TP (2x SL / 4x TP) macht die Strategie
profitabel, aber mit bescheidener Rendite.

## Context / Problem

- Der Bot lief 16 Stunden und predicted 16x "Down" während BTC 6% stieg
- Berechtigte Skepsis: War der ursprüngliche Backtest realistisch?
- Alter Backtest trainierte nur 1x pro Woche (168h-Fenster), nicht stündlich wie in Produktion
- Notwendigkeit eines ehrlichen Backtests mit exakter Produktions-Simulation

## Erkenntnisse

### 1. Alter Backtest war zu optimistisch

| Metrik | Alter Backtest (wöchentl.) | Realistisch (stündl.) |
|--------|---------------------------|----------------------|
| Training | 1x pro Woche | 1x pro Stunde |
| Accuracy | ~57% | **51.7%** |
| Win-Rate (65% Conf) | ~58% | **61.8%** |
| Avg P&L/Trade | +0.93% | **-0.039%** |
| Total P&L (90d) | positiv | **-13.42%** |

Der alte Backtest trainierte seltener → weniger Trades → optimistischere Statistik.

### 2. SL/TP-Verhältnis ist das Kernproblem

Mit dem aktuellen symmetrischen SL/TP (2x ATR / 2x ATR):
- Take-Profit: 221 Trades, 97% WR, aber nur **+0.44%** pro Trade
- Stop-Loss: 120 Trades, 0% WR, **-0.88%** pro Trade (doppelt so gross!)
- Gewinne werden abgeschnitten, Verluste voll realisiert

### 3. Systematische SL/TP-Untersuchung (90 Tage, 348 Trades)

| SL / TP | WR | Avg P&L | Total P&L |
|---------|-----|---------|-----------|
| 1x / 1x | 44.0% | -0.188% | -65.47% |
| 1x / 2x | 45.7% | -0.086% | -29.86% |
| **1x / 3x** | **42.2%** | **+0.011%** | **+3.75%** |
| 2x / 2x (aktuell) | 61.8% | -0.039% | -13.42% |
| **2x / 3x** | **58.0%** | **+0.092%** | **+32.01%** |
| **2x / 4x** | **56.6%** | **+0.242%** | **+84.13%** |
| 3x / 3x | 64.4% | +0.114% | +39.75% |
| Kein SL/TP | 58.3% | +1.058% | +368.12% |

**Erkenntnis**: Sobald TP >= 3x ATR, wird die Strategie profitabel. "Kein SL/TP" ist am besten,
aber riskanter.

### 4. Contrarian-Ansatz funktioniert nicht

Signal invertieren (kaufen wenn Modell "Down" sagt) produziert Verluste bei allen
Confidence-Schwellen. Das Modell ist also nicht systematisch falsch, sondern hat ein
schwaches aber reales Signal.

### 5. Realistische Kapital-Simulation ($453 Startkapital)

| Strategie | 90 Tage | 180 Tage | Annualisiert |
|-----------|---------|----------|-------------|
| ALT: SL 2x / TP 2x | -3.5% ($437) | -7.7% ($418) | ~-15% p.a. |
| NEU: SL 2x / TP 4x | +5.8% ($479) | +2.3% ($463) | ~4-5% p.a. |
| SL 3x / TP 4x | +6.0% ($480) | +1.9% ($461) | ~4% p.a. |
| Kein SL/TP | +10.5% ($500) | +15.3% ($522) | ~30% p.a. |

### 6. Confidence-Verteilung

| Confidence | Predictions | Accuracy |
|-----------|-------------|----------|
| >= 50% | 2'160 | 51.7% |
| >= 55% | 1'791 | 53.1% |
| >= 60% | 1'487 | 53.7% |
| >= 65% | 1'228 | 55.2% |
| >= 70% | 1'013 | 59.1% |
| >= 75% | 765 | **65.5%** |

Erst ab 75% Confidence wird die Accuracy wirklich interessant, aber dann gibt es sehr wenige
Up-Signale.

### 7. Volatilitäts-Regime

| Regime | Predictions | Accuracy | Trades | WR | Total P&L |
|--------|------------|----------|--------|-----|-----------|
| Niedrige Vol (Q1) | 515 | 44.3% | 75 | 70.7% | +1.12% |
| Mittlere Vol (Q2-Q3) | 1'281 | 55.4% | 240 | 59.6% | -14.34% |
| Hohe Vol (Q4) | 364 | 49.2% | 33 | 57.6% | -0.20% |

## Recherche: Neue Ansätze (2026-04-06)

Systematische Recherche nach Ansätzen, die über Standard-TA hinausgehen.

### Priorisierte Ansätze

| # | Ansatz | Erw. Rendite | Aufwand | Kosten | Priorität |
|---|--------|-------------|---------|--------|-----------|
| 1 | Regime-Erkennung (HMM) | Drawdown -50% | Gering | Kostenlos | **Sehr hoch** |
| 2 | Orderbook-Imbalance | +5-15% Accuracy | Mittel | Kostenlos | **Hoch** |
| 3 | Multi-Timeframe (4h+1h) | +8-12% WR | Gering | Kostenlos | **Hoch** |
| 4 | OI-Delta + Fear&Greed Filter | Filter-Effekt | Gering | Kostenlos | Mittel |
| 5 | Funding Rate Arbitrage | ~19% p.a., <2% DD | Mittel | Kostenlos | Mittel |
| 6 | Mean Reversion + Regime | 15-30% p.a. | Mittel | Kostenlos | Mittel |
| 7 | Hybrid Regression + Classif. | Besseres Sizing | Gering | Kostenlos | Niedrig |

### 1. Regime-Erkennung (HMM) — Grösster Einzelhebel

Hidden Markov Model mit 3 States (stabil / moderat volatil / extrem volatil).
Nur in stabilen/trending Regimes traden, bei extremer Volatilität pausieren.

- **Warum**: Unsere 16x Down-Predictions fielen in eine Phase, in der BTC 6% stieg —
  ein klares Regime-Mismatch. Ein HMM hätte "extreme Volatilität" erkannt und keine Trades ausgelöst.
- **Unser Backtest bestätigt das**: Niedrige Vol (Q1) → 70.7% WR, +1.12% P&L.
  Mittlere Vol (Q2-Q3) → 59.6% WR, -14.34% P&L. Das Modell performt nur in ruhigen Phasen.
- **Implementierung**: `hmmlearn` Library, Input = Returns + Volatilität, kein externer Datenbedarf.
- **Quelle**: "3-State Non-Homogeneous HMM for BTC Regime Detection" (2024-2026, Preprints.org)

### 2. Orderbook-Imbalance — Kostenloser kurzfristiger Edge

Bid/Ask-Volumenverhältnis aus dem Orderbook als Feature.

- **Edge**: Nachgewiesene kurzfristige Vorhersagekraft, besonders zu illiquiden Zeiten (03:00 UTC).
  Studien zeigen: besseres Feature-Engineering > tiefere Netzwerke → gut für LightGBM.
- **Implementierung**: Binance WebSocket (kostenlos), L2-Orderbook Top 5-20 Levels.
  Feature: `bid_volume / (bid_volume + ask_volume)`, gerollt über 5/15/60 Min.
- **Aufwand**: Mittel — braucht WebSocket-Listener und Feature-Aggregation.
- **Quelle**: "Price Impact of Order Book Imbalance in Cryptocurrency Markets" (TowardsDataScience)

### 3. Multi-Timeframe-Analyse — Einfachste Verbesserung

4h- oder Daily-Trend als Richtungsfilter für 1h-Entries.

- **Edge**: +8-12% Win-Rate-Verbesserung gegenüber Single-Timeframe in Studien.
  Empfohlenes Verhältnis: 4:1 zwischen Timeframes (4h → 1h).
- **Implementierung**: 4h-Features (EMA, Trend-Richtung) zum bestehenden 1h-Modell hinzufügen.
  Oder: 4h-Modell als Richtungsfilter, 1h-Modell für Timing.
- **Aufwand**: Gering — gleiche Datenquelle, nur Resampling nötig.

### 4. OI-Delta + Fear & Greed Index

Open Interest Veränderungsrate und Fear & Greed als Regime-Filter.

- **OI-Delta**: Kostenlos via Binance API. Steigende OI + steigender Preis = bestätigter Trend.
  Fallende OI + steigender Preis = schwacher Trend (nicht traden).
- **Fear & Greed**: Kostenlos via alternative.me API. Daily-Auflösung.
  Extreme Fear (<25) → Kaufsignal, Extreme Greed (>75) → Vorsicht.
- **Aufwand**: Gering — API-Calls + Feature-Integration.

### 5. Funding Rate Arbitrage — Risikoärmste Strategie

Spot Long + Perpetual Short, Funding kassieren.

- **Rendite**: 2025 durchschnittlich 19.26% p.a. bei <2% Drawdown.
- **Problem**: Bei $450 Kapital fressen Gebühren überproportional. Besser ab ~$5'000.
  Zudem 215% mehr deployed Kapital als 2024 → kompetitiver werdend.
- **Alternative**: Extreme Funding als Reversal-Indikator nutzen (ohne Arbitrage).

### 6. Mean Reversion + Regime-Filter

RSI < 30 + Preis unter unterem Bollinger Band als Long-Entry, aber nur in Seitwärtsphasen.

- **Rendite**: 15-30% p.a. in Seitwärtsmärkten. ~60% Win Rate.
- **Kritisch**: Versagt komplett in Trendphasen → Regime-Filter (ADX oder HMM) zwingend nötig.
- **Kann als zweite Strategie neben Prediction laufen.**

### Nicht empfohlene Ansätze

| Ansatz | Grund |
|--------|-------|
| On-Chain-Daten (Glassnode) | ~$40/Mt API-Kosten, bei $450 Kapital unverhältnismässig |
| Liquidation Prediction | Nicht systematisierbar, Coinglass Pro teuer |
| Kalendereffekte | Instabil über Zeit, max. 3-8% p.a. additiv |
| LSTM/Transformer | Kein nachgewiesener Vorteil über LightGBM bei tabellarischen Features |

### Empfohlene Umsetzungsreihenfolge

1. **Regime-Erkennung (HMM)** implementieren → nicht traden bei schlechtem Regime
2. **Multi-Timeframe Features** (4h) zum bestehenden Modell hinzufügen
3. **OI-Delta + Fear & Greed** als zusätzliche Features/Filter
4. **Orderbook-Imbalance** als Feature (braucht WebSocket-Infrastruktur)
5. **Asymmetrisches SL/TP (2x/4x)** deployen (bereits lokal implementiert)

### Quellen

- [On-Chain Multi-Signal Framework](https://powerdrill.ai/blog/bitcoin-price-prediction)
- [Orderbook Imbalance Price Impact](https://towardsdatascience.com/price-impact-of-order-book-imbalance-in-cryptocurrency-markets-bf39695246f6/)
- [HMM Regime Detection BTC](https://www.preprints.org/manuscript/202603.0831)
- [HMM Practical Tutorial](https://blog.quantinsti.com/regime-adaptive-trading-python/)
- [Fear & Greed Index API](https://alternative.me/crypto/fear-and-greed-index/)
- [Ensemble Stacking](https://medium.com/@stevechesa/stacking-ensembles-combining-xgboost-lightgbm-and-catboost-to-improve-model-performance-d4247d092c2e)
- [Funding Rate Arbitrage 2025](https://www.gate.com/learn/articles/perpetual-contract-funding-rate-arbitrage/2166)
- [Bollinger Bands Varying Regimes](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5775962)

## Backtest-Ergebnisse: Neue Ansätze (2026-04-06)

### Test 1: HMM Regime-Filter + Multi-Timeframe + Kombination

Walk-Forward Backtest, 90 Tage, stündliches Retraining, $453 Startkapital.

| Ansatz | Trades | WR | Avg P&L | Total | Kapital |
|--------|--------|-----|---------|-------|---------|
| Baseline (SL 2x/TP 4x) | 291 | 53.6% | +0.208% | **+5.8%** | $479 |
| Multi-Timeframe (1h+4h Features) | 287 | 49.5% | +0.137% | +3.7% | $470 |
| HMM (0+1) + 4h-Trend-Filter | 92 | 41.3% | +0.125% | **+5.8%** | $479 |
| Alle Features (Base+HMM+4h) | 274 | 43.1% | -0.072% | **-5.7%** | $427 |

**Erkenntnisse:**
- HMM als **Filter** bringt gleiche Rendite mit 1/3 der Trades → effizienter
- HMM als **Feature** im Modell schadet (-5.7%) → Overfitting auf Regime-Labels
- Multi-Timeframe Features verbessern Accuracy leicht (52.9% vs 51.7%), aber nicht den Gewinn
- 4h-Features: trend_4h_ema8_21, trend_4h_direction, ret_4h_*, mom_4h_*, rsi_4h, vol_4h_6, adx_4h

### Test 2: Systematische Filter × SL/TP × Confidence Matrix

Alle Kombinationen getestet: 4 Filter × 4 Confidence × 4 SL/TP = 64 Konfigurationen.

**Top 10 (90 Tage):**

| Filter | Conf | SL/TP | Trades | WR | Avg P&L | Total |
|--------|------|-------|--------|-----|---------|-------|
| **Kein Filter** | **75%** | **kein** | **52** | **59.6%** | **+2.242%** | **+11.0%** |
| Kein Filter | 65% | kein | 90 | 54.4% | +1.087% | +10.5% |
| Kein Filter | 70% | kein | 82 | 43.9% | +0.611% | +9.4% |
| Kein Filter | 60% | 3x/4x | 335 | 54.6% | +0.101% | +7.1% |
| Kein Filter | 60% | 2x/4x | 376 | 47.6% | +0.080% | +6.7% |
| Kein Filter | 70% | 3x/4x | 178 | 62.4% | +0.258% | +6.0% |
| Kein Filter | 65% | 3x/4x | 274 | 58.8% | +0.234% | +6.0% |
| Kein Filter | 65% | 2x/4x | 291 | 53.6% | +0.208% | +5.8% |
| HMM(0+1)+Trend | 65% | 2x/4x | 92 | 41.3% | +0.125% | +5.8% |
| 4h-Trend | 65% | 2x/4x | 92 | 41.3% | +0.125% | +5.8% |

**Top 10 (180 Tage):**

| Filter | Conf | SL/TP | Trades | WR | Avg P&L | Total |
|--------|------|-------|--------|-----|---------|-------|
| **Kein Filter** | **70%** | **kein** | **114** | **44.7%** | **+0.530%** | **+16.4%** |
| Kein Filter | 65% | kein | 143 | 54.5% | +0.801% | +15.3% |
| Kein Filter | 75% | kein | 74 | 54.1% | +1.432% | +13.9% |
| Kein Filter | 75% | 2x/4x | 178 | 48.9% | +0.092% | -0.5% |
| 4h-Trend | 70% | kein | 40 | 50.0% | +0.845% | +8.8% |
| Kein Filter | 60% | kein | 221 | 55.2% | +0.148% | +5.5% |
| 4h-Trend | 60% | 3x/4x | 144 | 43.8% | -0.050% | +5.0% |
| HMM(0)+Trend | 70% | kein | 27 | 48.1% | +1.461% | +7.1% |
| Kein Filter | 60% | 2x/4x | 522 | 44.6% | +0.007% | +2.2% |

### Zentrale Erkenntnis: SL/TP entfernen > alle anderen Optimierungen

**"Kein SL/TP" dominiert ALLE Konfigurationen massiv:**

| Zeitraum | Mit SL/TP (bestes) | Kein SL/TP (bestes) | Differenz |
|----------|-------------------|--------------------|-----------| 
| 90 Tage | +7.1% (3x/4x, 60%) | **+11.0%** (kein, 75%) | +3.9pp |
| 180 Tage | +5.5% (3x/4x, 60%) | **+16.4%** (kein, 70%) | +10.9pp |

**Warum**: Das ML-Modell hat einen schwachen aber realen Edge (~52-55% Accuracy). 
Stop-Losses schneiden die seltenen grossen Gewinne ab, die den Edge profitabel machen.
Mit dem 72h-Zeithorizont ist das Time-Expiry der natürliche Stop-Loss.

**Filter (HMM, 4h-Trend) schaden eher:**
- Sie reduzieren die Trades-Anzahl, aber filtern auch profitable Trades heraus
- HMM(0)+Trend bei 65% Conf: WR 19.4%, -5.0% → extrem schlechte Ergebnisse
- Nur bei "kein SL/TP" + 70% Conf bringt der 4h-Trend-Filter leichten Vorteil (+8.8%)

### Empfohlene Produktions-Konfiguration

Basierend auf dem Tradeoff zwischen Performance und Robustheit:

| Parameter | Aktuell | Empfohlen | Begründung |
|-----------|---------|-----------|------------|
| SL/TP | 2x/4x ATR | **Kein SL/TP** | +11% vs +5.8% (90d) |
| Confidence | 65% | **70%** | Bester Tradeoff: genug Trades + hohe Rendite |
| Filter | Keiner | **Keiner** | Filter schaden, Time-Expiry reicht |
| Horizont | 72h | 72h (beibehalten) | Wirkt als natürlicher Stop-Loss |
| Positionsgrösse | Conf-gewichtet | Beibehalten | Funktioniert gut |

**Erwartete Rendite**: +10-16% über 90-180 Tage (~20-30% p.a.)
**Risiko**: Ohne SL kann ein einzelner Trade max. ~10-15% verlieren (72h-Fenster).
Aber Confidence ≥70% filtert bereits 50% der schwachen Signale heraus.

## Fazit

Die Standard-TA-Features (RSI, MACD, Bollinger, Returns, Volatilität) haben bei BTC 1h
nur einen **minimalen Edge** (~52% Accuracy). Dieser Edge ist real aber fragil.

**Der grösste Hebel ist nicht das Modell oder die Features, sondern das SL/TP-Management:**
- Symmetrisches SL/TP (2x/2x) → Verluste (-13.4%)
- Asymmetrisches SL/TP (2x/4x) → Kleiner Gewinn (+5.8%)
- **Kein SL/TP** + hohe Confidence → **Bestes Ergebnis** (+11-16%)

HMM Regime-Erkennung und Multi-Timeframe Features bringen **keinen signifikanten Vorteil**
gegenüber dem einfachen Entfernen der SL/TP-Orders. Der 72h-Zeithorizont ist der natürliche
Stop-Loss — das Modell braucht keine zusätzliche Risikobegrenzung bei hoher Confidence.

**Nächster Schritt**: SL/TP entfernen und Confidence auf 70% erhöhen in Produktion deployen.

## Backtest-Methodik

- Walk-Forward Validation mit stündlichem Retraining (exakt wie Produktion)
- 720h Train-Window, 72h Prediction-Horizont
- LightGBM Classifier, 19-32 Features (je nach Variante), Early Stopping
- Fee: 0.2% roundtrip (0.1% je Seite)
- Kapital-Simulation mit Confidence-gewichteter Positionsgrösse ($453 Start)
- Max Exposure: 80%
- Getestet: 90 und 180 Tage
- Backtest-Scripts: `scripts/backtest_new_approaches.py`, `scripts/backtest_filter_variations.py`
- Laufzeit: ~14 Minuten für alle Varianten
