# D) Risiko-Management & Portfolio — Vertiefte Recherche

> Zurueck zur Uebersicht: [erweiterungsmoeglichkeiten.md](erweiterungsmoeglichkeiten.md)

**Datum:** 2026-04-06 (aktualisiert 2026-04-07)
**Kontext:** CryptoTrader 3.0 — BTC-only, ~454 USDT, Binance Mainnet, 72h Zeitbarriere (kein SL/TP), Confidence >= 65%, Positionsgroesse 25-100% skaliert

> **Status-Update 2026-04-07:** D1 (Kelly Criterion) und D4 (Drawdown Protection) wurden am 2026-04-06 implementiert und auf die GCP VM deployed. Siehe Story `20260406220000-five-quick-wins-implementation.md`.

---

## D1: Kelly Criterion aktivieren — UMGESETZT 2026-04-06

### Was es ist

Das Kelly-Kriterium berechnet die mathematisch optimale Positionsgroesse zur Maximierung des langfristigen geometrischen Kapitalwachstums. Die Formel wurde 1956 von John L. Kelly Jr. bei Bell Labs entwickelt.

**Formel (vereinfacht fuer Trading)**:

```
Kelly% = W - (1 - W) / R

Wobei:
  W = Win-Rate (Gewinnwahrscheinlichkeit)
  R = Win/Loss-Ratio (durchschnittlicher Gewinn / durchschnittlicher Verlust)
```

**Beispiel mit aktuellen Bot-Daten** (Walk-Forward Backtest: 55.5% WR):

```
Angenommen: W = 0.555, avg_win = 2.0%, avg_loss = 1.5%
R = 2.0 / 1.5 = 1.333

Kelly% = 0.555 - (1 - 0.555) / 1.333
       = 0.555 - 0.334
       = 0.221 (22.1%)

Half-Kelly = 11.05%
Quarter-Kelly = 5.53%
```

Bei 454 USDT Kapital und Quarter-Kelly waere die maximale Positionsgroesse ~25 USDT pro Trade.

### Konkrete Implementierungsdetails

Der `KellySizer` existiert bereits in `src/crypto_bot/risk/position_sizer.py` (Zeilen 159-270). Er ist vollstaendig implementiert mit:

- Konfigurierbarer Kelly-Fraktion (Half-Kelly default, Quarter-Kelly empfohlen)
- Cap bei 25% des Kapitals (Zeile 228)
- Validierung von Win-Rate und Win/Loss-Ratio

**Aktivierung erfordert**:
1. Trade-History auswerten: Win-Rate und durchschnittlichen Gewinn/Verlust aus abgeschlossenen Trades berechnen
2. `_calculate_position_size()` in `prediction_strategy.py` erweitern, um `KellySizer.calculate_kelly()` als zusaetzlichen Skalierungsfaktor einzubauen
3. Rolling-Window fuer die Statistiken (z.B. letzte 30-50 Trades) statt Gesamthistorie
4. Minimum-Stichprobengroesse definieren (z.B. >= 20 Trades), darunter Fallback auf aktuelle Confidence-Skalierung

**Integration in bestehenden Code**:
```
# Pseudo-Code
kelly_pct = kelly_sizer.calculate_kelly(win_rate, avg_win, avg_loss)
kelly_scale = float(kelly_pct) / float(max_per_coin_pct)  # Normalisieren
combined_scale = min(confidence_scale * kelly_scale, 1.0)
```

### Akademische/praktische Evidenz

- **Akademisch**: Kelly (1956) bewies mathematisch, dass diese Strategie das geometrische Wachstum maximiert. Thorp (1962, 2006) validierte dies empirisch im Blackjack und an der Boerse.
- **Praktische Evidenz**: Professionelle Trader (Citadel, Renaissance Technologies) nutzen modifizierte Kelly-Varianten. Die meisten verwenden Fractional Kelly (1/4 bis 1/2), weil Full Kelly zu aggressive Schwankungen produziert (~5x hoehere Drawdowns als Half-Kelly).
- **Krypto-spezifisch**: Bei Bitcoins 30-45% annualisierter Volatilitaet (2024-2025) empfehlen aktuelle Analysen (Medium, Jan 2026) ausdruecklich Quarter-Kelly. Bei einem 30%-Drop von Bitcoin resultiert Quarter-Kelly in nur ~7.5% Portfolio-Verlust statt 30%.

### Relevanz fuer dieses Projekt

**Hoch**, aber mit Einschraenkungen:

- **Pro**: Existiert bereits im Code, nur Aktivierung noetig. Ersetzt die willkuerliche 25-100% Confidence-Skalierung durch eine mathematisch fundierte Methode.
- **Contra -- Kleines Kapital**: Bei 454 USDT und Quarter-Kelly (~5.5%) resultiert eine Positionsgroesse von ~25 USDT. Binance hat ein Minimum von 10 USDT pro Order, was erfuellt ist. Aber die Granularitaet ist gering -- der Unterschied zwischen "aggressiv" und "konservativ" betraegt nur wenige USDT.
- **Contra -- Statistische Unsicherheit**: Bei 55.5% Win-Rate braucht man mindestens ~100 Trades fuer eine stabile Kelly-Schaetzung. Mit 1h-Retraining und BTC-only ergeben sich wenige Trades pro Woche.
- **Empfehlung**: Half-Kelly als Obergrenze, Confidence-Skalierung als Gewichtung innerhalb dieses Rahmens beibehalten. Kelly bestimmt "wie viel maximal", Confidence bestimmt "wie viel innerhalb dieses Maximums".

