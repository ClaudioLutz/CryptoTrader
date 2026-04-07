# F: Analyse & Forschung — Detailrecherche

> Zurück zur Übersicht: [erweiterungsmoeglichkeiten.md](erweiterungsmoeglichkeiten.md)

> Stand: 2026-04-06 (aktualisiert 2026-04-07)
> Kontext: CryptoTrader 3.0 — BTC-only, LightGBM 1h, 72h Zeitbarriere, ~454 USDT, GCP VM

> **Status-Update 2026-04-07:** F2 (Prediction Journaling) wurde am 2026-04-06 implementiert und deployed. SQLite-basiertes Journal unter `logs/prediction_journal.db` speichert jede Prediction mit Confidence, Features und Optuna-Params.

---

## F1: Live SHAP Dashboard — Feature-Importance in Echtzeit

### Was es ist

Ein Echtzeit-Dashboard, das bei jeder Prediction visualisiert, **warum** das Modell so entschieden hat. SHAP (SHapley Additive exPlanations) zerlegt jede Vorhersage in die Beitraege einzelner Features. Statt nur "Up mit 72% Confidence" zu sehen, zeigt das Dashboard z.B.: "RSI_14 drueckt +8%, NVT_Ratio drueckt -3%, Fear_Greed_Index drueckt +5%".

### Konkrete Implementierungsdetails

**Bereits vorhanden im Projekt:**
- `coin_prediction_src/src/evaluation/shap_analysis.py` — `compute_shap_values()` und `get_shap_importance()` existieren bereits
- `shap.TreeExplainer` ist fuer LightGBM optimiert und direkt in den C++-Code von LightGBM integriert
- Das bestehende Dashboard (Streamlit/NiceGUI) auf Port 8081

**Libraries:**
- `shap>=0.43` (bereits installiert, TreeExplainer fuer LightGBM)
- `plotly` (fuer interaktive Waterfall/Force-Plots im Dashboard)
- Optional: `explainerdashboard>=0.5` (fertige interaktive Dashboard-Komponenten)

**Architektur-Entwurf:**

```
[Bot auf GCP VM]                    [Dashboard lokal]
  Bei jeder Prediction:               Neuer Tab "SHAP Analyse":
  1. model.predict(X)                  - Waterfall Plot (aktuelle Prediction)
  2. TreeExplainer(model)              - Bar Chart (globale Importance)
  3. shap_values → JSON                - Zeitverlauf der Top-5 Features
  4. /api/shap-current endpoint        - Feature-Drift Heatmap
```

**Konkrete Schritte:**
1. Im Bot nach jedem `predict()`: SHAP-Werte berechnen (TreeExplainer ist schnell, ~50ms fuer 19 Features)
2. Neuen API-Endpoint `/api/shap-current` erstellen (analog zu `/api/prediction-history`)
3. SHAP-Werte als JSON serialisieren: `{"features": [...], "shap_values": [...], "base_value": 0.52}`
4. Im Dashboard: `shap.plots.waterfall()` als Plotly-Figure rendern
5. Historische SHAP-Werte in SQLite speichern fuer Zeitverlauf-Analyse

**Performance-Betrachtung:**
- `shap.TreeExplainer` berechnet exakte Werte (kein Sampling noetig bei einem einzelnen Sample)
- Fuer globale Importance: Die bestehende Funktion nutzt max 500 Samples
- Auf e2-small VM: ~50-100ms pro Prediction, vernachlaessigbar bei 1h-Intervall

### Relevanz fuer dieses Projekt

**Hoch.** Bei 19 Features und taeglichem Retraining ist Transparenz entscheidend:
- Erkennen ob das Modell auf sinnvolle Features reagiert (nicht auf Noise)
- Debugging bei schlechten Predictions ("Warum hat es bei 65'000 USD gekauft?")
- Validierung nach Retraining: Hat sich die Feature-Nutzung sinnvoll veraendert?
- Fruehwarnung: Wenn ein Feature plotzlich dominiert, koennte Overfitting vorliegen

