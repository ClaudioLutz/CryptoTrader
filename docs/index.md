# CryptoTrader Project Documentation

> **Auto-generated**: 2026-01-05 | **Scan Level**: Exhaustive | **Parts**: 2

## Project Overview

**CryptoTrader** is a modular cryptocurrency trading platform consisting of two integrated parts:

| Part | Name | Type | Description |
|------|------|------|-------------|
| **crypto-bot** | Crypto Trading Bot | Backend | Async Python bot with grid trading strategy, risk management, and exchange integration |
| **trading-dashboard** | Trading Dashboard | Web | Streamlit-based multi-page dashboard for monitoring and control |

---

## Quick Start

```bash
# Install the trading bot
pip install -e .

# Configure exchange credentials
cp .env.example .env
# Edit .env with your Binance API keys

# Run the bot
python -m crypto_bot run --symbol BTC/USDT --dry-run

# Run the dashboard (separate terminal)
cd trading_dashboard
pip install -r requirements.txt
streamlit run app.py
```

---

## Architecture Overview

```
                                CryptoTrader System
    +-----------------------------------------------------------------+
    |                                                                 |
    |  +---------------------+       REST API       +---------------+ |
    |  |  trading-dashboard  |<----:8080---------->|   crypto-bot  | |
    |  |    (Streamlit)      |     /api/*          |   (aiohttp)   | |
    |  +---------------------+                     +-------+-------+ |
    |                                                      |         |
    |                                                      v         |
    |                                        +--------------------+  |
    |                                        |    Binance API     |  |
    |                                        |   (ccxt wrapper)   |  |
    |                                        +--------------------+  |
    |                                                                |
    |  +-----------------------------------------------------------+ |
    |  |                     SQLite (trading.db)                   | |
    |  |  trades | orders | strategy_states | balance_snapshots    | |
    |  +-----------------------------------------------------------+ |
    |                                                                 |
    +-----------------------------------------------------------------+
```

---

## Part 1: crypto-bot (Backend)

### Entry Points

| Entry Point | Purpose |
|-------------|---------|
| `python -m crypto_bot run` | Start live trading bot |
| `python -m crypto_bot backtest` | Run backtesting simulation |
| `python -m crypto_bot validate` | Validate API credentials |

### Module Structure

```
src/crypto_bot/
+-- __init__.py
+-- __main__.py           # CLI entry point
+-- main.py               # CLI commands (run, backtest, validate)
+-- bot.py                # TradingBot orchestrator + BotBuilder
|
+-- config/
|   +-- settings.py       # Pydantic Settings (BotSettings, ExchangeSettings, etc.)
|   +-- logging_config.py # structlog JSON configuration
|
+-- exchange/
|   +-- base_exchange.py  # BaseExchange protocol + domain types
|   +-- ccxt_wrapper.py   # CCXTExchange implementation
|   +-- binance_adapter.py # Binance-specific filter handling
|   +-- websocket_handler.py # WebSocket price feeds
|
+-- strategies/
|   +-- base_strategy.py  # Strategy Protocol + StrategyFactory
|   +-- strategy_state.py # Persistent strategy state
|   +-- grid_trading.py   # GridTradingStrategy implementation
|
+-- risk/
|   +-- risk_manager.py   # Central risk orchestrator
|   +-- position_sizer.py # Fixed fractional position sizing
|   +-- stop_loss.py      # Stop-loss handlers (fixed, trailing)
|   +-- circuit_breaker.py # Trading halt on limits breach
|   +-- drawdown.py       # Drawdown tracking
|
+-- data/
|   +-- models.py         # SQLAlchemy 2.0 ORM models
|   +-- persistence.py    # Repository pattern + Unit of Work
|   +-- ohlcv_cache.py    # OHLCV candlestick cache
|
+-- backtest/
|   +-- engine.py         # BacktestEngine orchestrator
|   +-- backtest_context.py # Simulated execution context
|   +-- simulation.py     # Order simulation + fee modeling
|   +-- metrics.py        # Performance metrics calculation
|   +-- optimization.py   # Parameter optimization
|
+-- utils/
    +-- health.py         # aiohttp health check server
    +-- alerting.py       # Telegram/Discord notifications
    +-- retry.py          # Exponential backoff decorator
    +-- validators.py     # Input validation helpers
    +-- secrets.py        # Secrets management
    +-- audit.py          # Audit logging
    +-- security_check.py # Security validation
    +-- api_validator.py  # API key validation
```

### Core Classes

#### TradingBot (`bot.py`)
The main orchestrator class that coordinates all components.

```python
# Construction via Builder pattern
bot = await (
    BotBuilder()
    .with_settings(settings)
    .with_exchange(BinanceAdapter(exchange_settings))
    .with_strategy(GridTradingStrategy(grid_config))
    .with_risk_manager(risk_manager)
    .with_persistence(persistence)
    .build()
)

# Running the bot
await bot.run()
```

