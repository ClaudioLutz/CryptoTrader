# Aktien-Integration in CryptoTrader 3.0 — Landschafts-Recherche

**Datum**: 2026-04-11
**Status**: Breiter Überblick, **keine** Entscheidung
**Kontext**: Python 3.13, asyncio, ccxt, LightGBM, Docker auf GCP VM, Benutzer in der Schweiz
**Ziel**: Das gesamte Feld abstecken, bevor vertieft wird

> Dieses Dokument beantwortet bewusst **nicht** die Frage "welcher Broker ist der beste?".
> Es gibt einen neutralen Überblick über **alle** praktikablen Optionen, damit wir in einer
> zweiten Runde gezielt vertiefen können. Details wie Preise und API-Verfügbarkeit können
> sich ändern — vor einer Entscheidung aktiv nachprüfen.

---

## 1. Broker-API-Landschaft

Die Landschaft zerfällt in vier Gruppen:
**(a)** professionelle Multi-Asset-Broker mit dokumentierter API,
**(b)** Retail-Broker (meist US) mit moderner REST/WebSocket-API,
**(c)** EU/CH-Retail-Broker meist ohne offizielle API,
**(d)** B2B-Infrastrukturanbieter.

### 1a. Professionelle Multi-Asset-Broker

| Broker | Herkunft | Assets | API-Reife | CH-Zugang | Kosten (grob) | Python-Lib |
|---|---|---|---|---|---|---|
| **Interactive Brokers (IBKR)** | USA | Aktien, ETF, Futures, Options, FX, Anleihen, ~150 Börsen | Sehr hoch: TWS API, IB Gateway, Client Portal Web API, neuer REST | Ja, CH-Konto direkt | 0.05–0.35% pro Trade, ~10 USD/Mt Inaktivität (meist entfallend) | `ib_async` (aktiver Fork von `ib_insync`), `ibapi` (offiziell) |
| **Saxo Bank** | DK, hat CH-Entität | Aktien, ETF, Forex, Futures, Optionen, CFDs | Hoch: OpenAPI REST + Streaming | Ja (Saxo Bank CH) | Höher als IBKR, CH-Börse ~0.1% | `saxo-openapi` (Community) |
| **Swissquote** | CH | Aktien, ETF, Forex, Krypto, Optionen | Mittel: Trading-API nur auf Anfrage für Pro-Kunden; Forex via MT4/MT5 | Ja (Heimmarkt) | Hoch (~9–80 CHF/Trade) + Stempelsteuer | keine offizielle Python-Lib |
| **LYNX** | NL, White-Label von IBKR | Wie IBKR | Nutzt IBKR TWS API | Ja | Ähnlich IBKR | `ib_async` |
| **CapTrader** | DE, IBKR-Introducing-Broker | Wie IBKR | IBKR TWS API | Ja | Ähnlich IBKR | `ib_async` |
| **MEXEM** | CY, IBKR-Introducing | Wie IBKR | IBKR TWS API | Ja | Ähnlich, teilweise günstiger | `ib_async` |

### 1b. Retail mit moderner API

| Broker | Herkunft | Assets | CH-Zugang | Python-Lib |
|---|---|---|---|---|
| **Alpaca** | USA | US-Aktien, US-ETF, Krypto, seit 2024 Options | **Nur US-Residents** (Stand 2025) | `alpaca-py` (offiziell) |
| **Tradier** | USA | US-Aktien, Optionen | Nein | `tradier-python` (Community) |
| **TradeStation** | USA | Aktien, Optionen, Futures, Krypto | Limitiert, CH eher nicht | `tradestation-python` |
| **Charles Schwab** | USA | Vollspektrum | Nein für CH-Residents | `schwab-py`, `schwabdev` |
| **Robinhood** | USA | Aktien, Optionen, Krypto | Nein | `robin_stocks` (inoffiziell) |
| **Webull** | USA | Aktien, Optionen, Krypto | Nein | `webull` (inoffiziell) |
| **Questrade** | CA | Aktien, ETF, Optionen, FX | Nein (CA-Residents) | `questrade-api` (Community) |
| **Freedom24** | CY/KZ | Aktien, Optionen, IPOs | Ja (EU-reguliert) | REST auf Anfrage |
| **Zerodha (Kite Connect)** | IN | Indische Aktien, F&O, Commodities | Nein (NRI-Requirements) | `kiteconnect` (offiziell) |
| **Upstox** | IN | Indische Aktien, F&O | Nein | `upstox-python-sdk` |

