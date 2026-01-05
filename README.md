# CryptoTrader

A modular, production-grade cryptocurrency trading bot with grid strategy support and a real-time Streamlit dashboard.

## Features

- **Grid Trading Strategy**: Automated buy/sell at predefined price levels with arithmetic or geometric spacing
- **Multiple Exchange Support**: Built on CCXT for exchange abstraction (Binance, testnet support)
- **Dry-Run Mode**: Test strategies without risking real capital
- **Real-Time Dashboard**: Streamlit-based UI for monitoring, analysis, and configuration
- **Risk Management**: Circuit breakers, position sizing, stop-loss, and drawdown protection
- **State Persistence**: SQLite/PostgreSQL-backed state for crash recovery
- **Async Architecture**: High-performance async/await design with rate limiting
- **Structured Logging**: JSON logging with structlog for production monitoring
- **Alerting**: Telegram and Discord notification support

## Architecture

```
src/crypto_bot/
├── main.py              # CLI entry point
├── bot.py               # Main orchestrator
├── config/              # Pydantic settings & logging
├── exchange/            # CCXT wrapper & Binance adapter
├── strategies/          # Grid trading & strategy framework
├── risk/                # Position sizing & circuit breaker
├── data/                # SQLAlchemy models & persistence
├── backtest/            # Backtesting framework
└── utils/               # Retry, alerting, health checks

trading_dashboard/       # Streamlit dashboard
├── app.py               # Dashboard entry point
├── components/          # Auth, API client, state
└── pages/               # Dashboard, positions, history, risk, grid, config
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/crypto-trading-bot.git
cd crypto-trading-bot

# Create virtual environment and install
uv venv
uv pip install -e .

# With development dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings:
   ```ini
   # Exchange (use testnet first!)
   EXCHANGE__NAME=binance
   EXCHANGE__API_KEY=your_api_key
   EXCHANGE__API_SECRET=your_api_secret
   EXCHANGE__TESTNET=true

   # Trading
   TRADING__SYMBOL=BTC/USDT
   TRADING__DRY_RUN=true

   # Risk Management
   RISK__MAX_DAILY_LOSS_PCT=0.05
   RISK__MAX_DRAWDOWN_PCT=0.15
   ```

> **Security Notes:**
> - Never enable withdrawal permission on API keys
> - Enable IP whitelisting in exchange settings
> - Start with `TESTNET=true` and `DRY_RUN=true`

## Quick Start

```bash
# Start in dry-run mode (no real trades)
crypto-bot --dry-run

# With a custom symbol
crypto-bot --symbol ETH/USDT --dry-run

# Enable verbose logging
crypto-bot --dry-run --log-level DEBUG

# With custom config file
crypto-bot -c config/config.yaml
```

## Live Trading

To run with real trades, omit the `--dry-run` flag and set `TRADING__DRY_RUN=false` in your `.env`:

```bash
# Live trading on testnet (recommended first step)
crypto-bot --symbol BTC/USDT

# Live trading on mainnet (real money!)
# Ensure EXCHANGE__TESTNET=false in .env
crypto-bot --symbol BTC/USDT
```

### Pre-Flight Checklist

Before running live, verify:

- [ ] Tested extensively in dry-run mode
- [ ] Tested on testnet with test funds
- [ ] API key has **NO withdrawal permissions**
- [ ] IP whitelist configured on exchange
- [ ] Risk parameters set appropriately:
  - `RISK__MAX_DAILY_LOSS_PCT` (default: 5%)
  - `RISK__MAX_DRAWDOWN_PCT` (default: 15%)
  - `RISK__MAX_CONSECUTIVE_LOSSES` (default: 5)
- [ ] Alerting configured (Telegram/Discord) for trade notifications
- [ ] Stop-loss and circuit breaker tested
- [ ] Sufficient balance for grid strategy + reserves
- [ ] Monitoring dashboard accessible

### Safety Features

The bot includes multiple safety layers:
- **Circuit Breaker**: Automatically pauses trading on daily loss limit or consecutive losses
- **Drawdown Protection**: Stops trading if portfolio drops beyond threshold
- **State Persistence**: Recovers open orders and positions after restart
- **Dry-Run Override**: CLI `--dry-run` flag overrides config for safety

## CLI Options

```
usage: crypto-bot [-h] [--config CONFIG] [--dry-run] [--log-level {DEBUG,INFO,WARNING,ERROR}]
                  [--symbol SYMBOL] [--api-port PORT] [--no-api] [--version]

Options:
  --config, -c     Path to configuration file (YAML)
  --dry-run        Run in simulation mode without real trades
  --log-level      Logging verbosity (DEBUG, INFO, WARNING, ERROR)
  --symbol         Trading pair symbol (e.g., BTC/USDT)
  --api-port       Port for the dashboard API server (default: 8080)
  --no-api         Disable the dashboard API server
  --version        Show version and exit
```

## Dashboard

The trading dashboard provides real-time monitoring and analysis.

### Setup

```bash
cd trading_dashboard
pip install -r requirements.txt

# Create auth config
cp config.yaml.example config.yaml
# Edit config.yaml with your credentials
```

### Run Dashboard

```bash
# Make sure the bot is running first (provides the API)
crypto-bot --dry-run

# In another terminal, start the dashboard
cd trading_dashboard
streamlit run app.py
```

### Dashboard Features

- **Live Metrics**: Real-time P&L, equity curve, balance
- **Positions & Orders**: Open positions and pending order management
- **Trade History**: Historical trades with filtering and export
- **Risk Management**: Circuit breaker status, risk metrics
- **Grid Visualization**: Interactive grid level charts
- **Configuration**: Bot settings (read-only by default for safety)

## Development

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# With coverage
pytest --cov=src/crypto_bot

# Skip slow/integration tests
pytest -m "not slow and not integration"
```

### Code Quality

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type checking
mypy src

# Security scan
bandit -r src
```

### Integration Testing

Binance testnet is available for integration tests:
```bash
# Set testnet credentials in .env
EXCHANGE__TESTNET=true

# Run integration tests
pytest tests/integration -m integration
```

## Additional CLI Tools

```bash
# Manage API secrets securely
crypto-bot-secrets

# Security configuration check
crypto-bot-security

# Audit verification
crypto-bot-audit
```

## Project Documentation

Detailed documentation is available in the `docs/` folder:
- `docs/001-initial-setup-plan/` - Architecture and implementation plan
- `docs/002-streamlit-dashboard/` - Dashboard design and epics
- `docs/stories/` - Change documentation

## License

MIT
