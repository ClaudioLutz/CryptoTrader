# C) Neue Datenquellen & Features — Vertiefte Recherche

> Zurueck zur Uebersicht: [erweiterungsmoeglichkeiten.md](erweiterungsmoeglichkeiten.md)

**Datum:** 2026-04-06 (aktualisiert 2026-04-07)
**Kontext:** CryptoTrader 3.0 — BTC-only, 1h LightGBM, 19 TA-Features + 27 Macro-Features (inkl. Fear&Greed, On-Chain, Cross-Asset)
**Kernproblem:** Standard-TA-Features haben nur ~0.045 Korrelation mit Preisbewegung. Neue, unkorrelierte Datenquellen sind der groesste Hebel.

> **Status-Update 2026-04-07:** C6 (Macro-Daten) und C11 (Cross-Market Signals) wurden am 2026-04-06 implementiert und deployed. 27 neue Features via yfinance (DXY, VIX, US10Y, MSTR, Gold/GLD, SPY). Backtest: bester Total P&L aller Varianten (-82.3% vs -203.3% Baseline).

---

## Uebersicht & Priorisierung

| # | Datenquelle | Kosten/Mt | Aufwand (Tage) | Erwarteter Impact | Empfehlung |
|---|-------------|-----------|----------------|-------------------|------------|
| C1 | Social Sentiment (Twitter/X, Reddit) | $24-240/Mt | 5-8 | Hoch | **Empfohlen** (via LunarCrush) |
| C2 | News Sentiment (news_analysis_3.0) | $0 (eigene Infra) | 3-5 | Mittel-Hoch | **Empfohlen** (Synergie) |
| C3 | Whale Tracking | $0-35/Mt | 3-4 | Mittel | Empfohlen |
| C4 | Liquidation Heatmaps | $28/Mt | 2-3 | Mittel-Hoch | **Empfohlen** |
| C5 | Order Book Depth | $0 | 3-5 | Mittel | Optional |
| C6 | ~~Macro-Daten (DXY, Yields)~~ | $0 | ~~2-3~~ | ~~Mittel-Hoch~~ | **UMGESETZT** |
| C7 | Google Trends | $0 | 1-2 | Niedrig-Mittel | Optional |
| C8 | GitHub Activity | $0 | 1-2 | Niedrig | Nicht empfohlen (BTC) |
| C9 | Stablecoin Supply | $0-39/Mt | 2-3 | Mittel-Hoch | **Empfohlen** |
| C10 | Prediction Markets | $0 | 2-3 | Niedrig-Mittel | Optional |
| C11 | ~~Cross-Market Signals~~ | $0 | ~~2-3~~ | ~~Mittel-Hoch~~ | **UMGESETZT** |

**Top-5 Empfehlungen (nach Impact/Aufwand-Verhaeltnis):**
1. ~~C6 Macro-Daten~~ — **UMGESETZT 2026-04-06** (DXY, VIX, US10Y via yfinance)
2. ~~C11 Cross-Market Signals~~ — **UMGESETZT 2026-04-06** (MSTR, Gold/GLD, SPY)
3. C4 Liquidation Heatmaps — guenstig, stark fuer BTC 1h
4. C2 News Sentiment — eigenes Projekt, kein API-Kostenpunkt
5. C9 Stablecoin Supply — gratis moeglich, akademisch belegt

---

## C1: Social Sentiment — Twitter/X, Reddit, Telegram

### Was es ist
Aggregiertes Sentiment aus Social-Media-Beitraegen ueber Kryptowaehrungen. NLP/LLM-Modelle klassifizieren Posts als bullish/bearish/neutral und erzeugen einen Sentiment-Score. Die Grundidee: Social-Media-Stimmung laeuft der Preisbewegung voraus (oder verstaerkt sie).

### Konkrete APIs und Datenquellen

**X (Twitter) API — Direkt:**
- URL: https://developer.x.com
- Free Tier: ~1 Request/15 Min, 1'500 Tweets/Mt schreiben, kein Suchen
- Basic: $200/Mt — 10'000 Tweets/Mt, 7 Tage Suchhistorie
- Pro: $5'000/Mt — 1 Mio Tweets/Mt, Filtered/Sampled Stream
- Enterprise: ab $42'000/Mt — Full Firehose
- **NEU (Feb 2026):** Pay-per-Use als Default fuer neue Entwickler, max. 2 Mio Post-Reads/Mt
- Rate Limits: Tier-abhaengig, Basic = 10'000 Tweets/Mt
- **Problem:** Basic Tier ($200/Mt) liefert nur 10'000 Tweets — fuer sinnvolles Sentiment-Tracking bei BTC unrealistisch wenig

**Reddit API:**
- URL: https://www.reddit.com/dev/api/
- Free Tier: 100 Requests/Min (OAuth), 10'000 Requests/Mt total
- Kommerzielle Nutzung: $0.24 pro 1'000 Requests, oder ab $12'000/Jahr
- Relevante Subreddits: r/Bitcoin, r/CryptoCurrency, r/BitcoinMarkets
- **Problem:** Free Tier reicht fuer stuendliches Polling, aber kommerziell = teuer

**LunarCrush (Aggregiert — empfohlener Weg):**
- URL: https://lunarcrush.com
- Discover (Free): Basis-Features
- Individual: $24/Mt — alle Social/Market-Metriken
- Builder: $240/Mt — API-Zugang, hoehere Limits
- Enterprise: Custom Pricing
- Aggregiert Twitter, Reddit, YouTube, TikTok, Telegram etc.
- Galaxy Score, AltRank, Social Dominance als fertige Metriken
- **Empfehlung:** Builder-Plan ($240/Mt) fuer programmatischen Zugang