### 1c. EU/CH-Retail ohne offizielle API

| Broker | Status | Anmerkung |
|---|---|---|
| **DEGIRO** | Keine offizielle API, inoffizielle Libs (`degiro-connector`), ToS-Grauzone | NL, CH zugänglich |
| **Trade Republic** | Keine offizielle API, Community-Reverse-Engineering (`pytr`) nur Read | DE, CH seit 2024 |
| **Scalable Capital** | Keine API | DE |
| **Trading 212** | Keine offizielle Trading-API | CY/UK |
| **Plus500** | Keine API (nur CFD) | CH-reguliert |
| **eToro** | Keine öffentliche Retail-API (B2B Partner-API für Copy-Trading) | CH zugänglich |
| **Bitpanda Stocks** | Keine Trading-API; Stocks sind synthetisch | AT |

### 1d. B2B-Infrastruktur (nicht für Einzelkunden)

- **DriveWealth** — US-Aktien, Fractional Shares, Enterprise-Pricing, nur Fintech-Kunden
- **Alpaca Broker API** — separates Produkt für Fintechs (vs. Trading-API für Einzelkunden)

### 1e. Krypto-Börsen mit Aktien-Tokens

- **Binance Stock Tokens** — gestartet 2021, **April 2021 eingestellt** (regulatorischer Druck)
- **FTX Tokenized Stocks** — nach FTX-Kollaps 2022 erledigt
- **Kraken Securities** (UK) — Launch mehrfach verschoben, Stand 2025 noch nicht breit
- **Backed Finance (xStocks)** — **Schweizer FINMA-regulierter Emittent**, tokenisierte Aktien (AAPLX, TSLAX etc.) auf Solana/Ethereum, handelbar via Kraken, Bybit und DEX. **Relevant für CH wegen FINMA-Regulierung**

---

## 2. Alternative Asset-Klassen im gleichen Kontext

| Klasse | Typische Broker | Python-Einstieg | Relevanz |
|---|---|---|---|
| **ETFs** | IBKR, Saxo, Swissquote | Gleich wie Aktien | Liquider als Einzeltitel, weniger Earnings-Risk — natürlicher Einstieg |
| **Futures (CME, Eurex, CBOE)** | IBKR, Saxo, TradeStation | `ib_async` | Hebel, teils 24h-Handel, gut für Macro-Strategien |
| **Optionen** | IBKR, Tradier, Alpaca, Schwab | `ib_async`, `py_vollib` | Komplexer (Greeks); für ML fortgeschritten |
| **Forex** | OANDA (v20 REST, `oandapyV20`), IBKR, Saxo, dukascopy, FXCM | `oandapyV20`, `MetaTrader5` | Retail-dominiert durch MT4/5 |
| **Prediction Markets** | Polymarket (on-chain, USDC auf Polygon), Kalshi (US), Manifold | `py-clob-client` (Polymarket) | Polymarket via DeFi CH-zugänglich; Kalshi US-only |
| **Synthetische DeFi-Assets** | Synthetix, GMX | `web3.py`, `ethers` | Liquidität moderat |
| **Tokenized Stocks** | Backed Finance (xStocks), Swarm Markets | DEX-basiert | CH-regulierter Sonderweg |
| **Commodities via ETFs/Futures** | IBKR, Saxo | wie Aktien/Futures | GLD, GC=F, USO, CL=F |

---

## 3. Market-Data-Anbieter

### Gratis / Hobby

| Anbieter | Stärken | Schwächen |
|---|---|---|
| **yfinance** | Bereits im Projekt, breit, kein Auth | Inoffiziell, wird zunehmend fragil, Rate-Limits unklar |
| **Stooq** | Gratis historische EOD, breit (EU inkl.) | Kein Realtime |
| **SEC EDGAR** | **Gold-Standard für US-Filings**, Form 4 (Insider), 10-K/10-Q, 13F | Nur USA |
| **FRED (St. Louis Fed)** | Gratis, Makro (Yields, VIX, CPI, Unemployment) | Nur Makro |
| **Alpha Vantage** | Freemium (5 Calls/Min gratis) | Langsam im Free-Tier |
| **Finnhub** | 60 Calls/Min gratis, Company News, Sentiment | Realtime ab ~50 USD/Mt |
| **Twelve Data** | 800 Calls/Tag gratis | Premium ab 29 USD/Mt |
| **Marketstack** | REST, günstig (ab 10 USD/Mt) | EOD-Fokus |

