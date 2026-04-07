# A) Trading-Strategien & Signale — Vertiefte Recherche

> Zurueck zur Uebersicht: [erweiterungsmoeglichkeiten.md](erweiterungsmoeglichkeiten.md)

**Datum:** 2026-04-06
**Kontext:** CryptoTrader 3.0 — BTC-only, LightGBM 1h, 72h-Zeitbarriere, 65% Min-Confidence, ~454 USDT, Binance Mainnet

---

## A1: Multi-Coin reaktivieren (1h statt 1d)

### Was es ist

Reaktivierung der Multi-Coin-Strategie fuer die 18 bereits definierten Coins (`ALL_PREDICTION_COINS` in `prediction_config.py`), diesmal mit 1h-Daten statt dem frueher getesteten 1d-Timeframe, der nur ~50% Accuracy lieferte (Muenzwurf-Niveau).

### Konkrete Implementierungsdetails

**Bestehendes Fundament:** Die Infrastruktur existiert bereits vollstaendig:
- `ALL_PREDICTION_COINS` definiert 18 Coins (ETH, SOL, XRP, BNB, TRX, DOGE, ADA, DOT, ETC, EOS, ATOM, AVAX, NEAR, XLM, MATIC, LINK, LTC)
- `PredictionPipeline` unterstuetzt Multi-Coin nativ
- `PredictionStrategy` verwaltet bereits mehrere Positionen gleichzeitig

**Notwendige Aenderungen:**
1. **Feature-Pipeline fuer 1h-Daten auf alle 18 Coins erweitern** — Aktuell ist die 1h-Feature-Berechnung inline nur fuer BTC optimiert. Muesste fuer jeden Coin adaptiert werden.
2. **Training parallelisieren** — 18 Modelle trainieren dauert bei 1h-Retraining-Intervall zu lange sequentiell. `concurrent.futures.ProcessPoolExecutor` oder joblib empfohlen.
3. **Position-Sizing anpassen** — `max_per_coin_pct` von 80% (BTC-only) auf ~10-15% reduzieren fuer Diversifikation.
4. **Kapital-Fragmentierung beachten** — Bei 454 USDT und 18 Coins waeren das nur ~25 USDT pro Coin. Binance Spot Minimum Notional ist 5-10 USDT, also grenzwertig.

**Libraries:** Keine neuen erforderlich. `ccxt` (Binance), `lightgbm`, `pandas`, `ta` bereits im Projekt.

### Akademische/praktische Evidenz

- **LightGBM auf 42 Kryptowaehrungen:** Sun & Liu (ScienceDirect) zeigten, dass LightGBM auf Multi-Coin-Daten robuste Ergebnisse liefert, allerdings auf Daily-Daten.
- **Altcoin-Korrelation:** Grayscale-Research (Q1 2025) zeigt, dass Altcoins durchschnittlich eine Korrelation von 60-70% zu BTC haben. Diversifikationseffekt existiert, ist aber begrenzt.
- **Hourly vs. Daily:** IEEE-Paper (Predicting BTCUSDT with LightGBM Classification) bestaetigt bessere Ergebnisse auf Intraday-Daten durch hoehere Sample-Groesse.
- **Altcoin Season:** Altcoins bewegen sich in 75% der Zeit synchron zu BTC. Echter Diversifikationsvorteil tritt nur in Altcoin-Seasons auf.

### Relevanz fuer dieses Projekt