### Risiken und Fallstricke

1. **Ueberschaetzung der Edge**: Wenn Win-Rate oder Win/Loss-Ratio ueberschaetzt werden, schlaegt Kelly zu grosse Positionen vor. Bei kleinem Kapital kann dies fatale Folgen haben.
2. **Nicht-stationaere Maerkte**: Die Kelly-Formel setzt stabile Wahrscheinlichkeiten voraus. Krypto-Maerkte aendern ihr Regime haeufig (Bull/Bear/Range). Rolling-Window mildert dies teilweise.
3. **Korrelierte Bets**: Kelly gilt fuer unabhaengige Wetten. Bei 72h-Halteperiode koennten sich Positionen ueberlappen -- die effektive Exposition ist dann hoeher als Kelly empfiehlt.
4. **Minimum Trade Size**: Bei sehr negativem Kelly (kein Edge) gibt die Formel korrekt 0 zurueck -- das ist gewollt und ein Feature, kein Bug.

### Geschaetzter Aufwand

**1-2 Tage** → **Tatsaechlich: 0.5 Tage (als Teil des 5-Quick-Wins Pakets)**

### Umsetzung (2026-04-06)

- Quarter-Kelly (fraction=0.25) als Default — konservativ fuer 454 USDT
- `_get_trade_stats()` berechnet Win-Rate/Avg-Win/Avg-Loss aus Rolling 50 Trades
- Fallback auf Confidence-Skalierung bei < 20 Trades (kelly_min_trades)
- Kelly bestimmt **Maximum**, Confidence skaliert **innerhalb** des Rahmens
- Backtest: MaxDD sinkt von 98.9% auf 13.7% (in Kombination mit D4)
- Config-Felder: `kelly_enabled`, `kelly_fraction`, `kelly_min_trades`, `kelly_lookback_trades`
- Dateien: `prediction_strategy.py` (Integration), `prediction_config.py` (Config)

---

## D2: Dynamischer Confidence-Threshold

### Was es ist

Statt eines fixen Confidence-Schwellenwerts (aktuell 65%) wird der Threshold dynamisch an die Marktvolatilitaet angepasst. In hochvolatilen Phasen wird ein hoeherer Schwellenwert verlangt (konservativeres Trading), in ruhigen Phasen ein niedrigerer (mehr Trades, da geringeres Risiko).

**Formel**:

```
threshold_dynamic = base_threshold + alpha * (current_vol / avg_vol - 1)

Wobei:
  base_threshold = 0.65 (aktueller Fixwert)
  alpha = Sensitivitaetsfaktor (z.B. 0.10)
  current_vol = aktuelle Volatilitaet (z.B. ATR(14) oder Realized Vol)
  avg_vol = langfristiger Volatilitaetsdurchschnitt (z.B. 50-Bar SMA)

Beispiel:
  Volatilitaet 50% ueber Durchschnitt: threshold = 0.65 + 0.10 * 0.5 = 0.70
  Volatilitaet 30% unter Durchschnitt: threshold = 0.65 + 0.10 * (-0.3) = 0.62
```

### Konkrete Implementierungsdetails

1. **Volatilitaets-Berechnung**: ATR(14) aus den 1h-Daten berechnen und mit einem 50-Bar SMA normalisieren. Die Daten sind bereits im Pipeline-Code verfuegbar (Features werden ohnehin berechnet).

2. **Threshold-Grenzen setzen**: Min/Max-Grenzen sind essentiell:
   - Minimum: 0.55 (unter 55% ist die Win-Rate statistisch kaum besser als Zufall)
   - Maximum: 0.80 (ueber 80% werden fast keine Trades mehr ausgefuehrt)

3. **Integration in `prediction_strategy.py`**:
   - In `_process_predictions()` den dynamischen Threshold berechnen
   - `self._config.min_confidence` als Basis, nicht als fixen Wert verwenden
   - ATR-Daten aus dem letzten Retraining-Zyklus uebernehmen

4. **Logging**: Den aktuellen dynamischen Threshold in jedem Zyklus loggen fuer spaetere Analyse

### Akademische/praktische Evidenz

- **MDPI-Paper (2025)**: "Machine Learning Analytics for Blockchain-Based Financial Markets: A Confidence-Threshold Framework" erreichte 82.68% Direction-Accuracy auf ausgefuehrten Trades bei 11.99% Marktabdeckung. Das Paper zeigt, dass adaptive Thresholds die Trade-Qualitaet signifikant verbessern.
- **TradingView/PhenLabs (2025)**: Adaptive ML Trading System nutzt ATR(14)/SMA(50) als Volatilitaets-Regime-Indikator, der Overbought/Oversold-Schwellenwerte dynamisch anpasst.
- **Allgemein**: Volatilitaets-adjustierte Confidence-Schwellenwerte sind in institutionellen Quant-Firmen Standard. Die Logik: In volatilen Maerkten ist das Signal-zu-Rausch-Verhaeltnis schlechter, daher braucht man staerkere Signale.