### Professionell / Mid-Tier

| Anbieter | Preis | Stärken |
|---|---|---|
| **Polygon.io** | 29/79/199 USD/Mt | US-Aktien, Optionen, Forex, Krypto; REST + WebSocket; hohe Qualität |
| **Tiingo** | ab ~10 USD/Mt | US-Aktien + News + Crypto, saubere Fundamentals |
| **Financial Modeling Prep (FMP)** | 22–129 USD/Mt | Breit, inkl. Earnings-Call-Transkripte |
| **EOD Historical Data** | 20–80 USD/Mt | **Breite internationale Abdeckung** (inkl. SIX Swiss Exchange) |
| **Nasdaq Data Link** (ex-Quandl) | Je Datensatz | Diverse Quant-Datasets |
| **Intrinio** | ab ~100 USD/Mt | Mid-Market |
| **Benzinga** | ab ~200 USD/Mt | Pro-Daten + News |
| **IEX Cloud** | **Eingestellt August 2024** | — |

### Enterprise

- **Refinitiv Eikon/LSEG** — 4–5-stellig pro Jahr
- **Bloomberg Terminal + BLPAPI** — 2'500 USD/Mt pro User, Python `blpapi`
- **FactSet, AlphaSense, Ravenpack** — alles Enterprise

### News/Sentiment

- **NewsAPI.org** — gratis, breit aber nicht finanzspezifisch
- **Marketaux** — Finanznews mit Entity-Tagging, günstig
- **StockNewsAPI** — ähnlich
- **Benzinga News** — qualitativ hoch, teuer
- **Finnhub News** — im Finnhub-Abo inkludiert

### Krypto (für bestehenden Teil)

- **CryptoCompare**, **CoinGecko** (Pro ab 129 USD/Mt), **CoinMarketCap API**, **Kaiko** (institutional), **Amberdata**

---

## 4. Backtesting- und Trading-Frameworks

| Framework | Aktien | Krypto | Live | Aktivität 2025 | Bemerkung |
|---|---|---|---|---|---|
| **backtrader** | Ja | Ja (via ccxt-store) | Ja (IB, Oanda, ccxt) | Wenig Entwicklung seit 2022 | Reifer Klassiker, Community-Forks |
| **Zipline-Reloaded** | Ja (primär) | Limitiert | Nein | Aktiv (Stefan Jansen) | Quantopian-Erbe, US-Aktien |
| **Catalyst** | Nein | Ja | Nein | **Tot** (2019) | — |
| **vectorbt** | Ja | Ja | Nein | Aktiv | NumPy-vectorized, schnell für Research |
| **vectorbt PRO** | Ja | Ja | Nein | Aktiv (~500–1000 USD/Jahr) | Deutlich mächtiger |
| **QuantConnect LEAN** | Ja (sehr stark) | Ja | Ja (IB, Tradier, Bitfinex, Binance, Coinbase, OANDA, TradeStation, Kraken, Bybit, ...) | Sehr aktiv | **Multi-Asset Gold-Standard OSS**, C#-Kern + Python-API |
| **Nautilus Trader** | Ja | Ja (FX, Futures, Options, Crypto) | Ja | **Sehr aktiv (2024/25 viel Momentum)** | Rust-Kern + Python, Event-Driven, Low-Latency |
| **QSTrader** | Ja | Begrenzt | Nein | Mässig aktiv | Portfolio-Fokus |
| **FreqTrade** | Nein | Ja | Ja | Sehr aktiv | Krypto-Retail-Standard |
| **Jesse** | Nein | Ja | Ja | Aktiv | Krypto-only Python-DSL |
| **Hummingbot** | Nein | Ja (+DeFi) | Ja | Sehr aktiv | Market-Making-Fokus |
| **bt** | Ja | Ja | Nein | Wenig aktiv | Portfolio-Backtesting, simpel |
| **fastquant** | Ja | Ja | Nein | Legacy | Wrapper um backtrader |
| **Lumibot** | Ja | Ja | Ja (Alpaca, IB, Tradier) | Aktiv | Simpel, Alpaca-first |

---