**Santiment:**
- URL: https://santiment.net
- Free: Basis-Dashboard, 30-Tage Daten-Lag bei Restricted Metrics
- Pro: ab $44/Mt — hoehere API-Limits
- Business: Custom — voll uneingeschraenkter API-Zugang
- Bietet Social Volume, Weighted Sentiment, Social Dominance
- Python-Client: `sanpy` (https://github.com/santiment/sanpy)

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** LunarCrush ab ~2019, Santiment ab ~2017
- **Update-Frequenz:** Stuendlich (LunarCrush), teilweise 5-Min (Santiment Pro)
- **BTC-Relevanz:** BTC hat die hoechste Social-Media-Abdeckung aller Coins
- **Qualitaetsprobleme:** Bot-Aktivitaet, koordinierte Manipulation, Sarkasmus-Erkennung

### Akademische Evidenz
- **"The predictive power of public Twitter sentiment for forecasting cryptocurrency prices"** (Sattarov et al., 2020, ScienceDirect): Zeigt signifikante Vorhersagekraft von Twitter-Sentiment fuer BTC-Preise
- **"Sentiment Matters for Cryptocurrencies: Evidence from Tweets"** (MDPI Data, 2025): Bestaetigt Sentiment-Alpha bei Crypto
- **"Deep learning and NLP in cryptocurrency forecasting"** (ScienceDirect, 2025): Integration von Social-Media-Daten verbessert Forecast-Accuracy gegenueber reinen Finanzdaten
- **"Attention-augmented hybrid CNN-LSTM model for social media sentiment"** (Nature Scientific Reports, 2025): CNN-LSTM auf Social-Sentiment uebertrifft traditionelle Modelle
- **CryptoBERT** (HuggingFace): Pre-trained auf 3.2 Mio Crypto-Posts, spezialisiert auf Crypto-Jargon ("Moon"=bullish, "Rekt"=bearish)

### Integration in Feature-Pipeline
```python
# Moegliche Features (stuendlich aktualisiert):
"social_volume_1h"        # Anzahl Social-Media-Posts in letzter Stunde
"social_sentiment_1h"     # Gewichteter Sentiment-Score [-1, 1]
"social_dominance_btc"    # BTC-Anteil am gesamten Crypto-Social-Volume
"social_volume_change_24h"  # Relative Aenderung vs. 24h-Durchschnitt
"social_sentiment_ma_24h" # 24h gleitender Durchschnitt des Sentiments
```

### Kosten
- **Minimum:** $24/Mt (LunarCrush Individual) — nur Dashboard, kein API
- **Empfohlen:** $240/Mt (LunarCrush Builder) — voller API-Zugang
- **Alternative:** Santiment Pro ab $44/Mt (Social + On-Chain in einem)
- **DIY (X + Reddit direkt):** Unrealistisch teuer ($200+/Mt) und fragil

### Risiken und Fallstricke
- Social Sentiment ist ein **Lagging Indicator** — reagiert oft nach der Preisbewegung
- Bot-Manipulation kann Sentiment verzerren (insbesondere bei Low-Cap Coins, weniger bei BTC)
- API-Preise von X/Reddit steigen kontinuierlich (X hat 2026 nochmals erhoeht)
- LunarCrush koennte Preise aendern oder Free Tier einschraenken
- Overfitting-Risiko: Sentiment-Daten sind noisy, brauchen sorgfaeltige Feature-Engineering

### Geschaetzter Aufwand
- **5-8 Tage** (mit LunarCrush API)
  - Tag 1-2: API-Integration, Daten-Fetcher, Caching
  - Tag 3-4: Feature-Engineering (Sentiment-Scores, Volumen-Metriken)
  - Tag 5-6: Backtesting mit historischen Daten
  - Tag 7-8: Integration in Live-Pipeline, Monitoring

---

## C2: News Sentiment — news_analysis_3.0 Integration

### Was es ist
Integration des eigenen news_analysis_3.0 Projekts als Sentiment-Datenquelle. Das Projekt sammelt Artikel von 30+ RSS-Feeds, klassifiziert sie per LLM (DeepSeek/Gemini) und erzeugt strukturierte Zusammenfassungen. Statt eines externen API-Anbieters wird das eigene NLP-System genutzt.

### Konkrete Datenquellen (bereits vorhanden)
- **Projekt-Pfad:** `C:\Codes\news_analysis_3.0`
- **Datenbank:** SQLite (`news.db`) mit allen klassifizierten Artikeln
- **Pipeline:** RSS-Feeds → Scraping (Trafilatura/Playwright) → LLM-Klassifikation → SQLite
- **LLM-Provider:** DeepSeek (Klassifikation), Gemini (Zusammenfassung)
- **Aktueller Fokus:** Schweizer Wirtschaftsnachrichten (Creditreform)
- **Adaption noetig:** RSS-Feeds auf Crypto/Bitcoin-Quellen erweitern

### Crypto-Nachrichtenquellen (hinzuzufuegen)
- CoinDesk RSS: https://www.coindesk.com/arc/outboundfeeds/rss/
- CoinTelegraph RSS: https://cointelegraph.com/rss
- The Block RSS: https://www.theblock.co/rss.xml
- Bitcoin Magazine: https://bitcoinmagazine.com/feed
- Decrypt: https://decrypt.co/feed
- Bloomberg Crypto (paywall): Bloomberg Terminal noetig

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Ab Zeitpunkt der Aktivierung (keine Rueckwirkung ohne Scraping-Backfill)
- **Update-Frequenz:** Konfigurierbar, empfohlen alle 1-4 Stunden
- **Qualitaet:** LLM-basierte Klassifikation ist qualitativ hochwertig (vgl. Paper unten)
- **Latenz:** RSS-Feeds haben 5-30 Min Verzoegerung gegenueber Originalveroeffentlichung

### Akademische Evidenz
- **"Cryptocurrency Price Prediction Using News and Social Media Sentiment"** (Lamon et al., ACM): News-Sentiment verbessert BTC-Preis-Prediction signifikant
- **"LLMs and NLP Models in Cryptocurrency Sentiment Analysis: A Comparative Study"** (MDPI Big Data, 2024): LLMs (GPT-4, BERT) uebertreffen klassische NLP-Modelle (VADER, TextBlob) deutlich bei Crypto-Sentiment
- **"Forecasting directional bitcoin price returns using aspect-based sentiment analysis"** (Springer Machine Learning, 2021): Aspekt-basierte Analyse verbessert directional accuracy
- **CryptoBERT** (HuggingFace ElKulako/cryptobert): Pre-trained Modell, direkt einsetzbar

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"news_sentiment_1h"      # Durchschnittliches Sentiment der letzten Stunde [-1, 1]
"news_volume_1h"         # Anzahl relevanter Artikel in der letzten Stunde
"news_sentiment_change"  # Sentiment-Aenderung vs. 24h-Durchschnitt
"news_urgency_score"     # Gewichtet nach Quelle (Bloomberg > Blog)
"news_negative_spike"    # Binary: Deutlicher Negativ-Ausschlag (>2 Sigma)
```

### Kosten
- **API-Kosten LLM:** ~$0.50-2.00/Tag fuer DeepSeek/Gemini (je nach Artikelvolumen)
- **Infrastruktur:** Laeuft lokal oder auf bestehender GCP-VM
- **Total:** ~$15-60/Mt (nur LLM-API-Kosten)
- **Kein neuer externer Service noetig** — nutzt bestehende Infrastruktur

### Risiken und Fallstricke
- news_analysis_3.0 ist aktuell auf Schweizer Wirtschaftsnachrichten ausgerichtet — RSS-Feeds muessen erweitert werden
- LLM-Klassifikation hat Latenz (Sekunden pro Artikel) — nicht fuer sub-sekuendliche Signale
- Backtesting problematisch: Historische News-Daten muessen zuerst aufgebaut werden
- LLM-Provider-Abhaengigkeit (DeepSeek/Gemini koennte Pricing aendern)
- Doppelte Maintenance-Last: Zwei Projekte pflegen

### Geschaetzter Aufwand
- **3-5 Tage**
  - Tag 1: Crypto-RSS-Feeds zu news_analysis_3.0 hinzufuegen, Crypto-Klassifikationsschema
  - Tag 2: API/Shared-DB-Interface zwischen news_analysis_3.0 und CryptoTrader
  - Tag 3: Feature-Engineering (Sentiment-Aggregation, Zeitfenster)
  - Tag 4-5: Backtesting (nach Aufbau von min. 2-4 Wochen Daten)

---

## C3: Whale Tracking — Grosse Wallet-Bewegungen

### Was es ist
Tracking von grossen Krypto-Transaktionen (>$1 Mio) auf der Blockchain. Wenn "Wale" (Adressen mit >1'000 BTC) grosse Mengen bewegen — insbesondere zu/von Exchanges — kann dies Kauf-/Verkaufsdruck signalisieren.

### Konkrete APIs und Datenquellen

**Whale Alert:**
- URL: https://whale-alert.io / https://docs.whale-alert.io
- Free Trial: 7 Tage
- Alerts-Plan: Persoenliche Nutzung (Preis auf Anfrage, geschaetzt ~$15-35/Mt)
- Quantitative-Plan: Fuer Trading-Modelle (Preis auf Anfrage, geschaetzt ~$50-100/Mt)
- Historische Datensaetze: $499/Jahr pro Blockchain (ML-Training)
- Rate Limits: Max 1'000 Calls/Min
- API liefert: Transaktionswert, Absender-/Empfaenger-Typ (exchange, unknown, whale)

**Glassnode (Alternative):**
- URL: https://glassnode.com
- Free: Taegliche Aufloesung, verzoegert
- Advanced: ~$39/Mt — stuendliche Aufloesung
- Professional + API-Addon: ~$799/Mt — 10-Min-Aufloesung, API-Zugang
- Metriken: Exchange Inflows/Outflows, Whale Entity Count, Accumulation Trends

**CryptoQuant (Alternative):**
- URL: https://cryptoquant.com
- Free: Limitierter Zugang
- Advanced: $39/Mt
- Professional: $99/Mt mit API
- Premium: $1'999/Mt — voll uneingeschraenkt
- Metriken: Exchange Reserve, Whale Ratio, Fund Flow Ratio

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Whale Alert ab 2018, Glassnode ab 2009 (Bitcoin Genesis)
- **Update-Frequenz:** Near-Realtime (Whale Alert: Minuten), Glassnode Free: taeglich
- **BTC-Relevanz:** Sehr hoch — BTC hat die transparenteste Blockchain
- **Qualitaet:** Exchange-Zuordnung ist ~90% korrekt, "Unknown"-Wallets schwer zu interpretieren

### Akademische Evidenz
- **"Do Bitcoin whales generate alpha?"** (Charles University Prague, 2025): Einzeltransaktionen haben ~50% Vorhersagekraft (= Muenzwurf), aber aggregierte Flows zeigen Signal
- **"Forecasting Bitcoin Volatility through On-Chain and Whale-Alert Tweet Analysis"** (ResearchGate, 2023): ML-Modell mit On-Chain + Whale-Daten: Precision 0.71, Recall 0.89, F1 0.789 fuer BTC-Uptrend-Prediction
- **"The role of whale investors in the bitcoin market"** (ScienceDirect, 2025): Whale-Aktivitaet als fuehrender Indikator fuer Preisbewegungen empirisch bestaetigt
- **Wichtig:** Nicht einzelne Transaktionen tracken, sondern aggregierte Flows (Exchange Inflows/Outflows ueber Zeitfenster)

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"whale_exchange_inflow_1h"   # BTC-Zufluss zu Exchanges in letzter Stunde
"whale_exchange_outflow_1h"  # BTC-Abfluss von Exchanges in letzter Stunde
"whale_net_flow_1h"          # Netto-Flow (negativ = Abzug von Exchange = bullish)
"whale_tx_count_large_24h"   # Anzahl Transaktionen >$1M in 24h
"whale_flow_ratio_24h"       # Inflow/Outflow-Ratio (>1 = bearish)
```

### Kosten
- **Minimum:** $0 (Glassnode Free, taeglich, verzoegert)
- **Empfohlen:** ~$35/Mt (Whale Alert Alerts-Plan)
- **Premium:** $99/Mt (CryptoQuant Professional mit API)
- **ML-Training:** $499 einmalig (Whale Alert historische Daten, 1 Blockchain)

### Risiken und Fallstricke
- Einzelne Whale-Transaktionen sind Rauschen — nur aggregierte Metriken sind nuetzlich
- Exchange-Zuordnung nicht 100% korrekt (Cold Wallets, OTC-Desks)
- "Unknown"-zu-"Unknown"-Transfers nicht interpretierbar
- Whale-Alerts auf Social Media sind bereits eingepreist wenn sie viral gehen
- Latenz: On-Chain-Daten brauchen Blockbestaetigung (~10 Min bei BTC)

### Geschaetzter Aufwand
- **3-4 Tage**
  - Tag 1: API-Integration (Whale Alert oder Glassnode)
  - Tag 2: Feature-Engineering (Aggregation, Zeitfenster, Ratios)
  - Tag 3: Backtesting mit historischen Daten
  - Tag 4: Integration in Live-Pipeline

---

## C4: Liquidation Heatmaps — Liquidationslevel

### Was es ist
Visualisierung und Quantifizierung von Preisniveaus, an denen gehebelten Positionen liquidiert werden. Diese "Magnetische Zonen" ziehen den Preis an, weil Liquidationen kaskadenartige Preisbewegungen ausloesen. Besonders relevant fuer BTC im 1h-Timeframe.

### Konkrete APIs und Datenquellen

**Coinglass (primaere Empfehlung):**
- URL: https://www.coinglass.com/pricing / https://docs.coinglass.com
- Free Tier: Real-Time Open Interest, Funding Rates, Long/Short Ratios, Liquidations
- Prime: $28/Mt — alle Coins, erweiterte Zeitraeume, Auto-Refresh
- API: Separates Pricing (auf Anfrage), Basis-Endpoints teilweise frei
- Endpoints: `/api/futures/liquidation/heatmap`, `/api/futures/liquidation/aggregate-heatmap`
- Zeitraeume: 12h, 24h, 3d, 7d, 14d, 30d, 90d, 1y

**Hyblock Capital (Alternative):**
- URL: https://hyblock.co
- Bekanntester Anbieter fuer Liquidation-Daten
- Pricing: ~$50-100/Mt fuer API-Zugang
- Mehr Tiefe als Coinglass, aber teurer

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Begrenzt — Liquidationslevel sind dynamisch und aendern sich staendig
- **Update-Frequenz:** Real-Time (Coinglass Website), API-Updates je nach Plan
- **BTC-Relevanz:** **Extrem hoch** — BTC hat das groesste Futures-Volumen und die meisten Liquidationen
- **Qualitaet:** Berechnet auf Basis von Open Interest und ueblichen Leverage-Ratios, nicht 100% exakt

### Akademische Evidenz
- **Keine peer-reviewed Papers** direkt zu Liquidation Heatmaps als Prediktor
- Konzept basiert auf Markt-Mikrostruktur-Theorie: Liquidation Cascades sind wohlbekannt
- **Glassnode Insights (2025): "Pressure Points: Liquidation Heatmaps & Market Bias"** — Praktiker-Evidenz
- **Coinglass:** "Magnetische Zonen" — Preise bewegen sich zu Bereichen mit hoher Liquidationsdichte
- **Praktische Evidenz stark**, akademische Evidenz fehlt (Forschungsluecke)

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"liq_density_above_pct"     # Liquidationsvolumen oberhalb des aktuellen Preises (in %)
"liq_density_below_pct"     # Liquidationsvolumen unterhalb des aktuellen Preises (in %)
"liq_imbalance"             # (above - below) / (above + below) — Asymmetrie [-1, 1]
"liq_nearest_cluster_dist"  # Distanz zum naechsten grossen Liquidations-Cluster (in %)
"liq_24h_volume"            # Total liquidiertes Volumen in 24h (USD)
"liq_long_short_ratio"      # Long/Short-Liquidations-Verhaeltnis
```

### Kosten
- **Minimum:** $0 (Coinglass Free Tier — Basis-Liquidationsdaten)
- **Empfohlen:** $28/Mt (Coinglass Prime — alle Features, erweiterte Daten)
- **Premium:** ~$50-100/Mt (Hyblock fuer tiefere Daten)

### Risiken und Fallstricke
- Liquidationslevel sind Schaetzungen — exakte Levels sind nur den Exchanges bekannt
- Historische Backtesting-Daten schwer zu bekommen (Levels aendern sich dynamisch)
- Coinglass API-Dokumentation nicht immer aktuell
- Overfitting-Risiko: Liquidations-Cluster verschieben sich schnell
- Feature muss staendig aktualisiert werden (nicht statisch wie OHLCV)

### Geschaetzter Aufwand
- **2-3 Tage**
  - Tag 1: Coinglass API-Integration, Liquidationsdaten abrufen
  - Tag 2: Feature-Engineering (Imbalance, Cluster-Distanz)
  - Tag 3: Integration in Live-Pipeline, Tests

---

## C5: Order Book Depth — Bid/Ask Imbalance

### Was es ist
Analyse der Orderbuch-Tiefe (Bid/Ask-Seite) auf Binance. Order Book Imbalance (OBI) misst das Verhaeltnis zwischen Kauf- und Verkaufsorders und kann kurzfristige Preisbewegungen vorhersagen.

### Konkrete APIs und Datenquellen

**Binance API (kostenlos):**
- REST: `GET /api/v3/depth` — Snapshot mit max. 5'000 Levels pro Seite
- WebSocket: `<symbol>@depth` / `<symbol>@depth@100ms` — Inkrementelle Updates
- Rate Limits: WebSocket max 5 Nachrichten/Sek eingehend, 300 Connections/5 Min/IP
- Keine Kosten, kein API-Key fuer Marktdaten noetig
- Historische Snapshots: Nicht direkt von Binance (nur Live)

**CoinAPI (historische Daten):**
- URL: https://www.coinapi.io
- Historische Order-Book-Snapshots von Binance
- Pricing: ab $79/Mt (Startup), $249/Mt (Streamer)

**Amberdata (Alternative):**
- URL: https://www.amberdata.io
- L2/L3 Order Book Daten, historisch und live
- Enterprise Pricing (auf Anfrage, ~$500+/Mt)

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Live via Binance gratis, historisch nur ueber Drittanbieter (teuer)
- **Update-Frequenz:** Real-Time (100ms WebSocket-Updates)
- **BTC-Relevanz:** Hoch — BTC/USDT ist das liquideste Paar auf Binance
- **Qualitaet:** Orderbuch ist dynamisch, Spoofing/Layering verfaelscht Daten

### Akademische Evidenz
- **"Price Impact of Order Book Imbalance in Cryptocurrency Markets"** (Towards Data Science / akademisch): Lineare Beziehung zwischen OBI und kurzfristigen Preisaenderungen nachgewiesen
- **"Impact of order book asymmetries on cryptocurrency prices"** (Charles University, 2025): OBI erklaert signifikanten Anteil der kurzfristigen Preisbewegung
- **"Exploring Microstructural Dynamics in Cryptocurrency Limit Order Books"** (arXiv, 2025): Deep Learning auf LOB-Daten uebertrifft klassische Features
- **Einschraenkung:** Alpha ist auf **sehr kurzfristige** Horizonte beschraenkt (Sekunden bis Minuten). Bei 1h-Timeframe deutlich reduziert.
- **Profitabilitaet:** Mid-Price Returns <10 Basispunkte fuer 10-Sek-Perioden — nach Fees (10 bps bei Binance) kaum profitabel

### Integration in Feature-Pipeline
```python
# Moegliche Features (aggregiert fuer 1h):
"ob_imbalance_level5"     # Bid/Ask Imbalance auf Level 5 Tiefe
"ob_imbalance_level20"    # Bid/Ask Imbalance auf Level 20 Tiefe
"ob_spread_avg_1h"        # Durchschnittlicher Spread in letzter Stunde
"ob_depth_ratio"          # Total Bid Volume / Total Ask Volume (Top 50 Levels)
"ob_large_wall_distance"  # Distanz zur groessten Sell/Buy-Wall (%)
```

### Kosten
- **Minimum:** $0 (Binance Live-API, kein API-Key noetig fuer Marktdaten)
- **Historisch:** $79-249/Mt (CoinAPI) fuer Backtesting
- **Problem:** Historische Daten fuer Backtesting sind teuer oder muessen selbst gesammelt werden

### Risiken und Fallstricke
- **Groesster Einwand:** OBI-Alpha ist primaer auf Sekunden/Minuten-Horizonte beschraenkt — bei 1h-Prediction stark verduennt
- Spoofing und Layering (gefaelschte Orders) sind auf Crypto-Exchanges verbreitet
- Orderbuch-Daten sind extrem grossvolumig (Speicher, CPU)
- Historische Daten muessen selbst gesammelt werden (Monate Vorlauf) oder teuer gekauft werden
- WebSocket-Verbindung muss stabil laufen — erhoehte Infrastruktur-Komplexitaet auf e2-small VM

### Geschaetzter Aufwand
- **3-5 Tage** (ohne historische Datensammlung)
  - Tag 1-2: Binance WebSocket-Integration, Snapshot-Aggregation
  - Tag 3: Feature-Engineering (Imbalance-Metriken)
  - Tag 4-5: Live-Integration, Stabilitaetstests
  - **Zusaetzlich:** 2-4 Wochen Datensammlung vor erstem Backtesting

---

## C6: Macro-Daten — UMGESETZT 2026-04-06

### Was es ist
Integration von makrooekonomischen Indikatoren, die nachweislich mit BTC korrelieren. Der US Dollar Index (DXY) hat eine inverse Korrelation mit BTC, Treasury Yields beeinflussen die Risikobereitschaft, und Fed-Entscheidungen bewegen alle Maerkte.

### Konkrete APIs und Datenquellen

**FRED API (Federal Reserve Economic Data — primaere Empfehlung):**
- URL: https://fred.stlouisfed.org/docs/api/fred/
- **Komplett kostenlos**, API-Key gratis erhaeltlich
- Rate Limit: 120 Requests/Min
- 800'000+ Zeitreihen
- Python-Library: `fredapi` (https://pypi.org/project/fredapi/)
- Relevante Serien:
  - `DGS2` — 2-Year Treasury Yield
  - `DGS10` — 10-Year Treasury Yield
  - `T10Y2Y` — 10Y-2Y Spread (Yield Curve)
  - `DFEDTARU` — Fed Funds Target Rate (Upper)
  - `DTWEXBGS` — Trade Weighted Dollar Index (DXY-Proxy)
  - `VIXCLS` — VIX Volatility Index

**Twelve Data (DXY live):**
- URL: https://twelvedata.com
- Free: 800 Requests/Tag, 8 Requests/Min
- DXY, Gold, Forex direkt abrufbar
- Pro: ab $29/Mt fuer hoehere Limits

**yfinance (Python, kostenlos):**
- `DX-Y.NYB` — DXY Index
- `^TNX` — 10-Year Treasury Yield
- `GC=F` — Gold Futures
- **Achtung:** Inoffizieller Scraper, kann jederzeit brechen
- Daten verzoegert (15-20 Min)

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** FRED ab 1950er (je nach Serie), yfinance ab ~2000
- **Update-Frequenz:** FRED: taeglich (EOD), Twelve Data: intrataeglich
- **BTC-Relevanz:** Historische Korrelation BTC-DXY = ~-0.33 (S&P BMI vs. 2Y Treasury)
- **Qualitaet:** Institutionelle Qualitaet (Fed-Daten)

### Akademische Evidenz
- **"The Bitcoin-Macro Disconnect"** (NY Fed Staff Report No. 1052, 2024): Zeigt signifikante BTC-Macro-Korrelation seit 2020, vorher gering
- **S&P Global (2023): "Are crypto markets correlated with macroeconomic factors?"**: BTC-Korrelation mit Macro ist seit 2020 signifikant gewachsen
- **"Do Prediction Markets Forecast Cryptocurrency Volatility?"** (arXiv, 2026): Fed Funds implied rate changes und 10Y Treasury Returns als Volatilitaets-Praediktoren fuer Crypto
- **Praktisch bestaetigt:** DXY-Staerke = Crypto-Schwaeche (Zinsanhebungen druecken Crypto)

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"dxy_daily"                # DXY-Kurs (taeglich aktualisiert)
"dxy_change_5d"            # DXY 5-Tage-Veraenderung (%)
"treasury_10y_yield"       # 10-Jahres US Treasury Yield
"treasury_2y_yield"        # 2-Jahres US Treasury Yield
"yield_curve_spread"       # 10Y - 2Y Spread (Inversions-Signal)
"vix_level"                # VIX Volatilitaetsindex
"fed_rate"                 # Aktueller Fed Funds Rate
```
**Hinweis:** Macro-Daten sind taeglich — fuer 1h-Timeframe per Forward-Fill auf stuendliche Aufloesung expandieren (gleicher Mechanismus wie beim Fear & Greed Index).

### Kosten
- **$0** — FRED API komplett kostenlos
- **$0** — yfinance kostenlos (aber fragil)
- **$29/Mt** — Twelve Data Pro (optional fuer intraday DXY)

### Risiken und Fallstricke
- Macro-Daten sind taeglich — bei 1h-Trading-Horizont ist Granularitaet begrenzt
- BTC-Macro-Korrelation ist nicht stabil — kann sich in verschiedenen Marktphasen aendern (vgl. NY Fed Paper)
- yfinance ist ein inoffizieller Scraper und kann jederzeit brechen
- FRED hat keine Intraday-Daten — fuer 1h-Prediction nur als "Hintergrund-Feature"
- Forward-Fill erzeugt keine neuen Informationen innerhalb eines Tages

### Geschaetzter Aufwand
- **2-3 Tage**
  - Tag 1: FRED API + yfinance Integration, Daten-Fetcher
  - Tag 2: Feature-Engineering, Forward-Fill, Alignment mit OHLCV-Index
  - Tag 3: Backtesting, Integration in Pipeline

---

## C7: Google Trends — Suchvolumen als Sentiment-Proxy

### Was es ist
Google Trends misst das relative Suchvolumen fuer Keywords wie "Bitcoin", "BTC kaufen", "Bitcoin crash" etc. Hoeheres Suchvolumen korreliert oft mit Preisbewegungen — insbesondere Retail-getriebene Spikes.

### Konkrete APIs und Datenquellen

**pytrends (Python-Library — bereits im Projekt vorhanden):**
- URL: https://pypi.org/project/pytrends/
- **Kostenlos** — inoffizieller Scraper fuer Google Trends
- Existiert bereits in `coin_prediction/src/ingestion/sentiment_fetcher.py`
- Rate Limits: Konservativ (15 Sek Pause zwischen Batches empfohlen)
- Max 5 Keywords pro Request
- **Bereits implementiert**, aber nicht aktiv genutzt!

**SerpApi (Alternative, zuverlaessiger):**
- URL: https://serpapi.com
- $50-250/Mt — zuverlaessigerer Zugang zu Google Trends
- Weniger Rate-Limiting-Probleme

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Ab 2004 (woechentlich), ab 2020 (taeglich)
- **Update-Frequenz:** Taeglich bis woechentlich (Google-intern verzoegert)
- **Granularitaet:** Nur woechentlich fuer Zeitraeume >5 Jahre, taeglich fuer <90 Tage
- **Qualitaet:** Relative Werte (0-100), nicht absolute Zahlen. Normierung aendert sich.

### Akademische Evidenz
- **"Google trend index as an investor sentiment proxy in cryptomarket"** (Springer CJOR, 2025): Nichtlineare Beziehung zwischen Google Trends und Crypto-Preisen, Vorhersagekraft mit ML-Ansaetzen
- **"Predicting Bitcoin's price using AI"** (PMC, 2025): 7-Tage Rolling Mean des Google Trends Search Interest verbessert BTC-Prediction
- **"Exploring the Relationship Between Google Trends and Cryptocurrency Metrics"** (ResearchGate, 2024): Signifikanter Zusammenhang zwischen Suchvolumen und Preis/Volumen

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"gtrends_bitcoin_daily"    # Google Trends Score fuer "Bitcoin" (0-100)
"gtrends_bitcoin_7d_ma"   # 7-Tage gleitender Durchschnitt
"gtrends_change_7d"        # Woche-ueber-Woche Aenderung
"gtrends_btc_crash"        # Suchvolumen fuer "Bitcoin crash" (Angst-Proxy)
```

### Kosten
- **$0** — pytrends kostenlos (bereits vorhanden)
- **$50/Mt** — SerpApi fuer zuverlaessigeren Zugang

### Risiken und Fallstricke
- pytrends wird haeufig von Google rate-limited oder blockiert
- Daten sind nur taeglich/woechentlich — fuer 1h-Timeframe wenig Mehrwert
- Google Trends ist ein **Lagging Indicator** — reagiert nach der Preisbewegung
- Relative Werte machen historische Vergleiche schwierig
- Bereits im Projekt vorhanden, aber bisher nicht aktiviert — vermutlich aus gutem Grund

### Geschaetzter Aufwand
- **1-2 Tage**
  - Tag 1: Bestehenden Code aktivieren, Keywords anpassen
  - Tag 2: Feature-Engineering, Backtesting
  - **Niedrig** weil Code bereits existiert

---

## C8: GitHub Activity — Developer-Aktivitaet

### Was es ist
Tracking der Entwickler-Aktivitaet in oeffentlichen GitHub-Repositories eines Crypto-Projekts. Commits, Pull Requests, Issues, und Contributors als Mass fuer die Gesundheit und Aktivitaet eines Projekts.

### Konkrete APIs und Datenquellen

**Santiment Development Activity:**
- URL: https://academy.santiment.net/metrics/development-activity/
- Trackt GitHub-Events statt nur Commits (zuverlaessiger)
- Free: Basis-Zugang mit 30-Tage-Lag
- Pro: ab $44/Mt

**Electric Capital Developer Report:**
- URL: https://www.developerreport.com
- Kostenlose Analyse von 100+ Mio Commits
- Kein API, nur Report (jaehrlich)

**GitHub API (direkt):**
- URL: https://api.github.com
- Kostenlos: 60 Requests/Stunde (unauthentifiziert), 5'000/Stunde (authentifiziert)
- BTC-Repository: https://github.com/bitcoin/bitcoin

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** GitHub API ab 2008, Santiment ab ~2017
- **Update-Frequenz:** Taeglich (ausreichend)
- **BTC-Relevanz:** **Gering** — Bitcoin Core hat stabile, langsame Entwicklung. Keine Preisrelevanz.

### Akademische Evidenz
- **Keine signifikante akademische Evidenz** fuer BTC-Preis-Prediction via GitHub Activity
- Santiment-eigene Analysen zeigen Korrelation bei **Altcoins** (Entwicklung = Adoption = Preis)
- Fuer BTC ist Development Activity kein sinnvoller Prediktor — BTC-Preis wird nicht von Code-Commits getrieben

### Integration in Feature-Pipeline
```python
# Theoretische Features (aber nicht empfohlen fuer BTC):
"github_commits_7d"        # Commits in den letzten 7 Tagen
"github_contributors_30d"  # Aktive Contributors in 30 Tagen
"github_activity_change"   # Aenderung vs. Vormonat
```

### Kosten
- **$0** — GitHub API kostenlos
- **$44/Mt** — Santiment Pro (inkl. andere Metriken)

### Risiken und Fallstricke
- **Fuer BTC nicht relevant** — Bitcoin Core Entwicklung ist langsam und vorhersagbar
- Nur sinnvoll fuer Altcoins (z.B. Ethereum, Solana)
- Commits != Qualitaet (Auto-Formatting, Dependency-Updates zaehlen auch)
- Crypto-Developer-Aktivitaet sinkt seit 2022 massiv (von 31'000 auf ~18'000 aktive Devs, Stand 2025)

### Geschaetzter Aufwand
- **1-2 Tage** (aber nicht empfohlen fuer BTC-only Bot)

---

## C9: Stablecoin Supply — USDT/USDC Mint/Burn als Kapitalfluss-Proxy

### Was es ist
Tracking der Stablecoin-Ausgabe (Mint) und -Vernichtung (Burn). Wenn neue USDT/USDC gepraegt werden, fliesst Kapital in den Crypto-Markt ("Dry Powder"). Grosse Burns signalisieren Kapitalabfluss. USDT + USDC repraesentieren ~90% des Stablecoin-Marktes.

### Konkrete APIs und Datenquellen

**CryptoQuant:**
- URL: https://cryptoquant.com/catalog
- Metriken: Stablecoin Minted Supply, Net Stablecoin Flow, Exchange Stablecoin Reserve
- Free: Limitierter Zugang
- Advanced: $39/Mt
- Professional: $99/Mt mit API
- Python: Kein offizieller Client, REST-API

**Glassnode:**
- URL: https://glassnode.com
- Metriken: Stablecoin Supply (USDT, USDC, BUSD), Stablecoin Exchange Flows
- Free: Taeglich, verzoegert
- Professional + API: ~$799/Mt

**DefiLlama (kostenlos):**
- URL: https://defillama.com/stablecoins
- API: https://stablecoins.llama.fi/stablecoins
- **Komplett kostenlos**, kein API-Key noetig
- Historische Supply-Daten fuer alle grossen Stablecoins
- Update: Taeglich
- **Empfohlen als primaere Datenquelle**

**On-Chain direkt (Etherscan/BSCScan):**
- USDT Contract Events (Mint/Burn) ueber Etherscan API
- Kostenlos (Etherscan Free: 5 Calls/Sek)
- Mehr Aufwand, aber granularste Daten

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** USDT ab 2014, USDC ab 2018, DefiLlama ab ~2020
- **Update-Frequenz:** DefiLlama taeglich, CryptoQuant bis minuetlich (Premium)
- **BTC-Relevanz:** Sehr hoch — Stablecoin-Zufluesse korrelieren mit BTC-Kaufdruck
- **Qualitaet:** Mint/Burn-Events sind objektive Blockchain-Daten (nicht manipulierbar)

### Akademische Evidenz
- **BIS Working Paper No. 1340: "Stablecoin flows and spillovers to FX markets"** (2025): Stablecoin-Flows haben signifikante Spillover-Effekte auf traditionelle Maerkte
- **BIS Working Paper No. 1270: "Stablecoins and safe asset prices"** (2024): $3.5 Mrd Stablecoin-Inflow komprimiert 3-Monats-Yields um 5-8 Basispunkte
- **NBER Working Paper: "What keeps stablecoins stable?"** (Lyons): Order Flow = ~$40 Mio pro 1% Preisaenderung im Tether-Dollar-Paar
- **"Cryptocurrencies and stablecoins: a high-frequency analysis"** (Springer Digital Finance, 2022): Hochfrequenz-Zusammenhang zwischen Stablecoin-Flows und BTC-Preis
- **IMF Working Paper (2025): "Understanding Stablecoins"**: USDT/USDC repraesentieren ~90% des Marktes

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"stablecoin_total_supply"      # Gesamte Stablecoin-Marktkapitalisierung
"stablecoin_supply_change_7d"  # 7-Tage Aenderung der Supply (%)
"usdt_supply_change_1d"        # USDT taegl. Supply-Aenderung
"usdc_supply_change_1d"        # USDC taegl. Supply-Aenderung
"stablecoin_exchange_ratio"    # Stablecoins auf Exchanges / Total Supply
"stablecoin_net_mint_7d"       # Netto-Minting in 7 Tagen (positiv = bullish)
```

### Kosten
- **$0** — DefiLlama API komplett kostenlos
- **$39/Mt** — CryptoQuant Advanced fuer hoehere Granularitaet
- **$0** — Etherscan Free Tier (5 Calls/Sek)

### Risiken und Fallstricke
- Taeglich-Daten: Fuer 1h-Timeframe nur als Hintergrund-Signal (wie Macro-Daten)
- Grosse Mints bedeuten nicht automatisch "sofortiger BTC-Kauf" — kann Wochen dauern
- USDT Mint/Burn kann durch Nicht-Crypto-Verwendung verzerrt sein (Cross-Border-Payments)
- Supply-Aenderungen sind traege Indikatoren — signalisieren langfristige Trends, nicht kurzfristige Moves

### Geschaetzter Aufwand
- **2-3 Tage**
  - Tag 1: DefiLlama API-Integration, Stablecoin-Supply-Fetcher
  - Tag 2: Feature-Engineering, Alignment mit BTC-OHLCV
  - Tag 3: Backtesting, Integration

---

## C10: Prediction Markets — Polymarket/Kalshi

### Was es ist
Prediction Markets sind Wettmaerkte, auf denen Teilnehmer auf zukuenftige Ereignisse wetten. Die Preise spiegeln aggregierte Wahrscheinlichkeiten wider. Polymarket (Crypto-basiert) und Kalshi (CFTC-reguliert) bieten Maerkte zu Crypto-Preiszielen, Fed-Entscheidungen, und makrooekonomischen Events.

### Konkrete APIs und Datenquellen

**Polymarket Gamma API:**
- URL: https://gamma-api.polymarket.com
- Dokumentation: https://docs.polymarket.com/developers/gamma-markets-api/overview
- **Komplett kostenlos**, keine Authentifizierung noetig
- Endpoints: `GET /events`, `GET /markets`, `GET /events/{id}`
- 5'439 aktive Crypto-Maerkte (Stand 2026)
- Crypto-spezifisch: Bitcoin-Preisziele, ETF-Approvals, Regulatory Events

**Kalshi API:**
- URL: https://docs.kalshi.com
- **API-Zugang kostenlos** — nur Trading-Fees bei Transaktionen
- Demo-Environment: `demo-api.kalshi.co` (Fake-Money zum Testen)
- Python SDK: Offiziell verfuegbar
- CFTC-reguliert — serioeseste Plattform
- Maerkte: Fed-Entscheidungen, Inflation, BTC-Preisziele

**Aggregatoren:**
- Oddpool: Aggregiert Polymarket + Kalshi + andere
- PolyRouter: Normalisierte Daten ueber alle Plattformen

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Polymarket ab 2020, Kalshi ab 2021
- **Update-Frequenz:** Real-Time (Orderbook-basiert)
- **BTC-Relevanz:** Direkt — BTC-Preisziel-Maerkte existieren (z.B. "BTC above $X by date Y")
- **Qualitaet:** Polymarket-Genauigkeit >94% einen Monat vor Ergebnis
- **Volumen:** $21 Mrd monatliches Volumen (2026) — genuegend Liquiditaet

### Akademische Evidenz
- **"Do Prediction Markets Forecast Cryptocurrency Volatility?"** (arXiv, 2026): Kalshi Macro-Contracts (Fed Funds, Treasury) als Crypto-Volatilitaets-Praediktoren
- **Polymarket Accuracy:** >94% Trefferquote bei dicken Maerkten
- **Einschraenkung:** Akademische Forschung zu Prediction Markets als Trading-Signal ist noch jung
- **Manipulation:** Duenne Orderbuecher koennen durch Whale-Aktivitaet verzerrt werden

### Integration in Feature-Pipeline
```python
# Moegliche Features:
"pm_btc_above_target_prob"    # Polymarket: Wahrsch. BTC > naechstes Preisziel
"pm_fed_rate_cut_prob"        # Kalshi: Wahrsch. Fed senkt Zinsen naechste Sitzung
"pm_btc_vol_high_prob"        # Wahrsch. BTC-Volatilitaet > X% diese Woche
"pm_crypto_regulation_prob"   # Wahrsch. neuer Crypto-Regulierung
```

### Kosten
- **$0** — Polymarket Gamma API komplett kostenlos
- **$0** — Kalshi API kostenlos (nur Trading-Fees)

### Risiken und Fallstricke
- Prediction Markets sind noch jung — duenne Liquiditaet in manchen Maerkten
- Maerkte mit wenig Volumen sind leicht manipulierbar
- BTC-spezifische Maerkte sind oft kurzlebig (laufen aus, neue entstehen)
- Feature-Engineering komplex: Welcher Markt ist relevant? Preisziele aendern sich.
- "Preis > $X"-Maerkte sind primaer fuer laengere Horizonte (Tage/Wochen), weniger fuer 1h
- Polymarket ist Crypto-basiert — regulatorische Risiken

### Geschaetzter Aufwand
- **2-3 Tage**
  - Tag 1: Polymarket + Kalshi API-Integration, Markt-Discovery
  - Tag 2: Feature-Engineering (relevante Maerkte filtern, Scores berechnen)
  - Tag 3: Integration in Pipeline, Tests

---

## C11: Cross-Market Signals — UMGESETZT 2026-04-06

### Was es ist
Integration von traditionellen Finanzmaerkten, die mit BTC korrelieren. MicroStrategy (MSTR) ist ein 2.5x-gehebeltes BTC-Proxy (~500'000+ BTC auf der Bilanz), Coinbase (COIN) ist ein Krypto-Adoption-Proxy, Gold korreliert als "Digital Gold"-Narrativ mit BTC.

### Konkrete APIs und Datenquellen

**yfinance (kostenlos, bereits nutzbar):**
- MSTR: `MSTR` — 90-Tage Rolling Correlation mit BTC = ~0.97
- Coinbase: `COIN`
- Gold: `GC=F` (Futures) oder `GLD` (ETF)
- DXY: `DX-Y.NYB`
- EUR/USD: `EURUSD=X`
- SPY: `SPY` (S&P 500 als Risiko-Appetit-Proxy)
- **Problem:** Verzoegert (15-20 Min), inoffizieller Scraper

**Twelve Data:**
- URL: https://twelvedata.com
- Free: 800 Requests/Tag
- $29/Mt: Hoehere Limits, Intraday-Daten

**Alpha Vantage:**
- URL: https://www.alphavantage.co
- Free: 25 Requests/Tag — sehr limitiert
- $50/Mt: 75 Requests/Min

**Bereits teilweise vorhanden:**
- Cross-Asset-Features existieren in `coin_prediction/src/features/cross_asset.py`
- Aktuell: BTC, ETH, EOS, SOL, BNB Returns, Korrelation, Seesaw-Effekt
- **Fehlend:** MSTR, Gold, DXY, SPY, Coinbase

### Datenqualitaet und -verfuegbarkeit
- **Historische Daten:** Ab 2000+ (yfinance), MSTR ab 1998 (als MicroStrategy), BTC-Korrelation relevant ab Aug 2020
- **Update-Frequenz:** Taeglich (EOD) mit yfinance, intraday mit Twelve Data
- **BTC-Relevanz:**
  - MSTR: 0.97 Korrelation (90 Tage) — staerkstes Aktien-Proxy
  - Gold: Variable Korrelation, steigt in Krisenzeiten
  - DXY: ~-0.33 inverse Korrelation
  - SPY: ~0.3-0.5 Korrelation (Risk-On/Risk-Off)
- **Qualitaet:** Regulierte Maerkte, hoechste Datenqualitaet

### Akademische Evidenz
- **CoinGlass Analysis: "MSTR's fundamentals and its high correlation with BTC"**: 90-Tage Rolling Correlation nahe 0.97
- **CoinDesk (2024): "MSTR vs BTC"**: MSTR als 2.5x gehebeltes BTC-Exposure
- **S&P Global (2023)**: BTC-Korrelation mit traditionellen Maerkten seit 2020 signifikant gestiegen
- **NY Fed Staff Report 1052**: BTC-Macro Disconnect hat sich nach 2020 geschlossen

### Integration in Feature-Pipeline
```python
# Moegliche Features (Erweiterung bestehender cross_asset.py):
"cross_mstr_ret_1d"         # MSTR Tagesrendite (t-1)
"cross_mstr_ret_5d"         # MSTR 5-Tage-Rendite
"cross_mstr_btc_premium"    # MSTR Market Cap / BTC Holdings Value (Premium/Discount)
"cross_gold_ret_1d"         # Gold Tagesrendite
"cross_gold_btc_corr_30d"   # 30-Tage Rolling Correlation Gold-BTC
"cross_spy_ret_1d"          # S&P 500 Tagesrendite (Risk-Appetit)
"cross_dxy_ret_1d"          # DXY Tagesrendite
"cross_coin_ret_1d"         # Coinbase-Aktie Tagesrendite
```

### Kosten
- **$0** — yfinance kostenlos
- **$29/Mt** — Twelve Data Pro (optional, zuverlaessiger)

### Risiken und Fallstricke
- yfinance ist inoffiziell und kann jederzeit brechen (haeufige Breaking Changes)
- Aktiendaten nur waehrend US-Handelszeiten (NYSE 15:30-22:00 CET) — Luecken am Wochenende/Feiertage
- Forward-Fill noetig fuer Wochenenden (kein neues Signal Sa/So)
- MSTR-Premium/Discount kann sich strukturell aendern (z.B. bei BTC-Verkaeufen)
- Korrelationen sind nicht stabil — koennen sich in Krisenzeiten invertieren
- **Cross-Asset-Features existieren bereits** — nur Erweiterung um MSTR/Gold/DXY noetig

### Geschaetzter Aufwand
- **2-3 Tage**
  - Tag 1: yfinance-Fetcher fuer MSTR, Gold, DXY, SPY, COIN
  - Tag 2: Integration in bestehende `cross_asset.py`, Feature-Engineering
  - Tag 3: Backtesting, Forward-Fill-Logik, Live-Integration

---

## Zusammenfassung: Implementierungsreihenfolge

### Phase 1: Quick Wins (Woche 1-2)
| # | Item | Tage | Kosten/Mt |
|---|------|------|-----------|
| C6 | Macro-Daten (FRED + yfinance) | 2-3 | $0 |
| C11 | Cross-Market (MSTR, Gold in bestehende Pipeline) | 2-3 | $0 |
| C7 | Google Trends (Code existiert bereits) | 1-2 | $0 |

**Total Phase 1:** 5-8 Tage, $0/Mt zusaetzlich

### Phase 2: Mittlerer Aufwand, hoher Impact (Woche 3-5)
| # | Item | Tage | Kosten/Mt |
|---|------|------|-----------|
| C4 | Liquidation Heatmaps (Coinglass) | 2-3 | $28 |
| C9 | Stablecoin Supply (DefiLlama) | 2-3 | $0 |
| C2 | News Sentiment (news_analysis_3.0) | 3-5 | ~$30 (LLM) |

**Total Phase 2:** 7-11 Tage, ~$58/Mt zusaetzlich

### Phase 3: Hoehrer Aufwand (Woche 6-8)
| # | Item | Tage | Kosten/Mt |
|---|------|------|-----------|
| C3 | Whale Tracking | 3-4 | $0-35 |
| C1 | Social Sentiment (LunarCrush) | 5-8 | $240 |

**Total Phase 3:** 8-12 Tage, $240-275/Mt zusaetzlich

### Phase 4: Optional / Spaeter evaluieren
| # | Item | Tage | Kosten/Mt | Grund |
|---|------|------|-----------|-------|
| C5 | Order Book Depth | 3-5 | $0 | Alpha v.a. kurzfristig, 1h zu lang |
| C10 | Prediction Markets | 2-3 | $0 | Akademische Evidenz noch duenn |
| C8 | GitHub Activity | 1-2 | $0 | Nicht relevant fuer BTC |

### Gesamtkosten bei voller Implementierung (Phase 1-3)
- **Einmalig:** ~20-31 Entwicklungstage
- **Laufend:** ~$298-333/Mt ($0 ohne LunarCrush, da viele gratis Quellen)
- **Minimal-Setup (Phase 1 only):** 5-8 Tage, $0/Mt

---

## Quellen

### APIs & Plattformen
- [X API Pricing 2026](https://www.xpoz.ai/blog/guides/understanding-twitter-api-pricing-tiers-and-alternatives/)
- [X API Pricing Tiers (Postproxy)](https://postproxy.dev/blog/x-api-pricing-2026/)
- [Reddit API Pricing Guide](https://autogpt.net/how-reddit-api-pricing-works/)
- [LunarCrush Pricing](https://lunarcrush.com/pricing)
- [Santiment API Plans](https://academy.santiment.net/products-and-plans/sanapi-plans/)
- [Whale Alert API](https://docs.whale-alert.io/)
- [Whale Alert Pricing](https://developer.whale-alert.io/pricing.html)
- [Coinglass API Docs](https://docs.coinglass.com/)
- [Coinglass Pricing](https://www.coinglass.com/pricing)
- [Binance Order Book API](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/websocket-api/Order-Book)
- [FRED API](https://fred.stlouisfed.org/docs/api/fred/)
- [fredapi (Python)](https://pypi.org/project/fredapi/)
- [pytrends (Python)](https://pypi.org/project/pytrends/)
- [Santiment Development Activity](https://academy.santiment.net/metrics/development-activity/)
- [Electric Capital Developer Report](https://www.developerreport.com/)
- [DefiLlama Stablecoins](https://defillama.com/stablecoins)
- [CryptoQuant](https://cryptoquant.com)
- [Glassnode](https://glassnode.com)
- [Polymarket API](https://docs.polymarket.com/developers/gamma-markets-api/overview)
- [Kalshi API](https://docs.kalshi.com)
- [Twelve Data](https://twelvedata.com)

### Akademische Papers & Research
- [The predictive power of public Twitter sentiment (ScienceDirect, 2020)](https://www.sciencedirect.com/science/article/abs/pii/S104244312030072X)
- [Sentiment Matters for Cryptocurrencies (MDPI Data, 2025)](https://www.mdpi.com/2306-5729/10/4/50)
- [Deep learning and NLP in cryptocurrency forecasting (ScienceDirect, 2025)](https://www.sciencedirect.com/science/article/pii/S0169207025000147)
- [Attention-augmented CNN-LSTM for crypto sentiment (Nature Sci. Reports, 2025)](https://www.nature.com/articles/s41598-025-18245-x)
- [LLMs and NLP Models in Cryptocurrency Sentiment Analysis (MDPI, 2024)](https://www.mdpi.com/2504-2289/8/6/63)
- [CryptoBERT (HuggingFace)](https://huggingface.co/ElKulako/cryptobert)
- [Do Bitcoin whales generate alpha? (Charles University, 2025)](https://dspace.cuni.cz/bitstream/handle/20.500.11956/196885/120498252.pdf)
- [Forecasting BTC Volatility via On-Chain and Whale-Alert (ResearchGate, 2023)](https://www.researchgate.net/publication/374099900)
- [The role of whale investors in the bitcoin market (ScienceDirect, 2025)](https://www.sciencedirect.com/science/article/abs/pii/S0275531925002648)
- [Price Impact of Order Book Imbalance in Crypto (TDS)](https://towardsdatascience.com/price-impact-of-order-book-imbalance-in-cryptocurrency-markets-bf39695246f6/)
- [Impact of order book asymmetries on crypto prices (Charles University, 2025)](https://dspace.cuni.cz/bitstream/handle/20.500.11956/200516/120505902.pdf)
- [The Bitcoin-Macro Disconnect (NY Fed Staff Report 1052, 2024)](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1052.pdf)
- [Are crypto markets correlated with macro factors? (S&P Global, 2023)](https://www.spglobal.com/content/dam/spglobal/corporate/en/images/general/special-editorial/are-crypto-markets-correlated-with-macroeconomic-factors.pdf)
- [Google Trends as investor sentiment proxy (Springer CJOR, 2025)](https://link.springer.com/article/10.1007/s10100-025-01012-8)
- [Predicting Bitcoin's price using AI (PMC, 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12058735/)
- [BIS Working Paper 1340: Stablecoin flows and FX spillovers (2025)](https://www.bis.org/publ/work1340.pdf)
- [BIS Working Paper 1270: Stablecoins and safe asset prices (2024)](https://www.bis.org/publ/work1270.pdf)
- [NBER: What keeps stablecoins stable? (Lyons)](https://www.nber.org/system/files/working_papers/w27136/w27136.pdf)
- [Do Prediction Markets Forecast Crypto Volatility? (arXiv, 2026)](https://arxiv.org/html/2604.01431)
- [MSTR vs BTC Correlation Analysis (CoinGlass)](https://www.coinglass.com/learn/ana-mstr-btc-corr-en)
- [Crypto developer activity decline (CoinDesk, 2026)](https://www.coindesk.com/tech/2026/03/12/crypto-developer-activity-sinks-to-multi-year-low-as-ai-absorbs-github-s-talent-boom)