### Relevanz fuer dieses Projekt

**Mittel-Hoch**:

- **Pro**: Der Bot handelt bereits mit Confidence-basiertem Filtering. Eine Volatilitaets-Anpassung ist eine natuerliche Evolution. BTC-Volatilitaet schwankt stark (30-45% annualisiert in 2024-2025), was den dynamischen Threshold wertvoll macht.
- **Pro**: Koennte die Win-Rate verbessern, indem in volatilen Phasen nur die staerksten Signale gehandelt werden.
- **Contra**: Reduziert die Anzahl Trades in volatilen Phasen -- genau dann, wenn die groessten Gewinne moeglich sind. Es besteht die Gefahr, profitable Opportunities zu verpassen.
- **Contra -- Kleines Kapital**: Bei ohnehin wenigen Trades (BTC-only, 1h) koennte eine weitere Filterung zu zu wenigen Trades fuehren, was die statistische Aussagekraft mindert.
- **Empfehlung**: Erst im Backtest validieren. Vergleich: dynamischer Threshold vs. fix 65% ueber 12+ Monate historische Daten. Alpha-Parameter via Grid-Search optimieren.

### Risiken und Fallstricke

1. **Overfitting**: Der Alpha-Parameter und die Volatilitaets-Fenster sind zusaetzliche Hyperparameter, die ueberangepasst werden koennen.
2. **Verpasste Chancen**: Hochvolatile Phasen (z.B. nach wichtigen News) koennen die besten Trades bieten -- ein zu hoher Threshold filtert diese heraus.
3. **Lag-Problem**: Volatilitaets-Indikatoren sind rueckblickend. Ein ploetzlicher Volatilitaetssprung wird erst mit Verzoegerung erkannt.
4. **Wechselwirkung mit Kelly**: Falls Kelly und dynamischer Threshold gleichzeitig aktiv sind, reduzieren beide die Positionsgroesse in volatilen Phasen -- das kann zu exzessiver Vorsicht fuehren.

### Geschaetzter Aufwand

**2-3 Tage**

- 0.5 Tage: ATR-basierte Volatilitaets-Normalisierung implementieren
- 0.5 Tage: Dynamischen Threshold in `_process_predictions()` einbauen
- 1-2 Tage: Backtest-Infrastruktur erweitern und Grid-Search ueber Alpha/Min/Max Parameter
- Optional: Dashboard-Visualisierung (Threshold-Verlauf vs. Volatilitaet)

---

## D3: Correlation-aware Sizing

### Was es ist

Bei einem Multi-Coin-Portfolio wird die Positionsgroesse nicht nur pro Asset isoliert bestimmt, sondern unter Beruecksichtigung der Korrelationen zwischen den gehaltenen Assets. Hoch korrelierte Positionen (z.B. BTC und ETH, Korrelation ~0.85) werden zusammen als ein Risiko-Cluster behandelt und die Gesamtexposure entsprechend reduziert.

**Formel (Portfolio-Varianz-basiert)**:

```
Portfolio_Var = sum(w_i^2 * sigma_i^2) + 2 * sum(w_i * w_j * sigma_i * sigma_j * rho_ij)

Wobei:
  w_i = Gewicht von Asset i
  sigma_i = Volatilitaet von Asset i
  rho_ij = Korrelation zwischen Asset i und j

Vereinfachte Reduktion:
  Wenn Korrelation(A, B) > 0.7:
    max_combined_exposure(A + B) = max_single_exposure * (1 + (1 - rho))
    z.B. rho = 0.85: max_combined = max_single * 1.15 (statt 2x)
```

### Konkrete Implementierungsdetails

1. **Korrelationsmatrix berechnen**: Rolling-Window (z.B. 720h = 30 Tage) ueber 1h-Returns der gehaltenen Coins. Die Daten werden bereits fuer Cross-Asset Features geladen.

2. **Korrelations-Cluster identifizieren**: Assets mit Korrelation > 0.7 gruppieren. Typische Crypto-Cluster:
   - BTC-Cluster: BTC, ETH (rho ~0.85), SOL (rho ~0.75)
   - Alt-Cluster: DOGE, SHIB (rho ~0.80)
   - DeFi-Cluster: LINK, AAVE (rho ~0.70)

3. **Exposure-Reduktion pro Cluster**: Die kumulative Exposure eines Clusters darf die max_per_coin_pct nicht wesentlich ueberschreiten, gewichtet nach Korrelation.

4. **Integration**: In `_process_predictions()` vor der Positionseroeffnung die aktuelle Cluster-Exposure pruefen.

### Akademische/praktische Evidenz

- **Markowitz (1952)**: Modern Portfolio Theory -- die Grundlage. Diversifikation reduziert Risiko nur bei imperfekter Korrelation.
- **Crypto-spezifisch (2025)**: CNBC-Analyse (Dezember 2025) zeigt, dass institutionelle Crypto-Investoren zunehmend Korrelationsmatrizen fuer Position Sizing nutzen. Krypto-Assets sind generell hoch korreliert (BTC dominiert), was Diversifikationsvorteile limitiert.
- **Breaking Alpha (2025)**: Korrelations-Risikomanagement ueber multiple Algorithmen erfordert explizite Beruecksichtigung von Korrelationsinstabilitaet -- Korrelationen steigen in Krisenzeiten sprunghaft an (Contagion-Effekt).
- **Stress-Test-Empfehlung**: Gleichzeitiger 30%-Drawdown ueber alle korrelierte Assets simulieren (Stoic.ai Framework).

