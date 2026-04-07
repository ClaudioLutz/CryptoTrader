# E) Infrastruktur & Operations — Vertiefte Recherche

> Zurueck zur Uebersicht: [erweiterungsmoeglichkeiten.md](erweiterungsmoeglichkeiten.md)

**Datum:** 2026-04-06 (aktualisiert 2026-04-07)
**Kontext:** CryptoTrader 3.0 — GCP e2-small (2 vCPUs @ 25%, 2 GB RAM, ~10 CHF/Mt), Docker auf Container-Optimized OS, Bot 24/7, Dashboard lokal via SSH-Tunnel

> **Status-Update 2026-04-07:** E1 (Telegram Bot) wurde am 2026-04-06 implementiert und deployed. Nutzt direkt Telegram Bot API via aiohttp (keine extra Dependency). Token auf VM noch nicht gesetzt — Telegram ist deployed aber inaktiv bis Token konfiguriert wird.

---

## E1: Telegram Bot — UMGESETZT 2026-04-06

### Was es ist
Ein Messaging-Bot, der bei Trade-Ausfuehrungen sofort eine Notification sendet und taeglich eine P&L-Zusammenfassung liefert. Ermoeglicht Echtzeit-Ueberwachung des Bots ohne Dashboard-Zugriff.

### Konkrete Implementierungsdetails

**Empfehlung: Telegram** (bevorzugt gegenueber Discord fuer Solo-Trader)

**Library**: `python-telegram-bot` v22+ (vollstaendig async, basiert auf `asyncio`)
- Alternative: `aiogram` (ebenfalls async, leichtgewichtiger)
- Fuer reine Notifications ohne Command-Handling reicht auch direkt die Telegram Bot API via `aiohttp` (bereits im Projekt)

**Architektur-Integration**:
```
Bot (asyncio loop) → Event-System → TelegramNotifier
                                         ↓
                                    Telegram Bot API
                                         ↓
                                    Smartphone
```

**Wichtig bei python-telegram-bot v21+**: Die Convenience-Methoden `run_polling()`/`run_webhook()` blockieren den Event-Loop. Fuer die Integration in den bestehenden asyncio-Loop des Trading-Bots muessen `Application.initialize()`, `start()` und `shutdown()` manuell aufgerufen werden.

**Minimale Implementierung** (reiner Notification-Sender):
- Neues Modul `src/crypto_bot/notifications/telegram.py`
- `TelegramNotifier`-Klasse mit `send_trade()`, `send_daily_summary()`, `send_alert()`
- Bot-Token und Chat-ID ueber `.env` konfigurieren
- Hook in `bot.py` bei Trade-Ausfuehrung und als Scheduled Task fuer Daily Summary

**Setup fuer den Nutzer**:
1. BotFather auf Telegram → neuen Bot erstellen → Token erhalten
2. Chat mit Bot starten → Chat-ID ermitteln (z.B. via `getUpdates`)
3. `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` in `.env`

**Discord-Alternative**:
- Library: `discord.py` v2.x (async)
- Einfacher: Webhook-URL (kein Bot noetig, reiner POST-Request via `aiohttp`)
- Nachteil: Overkill fuer Solo-Nutzung, Server-Setup noetig

### Kosten
- **Telegram Bot API**: Kostenlos, keine Rate-Limits fuer normale Nutzung (< 30 Nachrichten/Sekunde)
- **Discord Webhook**: Kostenlos
- **VM-Ressourcen**: Vernachlaessigbar (ein HTTP-Request pro Trade)

### Relevanz fuer dieses Projekt
**Hoch**. Derzeit ist der einzige Weg, den Bot-Status zu pruefen, das Dashboard via SSH-Tunnel zu starten. Telegram-Notifications sind die einfachste Methode, unterwegs informiert zu bleiben — besonders wichtig bei einem Bot mit echtem Geld.