**Synergien:** Baut direkt auf existierendem Code auf (`shap_analysis.py`). Ergaenzt F2 (Prediction Journaling) und F3 (Walk-Forward Monitoring).

### Geschaetzter Aufwand

**3-4 Tage**
- Tag 1: API-Endpoint `/api/shap-current` im Bot, SHAP-Berechnung nach jeder Prediction
- Tag 2: Dashboard-Tab mit Waterfall Plot (aktuelle Prediction) und Bar Chart (global)
- Tag 3: Historische SHAP-Speicherung (SQLite), Zeitverlauf-Visualisierung
- Tag 4: Testen, Edge Cases (Retraining, fehlende Daten), Feinschliff

---

## F2: Prediction Journaling — UMGESETZT 2026-04-06

### Was es ist

Ein systematisches Log jeder Prediction, das nicht nur das Ergebnis (Up/Down, Confidence) speichert, sondern auch den kompletten Feature-Vektor, SHAP-Werte und spaeter das tatsaechliche Outcome. Das ermoeglicht Post-hoc-Analyse: "Bei welchen Feature-Konstellationen ist das Modell zuverlaessig? Wo liegt es systematisch falsch?"

### Konkrete Implementierungsdetails

**Bereits vorhanden im Projekt:**
- `/api/prediction-history` Endpoint existiert bereits
- Walk-Forward-Backtesting speichert Fold-Ergebnisse
- structlog ist durchgaengig implementiert

**Datenmodell (SQLite-Tabelle `prediction_journal`):**

```sql
CREATE TABLE prediction_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO 8601
    coin TEXT NOT NULL,                -- 'BTCUSDT'
    timeframe TEXT NOT NULL,           -- '1h'
    prediction TEXT NOT NULL,          -- 'up' / 'down'
    confidence REAL NOT NULL,          -- 0.0 - 1.0
    position_size_pct REAL,           -- 25-100%
    model_version TEXT,               -- Hash des Modells
    train_window_start TEXT,          -- Beginn Trainingsfenster
    train_window_end TEXT,            -- Ende Trainingsfenster
    features_json TEXT NOT NULL,      -- Kompletter Feature-Vektor als JSON
    shap_values_json TEXT,            -- SHAP-Werte (optional, Synergie mit F1)
    actual_outcome TEXT,              -- 'up' / 'down' (72h spaeter befuellt)
    actual_return_pct REAL,           -- Tatsaechliche Rendite in %
    was_correct BOOLEAN,             -- Prediction korrekt?
    trade_executed BOOLEAN,          -- Wurde ein Trade gemacht?
    notes TEXT                        -- Manuelle Notizen
);
```

**Libraries:**
- `sqlite3` (Standardbibliothek, kein zusaetzliches Paket)
- `pandas` (fuer Analyse-Queries)
- Optional: `DuckDB` (schnellere analytische Queries bei wachsender Datenmenge)

**Konkrete Schritte:**
1. SQLite-Tabelle erstellen (in `src/crypto_bot/data/persistence.py` ergaenzen)
2. Nach jeder Prediction: Feature-Vektor + Metadata speichern
3. Cronjob/Timer: 72h nach jeder Prediction das Outcome befuellen
4. Dashboard-Tab "Journal": Tabelle mit Filtern (Datum, Confidence, Korrektheit)
5. Analyse-Views: Accuracy nach Feature-Ranges, Confusion Matrix ueber Zeit

**Analyse-Moeglichkeiten:**
- "Accuracy bei RSI > 70 vs. RSI < 30?"
- "Performt das Modell besser bei hoher oder niedriger Volatilitaet?"
- "Welche Feature-Kombination fuehrt zu False Positives?"
- "Wie veraendert sich Accuracy nach Retraining?"

### Relevanz fuer dieses Projekt