### Relevanz fuer dieses Projekt

**Aktuell keine -- erst bei Multi-Coin**:

- Der Bot handelt derzeit nur BTC. Korrelations-aware Sizing ist irrelevant fuer ein Single-Asset-Portfolio.
- **Wird relevant bei Reaktivierung von Multi-Coin (Idee A1)**. Die Infrastruktur (18 Coins in `ALL_PREDICTION_COINS`) existiert bereits.
- **Wichtig zu wissen**: Krypto-Korrelationen sind nicht stabil. In Bullenmaerkten korreliert alles mit BTC (rho > 0.8), in Baerenmaerkten sogar noch staerker (Flight to BTC). Echte Diversifikation in Krypto ist schwer zu erreichen.

### Risiken und Fallstricke

1. **Instabile Korrelationen**: Korrelationen aendern sich dramatisch zwischen Marktregimen. Eine auf 30-Tage-Daten basierende Matrix kann in einer Krise voellig falsch sein.
2. **Computation-Overhead**: Fuer 18 Coins: 153 Korrelationspaare. Bei stuendlicher Neuberechnung moderat, aber nicht trivial auf einem e2-small VM.
3. **Ueberkompensation**: Zu aggressive Korrelationsreduktion fuehrt dazu, dass bei positiven Signalen fuer korrelierte Assets nur minimal investiert wird -- genau in den Phasen, wo der gesamte Markt steigt.
4. **Illusion der Diversifikation**: In Crypto bewegen sich in Extremsituationen alle Assets zusammen. Korrelations-aware Sizing schuetzt nicht vor systematischem Risiko.

### Geschaetzter Aufwand

**3-5 Tage** (erst sinnvoll bei Multi-Coin-Reaktivierung)

- 1 Tag: Rolling-Korrelationsmatrix implementieren
- 1 Tag: Cluster-Erkennung und Exposure-Logik
- 1 Tag: Integration in Position-Sizing-Pipeline
- 1-2 Tage: Backtesting mit Multi-Coin-Daten

---

## D4: Drawdown Protection aktivieren — UMGESETZT 2026-04-06

### Was es ist

Progressives Reduzieren der Positionsgroesse bei Verlustserien oder wenn der aktuelle Drawdown einen Schwellenwert ueberschreitet. Verhindert, dass der Bot in einer Verlustphase mit voller Groesse weitertradet und den Drawdown vertieft.

**Bereits implementiert in `DynamicPositionSizer`** (Zeilen 402-505 in `position_sizer.py`):

```
Schwellenwerte (aktueller Code):
- Drawdown > 5%: Reduktion beginnt
- Drawdown 10%: Position um 50% reduziert
- Drawdown 15%: Position um 75% reduziert
- Minimum: 25% der normalen Positionsgroesse

Formel: dd_factor = 1 - (current_drawdown_pct * 5)
        dd_factor = max(dd_factor, 0.25)

Volatilitaets-Adjustment (ebenfalls implementiert):
- ATR/avg_ATR > 1.5: Positionsreduktion proportional
- Minimum: 50% der normalen Groesse
```

### Konkrete Implementierungsdetails

Der `DynamicPositionSizer` existiert vollstaendig. Aktivierung erfordert:

1. **DrawdownTracker instanziieren**: In `PredictionStrategy.__init__()` einen `DrawdownTracker` mit dem aktuellen Kapital initialisieren.

2. **Equity-Updates**: Nach jedem Trade-Close `tracker.update(new_equity)` aufrufen.

3. **Position Sizing anpassen**: `_calculate_position_size()` erweitern:
   ```
   metrics = self._drawdown_tracker.get_current_metrics()
   if metrics.current_drawdown_pct > Decimal("0.05"):
       dd_factor = max(Decimal("0.25"), 1 - metrics.current_drawdown_pct * 5)
       size = size * dd_factor
   ```

4. **State Persistence**: DrawdownTracker-State in `get_state()`/`from_state()` serialisieren, damit peak_equity ueber Neustarts erhalten bleibt.

5. **ATR-Daten durchreichen**: `current_atr` und `average_atr` aus dem Pipeline-Output an den Sizer uebergeben.

### Akademische/praktische Evidenz

- **Quantfish Research**: Systematische Studie zeigt, dass Drawdown-basierte Positionsreduktion den Maximum Drawdown um 20-40% reduziert, bei nur 5-15% Einbusse im Gesamtertrag. Das Sharpe-Ratio verbessert sich fast immer.
- **Tradetron (2025)**: Empfiehlt ein gestaffeltes System: -10% Position bei 5% DD, -25% bei 10% DD, -50% bei 15% DD. Aehnlich dem bereits implementierten Code.
- **QuantifiedStrategies.com**: Maximum-Drawdown-basiertes Position Sizing ist eine der robustesten Methoden, da sie automatisch auf Regime-Wechsel reagiert, ohne diese explizit erkennen zu muessen.
- **Prop-Trading-Firmen**: Praktisch alle professionellen Prop-Trading-Firmen nutzen zwingend Drawdown-Protection. Typische Regel: Bei 10% Drawdown halbe Groesse, bei 15% Pause.