### Risiken und Fallstricke
- **Telegram-Ausfaelle**: Selten, aber Notifications koennen verzoegert ankommen. Nicht als primaere Fehler-Erkennung nutzen.
- **Token-Sicherheit**: Bot-Token darf nicht ins Git-Repo. Bereits ueber `.env`-Pattern abgesichert.
- **Event-Loop-Konflikte**: python-telegram-bot v21+ will eigenen Event-Loop managen. Loesung: Nur den Bot-Client direkt nutzen (`telegram.Bot.send_message()`), nicht das Application-Framework.
- **Nachrichtenflut**: Bei vielen Trades (12 Coins × mehrere Signale) koennen viele Nachrichten entstehen. Loesung: Nur tatsaechliche Ausfuehrungen notifizieren, nicht Signale.

### Geschaetzter Aufwand
**2–3 Tage**
- Tag 1: TelegramNotifier-Klasse, Integration in Bot-Loop, .env-Konfiguration
- Tag 2: Nachrichtenformatierung (Markdown), Daily-Summary-Job, Error-Notifications
- Tag 3: Testing, Deployment auf VM, Edge-Cases (Bot-Restart, Netzwerkfehler)

---

## E2: Automated Reporting — taeglicher/woechentlicher Performance-Report

### Was es ist
Automatisierte Erstellung und Versand von Performance-Reports als PDF/HTML mit Kennzahlen wie P&L, Win-Rate, Drawdown, offene Positionen. Taeglich und/oder woechentlich.

### Konkrete Implementierungsdetails

**Libraries**:
- Report-Generierung: `plotly` (bereits im Projekt) + `kaleido` fuer statische Bilder
- PDF-Erstellung: `weasyprint` oder `reportlab` oder `fpdf2`
- HTML-Reports: `jinja2` Templates (leichtgewichtig, kein PDF noetig)
- Versand: Via Telegram (einfachste Option, kein SMTP noetig) oder `smtplib` + Gmail

**Architektur**:
```
Scheduled Task (asyncio) → ReportGenerator
    ↓                          ↓
Datenbank-Abfrage       Plotly-Charts → HTML/PDF
    ↓                          ↓
Aggregation             Telegram/Email-Versand
```

**Empfohlener Ansatz** (minimale Komplexitaet):
1. `ReportGenerator`-Klasse in `src/crypto_bot/reporting/`
2. Report als HTML mit eingebetteten Plotly-Charts (kein PDF noetig)
3. Versand als Telegram-Nachricht (Text-Summary) + HTML-Datei
4. Scheduling: `asyncio.create_task()` mit taeglichem Timer im bestehenden Bot-Loop

**Report-Inhalte**:
- Tagesperformance: P&L (absolut + %), Trades, Win-Rate
- Offene Positionen mit unrealisiertem P&L
- Equity-Kurve (7/30 Tage)
- Model-Confidence-Verteilung
- Woechentlich zusaetzlich: Coin-Attribution, Drawdown-Analyse

### Kosten
- **Libraries**: Kostenlos (Open Source)
- **Email-Versand via Gmail**: Kostenlos (bis 500/Tag)
- **Telegram-Versand**: Kostenlos
- **VM-Ressourcen**: Plotly-Chart-Rendering braucht kurzzeitig RAM. Bei 2 GB knapp, aber machbar wenn nicht waehrend Retraining.

### Relevanz fuer dieses Projekt
**Mittel-Hoch**. Ergaenzt E1 (Telegram) perfekt — Echtzeit-Notifications plus taegliche Zusammenfassung. Allerdings: Wenn E1 implementiert ist, deckt die Daily-Summary-Notification bereits 80% des Nutzens ab. Ein visueller Report mit Charts bringt dann noch ~20% Mehrwert.

### Risiken und Fallstricke
- **RAM-Limits auf e2-small**: Chart-Rendering mit Plotly/Kaleido kann 200–500 MB verbrauchen. Timing mit Retraining koordinieren.
- **Komplexitaet**: PDF-Generierung ist erstaunlich frickelig (Schriften, Layout, Unicode). HTML-Reports sind deutlich einfacher.
- **Zeitzone**: Reports muessen konsistent UTC oder lokale Zeit verwenden.

