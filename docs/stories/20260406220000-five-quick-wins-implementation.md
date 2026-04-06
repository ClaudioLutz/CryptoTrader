# Five Quick-Wins: Kelly, Drawdown, Optuna, Macro-Features, Telegram, Journaling

## Summary

Implementierung von 5 priorisierten Erweiterungen aus der Research-Phase:
D1+D4 (Kelly Criterion + Drawdown Protection), B8 (Optuna AutoML),
C6+C11 (Macro/Cross-Market Features), E1 (Telegram Notifications),
F2 (Prediction Journaling).

## Context / Problem

Die Research-Phase identifizierte ~40 moegliche Erweiterungen in 8 Kategorien.
Die Top Quick-Wins wurden nach Impact/Aufwand-Verhaeltnis priorisiert:
- **Risikomanagement**: Positionsgroessen waren bisher nur Confidence-basiert (willkuerlich 25-100%)
- **ML-Modell**: LightGBM-Hyperparameter waren statisch, `reg_alpha`/`reg_lambda` gar nicht optimiert
- **Features**: Nur 19 technische Features mit ~0.045 Korrelation, keine Macro/Cross-Market-Daten
- **Monitoring**: Kein Weg, Trades unterwegs zu verfolgen (nur Dashboard via SSH-Tunnel)
- **Analyse**: Keine systematische Aufzeichnung der Predictions fuer Post-hoc-Analyse

## What Changed

### D1: Kelly Criterion (position_sizer.py → prediction_strategy.py)
- `KellySizer` (existierte bereits) wird jetzt in `_calculate_position_size()` genutzt
- Quarter-Kelly (fraction=0.25) als Default — konservativ fuer 454 USDT
- Rolling-Window (letzte 50 Trades) fuer Win-Rate/Avg-Win/Avg-Loss
- Fallback auf bisherige Confidence-Skalierung bei < 20 Trades
- Kelly bestimmt **Maximum**, Confidence skaliert **innerhalb**

### D4: Drawdown Protection (prediction_strategy.py)
- Peak-Capital Tracking mit progressiver Positionsreduktion
- Ab 5% Drawdown: lineare Reduktion, bei 15% auf 25% der normalen Groesse
- `_update_drawdown()` wird in jedem Tick aufgerufen
- State wird persistiert (peak_capital, current_drawdown_pct)

### B8: Optuna AutoML (optuna_tuner.py → prediction_pipeline.py)
- Neues Modul `coin_prediction_src/src/models/optuna_tuner.py`
- TPE-Sampler, 30 Trials, 5 Min Timeout als Default
- Optimiert 9 Parameter inkl. `reg_alpha`/`reg_lambda` (bisher nicht optimiert!)
- Search Space: learning_rate [0.01-0.15], max_depth [3-8], etc.
- Integration in beide Pipeline-Pfade (1h und 1d)
- Gecachte `_best_params` fuer Journal-Logging

### C6+C11: Macro + Cross-Market Features (macro_fetcher.py → prediction_pipeline.py)
- Neues Modul `coin_prediction_src/src/ingestion/macro_fetcher.py`
- 6 Symbole via yfinance: DXY, US10Y, VIX, MSTR, GLD, SPY
- Features pro Symbol: Returns (1h/4h/24h), Rolling-Korrelation mit BTC (24h)
- Spezial-Features: VIX-Level, VIX-High-Flag, DXY-BTC-Divergenz
- Forward-Fill fuer Zeiten ausserhalb US-Handelszeiten
- Integration in `_build_1h_features()` via `build_macro_features()`

### E1: Telegram Bot (notifications/telegram.py → prediction_strategy.py)
- Neues Modul `src/crypto_bot/notifications/telegram.py`
- `TelegramNotifier` mit `send_trade()`, `send_daily_summary()`, `send_alert()`
- Nutzt direkt Telegram Bot API via aiohttp (keine extra Dependency)
- Notifications bei: Kauf, Verkauf (mit P&L), Daily Summary (18:00 UTC)
- Config via .env: `TELEGRAM__BOT_TOKEN`, `TELEGRAM__CHAT_ID`
- Lazy Init — wenn Token fehlt, wird kein Notifier erstellt

### F2: Prediction Journaling (prediction_journal.py → prediction_strategy.py)
- Neues Modul `src/crypto_bot/prediction/prediction_journal.py`
- SQLite-DB unter `logs/prediction_journal.db`
- Speichert: Timestamp, Coin, Prediction, Confidence, Features, Optuna-Params
- Outcome-Feld fuer spaetere Analyse (wird nach 72h befuellt)
- `get_accuracy_stats()` fuer Auswertung
- WAL-Mode fuer concurrent reads

### Infrastruktur
- `pyproject.toml`: Neues Extra `prediction` mit optuna, yfinance
- `Dockerfile`: Installiert jetzt `.[dashboard,prediction]`
- `scripts/start_prediction_bot.py`: Telegram + Optuna aus .env lesen

## How to Test

```bash
# 1. Imports verifizieren
python -c "from crypto_bot.prediction.prediction_strategy import PredictionStrategy; print('OK')"

# 2. Dry-Run starten (ohne Telegram)
python scripts/start_prediction_bot.py --dry-run

# 3. Telegram testen (Token und Chat-ID setzen)
export TELEGRAM__BOT_TOKEN=xxx
export TELEGRAM__CHAT_ID=yyy
python -c "
import asyncio
from crypto_bot.notifications.telegram import TelegramNotifier
n = TelegramNotifier('$TELEGRAM__BOT_TOKEN', '$TELEGRAM__CHAT_ID')
asyncio.run(n.send_alert('Test', 'CryptoTrader Test-Nachricht'))
"

# 4. Prediction Journal pruefen
python -c "
from crypto_bot.prediction.prediction_journal import PredictionJournal
j = PredictionJournal()
j.log_prediction('BTC', '1h', 'up', 0.72, 0.72)
print(j.get_recent_predictions())
"

# 5. Optuna-Tuner testen (dauert ~5 Min)
python -c "
import sys; sys.path.insert(0, 'coin_prediction_src')
from src.models.optuna_tuner import tune_and_train
import pandas as pd, numpy as np
X = pd.DataFrame(np.random.randn(500, 10))
y = pd.Series(np.random.randint(0, 2, 500))
model, params = tune_and_train(X[:400], y[:400], X[400:], y[400:], n_trials=5, timeout=30)
print(f'Best params: {params}')
"
```

## Risk / Rollback Notes

- **Kelly/Drawdown**: Falls Kelly zu aggressive Positionen vorschlaegt, `kelly_enabled=False` in Config setzen. Fallback ist die bisherige Confidence-Skalierung.
- **Optuna**: Falls Tuning zu lange dauert oder instabil ist, `optuna_enabled=False` setzen. Fallback auf DEFAULT_PARAMS.
- **Macro-Features**: Falls yfinance API-Limits erreicht oder Daten fehlen, werden die Features einfach uebersprungen (graceful degradation). Kein Impact auf bestehende Features.
- **Telegram**: Falls Token ungueltig oder Telegram down, werden Notifications still uebersprungen. Kein Impact auf Trading-Logik.
- **Journal**: Falls SQLite-Fehler, wird geloggt und uebersprungen. Kein Impact auf Trading-Logik.
- **Docker**: Image muss neu gebaut werden (neues Extra `prediction`). Rollback: `.[dashboard]` in Dockerfile.