### Relevanz fuer dieses Projekt

**Hoch -- Top-Prioritaet zur Aktivierung**:

- **Pro**: Code existiert und ist getestet! Minimaler Implementierungsaufwand.
- **Pro**: Bei 454 USDT Kapital ist jeder Prozentpunkt Drawdown schmerzhaft. Ein 15%-Drawdown = 68 USDT Verlust -- bei kleinem Kapital ist das psychologisch und praktisch relevant.
- **Pro**: Funktioniert unabhaengig von der Signalqualitaet -- auch wenn das ML-Modell temporaer schlecht performt, wird der Schaden begrenzt.
- **Contra**: In Erholungsphasen nach einem Drawdown wird mit reduzierter Groesse getradet, was die Recovery verlangsamt. Aber das ist ein akzeptabler Tradeoff fuer Kapitalschutz.
- **Empfehlung**: Sofort aktivieren mit konservativen Schwellenwerten. Bei 454 USDT sind die absoluten Drawdown-Werte klein genug, dass die Reduktion selten greifen sollte -- aber wenn sie greift, schuetzt sie das Kapital.

### Risiken und Fallstricke

1. **Recovery-Asymmetrie**: Nach einem 20%-Drawdown braucht man 25% Gewinn zur Erholung. Mit reduzierter Positionsgroesse dauert die Recovery noch laenger. Dies ist beabsichtigt (Kapitalschutz > schnelle Recovery).
2. **Whipsaw**: Bei schnellen Drawdown-Recovery-Zyklen (z.B. Flash Crash) kann die Reduktion gerade dann greifen, wenn die besten Einstiegspunkte kommen.
3. **Peak-Equity-Reset**: Wenn der Bot laenger laeuft und der Peak weit zurueckliegt, kann ein normaler Ruecksetzer permanent als "Drawdown" gelten. Empfehlung: Rolling Peak (z.B. 30-Tage-Hoch statt All-Time-High).
4. **State-Verlust bei Neustart**: Ohne korrekte Persistence geht der peak_equity-Wert verloren und der Drawdown wird nach Neustart als 0% berechnet.

### Geschaetzter Aufwand

**1 Tag** → **Tatsaechlich: 0.5 Tage (als Teil des 5-Quick-Wins Pakets)**

### Umsetzung (2026-04-06)

- Peak-Capital Tracking in `_update_drawdown()`, aufgerufen in jedem Tick
- Lineare Reduktion: bei 5% DD → 100%, bei 15% DD → 25% der normalen Groesse
- State wird persistiert (`peak_capital`, `current_drawdown_pct`)
- Kombiniert mit Kelly: `kelly_scale * drawdown_scale * confidence_scale`
- Config-Felder: `drawdown_protection_enabled`, `drawdown_threshold_pct`, `drawdown_max_reduction`
- Backtest: MaxDD von 98.9% auf 13.7% reduziert bei gleichem Signal

---

## D5: Volatility Targeting

### Was es ist

Die Positionsgroesse wird so angepasst, dass die erwartete Portfolio-Volatilitaet konstant bleibt (z.B. 10% annualisiert). In hochvolatilen Phasen wird die Position kleiner, in ruhigen Phasen groesser.

**Formel**:

```
target_vol = 0.10  (10% annualisiert)
current_vol = realized_vol_annualized  (z.B. 20-Tage realized vol)
leverage = target_vol / current_vol

position_size = capital * leverage * max_allocation

Beispiel:
  BTC realized vol = 40% annualisiert
  target_vol = 10%
  leverage = 10% / 40% = 0.25
  Bei 454 USDT und 80% max: position = 454 * 0.25 * 0.80 = 90.80 USDT

  BTC realized vol = 20%:
  leverage = 10% / 20% = 0.50
  position = 454 * 0.50 * 0.80 = 181.60 USDT
```

### Konkrete Implementierungsdetails

1. **Realized Volatility berechnen**: Annualisierte Volatilitaet aus 1h-Returns:
   ```
   hourly_returns = log(close[t] / close[t-1])
   realized_vol = std(hourly_returns, window=336) * sqrt(8760)  # 336h = 14 Tage
   ```
   Alternativ: Exponentially Weighted Moving Average (EWMA) fuer schnellere Reaktion.

2. **Target-Volatilitaet festlegen**: 10% annualisiert ist ein gaengiger Wert fuer moderate Risikotoleranz. Zum Vergleich: S&P 500 hat ~15%, BTC typisch 40-60%.

3. **Leverage-Berechnung**: Cap bei 1.0 (kein Hebel), Floor bei 0.10 (mindestens 10% der normalen Position).

4. **Integration**: In `_calculate_position_size()` den Volatilitaets-Skalierungsfaktor einbauen. Kompatibel mit Confidence-Skalierung (multiplikativ).

5. **Datenquelle**: 1h-Kerzendaten werden bereits fuer das ML-Modell geladen -- keine zusaetzliche API-Abfrage noetig.