### Geschaetzter Aufwand
**3–4 Tage**
- Tag 1: ReportGenerator-Grundstruktur, Daten-Aggregation
- Tag 2: Plotly-Charts, HTML-Template
- Tag 3: Scheduling, Telegram/Email-Integration
- Tag 4: Testing, Edge-Cases (leere Tage, fehlende Daten)

---

## E3: A/B Testing / Shadow Mode — neue Strategien parallel Paper-Traden

### Was es ist
Neue Trading-Strategien laufen parallel zum Live-Bot im "Shadow Mode": Sie empfangen dieselben Marktdaten, treffen Entscheidungen, fuehren aber keine echten Trades aus. Die simulierten Ergebnisse werden protokolliert und koennen mit der Live-Strategie verglichen werden.

### Konkrete Implementierungsdetails

**Architektur-Ansatz**:
```
Marktdaten (Live) ──┬──→ Live-Strategie → Echte Trades (Binance)
                    │
                    └──→ Shadow-Strategie A → Simulierte Trades (DB)
                    └──→ Shadow-Strategie B → Simulierte Trades (DB)
```

**Implementierung**:
- Bestehende `Strategy`-Basisklasse und `ExecutionContext` nutzen
- Neuer `ShadowExecutionContext` der `ExecutionContext` implementiert, aber Trades nur in DB schreibt
- Shadow-Strategien im selben asyncio-Loop ausfuehren (zusaetzliche Tasks)
- Separates DB-Schema/Tabelle fuer Shadow-Trades: `shadow_orders`, `shadow_positions`

**Dry-Run vs. Shadow**:
- Das Projekt hat bereits `TRADING__DRY_RUN=true` im Dockerfile
- Shadow Mode geht weiter: Mehrere Strategien gleichzeitig, Vergleichs-Dashboard
- Binance Testnet (neuer Endpoint: `demo-api.binance.com`) ist eine Option, aber unnoetig — reine Simulation im Bot reicht

**Vergleichs-Metriken**:
- P&L pro Strategie
- Win-Rate, Sharpe Ratio
- Signal-Uebereinstimmung (wo waeren beide long/short gewesen?)
- Statistischer Signifikanztest nach N Trades

**Dashboard-Erweiterung**:
- Neue Tab-Seite: "Shadow Strategies" mit Vergleichs-Charts
- Side-by-side Equity-Kurven

### Kosten
- **Zusaetzliche VM-Ressourcen**: Jede Shadow-Strategie braucht ~50–100 MB RAM fuer Model + State. Bei 2 GB VM max. 1–2 Shadow-Strategien parallel zum Live-Bot.
- **Keine Exchange-Kosten**: Kein zusaetzlicher API-Traffic noetig (Marktdaten werden geteilt)

### Relevanz fuer dieses Projekt
**Hoch**. Bei einem Bot mit echtem Geld ist die Moeglichkeit, neue Modelle/Parameter risikofrei zu testen, extrem wertvoll. Aktuell muss jede Aenderung direkt live gehen oder nur per Backtest validiert werden — Shadow Mode schliesst die Luecke zwischen Backtest und Live.

### Risiken und Fallstricke
- **RAM-Limits**: e2-small hat nur 2 GB. LightGBM-Model + Retraining + Shadow-Strategien koennen OOM verursachen. Loesung: Shadow-Strategien zeitversetzt zum Retraining laufen lassen.
- **Realismus der Simulation**: Ohne echte Orderbuch-Simulation ist die Shadow-Performance optimistischer (kein Slippage, perfekte Fills). Fuer Prediction-Strategie mit kleinen Positionen ist das akzeptabel.
- **Komplexitaet**: Saubere Trennung Live/Shadow erfordert gutes Interface-Design. Der bestehende `ExecutionContext`-Pattern ist dafuer gut geeignet.
- **Statistische Signifikanz**: Bei 1h-Timeframe und 12 Coins dauert es Wochen/Monate bis ein aussagekraeftiger Vergleich moeglich ist.