**Sehr hoch.** Dies ist die Grundlage fuer jede systematische Verbesserung:
- Aktuell fehlt ein strukturierter Rueckblick auf vergangene Predictions
- Bei ~58% Win Rate: 42% der Predictions sind falsch — warum?
- Ermoeglicht datengetriebene Entscheidungen statt Bauchgefuehl
- Grundlage fuer F3 (Walk-Forward Monitoring) und B4 (Meta-Learning)

**Besonders wertvoll** weil der Bot mit echtem Geld laeuft — jede Fehlentscheidung kostet.

### Geschaetzter Aufwand

**2-3 Tage**
- Tag 1: Datenmodell, SQLite-Integration, Logging nach jeder Prediction
- Tag 2: Outcome-Befuellung (72h-Timer), Dashboard-Tab mit Tabelle
- Tag 3: Analyse-Views (Accuracy nach Feature-Ranges, Zeitverlauf)

---

## F3: Walk-Forward Monitoring — Laufend pruefen ob Out-of-Sample Performance degradiert

### Was es ist

Ein kontinuierliches Monitoring-System, das erkennt, wenn die Live-Performance des Modells unter das erwartete Niveau faellt. Statt nur im Backtesting zu validieren, wird die Out-of-Sample-Performance laufend gemessen und bei Degradation alarmiert. Das ist besonders kritisch in Crypto, wo Regime-Wechsel (Bull/Bear/Range) haeufig vorkommen.

### Konkrete Implementierungsdetails

**Bereits vorhanden im Projekt:**
- `coin_prediction_src/src/evaluation/walk_forward.py` — Walk-Forward-Splits mit Purging und Embargo
- `coin_prediction_src/src/evaluation/metrics.py` — Metriken-Berechnung
- Circuit Breaker in `src/crypto_bot/risk/circuit_breaker.py`
- Taegliches Retraining ist aktiv

**Libraries:**
- `evidently>=0.5` — Open-Source ML-Monitoring mit 20+ Drift-Detection-Methoden (Kolmogorov-Smirnov, PSI, Jensen-Shannon Divergence)
- `scipy.stats` (fuer statistische Tests, bereits verfuegbar)
- Optional: `nannyml` (spezialisiert auf Performance-Estimation ohne Ground Truth)

**Monitoring-Metriken:**

| Metrik | Berechnung | Schwellwert | Aktion |
|--------|-----------|-------------|--------|
| Rolling Accuracy | Letzte 50 Predictions | < 52% (Zufall+2%) | Warnung |
| Rolling Sharpe | Letzte 30 Tage Returns | < 0.0 | Warnung |
| Confidence Calibration | Predicted vs. Actual Win Rate | Differenz > 10% | Alarm |
| Feature Drift (PSI) | Aktuelle vs. Trainings-Distribution | PSI > 0.2 | Alarm |
| Prediction Drift | Verteilung der Confidence-Werte | KS-Test p < 0.01 | Warnung |
| Max Drawdown | Laufende Equity-Kurve | > 10% | Trading pausieren |

**Architektur:**

```
[Bot auf GCP VM - stuendlich]
  1. Prediction + Trade
  2. Outcome nach 72h evaluieren
  3. Rolling-Metriken berechnen
  4. Drift-Detection (Evidently Report)
  5. Bei Schwellwert-Verletzung → Alert

[Dashboard - Monitoring Tab]
  - Rolling Accuracy Chart (mit Konfidenzband)
  - Feature Drift Heatmap
  - Calibration Plot
  - "Model Health" Ampel (Gruen/Gelb/Rot)
```

**Konkrete Schritte:**
1. Evidently-Integration: `DataDriftPreset` und `ClassificationPreset` konfigurieren
2. Referenz-Dataset: Feature-Verteilung zum Zeitpunkt des Trainings speichern
3. Stuendlich: Aktuelles Feature-Fenster mit Referenz vergleichen
4. Rolling-Metriken-Berechnung (benoetigt F2 Prediction Journal als Datenquelle)
5. Alert-System: Telegram/Discord Notification bei Schwellwert-Verletzung
6. Dashboard: "Model Health" Tab mit Ampel-System