### Akademische/praktische Evidenz

- **QuantPedia**: "An Introduction to Volatility Targeting" zeigt, dass Volatility Targeting ueber alle Anlageklassen hinweg die risikoadjustierte Rendite (Sharpe Ratio) verbessert. Der Effekt ist besonders stark in Maerkten mit hoher Volatilitaets-Clusterung -- genau wie Krypto.
- **Man Group (AHL)**: Einer der groessten Managed-Futures-Fonds nutzt Volatility Targeting seit Jahrzehnten. Ihre Forschung zeigt, dass die Methode besonders in Trendmaerkten den Drawdown reduziert.
- **Concretum Group (2025)**: Vergleich von Volatility Targeting vs. Volatility Parity vs. Pyramiding zeigt, dass einfaches Volatility Targeting die robusteste Methode ist -- weniger Hyperparameter, weniger Overfitting-Risiko.
- **Robot Wealth**: Volatilitaet ist "sticky" (autokorreliert), was Realized-Volatility-Schaetzungen zu brauchbaren Prognosen kuenftiger Volatilitaet macht. Das ist die theoretische Grundlage, warum Volatility Targeting funktioniert.
- **Krypto-spezifisch**: Bitcoin Volmex Implied Volatility liegt bei ~50% vs. VIX ~20%. Die Diskrepanz bedeutet, dass Volatility Targeting in Krypto einen staerkeren Effekt hat als bei traditionellen Assets.

### Relevanz fuer dieses Projekt

**Mittel-Hoch**:

- **Pro**: Elegant und robust. Erfordert keinen "Edge" -- funktioniert rein ueber Risikokontrolle. Selbst wenn das ML-Modell nur mittelmassig ist, haelt Volatility Targeting das Risiko konstant.
- **Pro**: Der `DynamicPositionSizer` hat bereits ein ATR-basiertes Volatilitaets-Adjustment implementiert (Zeilen 459-474). Volatility Targeting ist die formalisierte, sauberere Version davon.
- **Contra -- Kleines Kapital**: Bei 454 USDT und einem Leverage-Faktor von 0.25 (BTC Vol = 40%) resultiert eine Position von nur ~90 USDT. Das ist funktional, aber nahe am Minimum.
- **Contra**: In Phasen niedriger Volatilitaet (BTC Vol = 20%) wuerde der Bot groessere Positionen eroeffnen. Niedrige Volatilitaet geht aber oft ploetzlichen Spikes voraus -- die groessere Position traegt dann ein hoeheres Verlustrisiko.
- **Empfehlung**: Volatility Targeting als primaerenPositionsskalierungs-Mechanismus, mit Drawdown Protection als Sicherheitsnetz. Die Kombination ist Standard in professionellen Systemen.

### Risiken und Fallstricke

1. **Volatilitaets-Regime-Wechsel**: Ploetzliche Volatilitaetsspruenge (z.B. Flash Crash, regulatorische News) koennen nicht vorhergesagt werden. Der Bot wuerde in der ruhigen Phase grosse Positionen halten und dann den Spike voll abbekommen.
2. **Mean-Reversion-Falle**: Nach einer hochvolatilen Phase sinkt die Realized Vol langsam. Der Bot vergroessert die Position graduell -- aber wenn die Volatilitaet nochmals sprunghaft steigt, ist man ueberexponiert.
3. **Window-Wahl**: Zu kurz (7 Tage) = zu reaktiv, zu lang (60 Tage) = zu traege. 14-20 Tage ist der akademische Sweet Spot.
4. **Kosten bei kleinen Positionen**: Bei stark reduzierter Position (z.B. 15 USDT) werden Handelsgebuehren (0.1% = 0.015 USDT) prozentual irrelevant, aber das Gewinnpotenzial ist ebenfalls gering.

### Geschaetzter Aufwand

**2-3 Tage**

- 0.5 Tage: Realized Volatility (EWMA oder Rolling) implementieren
- 0.5 Tage: Target-Vol-Skalierungsfaktor in Position Sizing integrieren
- 1 Tag: Backtesting und Parameteroptimierung (target_vol, window)
- 0.5 Tage: Logging und ggf. Dashboard-Integration

---

## D6: Circuit Breaker

### Was es ist

Ein automatischer Schutzmechanismus, der das Trading komplett pausiert, wenn bestimmte Verlustgrenzen ueberschritten werden. Analog zum "Sicherungsschalter" an der Boerse, der bei extremen Kursverlusten den Handel stoppt.

**Bereits vollstaendig implementiert** in `src/crypto_bot/risk/circuit_breaker.py`:

```
Konfigurierbare Trigger (Defaults):
- max_daily_loss_pct: 5% Tagesverlust
- max_consecutive_losses: 5 Verlusttrades in Folge
- max_drawdown_pct: 15% Gesamt-Drawdown
- max_error_rate: 50% Fehlerrate
- cooldown_minutes: 60 Minuten Pause nach Trigger

Features:
- Automatisches Daily Reset um Mitternacht UTC
- Multi-Strategie-Support via CircuitBreakerManager
- Manual Trip/Reset
- Alert-System (Protocol-basiert)
- Vollstaendiges Status-Reporting
```

### Konkrete Implementierungsdetails