### Geschaetzter Aufwand
**5–7 Tage**
- Tag 1–2: ShadowExecutionContext, Shadow-DB-Schema
- Tag 3: Integration in Bot-Loop, Konfiguration via config.yaml
- Tag 4–5: Vergleichs-Logik, Metriken-Berechnung
- Tag 6–7: Dashboard-Tab, Equity-Vergleichs-Charts

---

## E4: Auto-Scaling Capital — bei nachhaltigem Profit automatisch Kapital erhoehen

### Was es ist
Der Bot erhoet automatisch die Positionsgroessen wenn sich ein nachhaltiger Profit-Trend zeigt. Umgekehrt reduziert er bei Verlusten. Ziel: Compound-Effekt nutzen, ohne manuell eingreifen zu muessen.

### Konkrete Implementierungsdetails

**Ansaetze (von konservativ bis aggressiv)**:

1. **Fixed-Fraction (Kelly-Criterion-basiert)**:
   - Positionsgroesse = f(aktuelles Portfolio-Equity, Win-Rate, Risk/Reward)
   - Kelly-Fraction: `f* = W - (1-W)/R` wobei W=Win-Rate, R=avg_win/avg_loss
   - Empfehlung: Half-Kelly (50% der berechneten Fraction) fuer Sicherheit

2. **Stufenmodell** (einfacher, empfohlen fuer den Start):
   - Equity < Startkapital: Minimale Positionsgroesse (Schutz)
   - Equity 100–110% Start: Normale Positionsgroesse
   - Equity 110–130% Start: +25% Positionsgroesse
   - Equity > 130% Start: +50% Positionsgroesse
   - Taeglich neu berechnet

3. **Profit-Reinvestment** (Bitsgap/3Commas-Ansatz):
   - X% der realisierten Gewinne werden in groessere Positionen reinvestiert
   - Typisch: 50–80% Reinvestment-Rate

**Sicherheitsmechanismen (PFLICHT)**:
- **Max-Exposure-Cap**: Nie mehr als X% des Gesamtportfolios in offenen Positionen
- **Daily-Drawdown-Breaker**: Bei > 3% Tagesverlust zurueck auf Minimal-Groesse
- **Cool-Down nach Verlusten**: Nach N Verlust-Trades in Folge Position reduzieren
- **Absolute Obergrenze**: Maximale Positionsgroesse unabhaengig von Equity

**Implementierung**:
- Neues Modul `src/crypto_bot/risk/capital_scaler.py`
- Integration in bestehende `risk/`-Logik
- Konfiguration ueber `config.yaml`:
  ```yaml
  capital_scaling:
    enabled: true
    mode: "stepped"  # oder "kelly", "reinvestment"
    max_exposure_pct: 0.06  # max 6% Portfolio in offenen Positionen
    daily_drawdown_limit: 0.03
    reinvestment_rate: 0.5
  ```

### Kosten
- **Keine zusaetzlichen Infrastrukturkosten**
- **Risiko-Kosten**: Fehlerhafte Skalierung kann zu uebermaessigen Verlusten fuehren

### Relevanz fuer dieses Projekt
**Mittel**. Sinnvoll erst wenn die Strategie nachweislich profitabel ist (aktuell: 58.3% Win-Rate, +0.93% Avg P&L laut Commit-History). Das Stufenmodell waere ein guter Start — aber erst nach mehreren Wochen/Monaten positiver Live-Performance.

### Risiken und Fallstricke
- **Premature Scaling**: Die groesste Gefahr. Wenn die Strategie in einer guten Phase skaliert und dann eine Verlustphase kommt, sind die Verluste ueberproportional.
- **Overfitting auf historische Performance**: Win-Rate und Avg P&L koennen sich aendern.
- **Volatilitaets-Cluster**: Crypto-Maerkte haben Phasen hoher Volatilitaet. Auto-Scaling muss volatilitaetsbereinigt sein.
- **Regulatory**: Bei groesseren Summen koennten steuerliche/regulatorische Aspekte relevant werden.
- **Empfehlung**: Mindestens 3 Monate profitable Live-Performance vor Aktivierung. Zuerst im Shadow Mode testen (E3).