**Concept Drift vs. Data Drift:**
- **Data Drift**: Feature-Verteilungen aendern sich (z.B. RSI-Werte ploetzlich alle > 70)
- **Concept Drift**: Zusammenhang zwischen Features und Outcome aendert sich (z.B. hoher RSI fuehrt ploetzlich nicht mehr zu "Up")
- Evidently erkennt beides, aber Concept Drift braucht Ground-Truth-Labels (72h Verzoegerung)

### Relevanz fuer dieses Projekt

**Sehr hoch.** Das ist das wichtigste Sicherheitsnetz fuer einen Bot mit echtem Geld:
- Der Bot tradet 24/7 — ohne Monitoring kann er tagelang verlieren bevor es auffaellt
- Crypto-Maerkte sind extrem regimeabhaengig (Bull → Bear → Range)
- Das Projekt hat bereits 64 Konfigurationen getestet, die alle schlechter waren — das zeigt wie fragil die Strategie sein kann
- Walk-Forward existiert nur im Backtesting, nicht live
- Ergaenzt den existierenden Circuit Breaker um ML-spezifische Checks

### Geschaetzter Aufwand

**4-5 Tage**
- Tag 1: Evidently-Integration, Referenz-Dataset bei jedem Retraining speichern
- Tag 2: Rolling-Metriken (Accuracy, Sharpe), Schwellwert-Logik
- Tag 3: Feature-Drift-Detection (PSI, KS-Test), Prediction-Drift
- Tag 4: Dashboard-Tab "Model Health" mit Ampel und Charts
- Tag 5: Alert-Integration (Telegram), Testen mit historischen Daten

**Voraussetzung:** F2 (Prediction Journaling) sollte zuerst implementiert werden — das Journal liefert die Daten fuer das Monitoring.

---

## F4: Benchmark Tracking — Performance vs. Buy & Hold, vs. S&P500

### Was es ist

Ein systematischer Vergleich der Bot-Performance gegen passive Benchmarks. Die zentrale Frage: "Ist der Bot besser als einfach Bitcoin halten? Oder in den S&P 500 investieren?" Ohne diesen Vergleich weiss man nicht, ob die Strategie tatsaechlich Alpha generiert oder ob man mit Buy & Hold besser dran waere.

### Konkrete Implementierungsdetails

**Benchmarks:**

| Benchmark | Datenquelle | Berechnung |
|-----------|------------|------------|
| BTC Buy & Hold | Binance API (existiert) | Startkapital × (BTC_aktuell / BTC_start) |
| S&P 500 (SPY) | `yfinance` Library | SPY Total Return im gleichen Zeitraum |
| DCA Bitcoin | Berechnet | Stuendlich gleicher Betrag kaufen |
| Risk-Free Rate | Fed Funds Rate | Annualisiert, taeglich berechnet |
| 60/40 BTC/Cash | Berechnet | 60% BTC Buy & Hold + 40% Cash |

**Libraries:**
- `yfinance>=0.2` — Kostenlose S&P 500 Daten (SPY ETF), kein API-Key noetig
- `pandas` (bereits installiert)
- `plotly` (bereits installiert, fuer Equity-Kurven-Vergleich)

**Metriken fuer den Vergleich:**

| Metrik | Beschreibung |
|--------|-------------|
| Total Return | Gesamtrendite in % |
| Annualized Return | Jahresrendite |
| Sharpe Ratio | Rendite pro Risiko (Risk-Free = Fed Funds) |
| Sortino Ratio | Nur Downside-Volatilitaet |
| Max Drawdown | Groesster Verlust vom Peak |
| Calmar Ratio | Return / Max Drawdown |
| Win Rate | Nur fuer Bot (nicht fuer Buy & Hold) |
| Alpha | Ueberrendite gegenueber Benchmark |
| Beta | Korrelation mit BTC-Markt |