Der Circuit Breaker ist production-ready. Aktivierung erfordert:

1. **CircuitBreaker in PredictionStrategy einbinden**:
   ```
   self._circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
       max_daily_loss_pct=Decimal("0.05"),
       max_consecutive_losses=5,
       max_drawdown_pct=Decimal("0.15"),
       cooldown_minutes=120,
   ))
   self._circuit_breaker.set_initial_equity(self._config.total_capital)
   ```

2. **Check vor Trade-Ausfuehrung**: In `_process_predictions()`:
   ```
   if not self._circuit_breaker.is_trading_allowed:
       logger.warning("circuit_breaker_active", status=self._circuit_breaker.get_status())
       return
   ```

3. **Trade-Ergebnis melden**: In `_close_position()`:
   ```
   pnl = close_price * amount - entry_price * amount
   self._circuit_breaker.record_trade(pnl, new_equity)
   ```

4. **Alert-Integration**: Optional mit Telegram/Discord Alerter verbinden.

5. **Dashboard**: Status-Endpoint im API hinzufuegen (Tripped/Active, Cooldown verbleibend).

### Akademische/praktische Evidenz

- **NYSE/CME Circuit Breakers**: Seit dem Flash Crash 1987 gibt es boersenweite Circuit Breakers. Level 1 (7% S&P Drop) pausiert 15 Min, Level 3 (20%) schliesst den Markt fuer den Tag. Das Konzept ist bewiesener Kapitalschutz.
- **3Commas (2025)**: AI Trading Bot Risk Management Guide empfiehlt Circuit Breaker als "non-negotiable" Komponente. Empfehlung: 3-5% Tagesverlustlimit.
- **FourChain (2025)**: Volatilitaets-basierte Circuit Breaker sind Best Practice -- sie reduzieren Positionsgroessen oder stoppen das Trading komplett, wenn Marktbedingungen historische Normen ueberschreiten.
- **ForTraders (2025)**: "Why Most Trading Bots Lose Money" -- fehlende Circuit Breaker werden als einer der Hauptgruende identifiziert, warum Bot-Trader Geld verlieren.

### Relevanz fuer dieses Projekt

**Hoch -- Sicherheitsnetz**:

- **Pro**: Code existiert und ist umfangreich getestet! Aktivierung ist trivial.
- **Pro**: Bei 454 USDT ist 5% Tagesverlust = 22.70 USDT. Das ist eine sinnvolle Schmerzgrenze. 15% Drawdown = 68 USDT -- danach zu pausieren ist vernuenftig.
- **Pro**: Die 72h-Halteperiode bedeutet, dass Verluste sich akkumulieren koennen, bevor eine Position geschlossen wird. Der Circuit Breaker verhindert, dass in einer Verlustphase neue Positionen eroeffnet werden.
- **Contra**: Bei BTC-only und 72h-Haltedauer sind "5 consecutive losses" selten (man hat typisch 1-3 Trades gleichzeitig offen). Die max_consecutive_losses muessen eventuell auf 3 reduziert werden.
- **Empfehlung**: Sofort aktivieren. Die Konfiguration sollte angepasst werden:
  - `max_daily_loss_pct`: 5% (Default beibehalten)
  - `max_consecutive_losses`: 3 (statt 5, wegen weniger Trades)
  - `max_drawdown_pct`: 12% (statt 15%, wegen kleinem Kapital)
  - `cooldown_minutes`: 360 (6 Stunden statt 1 Stunde -- bei 72h-Trades ist 1h zu kurz)

### Risiken und Fallstricke

1. **Zu frueher Trigger**: Bei kleinem Kapital und wenigen Trades kann ein einziger schlechter Trade den Circuit Breaker ausloesen. Beispiel: 454 USDT, eine 80%-Position mit -6% = -21.80 USDT = 4.8% Tagesverlust.
2. **Cooldown-Timing**: Wenn der Circuit Breaker waehrend eines Dips trigert und die Cooldown-Phase genau die Recovery-Phase abdeckt, verpasst man die Erholung.
3. **Interaktion mit Zeitbarriere**: Offene Positionen werden NICHT geschlossen (bewusste Design-Entscheidung). Nur neue Trades werden verhindert. Das bedeutet, bestehende Verlustpositionen laufen weiter.
4. **Daily Reset**: Der automatische Reset um Mitternacht UTC kann dazu fuehren, dass der Bot nach einem katastrophalen Tag sofort wieder tradet. Alternative: kein auto_reset, manueller Reset nach Review.

### Geschaetzter Aufwand

**0.5-1 Tag**

- 0.25 Tage: CircuitBreaker in PredictionStrategy instanziieren und verdrahten
- 0.25 Tage: Trade-Ergebnis-Reporting einbauen
- 0.25 Tage: Konfiguration optimieren und Tests
- Optional: Dashboard-Integration und Alert-System

---

## Zusammenfassung und Priorisierung