### Geschaetzter Aufwand
**3–4 Tage**
- Tag 1: CapitalScaler-Klasse mit Stufenmodell
- Tag 2: Sicherheitsmechanismen (Drawdown-Breaker, Exposure-Cap)
- Tag 3: Integration in Bot, Config, Logging
- Tag 4: Testing (Backtests mit verschiedenen Scaling-Szenarien)

---

## E5: Monitoring (Grafana/Prometheus) — Bot-Health, P&L, Latenz

### Was es ist
Professionelles Monitoring des Trading-Bots mit Metriken-Erfassung (Prometheus) und Visualisierung (Grafana). Ueberwacht Bot-Gesundheit, Trading-Performance und Systemressourcen.

### Konkrete Implementierungsdetails

**Problem: e2-small hat nur 2 GB RAM**
- Prometheus (voll): ~500 MB–1 GB RAM → zu viel
- Grafana: ~200–400 MB RAM → zu viel
- Beides zusammen: Nicht machbar auf e2-small neben dem Trading-Bot

**Loesung A: Grafana Cloud Free Tier (EMPFOHLEN)**
```
[GCP VM]                          [Grafana Cloud]
Bot → prometheus_client   ───→    Grafana Cloud
      (Metrics-Endpoint)          (Free: 10'000 active series)
      /metrics auf Port 8082      Dashboards, Alerting
```