## 5. Unterschiede Krypto vs. Aktien

- **Handelszeiten** — Krypto 24/7; Aktien haben Öffnungszeiten (NYSE/NASDAQ 9:30–16:00 ET, SIX 9:00–17:30 CET, Xetra 9:00–17:30 CET). Pre/After-Hours illiquid.
- **Market Calendar** — Feiertage pro Börse; Python-Libs: `pandas-market-calendars`, `exchange_calendars`.
- **Settlement** — Aktien **T+1** seit Mai 2024 in USA, T+2 in EU (Umstellung auf T+1 geplant für Oktober 2027). Krypto sofort.
- **Corporate Actions** — Splits, Dividenden, Spin-offs, Merger — **wesentlich** für korrekte Backtests (Total-Return-Serien). Krypto hat nur Forks/Token-Swaps.
- **FX / Multi-Currency** — Aktien oft in USD/EUR/CHF → P&L-Aggregation nicht trivial. Krypto intern meist USDT/USDC.
- **Liquidität / Slippage** — Small-Caps haben dünne Orderbücher.
- **Short Selling** — Aktien benötigen Borrow (Locate-Fee, Recall-Risk). Krypto-Perps haben Funding Rates.
- **Regulatorisches** — Aktien = Wertpapiere (strenger). Insider-Regeln, Wash-Sale-Regel (US), Market-Manipulation-Gesetze.
- **Gebührenstruktur** — Aktien oft fix + Stempelgebühr + FX; Krypto prozentual Maker/Taker.
- **Market Microstructure** — Aktien haben Auktionen (Open/Close), Halts, Circuit Breakers, Limit Up/Down.

---

## 6. Regulatorische Perspektive Schweiz

- **FINMA-Status Privatperson** — Eigenhandel mit eigenem Vermögen ist **nicht bewilligungspflichtig**. Sobald für Dritte gehandelt wird → Bewilligung nötig.
- **Gewerbsmässiger Wertschriftenhändler** (ESTV Kreisschreiben Nr. 36): 5 Kriterien — Haltedauer, Transaktionsvolumen, Kapitalgewinn-Anteil am Einkommen, Fremdkapital-Einsatz, Derivate-Nutzung. Wer als gewerbsmässig eingestuft wird, zahlt **Einkommenssteuer + AHV auf Kapitalgewinne**, sonst sind Kapitalgewinne steuerfrei. **Algorithmischer Hochfrequenz-Handel bringt automatisch Gewerbsmässigkeit-Risiko**.
- **Stempelsteuer (Umsatzabgabe)** — 0.075% auf CH-Titel, 0.15% auf ausländische Titel. Fällt bei CH-Brokern an, bei IBKR/Saxo teilweise nicht. Bei aktivem Trading substantiell.
- **Verrechnungssteuer** — 35% auf CH-Dividenden, rückforderbar bei Steuererklärung.
- **MiFID II / FIDLEG** — betrifft Broker, nicht dich als Privatperson.
- **AEOI** — IBKR/Alpaca/etc. melden an CH-Steuerbehörden.
- **Krypto-Gesetz (DLT-Gesetz seit 2021)** — tokenisierte Wertrechte sind anerkannt → Basis für Backed Finance xStocks.

---

## 7. Architektur-Patterns für Multi-Asset-Bots

Was etablierte Frameworks tun:

- **Asset-Klassen-Abstraktion** — Lean hat `Security` mit Subtypen `Equity`, `Crypto`, `Forex`, `Future`, `Option`, `Cfd`. Nautilus hat `Instrument`-Typen analog. backtrader nutzt `Data`-Feeds (weniger strikt typisiert).
- **Unified Symbol Schema** — Lean `Symbol` mit `SecurityIdentifier` (ID, Market, SecurityType). Nautilus `InstrumentId` mit Venue. ccxt nutzt `BASE/QUOTE`-Strings. Für Multi-Asset eigenes Schema nötig (z.B. `AAPL.NASDAQ`, `BTC-USDT.BINANCE`).
- **Market Calendar Handling** — `pandas-market-calendars` / `exchange_calendars` sind Python-Standard. Lean hat eingebauten Kalender-Service. Wichtig für: Backtest-Loop (keine Bars am Wochenende), Order-Submission (nicht bei geschlossenem Markt), Bar-Alignment.
- **Multi-Currency P&L** — Lean konvertiert alles in Account-Currency zum historischen Kurs. Nautilus hat Multi-Currency-Portfolio. Eigene Lösung braucht **FX-Kurs-Historie** (OANDA, ECB-Feed).
- **Datenmodell** — Event-driven (Nautilus, Lean) vs. Vectorized (vectorbt, bt). Für Live/Backtest-Symmetrie ist Event-Driven überlegen; Vectorized ist schneller für Research.
- **Order-Router / Execution-Adapter** — abstraktes `ExecutionVenue`-Interface, pro Broker eine Implementierung. Lean hat ~15 Brokerage-Integrationen.
- **Position Sizing / Risk** — Asset-Klassen-spezifisch: Aktien Cash-basiert, Futures Margin-basiert, Optionen Greeks-basiert.