| # | Massnahme | Existiert | Aufwand | Impact | Prioritaet |
|---|-----------|-----------|---------|--------|-------------|
| D4 | Drawdown Protection | Ja (Code fertig) | 1 Tag | Hoch -- Kapitalschutz | **1 -- Sofort** |
| D6 | Circuit Breaker | Ja (Code fertig) | 0.5-1 Tag | Hoch -- Sicherheitsnetz | **1 -- Sofort** |
| D1 | Kelly Criterion | Ja (Code fertig) | 1-2 Tage | Mittel -- fundiertes Sizing | **2 -- Bald** |
| D5 | Volatility Targeting | Teilweise (ATR-Adj.) | 2-3 Tage | Mittel-Hoch -- robustes Risiko | **3 -- Naechste Phase** |
| D2 | Dyn. Confidence-Threshold | Nein | 2-3 Tage | Mittel -- bessere Signale | **4 -- Nach Backtest** |
| D3 | Correlation-aware Sizing | Nein | 3-5 Tage | Keine (BTC-only) | **5 -- Erst bei Multi-Coin** |

### Empfohlene Reihenfolge

1. **D4 + D6 zusammen aktivieren** (1.5 Tage): Beide existieren im Code und bieten sofortigen Kapitalschutz. D4 reduziert die Positionsgroesse bei Drawdowns, D6 stoppt das Trading bei extremen Verlusten. Zusammen bilden sie ein mehrstufiges Sicherheitsnetz.

2. **D1 Kelly Criterion** (1-2 Tage): Ersetzt die willkuerliche Confidence-Skalierung durch eine mathematisch fundierte Methode. Quarter-Kelly empfohlen wegen kleinem Kapital und statistischer Unsicherheit.

3. **D5 Volatility Targeting** (2-3 Tage): Formalisiert das bereits vorhandene ATR-Adjustment. Haelt das Portfolio-Risiko konstant unabhaengig von BTC-Volatilitaetsschwankungen.

4. **D2 Dynamischer Threshold** (2-3 Tage): Erst nach Backtest-Validierung implementieren. Risiko des Overfitting und der Trade-Reduktion.

5. **D3 Correlation-aware Sizing**: Zurueckstellen bis Multi-Coin-Trading reaktiviert wird.

### Wichtige Wechselwirkungen

- **D4 + D5 ergaenzen sich**: Volatility Targeting haelt das Risiko konstant, Drawdown Protection greift wenn es trotzdem schiefgeht.
- **D1 + D2 koennen kollidieren**: Beide reduzieren in volatilen Phasen -- zusammen koennen sie die Positionsgroesse auf ein unpraktikables Minimum druecken.
- **D6 ist unabhaengig**: Der Circuit Breaker funktioniert als letzte Verteidigungslinie, egal welche anderen Mechanismen aktiv sind.
- **Gesamtaufwand alle Massnahmen**: ~10-14 Tage (sequentiell), ~7-10 Tage (mit Parallelisierung von Backtests).

---

## Quellen

- [Kelly Criterion for Crypto Traders (Medium, Jan 2026)](https://medium.com/@tmapendembe_28659/kelly-criterion-for-crypto-traders-a-modern-approach-to-volatile-markets-a0cda654caa9)
- [Kelly Criterion in Crypto Trading (OSL Academy)](https://www.osl.com/hk-en/academy/article/what-is-the-kelly-bet-size-criterion-and-how-to-use-it-in-crypto-trading)
- [Kelly Criterion Position Sizing (TradersPost)](https://blog.traderspost.io/article/kelly-criterion-position-sizing-automated-trading)
- [MDPI: Confidence-Threshold Framework for Crypto Price Prediction](https://www.mdpi.com/2076-3417/15/20/11145)
- [Adaptive ML Trading System (PhenLabs/TradingView)](https://www.tradingview.com/script/f11aCUPi-Adaptive-Machine-Learning-Trading-System-PhenLabs/)
- [Volatility Adjusted Position Sizing (Oboe/Modern Systematic Trading)](https://oboe.com/learn/modern-systematic-trading-and-2025-market-strategies-skyev0/volatility-adjusted-position-sizing-modern-systematic-trading-and-2025-market-strategies-3)
- [Introduction to Volatility Targeting (QuantPedia)](https://quantpedia.com/an-introduction-to-volatility-targeting/)
- [Position Sizing: Volatility Targeting vs. Parity vs. Pyramiding (Concretum Group)](https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/)
- [Volatility Targeting Tools (Robot Wealth)](https://robotwealth.com/tradingview-volatility-targeting-tools-cheat-sheet/)
- [AI Trading Bot Risk Management Guide 2025 (3Commas)](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025)
- [Crypto Trading Bot Risk Management (FourChain)](https://www.fourchain.com/trading-bot/crypto-trading-bot-risk-management-strategies/)
- [Reducing Position Sizing During Drawdowns (Quantfish Research)](https://quant.fish/wiki/reducing-position-sizing-during-drawdowns/)
- [Drawdown Management (QuantifiedStrategies)](https://www.quantifiedstrategies.com/drawdown/)
- [Correlation Risk Management Across Multiple Algorithms (Breaking Alpha)](https://breakingalpha.io/insights/correlation-risk-management-multiple-algorithms)
- [Crypto Portfolio Risk Simulation Framework (arXiv, 2025)](https://arxiv.org/html/2507.08915v1)
- [Risk Management Framework for Digital Assets (Stoic.ai)](https://stoic.ai/blog/risk-management-in-crypto-battle-tested-framework-for-protecting-digital-assets/)