**Key Methods:**
- `run()` - Main trading loop
- `stop()` - Graceful shutdown
- `get_status()` - Current bot status
- `_trading_loop()` - Core tick processing

#### GridTradingStrategy (`strategies/grid_trading.py`)
Implements grid trading with arithmetic or geometric spacing.

**Configuration:**
```python
GridConfig(
    symbol="BTC/USDT",
    lower_price=Decimal("90000"),
    upper_price=Decimal("110000"),
    num_grids=20,
    total_investment=Decimal("10000"),
    spacing_type="arithmetic",  # or "geometric"
)
```

**Key Methods:**
- `initialize(context)` - Set up grid levels and initial orders
- `on_tick(ticker)` - Handle price updates
- `on_order_filled(order)` - Replace filled orders
- `get_state()` / `from_state()` - Persistence

#### RiskManager (`risk/risk_manager.py`)
Central coordinator for all risk controls.

**Components:**
- `FixedFractionalSizer` - Position sizing (default 2% risk per trade)
- `CircuitBreaker` - Trading halt on daily loss, consecutive losses, or drawdown
- `DrawdownTracker` - Peak equity and drawdown monitoring
- `StopLossHandler` - Per-position stop-loss management

**Key Methods:**
- `validate_trade()` - Pre-trade validation
- `record_trade_result()` - Post-trade recording
- `check_stop_losses()` - Batch stop-loss checking

### Data Models (`data/models.py`)

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Trade` | Trade records | id, order_id, symbol, side, amount, price, cost, fee, timestamp |
| `Order` | Exchange orders | id, symbol, side, type, status, price, amount, filled |
| `StrategyState` | Strategy persistence | strategy_name, symbol, state_data (JSON), updated_at |
| `BalanceSnapshot` | Equity tracking | timestamp, currency, free, used, total |
| `OHLCVCache` | Candlestick cache | symbol, timeframe, timestamp, open, high, low, close, volume |
| `AlertLog` | Notification history | timestamp, severity, channel, message, delivered |

### Configuration (`config/settings.py`)

**Environment Variables:**
```bash
# Exchange
EXCHANGE_NAME=binance
EXCHANGE_API_KEY=your_api_key
EXCHANGE_API_SECRET=your_api_secret
EXCHANGE_TESTNET=true

# Trading
TRADING_SYMBOL=BTC/USDT
TRADING_DRY_RUN=true

# Risk
RISK_PCT_PER_TRADE=0.02
MAX_DRAWDOWN_PCT=0.15
MAX_DAILY_LOSS_PCT=0.05

# Alerting
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DISCORD_WEBHOOK_URL=...

# Database
DATABASE_URL=sqlite+aiosqlite:///trading.db
```

### API Endpoints (`utils/health.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/status` | GET | Bot status, grid config, risk metrics |
| `/api/trades` | GET | Recent trades |
| `/api/positions` | GET | Open positions |
| `/api/orders` | GET | Pending orders |
| `/api/strategies` | GET | Active strategies |
| `/api/equity` | GET | Equity curve data |
| `/api/ohlcv` | GET | Candlestick data |
| `/api/pnl` | GET | P&L calculations |
| `/api/orders/cancel` | POST | Cancel order |
| `/api/orders/cancel-all` | POST | Cancel all orders |
| `/api/risk/reset-circuit-breaker` | POST | Reset circuit breaker |
| `/api/risk/emergency-stop` | POST | Emergency stop |

---

## Part 2: trading-dashboard (Web)

### Module Structure

```
trading_dashboard/
+-- app.py                 # Streamlit entry point, navigation
+-- config.yaml            # Authentication config
+-- requirements.txt
|
+-- components/
|   +-- api_client.py      # httpx REST client with caching
|   +-- auth.py            # streamlit-authenticator integration
|   +-- state.py           # Session state management
|
+-- pages/
    +-- dashboard.py       # Main overview, P&L metrics, equity curve
    +-- positions_orders.py # Open positions, pending orders
    +-- trade_history.py   # Historical trades with filtering
    +-- risk_management.py # Risk metrics, circuit breaker controls
    +-- grid_strategy.py   # Grid visualization
    +-- configuration.py   # Bot settings (read-only)
```

### Pages

| Page | Features |
|------|----------|
| **Dashboard** | Portfolio P&L, equity curve, candlestick chart with orders, strategy performance |
| **Positions & Orders** | Open positions table (AgGrid), pending orders, cancel actions |
| **Trade History** | Filterable trade list, CSV export, P&L statistics |
| **Risk Management** | System status, drawdown/loss metrics, circuit breaker controls, emergency stop |
| **Grid Strategy** | Grid level visualization, parameters, statistics |
| **Configuration** | Bot settings display (read-only mode) |

### API Client (`components/api_client.py`)

```python
# Cached API calls with TTL
@st.cache_data(ttl=5)
def fetch_trades():
    return get_http_client().get("/api/trades").json()