- **Pro:** Infrastruktur zu 80% vorhanden. Diversifikation koennte Drawdowns reduzieren. Mehr Trading-Signale pro Stunde.
- **Contra:** 454 USDT sind extrem knapp fuer 18 Coins. BTC hat die hoechste Liquiditaet und die besten Predictions. Der 1d-Multi-Coin-Versuch scheiterte bereits mit ~50% Accuracy.
- **Empfehlung:** Erst mit mehr Kapital (>2'000 USDT) sinnvoll. Alternativ: nur Top-3 (BTC, ETH, SOL) testen.

### Risiken und Fallstricke

- **Overfitting pro Coin:** Weniger 1h-Datenhistorie fuer Altcoins verfuegbar als fuer BTC
- **Retraining-Last:** 18 Modelle alle 1h trainieren koennte die e2-small VM ueberlasten (2 vCPU, 2 GB RAM)
- **Slippage bei Small-Caps:** Coins wie EOS oder XLM haben deutlich weniger Liquiditaet
- **Kapitalfragmentierung:** 25 USDT pro Position generiert nach Fees kaum Gewinn

### Geschaetzter Aufwand

**3-5 Tage** (Feature-Pipeline erweitern: 2d, Training parallelisieren: 1d, Testing & Backtesting: 1-2d)

---

## A2: Short-Trading via Binance Futures

### Was es ist

Nutzung der bereits vorhandenen "down"-Signale des LightGBM-Klassifikators zum Eroeffnen von Short-Positionen ueber Binance USDT-M Futures. Aktuell werden "down"-Signale ignoriert — der Bot handelt nur bei "up"-Predictions.

### Konkrete Implementierungsdetails

**API-Integration:**
- Binance Futures API via `python-binance` oder `ccxt` (bereits im Projekt)
- USDT-M Futures (nicht Coin-M): `client.futures_create_order(symbol='BTCUSDT', side='SELL', type='MARKET', quantity=qty)`
- Leverage per API setzen: `client.futures_change_leverage(symbol='BTCUSDT', leverage=2)`

**Architektur-Aenderungen:**
1. **Neuer Exchange-Adapter:** `BinanceFuturesAdapter` neben bestehendem `BinanceAdapter` (Spot)
2. **Strategie erweitern:** `PredictionStrategy._process_predictions()` muss bei `direction="down"` + Confidence >= 65% eine Short-Position oeffnen
3. **Position-Tracking:** `PredictionPosition` um `side: Literal["long", "short"]` erweitern
4. **Risk-Management:** Maintenance-Margin ueberwachen, Liquidationspreis berechnen
5. **Funding-Rate beachten:** Alle 8h faellt eine Funding-Fee an (kann positiv oder negativ sein)

**Minimum-Anforderungen:**
- BTCUSDT Futures: Minimum Notional = 100 USDT
- Bei 454 USDT und 2x Leverage: Positionsgroesse bis 908 USDT moeglich
- Neue Accounts (<30 Tage): Max. 20x Leverage

**Fee-Struktur:**
- Maker: 0.02%, Taker: 0.05% (Standard-Tier)
- 10% Rabatt bei BNB-Zahlung
- Funding Rate: Alle 8h, durchschnittlich ~0.01% (kann bei Extremen auf 0.1%+ steigen)

### Akademische/praktische Evidenz

- **Erfaniaa/binance-futures-trading-bot** (GitHub, 1.5k+ Stars): Multi-strategischer Futures-Bot mit Long/Short zeigt praxistaugliche Implementierung.
- **Cogent Economics & Finance (2025):** Deep Q-Network fuer BTC-Trading mit Short-Positionen zeigt verbesserte risikobereinigte Renditen gegenueber Long-Only.
- **Symmetrische Signale:** Ein binaerer Klassifikator liefert theoretisch fuer Short genauso gute Signale wie fuer Long — die Accuracy ist identisch.
- **Praxis-Warnung:** Short-Positionen in einem langfristig bullishen Asset (BTC) tragen ein strukturelles Risiko. Historisch steigt BTC langfristig, was Shorts systematisch benachteiligt.

### Relevanz fuer dieses Projekt

- **Pro:** Verdoppelung der Trading-Signale ohne zusaetzliches Modell. Die "down"-Predictions existieren bereits und werden verschwendet. Bei 72h-Halteperiode sind Funding-Kosten ueberschaubar (~0.09% total bei 0.01%/8h).
- **Contra:** Futures-Account muss separat aktiviert werden. Liquidationsrisiko bei Leverage. Bei nur 454 USDT Kapital ist die Margin duenn. Regulatorische Unsicherheit (Futures-Verbot in einigen Laendern).
- **Empfehlung:** Vielversprechendste Erweiterung (ROI/Aufwand). Start mit 1x Leverage (kein Hebel), nur BTCUSDT.

### Risiken und Fallstricke

- **Liquidationsrisiko:** Bei 2x Leverage und 50% Gegenbewegung → Totalverlust. Bei 1x Leverage kein Liquidationsrisiko.
- **Funding-Kosten:** In starken Bullmaerkten zahlen Shorts bis zu 0.1%/8h (= 0.9%/72h). Frisst den Gewinn auf.
- **Regulatorisch:** Binance Futures nicht in allen Laendern verfuegbar (CH: aktuell ja, aber unsicher)
- **Strukturelles Bias:** BTC steigt langfristig — Shorts gegen den Trend sind statistisch benachteiligt
- **Komplexitaet:** Futures-Logik (Margin, Liquidation, Funding) ist deutlich komplexer als Spot

### Geschaetzter Aufwand

**5-7 Tage** (Futures-Adapter: 2-3d, Strategie-Erweiterung: 1-2d, Risk-Management: 1d, Testing: 1d)

---

## A3: Mean-Reversion Gegenstrategie

### Was es ist

Ein separates ML-Modell, das erkennt, wann der Markt in einer Range (Seitwaertsphase) ist, und dann eine Mean-Reversion-Strategie faehrt: kaufen an der Untergrenze, verkaufen an der Obergrenze. Komplementaer zur bestehenden Trend-Prediction-Strategie.

### Konkrete Implementierungsdetails

**Zwei-Stufen-Architektur:**

1. **Regime-Detektor (Stufe 1):** Klassifiziert den Markt als "trending" oder "ranging"
   - **Features:** ADX (Average Directional Index), Bollinger Band Width, ATR-Ratio, Hurst-Exponent
   - **Modell:** Hidden Markov Model (HMM) mit `hmmlearn` Library oder LightGBM-Klassifikator
   - Alternativ: Regelbasiert (ADX < 25 = Range, ADX > 25 = Trend)

2. **Mean-Reversion-Trader (Stufe 2):** Aktiv nur wenn Regime = "ranging"
   - **Entry:** RSI < 30 oder Preis am unteren Bollinger Band → Kauf
   - **Exit:** RSI > 70 oder Preis am oberen Bollinger Band → Verkauf
   - **Oder ML-basiert:** Zweites LightGBM-Modell trainiert nur auf Range-Phasen

**Libraries:**
- `hmmlearn` fuer Hidden Markov Models (Regime Detection)
- `ta` oder `pandas-ta` fuer technische Indikatoren (bereits vorhanden)
- `lightgbm` fuer zweites Modell (bereits vorhanden)

**Integration:**
- Neues Modul `src/crypto_bot/prediction/regime_detector.py`
- Neues Modul `src/crypto_bot/strategies/mean_reversion.py`
- `PredictionStrategy` erhaelt einen Switch: Trend-Modus vs. Range-Modus

### Akademische/praktische Evidenz

- **QuantPedia (2024):** "Revisiting Trend-following and Mean-reversion Strategies in Bitcoin" — Mean Reversion in BTC funktioniert, aber weniger zuverlaessig als Trend-Following. Kombiniert (50/50 Blend) erreichten sie einen Sharpe Ratio von 1.71.
- **MDPI Mathematics (2025):** Bayesian vs. Evolutionary Optimization zeigt, dass Mean-Reversion-Strategien bei BTC -1% bis -8% Underperformance liefern, waehrend Trend-Following +13% bis +37% bringt. **Wichtig: Mean Reversion allein underperformt.**
- **Akash Kumar (Medium/GitHub, 2025):** CryptoMarket Regime Classifier mit HMM + LSTM erreicht brauchbare Regime-Erkennung.
- **Stoic.ai (2025):** Mean Reversion mit BTC-neutralem Residual erzielte Sharpe ~2.3, aber nur als Ergaenzung zu Momentum.

### Relevanz fuer dieses Projekt

- **Pro:** Koennte die inaktiven Phasen (wenn Prediction "down" sagt) produktiv nutzen. Diversifiziert die Strategie-Typen.
- **Contra:** BTC verbringt weniger Zeit in klar definierten Ranges als Altcoins. Regime-Erkennung ist schwierig und fehleranfaellig. Hohe Komplexitaet fuer marginalen Mehrwert. Akademische Evidenz zeigt, dass Mean Reversion allein bei BTC underperformt.
- **Empfehlung:** Niedrige Prioritaet. Mean Reversion funktioniert besser bei Altcoins und auf hoeheren Timeframes. Fuer BTC 1h ist Trend-Following ueberlegen.

### Risiken und Fallstricke

- **Regime-Fehlklassifikation:** Wenn der Detektor einen Trend als Range misinterpretiert, kauft die Mean-Reversion-Strategie in einen Abwaertstrend → grosse Verluste
- **Whipsaw:** BTC-Preise koennen schnell von Range in Trend wechseln
- **Ueberoptimierung:** Zwei separate Modelle (Regime + Trading) verdoppeln das Overfitting-Risiko
- **Begrenzte Trainings-Samples:** Range-Phasen sind seltener als Trend-Phasen bei BTC

### Geschaetzter Aufwand

**7-10 Tage** (Regime-Detektor: 3-4d, Mean-Reversion-Strategie: 2-3d, Integration + Backtesting: 2-3d)

---

## A4: Grid + Prediction Hybrid

### Was es ist

Kombination der bestehenden Grid-Trading-Strategie (Code existiert in `grid_trading.py`) mit der Prediction-Strategie. Die Grid-Strategie laeuft nur waehrend predicted-up Phasen und wird bei "down"-Predictions pausiert.

### Konkrete Implementierungsdetails

**Architektur:**

1. **Prediction-Layer (bestehend):** LightGBM liefert stuendlich "up"/"down" mit Confidence
2. **Grid-Steuerung (neu):**
   - Bei `direction="up"` + Confidence >= 65%: Grid aktivieren
   - Grid-Grenzen dynamisch setzen: `lower = current_price * 0.97`, `upper = current_price * 1.03` (3% Range)
   - Bei `direction="down"`: Grid deaktivieren, offene Grid-Positionen schliessen
3. **Grid-Konfiguration fuer BTC 1h:**
   - 5-10 Grid-Levels (nicht zu viele bei 454 USDT)
   - Geometric Spacing (bereits implementiert)
   - Investment pro Level: ~45-90 USDT

**Bestehender Code:**
- `GridConfig` und `GridStrategy` existieren vollstaendig in `grid_trading.py`
- Unterstuetzt Arithmetic und Geometric Spacing
- `StrategyFactory`-Pattern fuer einfache Integration

**Neuer Code:**
- `HybridGridPredictionStrategy` als Wrapper
- Schaltet zwischen Grid-Trading (up-Phase) und Inaktivitaet (down-Phase) um
- Grid-Reset wenn Prediction-Richtung wechselt

### Akademische/praktische Evidenz

- **GoodCrypto Case Study (2025):** 180% APR mit Grid-Bot bei flachem BTC-Kurs ueber 5 Monate. Grid-Trading ist nachweislich profitabel in Seitwaertsmaerkten.
- **Dynamic Grid Trading (arXiv, 2025):** DGT-Strategie zeigte IRR von 60-70% bei deutlich besserem MDD als Buy-and-Hold (50% vs 80% Drawdown).
- **Zignaly Guide (2025):** Grid-Trading "thrives in sideways markets" — genau dort, wo Trend-Prediction wenig nutzt.
- **Hybrid AI Trading (EmergentMind, 2025):** Kombination aus ML-Prediction und regelbasiertem Trading zeigt bessere risikobereinigte Renditen als rein ML-basierte Ansaetze.

### Relevanz fuer dieses Projekt

- **Pro:** Grid-Code existiert bereits. Nutzt die "up"-Phasen effizienter als eine einzige Position. Generiert zusaetzliche Gewinne durch Micro-Trades innerhalb der Halteperiode.
- **Contra:** 454 USDT sind knapp fuer sinnvolles Grid-Trading (mindestens 5 Levels a 90 USDT = 450 USDT). Grid und Prediction koennen sich widersprechen: Grid verkauft bei Anstieg, Prediction haelt.
- **Empfehlung:** Interessant, aber erst mit mehr Kapital (~1'000+ USDT). Bei 454 USDT waere das Grid nur 3-4 Levels breit, was wenig Sinn macht.

### Risiken und Fallstricke

- **Kapitalknappheit:** Grid benoetigt vorgehaltenes Kapital auf allen Levels. Bei 454 USDT und 5 Levels sind nur ~90 USDT pro Level verfuegbar — nach Fees bleibt kaum Gewinn.
- **Prediction-Lag:** Grid aktivieren/deaktivieren basierend auf stuendlichen Predictions kann zu spaet kommen
- **Grid-Verluste im Breakout:** Wenn der Preis die Grid-Range nach unten durchbricht waehrend einer falsch-positiven "up"-Prediction
- **Komplexitaet:** Zwei Strategien gleichzeitig zu managen erhoeht die Fehlerquellen erheblich

### Geschaetzter Aufwand

**4-6 Tage** (Hybrid-Wrapper: 2d, Grid-Parameter-Optimierung: 1-2d, Backtesting: 1-2d)

---

## A5: DCA mit ML-Timing

### Was es ist

Dollar Cost Averaging (regelmaessiges Kaufen zu festen Zeitpunkten) kombiniert mit ML-basiertem Timing: Der Bot kauft nicht blind, sondern verstaerkt oder reduziert die DCA-Kaeufe basierend auf dem LightGBM-Signal. Bei hoher "up"-Confidence wird mehr gekauft, bei "down" wird pausiert oder weniger gekauft.

### Konkrete Implementierungsdetails

**Strategie-Varianten:**

1. **ML-gefilterte DCA:** Fester DCA-Rhythmus (z.B. taeglich 10 USDT), aber ueberspringen wenn Prediction = "down"
2. **Confidence-gewichtete DCA:** Basis 10 USDT/Tag, multipliziert mit Confidence-Faktor:
   - Confidence 90% up: 15 USDT kaufen (1.5x)
   - Confidence 70% up: 10 USDT kaufen (1.0x)
   - Confidence 60% down: 5 USDT kaufen (0.5x)
   - Confidence 80% down: 0 USDT (pausieren)
3. **Fear-basierte DCA:** Zusaetzlich Fear & Greed Index einbeziehen — bei "Extreme Fear" + ML "up" aggressiver kaufen

**Implementierung:**
- Neues Modul: `src/crypto_bot/strategies/dca_ml_strategy.py`
- DCA-Schedule (Intervall, Betrag)
- ML-Filter (nutzt bestehende PredictionPipeline)
- Confidence-Multiplikator
- Akkumulations-Tracking (Durchschnittskaufpreis)

**APIs/Libraries:**
- Fear & Greed Index: `alternative.me/crypto/fear-and-greed-index/` (kostenlose API, bereits integriert)
- Bestehende `PredictionPipeline` fuer ML-Signale
- Kein neues Modell noetig

### Akademische/praktische Evidenz

- **SpotedCrypto Backtests (2026):** 5-Jahres BTC DCA lieferte 202% Return. Fear-basierte DCA (kaufen nur bei Fear & Greed Index <= 10) erzielte +1'145%, 99 Prozentpunkte mehr als Buy-and-Hold.
- **BingX Research (2026):** Montags-DCA akkumulierte 14.36% mehr Bitcoin als andere Wochentage — Marktmikrostruktur-Effekt.
- **AlgosOne (2025):** DCA funktioniert auch 2025/2026 robust, insbesondere fuer Kleinanleger. Eliminiert Timing-Risiko.

### Relevanz fuer dieses Projekt

- **Pro:** Niedrigstes Risiko aller vorgeschlagenen Strategien. Funktioniert hervorragend mit kleinem Kapital (454 USDT). LightGBM-Signal als Filter ist ein Gratiszusatz. Ideal fuer langfristigen Vermoegensaufbau.
- **Contra:** Philosophisch anders als aktives Trading — es ist Akkumulation, nicht Spekulation. Generiert kein kurzfristiges P&L. Bei 10 USDT/Tag ist das Kapital in 45 Tagen aufgebraucht.
- **Empfehlung:** Sehr sinnvoll als Ergaenzung, nicht als Ersatz. Kann parallel zum Prediction-Bot laufen mit separatem Kapital.

### Risiken und Fallstricke

- **Kapital-Erschoepfung:** Bei nur 454 USDT ist DCA schnell am Ende. Benoetigt regelmaessige Einzahlungen.
- **Opportunity Cost:** Kapital in DCA steht nicht fuer aktives Trading zur Verfuegung
- **False Confidence:** ML-Filter kann dazu fuehren, dass in Aufwaertsbewegungen zu wenig gekauft wird
- **Steuerliche Komplexitaet:** Viele kleine Kaeufe erzeugen viele Transaktionen

### Geschaetzter Aufwand

**2-3 Tage** (DCA-Strategie: 1d, ML-Integration: 0.5d, Fear & Greed API: 0.5d, Testing: 1d)

---

## A6: Variable Halteperiode

### Was es ist

Statt der fixen 72h-Zeitbarriere sagt ein zusaetzliches ML-Modell (oder eine Erweiterung des bestehenden) die optimale Haltedauer vorher. Beispiel: "Kaufe BTC, halte 24h" vs. "Kaufe BTC, halte 120h" — je nach Marktbedingungen.

### Konkrete Implementierungsdetails

**Ansatz 1: Multi-Horizon Klassifikation**
- Mehrere LightGBM-Modelle fuer verschiedene Horizonte trainieren (12h, 24h, 48h, 72h, 120h)
- Das Modell mit der hoechsten Confidence bestimmt die Halteperiode
- Einfach zu implementieren, aber ressourcenintensiv (5 Modelle)

**Ansatz 2: Regression statt Klassifikation**
- Ein LightGBM-Regressionsmodell sagt den erwarteten Return fuer verschiedene Horizonte vorher
- Target: `max_return_within_window` — der maximale Return innerhalb von z.B. 120h
- Libraries: `lightgbm.LGBMRegressor` (statt `LGBMClassifier`)

**Ansatz 3: Quantil-Regression (teilweise vorhanden)**
- Das Projekt hat bereits `q10`, `q50`, `q90` im `PredictionResult`
- Erweiterung: Quantil-Regression ueber verschiedene Horizonte
- Exit wenn `q50` das Maximum erreicht oder `q10` negativ wird

**Ansatz 4: Survival Analysis**
- Modelliert die Wahrscheinlichkeit, dass der Trade nach X Stunden noch profitabel ist
- Libraries: `lifelines` oder `scikit-survival`
- Exit wenn die Survival-Wahrscheinlichkeit unter einen Schwellenwert faellt

### Akademische/praktische Evidenz

- **Frontiers in AI (2025):** Multi-Horizon-Predictions zeigen, dass kuerzere Horizonte (1-24h) hoehere Accuracy haben als laengere (72h+).
- **Springer Nature (2025):** ML-Strategie hielt BTC fuer 1'057 Tage (vs. 2'083 bei GPT), wobei kuerzere Halteperioden bessere risikobereinigte Renditen lieferten.
- **LightGBM Regression (2025, ScienceDirect):** Feature-Engineering (Slope-Ratios, EMA-Differenzen) verbessert die Vorhersagegenauigkeit fuer Preisbewegungen deutlich.

### Relevanz fuer dieses Projekt

- **Pro:** Fixe 72h sind ein Kompromiss — manchmal waere ein frueherer Exit besser, manchmal ein spaeterer. Quantil-Regression-Infrastruktur existiert bereits (q10/q50/q90).
- **Contra:** Deutlich hoehere Komplexitaet. Multi-Horizon-Training verdoppelt die Retraining-Zeit. Regression ist schwieriger zu evaluieren als Klassifikation.
- **Empfehlung:** Mittlere Prioritaet. Einfachster Ansatz (Ansatz 3: bestehende Quantil-Regression) ist mit geringem Aufwand machbar.

### Risiken und Fallstricke

- **Regressions-Noise:** Finanzielle Zeitreihen sind extrem verrauscht
- **Overfitting:** Mehr Modelle / komplexere Targets erhoehen das Risiko
- **Retraining-Last:** 5 Modelle statt 1 auf e2-small VM (2 vCPU, 2 GB RAM) problematisch
- **Feedback-Loop:** Variable Halteperiode aendert die Trainings-Labels retroaktiv

### Geschaetzter Aufwand

**2-3 Tage** (Ansatz 3, einfach) | **5-8 Tage** (Ansatz 1/2, komplett)

---

## Zusammenfassung und Priorisierung

| ID | Strategie | Aufwand | Risiko | Potenzial | Empfehlung |
|----|-----------|---------|--------|-----------|------------|
| **A2** | Short-Trading (Futures) | 5-7d | Mittel | Hoch | **Prio 1** — Verdoppelt Signalnutzung |
| **A5** | DCA mit ML-Timing | 2-3d | Niedrig | Mittel | **Prio 2** — Geringster Aufwand, sicherste Strategie |
| **A6** | Variable Halteperiode | 2-3d* | Mittel | Mittel | **Prio 3** — *Einfacher Ansatz via bestehende Quantile |
| **A4** | Grid + Prediction Hybrid | 4-6d | Mittel | Mittel | **Prio 4** — Grid-Code existiert, aber Kapital zu knapp |
| **A1** | Multi-Coin (1h) | 3-5d | Hoch | Mittel | **Prio 5** — Kapital zu knapp fuer 18 Coins |
| **A3** | Mean-Reversion | 7-10d | Hoch | Niedrig | **Prio 6** — Evidenz schwach fuer BTC |

**Kernempfehlung:** Mit ~454 USDT Kapital sind A2 (Short via Futures, mit 1x Leverage) und A5 (DCA mit ML-Filter) die vielversprechendsten Erweiterungen. A6 lohnt sich als schneller Test mit der bereits vorhandenen Quantil-Regression. A1, A3 und A4 werden erst mit signifikant mehr Kapital (>2'000 USDT) sinnvoll.