---

## 8. ML-Strategien spezifisch für Aktien (die im Krypto-Projekt noch fehlen)

- **Post-Earnings-Announcement Drift (PEAD)** — Aktien driften nach Earnings-Surprises Tage/Wochen in Überraschungsrichtung. Braucht Earnings-Calendar + EPS-Estimates (Zacks, Finnhub, FMP).
- **Insider Trading Signals** — Form-4-Filings von SEC EDGAR. Cluster-Buys von Insidern historisch prädiktiv. Gratis via EDGAR.
- **13F-Filings** — quartalsweise Hedgefund-Positionen mit 45-Tage-Lag. Hobby-Projekt-Material.
- **Short Interest / Borrow Rate** — FINRA-Daten, IBKR-Borrow-API.
- **Sector Rotation / Regime Detection** — Fama-French-Faktoren, Business-Cycle-Modelle, Cross-Asset mit Makro (Yields, DXY).
- **Mean Reversion / Pairs Trading** — Kointegration (Engle-Granger, Johansen). Klassiker — bei Krypto schwer weil alles mit BTC korreliert.
- **Cross-Sectional Ranking** — Portfolio-Modell statt Zeitreihen-Modell: ranke täglich N Aktien nach Score, Long-Top-Decile/Short-Bottom-Decile. Lean, Qlib und alphalens sind darauf ausgelegt.
- **Factor Investing** — Value (P/E, P/B), Momentum (12-1 Monate), Quality (ROE, Gross Profitability), Low-Vol, Size. Multi-Factor-Modelle. Braucht Fundamentaldaten.
- **News-NLP / Event Study** — FinBERT, Llama-basierte Finanz-LLMs, Earnings-Call-Transkript-Analyse.
- **Options-Flow-Signale** — Unusual Options Activity, Put/Call-Ratios. Teure Daten.
- **Seasonality / Calendar Effects** — January Effect, Sell-in-May, Turn-of-Month. In Krypto nicht stabil.
- **Analyst-Revisions-Momentum** — Upgrades/Downgrades, EPS-Revisions.

---

## 9. Open-Source-Projekte die Multi-Asset ML-Trading machen