**Konkrete Schritte:**
1. Bei Bot-Start: Startkapital und BTC-Preis als Basis speichern
2. Stuendlich: Benchmark-Werte aktualisieren (BTC-Preis via existierender Binance-Verbindung)
3. Taeglich: S&P 500 via `yfinance` abrufen (Marktzeiten beachten, Wochenenden)
4. Equity-Kurven: Bot vs. alle Benchmarks als ueberlagerte Plotly-Charts
5. Dashboard-Tab "Benchmarks": Tabelle mit allen Metriken + Equity-Chart

**API-Endpoint (neu):**
```
GET /api/benchmarks
Response: {
    "bot": {"total_return": 2.3, "sharpe": 1.2, "max_dd": -4.5, ...},
    "btc_hold": {"total_return": 5.1, "sharpe": 0.8, "max_dd": -12.3, ...},
    "spy": {"total_return": 3.2, "sharpe": 1.5, "max_dd": -3.1, ...},
    "dca": {"total_return": 4.8, "sharpe": 1.0, "max_dd": -8.2, ...},
    "equity_curves": {
        "timestamps": [...],
        "bot": [...],
        "btc_hold": [...],
        "spy": [...],
        "dca": [...]
    }
}
```

**Wichtige Ueberlegung — Fairness:**
- S&P 500 hat andere Handelszeiten (Mo-Fr, 9:30-16:00 ET) — Wochenenden interpolieren
- BTC Buy & Hold beruecksichtigt keine Gebuehren — Bot-Performance nach Gebuehren vergleichen
- Startpunkt des Vergleichs beeinflusst das Ergebnis stark — multiple Zeitraeume zeigen

### Relevanz fuer dieses Projekt

**Hoch.** Der ultimative Realitaetscheck:
- Bei ~454 USDT Kapital und ~58% Win Rate: Schlaegt der Bot Buy & Hold?
- Wenn nicht: Warum den Bot laufen lassen (Strom, VM-Kosten, Risiko)?
- Hilft bei der Entscheidung ob Kapital erhoehen (wenn Alpha vorhanden) oder nicht
- S&P 500 als "Opportunitaetskosten" — was haette man sonst verdient?

**Psychologischer Nutzen:** Objektiviert die Performance-Bewertung. "+2% im Monat" klingt gut, aber wenn BTC +15% gemacht hat, ist es schlecht.

### Geschaetzter Aufwand

**2 Tage**
- Tag 1: Benchmark-Berechnung (BTC Hold, DCA, S&P via yfinance), API-Endpoint
- Tag 2: Dashboard-Tab mit Equity-Kurven-Overlay und Metriken-Tabelle

---

## Empfohlene Reihenfolge

1. **F2 Prediction Journaling** (2-3 Tage) — Grundlage fuer alles andere
2. **F4 Benchmark Tracking** (2 Tage) — Schneller Reality-Check
3. **F1 SHAP Dashboard** (3-4 Tage) — Transparenz und Debugging
4. **F3 Walk-Forward Monitoring** (4-5 Tage) — Kritisch, aber braucht F2 als Basis

**Gesamtaufwand: 11-14 Tage**

---

## Quellen

- [SHAP Documentation](https://shap.readthedocs.io/)
- [SHAP TreeExplainer API](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html)
- [Explainerdashboard](https://explainerdashboard.readthedocs.io/)
- [Evidently AI — Data Drift Detection](https://www.evidentlyai.com/ml-in-production/data-drift)
- [Evidently AI — Concept Drift](https://www.evidentlyai.com/ml-in-production/concept-drift)
- [Evidently AI GitHub](https://github.com/evidentlyai/evidently)
- [Walk-Forward Analysis Guide](https://medium.com/funny-ai-quant/ai-algorithmic-trading-walk-forward-analysis-a-comprehensive-guide-to-advanced-backtesting-f3f8b790554a)
- [Walk-Forward vs. Backtesting](https://surmount.ai/blogs/walk-forward-analysis-vs-backtesting-pros-cons-best-practices)
- [Freqtrade — Open Source Crypto Trading Bot](https://github.com/freqtrade/freqtrade)
- [Jesse Trading Framework](https://jesse.trade/)