# Available functions:
fetch_status()      # ttl=3s
fetch_trades()      # ttl=5s
fetch_positions()   # ttl=3s
fetch_orders()      # ttl=3s
fetch_strategies()  # ttl=10s
fetch_equity()      # ttl=30s
fetch_ohlcv()       # ttl=60s
fetch_health()      # ttl=2s
```

### State Management (`components/state.py`)

```python
@dataclass
class DashboardState:
    config: dict[str, Any]
    read_only_mode: bool = True
    last_refresh: str | None = None
    selected_symbol: str = "BTC/USDT"

# Usage
state = get_state()
state.selected_symbol = "ETH/USDT"
```

### Authentication (`components/auth.py`)

Uses `streamlit-authenticator` with YAML config:

```yaml
# config.yaml
credentials:
  usernames:
    admin:
      email: admin@example.com
      name: Admin
      password: $2b$12$...  # bcrypt hash

cookie:
  name: crypto_trader_cookie
  key: your-secret-key
  expiry_days: 30
```

---

## Key Design Patterns

| Pattern | Usage |
|---------|-------|
| **Builder** | `BotBuilder` for constructing `TradingBot` |
| **Strategy** | `BaseStrategy` protocol with `GridTradingStrategy` implementation |
| **Repository** | `TradeRepository`, `OrderRepository` for data access |
| **Unit of Work** | `UnitOfWork` for transactional consistency |
| **Factory** | `StrategyFactory` for config-driven strategy creation |
| **Protocol** | Type-safe interfaces (`BaseExchange`, `Strategy`, `ExecutionContext`) |
| **Decorator** | `@retry_with_backoff` for resilient API calls |

---

## Technology Stack

### Backend (crypto-bot)

| Category | Technology | Version |
|----------|------------|---------|
| Language | Python | 3.11+ |
| Async | asyncio | stdlib |
| Config | Pydantic | 2.0+ |
| ORM | SQLAlchemy | 2.0+ |
| Exchange | ccxt | 4.0+ |
| HTTP | aiohttp | 3.9+ |
| Logging | structlog | 24.0+ |
| Testing | pytest | latest |

### Frontend (trading-dashboard)

| Category | Technology | Version |
|----------|------------|---------|
| Framework | Streamlit | 1.37+ |
| HTTP | httpx | 0.27+ |
| Charts | Plotly | 5.24+ |
| Tables | streamlit-aggrid | 0.3.4+ |
| Auth | streamlit-authenticator | 0.3.2+ |
| Data | pandas | 2.0+ |

---

## Development Guidelines

### Code Style
- Use `ruff` for linting and formatting
- Use `mypy` for type checking
- Use `black` for code formatting
- All functions must have docstrings
- Use type hints everywhere

### Testing
```bash
# Run all tests
pytest

# With coverage
pytest --cov=crypto_bot

# Specific test file
pytest tests/test_grid_trading.py -v
```

### Security
- Never commit `.env` files
- Use `SecretStr` for sensitive values
- API keys validated on startup
- Rate limiting on all exchange calls
- Bandit security scanning in CI

### Logging
All components use structured logging:
```python
logger = structlog.get_logger()
logger.info("order_created", symbol="BTC/USDT", side="buy", amount="0.1")
```

---

## File Index

| Path | Description |
|------|-------------|
| `src/crypto_bot/main.py` | CLI entry point |
| `src/crypto_bot/bot.py` | TradingBot + BotBuilder |
| `src/crypto_bot/config/settings.py` | All Pydantic settings |
| `src/crypto_bot/exchange/base_exchange.py` | Exchange protocol + types |
| `src/crypto_bot/exchange/binance_adapter.py` | Binance implementation |
| `src/crypto_bot/strategies/grid_trading.py` | Grid strategy |
| `src/crypto_bot/risk/risk_manager.py` | Risk orchestrator |
| `src/crypto_bot/data/models.py` | SQLAlchemy models |
| `src/crypto_bot/data/persistence.py` | Repositories + UoW |
| `src/crypto_bot/utils/health.py` | Health server + API |
| `trading_dashboard/app.py` | Dashboard entry |
| `trading_dashboard/components/api_client.py` | API client |
| `trading_dashboard/pages/dashboard.py` | Main dashboard |

---

## Related Documentation

- [Implementation Plan](001-initial-setup-plan/Modular-Python-Crypto-Trading-Bot-Complete-Implementation-Plan.md)
- [Dashboard Plan](002-streamlit-dashboard/streamlit-dashboard-initial-implementation.plan.md)
- [Change Log](stories/) - All change documentation