- Bot exponiert Metriken via `prometheus_client` Python-Library (< 10 MB RAM)
- Grafana Cloud Free Tier scraped die Metriken (kostenlos bis 10'000 active series)
- Kein Prometheus/Grafana auf der VM noetig
- Free Tier: 3 User, 10'000 Metriken-Serien, 14 Tage Retention

**Loesung B: Leichtgewichtiger Self-Hosted Stack**
- `VictoriaMetrics` statt Prometheus (5x weniger RAM, < 200 MB)
- Grafana mit `--cfg:server.enable_gzip=true` und minimaler Config
- Gesamtverbrauch: ~400–600 MB → knapp machbar, aber riskant auf e2-small

**Loesung C: VM-Upgrade auf e2-medium**
- 4 GB RAM statt 2 GB, Kosten: ~18 CHF/Mt statt ~10 CHF/Mt
- Voller Prometheus + Grafana Stack moeglich

**Custom Metriken fuer den Trading-Bot**:
```python
from prometheus_client import Counter, Gauge, Histogram

# Trading-Metriken
trades_total = Counter('trades_total', 'Total trades', ['coin', 'side'])
pnl_total = Gauge('pnl_total_usd', 'Total realized P&L in USD')
open_positions = Gauge('open_positions', 'Number of open positions')
model_confidence = Histogram('model_confidence', 'Prediction confidence', ['coin'])

# System-Metriken
tick_duration = Histogram('tick_duration_seconds', 'Duration of each tick')
exchange_latency = Histogram('exchange_api_latency', 'Exchange API latency')
retraining_duration = Gauge('retraining_duration_seconds', 'Last retraining duration')
```

**Integration**: Der Bot hat bereits einen HTTP-Server auf Port 8082 (API). Metriken koennen auf `/metrics` exponiert werden.

### Kosten

| Option | Monatliche Kosten |
|--------|-------------------|
| Grafana Cloud Free | 0 CHF (bis 10'000 Series) |
| Grafana Cloud Pro | ~19 USD/Mt |
| Self-Hosted (e2-small) | 0 CHF zusaetzlich, aber RAM-Risiko |
| VM-Upgrade e2-medium | +8 CHF/Mt |

### Relevanz fuer dieses Projekt
**Hoch**. Ein Bot mit echtem Geld braucht Monitoring. Aktuell ist die einzige Ueberwachung `docker logs` via SSH. Grafana Cloud Free Tier ist die beste Option: Kein zusaetzlicher RAM-Verbrauch auf der VM, professionelle Dashboards und Alerting.

### Risiken und Fallstricke
- **Metriken-Endpoint offen**: Port 8082 muss per GCP Firewall geschuetzt sein (ist es vermutlich bereits, da nur SSH-Tunnel-Zugriff). Fuer Grafana Cloud: Agent oder Remote-Write noetig.
- **Grafana Cloud Free Tier Limits**: 10'000 active Series reichen fuer dieses Projekt locker (geschaetzt: ~50–100 Series).
- **Self-Hosted auf e2-small**: OOM-Killer kann den Trading-Bot beenden wenn Prometheus/Grafana zu viel RAM brauchen.
- **Retention**: Free Tier hat nur 14 Tage Retention fuer Metriken. Fuer Langzeit-Analyse weiterhin die eigene DB nutzen.

### Geschaetzter Aufwand
**3–5 Tage**
- Tag 1: `prometheus_client` Integration, Custom Metriken definieren
- Tag 2: Metriken in Bot-Code instrumentieren (Trades, Latenz, Errors)
- Tag 3: Grafana Cloud Setup, Agent-Konfiguration oder Remote-Write
- Tag 4–5: Dashboards bauen (Bot-Health, Trading-Performance, System), Alerting-Regeln

---

## E6: Multi-Exchange — Bybit, OKX, Kraken anbinden

### Was es ist
Den Bot erweitern, um auf mehreren Boersen gleichzeitig zu handeln. Ziele: Bessere Liquiditaet, Arbitrage-Moeglichkeiten, Risikodiversifikation.

### Konkrete Implementierungsdetails

**Bestehende Architektur**:
- Das Projekt nutzt bereits `ccxt>=4.0.0` — ccxt unterstuetzt 100+ Boersen
- `BaseExchange`-Klasse in `src/crypto_bot/exchange/base_exchange.py` abstrahiert Exchange-Zugriff
- Prinzipiell ist Multi-Exchange im Design angelegt

**ccxt-Unified-API**:
```python
import ccxt.async_support as ccxt

exchanges = {
    'binance': ccxt.binance({'apiKey': '...', 'secret': '...'}),
    'bybit': ccxt.bybit({'apiKey': '...', 'secret': '...'}),
    'okx': ccxt.okx({'apiKey': '...', 'secret': '...', 'password': '...'}),
    'kraken': ccxt.kraken({'apiKey': '...', 'secret': '...'}),
}
```

**Herausforderungen pro Exchange**:

| Exchange | Besonderheiten |
|----------|---------------|
| **Bybit** | Unified Account noetig, andere Fee-Struktur, API v5 |
| **OKX** | Passphrase zusaetzlich zu API-Key/Secret, Sub-Account-System |
| **Kraken** | Andere Pair-Notation (XBT statt BTC), hoeherer API-Latenz |

**Architektur-Erweiterung**:
```
Config (pro Exchange) → ExchangeFactory → BaseExchange-Instanzen
                                              ↓
                                    ExchangeRouter (best price, oder dedicated)
                                              ↓
                                    Bot (unified Strategy)
```

**Zwei Ansaetze**:
1. **Einfach**: Jeder Exchange handelt unabhaengig dieselbe Strategie (parallel). Separates Kapital pro Exchange.
2. **Komplex**: Smart Order Routing — Preis auf allen Exchanges vergleichen, auf der guenstigsten ausfuehren.

### Kosten
- **API-Zugang**: Kostenlos bei allen genannten Exchanges
- **VM-Ressourcen**: Zusaetzlicher RAM pro Exchange-Verbindung (~50 MB), WebSocket-Connections
- **Trading-Gebuehren**: Variieren (Binance 0.1%, Bybit 0.1%, OKX 0.1%, Kraken 0.16/0.26%)
- **Kapital**: Muss auf mehrere Exchanges verteilt werden → weniger pro Exchange

### Relevanz fuer dieses Projekt
**Niedrig-Mittel**. Die Prediction-Strategie basiert auf BTC-1h-Daten und handelt 12 Coins. Die Daten kommen ohnehin von einer Quelle (ccxt/Binance). Multi-Exchange bringt erst Mehrwert bei:
- Deutlich groesserem Kapital (Liquiditaets-Limits)
- Arbitrage-Strategien (anderes Strategy-Design noetig)
- Ausfall-Absicherung (Exchange geht offline)

Fuer ein Solo-Projekt mit kleinem Kapital ist der Aufwand unverhältnismässig.

### Risiken und Fallstricke
- **API-Unterschiede trotz ccxt**: Jede Exchange hat Eigenheiten bei Order-Types, Min-Order-Sizes, Rate-Limits, Pair-Notation. ccxt abstrahiert vieles, aber nicht alles.
- **Kapitalfragmentierung**: Kapital muss auf mehrere Exchanges verteilt werden. Bei kleinem Gesamtkapital sind die Positionen pro Exchange zu klein.
- **Komplexitaet**: Jede Exchange braucht eigene API-Keys, eigenes Monitoring, eigene Fehlerbehandlung. Der Wartungsaufwand multipliziert sich.
- **Steuerliche Komplexitaet**: Trades auf mehreren Exchanges erschweren die Steuererklaerung erheblich.
- **Regulatory**: Einige Exchanges haben KYC-Anforderungen oder sind in bestimmten Laendern eingeschraenkt.

### Geschaetzter Aufwand
**7–14 Tage** (pro zusaetzliche Exchange ~3–5 Tage)
- Tag 1–3: ExchangeFactory, Config-Erweiterung, BaseExchange-Anpassungen
- Tag 4–6: Bybit-Integration (API v5, Testing)
- Tag 7–9: OKX-Integration (Passphrase, Sub-Accounts)
- Tag 10–12: Kraken-Integration (Pair-Notation, API-Eigenheiten)
- Tag 13–14: Cross-Exchange-Testing, Edge-Cases, Dashboard-Anpassung

---

## E7: Mobile Dashboard — Responsive Web-App

### Was es ist
Das bestehende NiceGUI-Dashboard so anpassen, dass es auf Smartphones und Tablets nutzbar ist. Idealerweise als Progressive Web App (PWA) installierbar.

### Konkrete Implementierungsdetails

**Bestehende Situation**:
- Dashboard nutzt NiceGUI (Quasar/Vue.js Frontend, Tailwind CSS verfuegbar)
- Dashboard laeuft lokal via SSH-Tunnel zur VM
- Zugriff nur im lokalen Netzwerk

**Ansatz 1: Responsive CSS (minimal)**
- NiceGUI basiert auf Quasar Framework, das bereits responsive Grid-Klassen hat
- Tailwind CSS Breakpoints: `sm:` (640px), `md:` (768px), `lg:` (1024px)
- Bestehende Komponenten mit responsive Klassen versehen
- Beispiel: `ui.grid(columns='1 sm:2 lg:3')` fuer responsive Spalten

**Ansatz 2: Mobile-First Redesign**
- Separate mobile Views mit vereinfachtem Layout
- Swipeable Tabs statt Side-by-Side-Charts
- Groessere Touch-Targets (min. 44px)
- Zusammenklappbare Sektionen

**Ansatz 3: PWA (Progressive Web App)**
- NiceGUI unterstuetzt `ui.run(title='...', favicon='...')` — aber kein natives PWA-Manifest
- Eigenes `manifest.json` und Service Worker moeglich via `app.mount()`
- Ermoeglicht "Add to Homescreen" auf dem Smartphone

**Erreichbarkeit-Problem**:
Das Dashboard laeuft aktuell nur lokal. Fuer mobilen Zugriff gibt es Optionen:
1. **Tailscale/WireGuard VPN**: Kostenlos, sicher, einfach. Bot-VM und Smartphone im selben Netz.
2. **Cloudflare Tunnel**: Dashboard via HTTPS erreichbar ohne Port-Oeffnung. Kostenloser Tier.
3. **Dashboard auf VM**: Dashboard auch auf der VM laufen lassen (braucht mehr RAM).

**Empfehlung**: Tailscale (kostenloses VPN, 1 Befehl auf VM + App auf Smartphone) + Responsive CSS.

### Kosten
- **Tailscale**: Kostenlos (bis 100 Geraete)
- **Cloudflare Tunnel**: Kostenlos
- **VM-Ressourcen**: Wenn Dashboard auf VM laeuft: +200–400 MB RAM (kritisch bei e2-small)

### Relevanz fuer dieses Projekt
**Mittel**. Ein mobiles Dashboard ist "nice to have", aber wenn E1 (Telegram-Notifications) implementiert ist, werden 90% der mobilen Use-Cases abgedeckt. Das volle Dashboard braucht man primaer fuer detaillierte Analyse — das passiert typischerweise am Desktop.

### Risiken und Fallstricke
- **RAM auf e2-small**: Dashboard auf der VM laufen lassen braucht zusaetzlichen RAM. NiceGUI + Plotly-Charts koennen 200–400 MB verbrauchen.
- **Sicherheit**: Dashboard oeffentlich erreichbar machen erfordert Authentifizierung (das Projekt hat bereits `auth.py`). VPN ist sicherer als Public-Exposure.
- **UX-Aufwand**: Ein wirklich gutes Mobile-UI braucht mehr als nur responsive CSS — Touch-Gesten, vereinfachte Navigation, Performance-Optimierung fuer mobile Netzwerke.
- **SSH-Tunnel-Abhaengigkeit**: Aktuell laeuft die API auf der VM. Fuer mobilen Dashboard-Zugriff muss die API ebenfalls erreichbar sein (via VPN/Tunnel).

### Geschaetzter Aufwand
**4–6 Tage**
- Tag 1: Bestandsaufnahme bestehender Komponenten, Responsive-Breakpoints definieren
- Tag 2–3: Responsive CSS fuer alle Dashboard-Views (Header, Charts, Tabellen)
- Tag 4: Tailscale/Cloudflare Tunnel Setup fuer mobilen Zugriff
- Tag 5: Mobile-spezifische UX-Verbesserungen (Touch, Navigation)
- Tag 6: Testing auf verschiedenen Geraeten, Performance-Optimierung

---

## Zusammenfassung & Priorisierungsempfehlung

| # | Erweiterung | Aufwand | Kosten/Mt | Relevanz | Empfehlung |
|---|-------------|---------|-----------|----------|------------|
| E1 | Telegram Bot | 2–3 Tage | 0 CHF | Hoch | **Sofort umsetzen** |
| E5 | Monitoring (Grafana Cloud) | 3–5 Tage | 0 CHF | Hoch | **Sofort umsetzen** |
| E3 | Shadow Mode | 5–7 Tage | 0 CHF | Hoch | Nach E1/E5 |
| E2 | Automated Reports | 3–4 Tage | 0 CHF | Mittel-Hoch | Nach E1 (teilweise redundant) |
| E4 | Auto-Scaling Capital | 3–4 Tage | 0 CHF | Mittel | Erst nach 3 Mt. Live-Profit |
| E7 | Mobile Dashboard | 4–6 Tage | 0 CHF | Mittel | Telegram deckt 90% ab |
| E6 | Multi-Exchange | 7–14 Tage | 0 CHF | Niedrig | Erst bei grossem Kapital |

**Empfohlene Reihenfolge**:
1. **E1 (Telegram)** → Sofortiger Nutzen, geringer Aufwand, Basis fuer E2
2. **E5 (Monitoring)** → Grafana Cloud Free, kein RAM-Overhead, professionelles Alerting
3. **E3 (Shadow Mode)** → Risikominimierung fuer Strategieaenderungen
4. **E2 (Reports)** → Aufbauend auf E1, visueller Mehrwert
5. **E4 (Auto-Scaling)** → Erst nach nachgewiesener Profitabilitaet
6. **E7 (Mobile)** → Nice-to-have, Telegram reicht meist
7. **E6 (Multi-Exchange)** → Erst bei Skalierungsbedarf