- **Microsoft Qlib** ([github.com/microsoft/qlib](https://github.com/microsoft/qlib)) — **Aktienfokus, ML-first, inkl. LightGBM-Beispiele!** Alpha-Factor-Framework, Rolling-Training, CN/US-Märkte. **Sehr relevant fürs bestehende Profil**, da LightGBM bereits im Stack.
- **QuantConnect LEAN** ([github.com/QuantConnect/Lean](https://github.com/QuantConnect/Lean)) — Multi-Asset, Multi-Broker, Multi-Data. C#-Kern mit Python-API. Cloud oder Self-Hosted.
- **Nautilus Trader** ([github.com/nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader)) — modernes Rust+Python, Multi-Asset, Low-Latency.
- **FinRL** ([github.com/AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL)) — Reinforcement Learning für Aktien+Krypto, akademisch.
- **TensorTrade** — RL-Framework, inaktiv seit 2022.
- **zipline-trader** — Zipline-Fork mit Alpaca-Integration, semi-aktiv.
- **alphalens / pyfolio** — Quantopian-Analyse-Tools, im Zipline-Reloaded-Ökosystem gepflegt.
- **Awesome Quant** ([github.com/wilsonfreitas/awesome-quant](https://github.com/wilsonfreitas/awesome-quant)) — kuratierte Liste.
- **Machine Learning for Trading** ([github.com/stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading)) — Buch + Code von Stefan Jansen, Aktien + LightGBM explizit.
- **OpenBB Platform** ([github.com/OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB)) — Open-Source-Bloomberg-Alternative, viele Data-Provider unter einem Dach.
- **FinGPT / FinBERT** — Finanz-LLMs auf HuggingFace.
- **Papers** — Marcos López de Prado "Advances in Financial Machine Learning" (2018): Meta-Labeling, Triple-Barrier-Method — Aktien-kompatibel.

---

## Mögliche Vertiefungs-Richtungen (für die nächste Runde)

Nach dieser Übersicht sehe ich fünf plausible Vertiefungs-Richtungen. Die eigentliche Entscheidung sollte erst **nach** einer dieser Vertiefungen getroffen werden:

1. **Broker-Deep-Dive** — IBKR vs. Saxo vs. Swissquote detailliert vergleichen (Gebühren-Szenario für 10k / 200 Trades, echte API-Limitationen, Gateway-Deployment).
2. **Framework-Deep-Dive** — Eigenen `BrokerAdapter`-Layer bauen vs. auf **QuantConnect LEAN** oder **Nautilus** migrieren. Grosse Architektur-Entscheidung.
3. **ML-Deep-Dive** — **Microsoft Qlib** evaluieren: wie gut passt es auf das bestehende LightGBM-Setup? Was wäre der Migrationspfad?
4. **Strategie-Deep-Dive** — Welche **Aktien-spezifischen ML-Strategien** sind für einen Einzelkunden mit 10k realistisch? Cross-Sectional Ranking vs. Time-Series vs. PEAD?
5. **Tokenized-Stocks-Deep-Dive** — **Backed Finance xStocks** wäre der minimale Integrationsaufwand (einfach neue Symbole auf Kraken/DEX), aber begrenztes Universum. Lohnt es sich als Zwischenschritt?

---

## Quellen

**Broker-APIs**
- IBKR API: [interactivebrokers.github.io/tws-api/](https://interactivebrokers.github.io/tws-api/)
- ib_async: [github.com/ib-api-reloaded/ib_async](https://github.com/ib-api-reloaded/ib_async)
- Alpaca: [alpaca.markets/docs/](https://alpaca.markets/docs/)
- Saxo OpenAPI: [developer.saxo/](https://developer.saxo/)
- Schwab API: [developer.schwab.com/](https://developer.schwab.com/)
- Kite Connect: [kite.trade/docs/connect/v3/](https://kite.trade/docs/connect/v3/)

**Frameworks**
- QuantConnect LEAN: [github.com/QuantConnect/Lean](https://github.com/QuantConnect/Lean)
- Nautilus Trader: [nautilustrader.io](https://nautilustrader.io/)
- Microsoft Qlib: [github.com/microsoft/qlib](https://github.com/microsoft/qlib)

**Daten**
- Polygon: [polygon.io](https://polygon.io/)
- Finnhub: [finnhub.io](https://finnhub.io/)
- FMP: [site.financialmodelingprep.com](https://site.financialmodelingprep.com/)
- EOD HD: [eodhistoricaldata.com](https://eodhistoricaldata.com/)
- SEC EDGAR: [sec.gov/edgar](https://www.sec.gov/edgar)
- FRED: [fred.stlouisfed.org](https://fred.stlouisfed.org/)

**Calendars**
- pandas-market-calendars: [github.com/rsheftel/pandas_market_calendars](https://github.com/rsheftel/pandas_market_calendars)
- exchange_calendars: [github.com/gerrymanoim/exchange_calendars](https://github.com/gerrymanoim/exchange_calendars)

**Schweiz**
- Backed Finance xStocks: [backedfi.com](https://backedfi.com)
- ESTV Kreisschreiben Nr. 36: [estv.admin.ch](https://www.estv.admin.ch)

**Community**
- Awesome Quant: [github.com/wilsonfreitas/awesome-quant](https://github.com/wilsonfreitas/awesome-quant)
- ML for Trading (Stefan Jansen): [github.com/stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading)

---

> **Wichtige Einschränkung**: Preise, API-Releases und regulatorische Details können sich
> zwischen dem Recherche-Stand und heute geändert haben — speziell Schwab-API-Evolution,
> Kraken-Securities-Launch, EU-T+1-Umstellung, neue xStocks-Listings und Alpaca-International-
> Zugang vor einer Entscheidung aktiv gegenprüfen.
