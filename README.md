# CryptoTrader

A modular, production-grade cryptocurrency trading bot with grid strategy support and a real-time NiceGUI dashboard.

## Features

- **Grid Trading Strategy**: Automated buy/sell at predefined price levels with arithmetic or geometric spacing
- **Multiple Exchange Support**: Built on CCXT for exchange abstraction (Binance mainnet and testnet)
- **Dry-Run Mode**: Test strategies without risking real capital
- **Real-Time Dashboard**: NiceGUI-based web UI for monitoring, P&L tracking, and configuration
- **WebSocket Integration**: Real-time price updates and order notifications
- **Risk Management**: Circuit breakers, position sizing, stop-loss, and drawdown protection
- **State Persistence**: SQLite-backed state with automatic reconciliation for crash recovery
- **Async Architecture**: High-performance async/await design with rate limiting
- **Structured Logging**: JSON logging with structlog for production monitoring
- **Clock Skew Handling**: Automatic time synchronization with exchange servers
- **Alerting**: Telegram and Discord notification support (optional)

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

dashboard/               # NiceGUI dashboard
├── main.py              # Dashboard entry point
├── components/          # UI components (header, charts, tables)
├── services/            # API client, WebSocket service, P&L calculator
├── auth.py              # Optional password authentication
└── config.py            # Dashboard configuration
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

### Option 1: Using Startup Scripts (Recommended)

**Windows:**
```cmd
# Start the bot (with API on port 8080)
start_bot.bat

# In another terminal, start the dashboard
start_dashboard.bat

# To stop the bot
stop_bot.bat
```

**Linux/Mac:**
```bash
# Start the bot (with API on port 8080)
./start_bot.sh

# In another terminal, start the dashboard
./start_dashboard.sh

# To stop the bot
./stop_bot.sh
```

### Option 2: Manual Start

```bash
# Start bot in dry-run mode (no real trades)
python -m crypto_bot.main --dry-run --api-port 8080

# With a custom symbol
python -m crypto_bot.main --symbol ETH/USDT --dry-run --api-port 8080

# Enable verbose logging
python -m crypto_bot.main --dry-run --log-level DEBUG --api-port 8080

# Without API server (headless)
python -m crypto_bot.main --no-api
```

### Accessing the Dashboard

Once both bot and dashboard are running, open your browser to:
```
http://localhost:8081
```

The dashboard provides:
- Real-time balance and P&L tracking
- Live price charts with grid visualization
- Active orders and trade history
- Configuration management

## Docker Deployment

Run CryptoTrader in Docker for isolated, reproducible deployments.

### Quick Start with Docker

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Run bot + dashboard (combined)
docker compose --profile combined up -d cryptotrader

# Or run as separate services
docker compose up -d bot dashboard

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `bot` | 8080 | Trading bot with health API |
| `dashboard` | 8081 | NiceGUI web dashboard |
| `cryptotrader` | 8080, 8081 | Combined (both services) |

### Build Locally

```bash
docker build -t cryptotrader:latest .
docker run -d --env-file .env -p 8080:8080 -p 8081:8081 cryptotrader:latest
```

## Cloud Deployment (GCP)

Deploy CryptoTrader to Google Cloud Platform for 24/7 operation.

### Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- Binance API credentials

### Quick Deploy

```bash
# Set your project ID
export GCP_PROJECT_ID="your-project-id"

# Run full setup
./deploy/gcp/deploy.sh setup    # Enable APIs
./deploy/gcp/deploy.sh secrets  # Add API keys to Secret Manager
./deploy/gcp/deploy.sh build    # Build Docker image
./deploy/gcp/deploy.sh deploy-vm # Deploy to Compute Engine
```

### Deployment Options

| Option | Best For | Cost |
|--------|----------|------|
| **Compute Engine** | 24/7 trading (recommended) | ~$13-15/month |
| **Cloud Run** | Event-driven, sporadic use | Pay-per-request |

### Region Selection

> **Important:** Binance blocks US-based IP addresses. Deploy in EU or Asia regions:
> - `europe-west4` (Netherlands) - Recommended
> - `europe-west6` (Switzerland)
> - `asia-east1` (Taiwan)

### Useful Commands

```bash
# Check VM status
gcloud compute instances list

# SSH into VM
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a

# View container logs
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a \
  --command="docker logs \$(docker ps -q) --tail 100"

# Stop/Start VM
gcloud compute instances stop cryptotrader-vm --zone=europe-west4-a
gcloud compute instances start cryptotrader-vm --zone=europe-west4-a
```

For detailed instructions, see [deploy/gcp/README.md](deploy/gcp/README.md).

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

The NiceGUI dashboard provides real-time monitoring, analysis, and configuration.

### Dashboard Requirements

Install the dashboard dependencies:
```bash
pip install -r dashboard/requirements.txt
```

### Running the Dashboard

**Option 1: Using startup script (recommended)**
```bash
# Windows
start_dashboard.bat

# Linux/Mac
./start_dashboard.sh
```

**Option 2: Manual start**
```bash
python -m dashboard.main
```

The dashboard will start on **port 8081** and requires the bot API to be running on **port 8080**.

### Port Configuration

- **Bot API:** Port 8080 (configurable with `--api-port`)
- **Bot Health Server:** Port 8081 (set in `.env` as `HEALTH__PORT`)
- **Dashboard:** Port 8081 (set via `DASHBOARD_PORT` environment variable)

Note: The bot can run with `--no-api` flag for headless operation (dashboard won't work in this mode).

### Dashboard Features

- **Live Metrics**: Real-time P&L, balance, unrealized gains
- **Price Charts**: Multi-timeframe charts (1H, 4H, 1D, 1W) with grid level visualization
- **Order Management**: View active buy/sell orders with current prices
- **Trade History**: Complete trade history with fills and execution details
- **WebSocket Updates**: Real-time order updates and balance changes via Binance WebSocket
- **Configuration**: Manage bot settings, API keys, and risk parameters
- **Optional Authentication**: Password-protect dashboard access (configurable)

### Dashboard Configuration

Create or edit `.env` to configure dashboard settings:

```ini
# Dashboard Settings
DASHBOARD_PORT=8081
DASHBOARD_API_BASE_URL=http://localhost:8080
DASHBOARD_POLL_INTERVAL_TIER1=2.0    # Health, P&L refresh rate (seconds)
DASHBOARD_POLL_INTERVAL_TIER2=5.0    # Chart, table refresh rate (seconds)

# Optional Authentication
DASHBOARD_AUTH_ENABLED=false
DASHBOARD_AUTH_PASSWORD=your_secure_password
DASHBOARD_AUTH_SESSION_HOURS=24
```

## Troubleshooting

### Clock Skew / Timestamp Errors

If you see errors like:
```
InvalidNonce: binance {"code":-1021,"msg":"Timestamp for this request was 1000ms ahead of the server's time."}
```

**Solution:** The bot automatically syncs with Binance server time using CCXT's `load_time_difference()`. This handles system clock differences up to several minutes. No manual intervention needed - the fix is built-in.

**Technical Details:** See [docs/stories/20260107131500-fix-binance-timestamp-sync-for-clock-skew.md](docs/stories/20260107131500-fix-binance-timestamp-sync-for-clock-skew.md)

### Port Already in Use

If you see:
```
OSError: [WinError 10048] Only one usage of each socket address is normally permitted
```

**Solutions:**
1. Stop existing bot processes: Run `stop_bot.bat` (Windows) or `./stop_bot.sh` (Linux/Mac)
2. Check what's using the port:
   ```bash
   # Windows
   netstat -ano | findstr :8080

   # Linux/Mac
   lsof -i :8080
   ```
3. Kill the process using the port:
   ```bash
   # Windows
   taskkill /PID <pid> /F

   # Linux/Mac
   kill <pid>
   ```

### Log File Locked Error

If `start_bot.bat` fails with "The process cannot access the file because it is being used by another process":

**Solutions:**
1. Close the log file if open in VS Code or another editor
2. Stop all Python processes: `stop_bot.bat` or manually via Task Manager
3. Rename or delete the locked log file:
   ```bash
   # Windows
   ren logs\bot_output.log logs\bot_output_old.log

   # Linux/Mac
   mv logs/bot_output.log logs/bot_output_old.log
   ```

### Bot Not Trading

If the bot is running but not placing trades:

1. **Check strategy state in database**
   - Strategy may be in `stopped: true` state from previous stop-loss trigger
   - Reset in database or delete `trading.db` to start fresh (loses history)

2. **Check balance**
   - Verify sufficient USDT balance for grid orders
   - Grid requires capital for multiple buy orders

3. **Check current price**
   - Price must be within grid range to place orders
   - If price is outside grid bounds, adjust configuration

4. **Check logs**
   ```bash
   tail -f logs/bot_output.log
   ```
   Look for:
   - `grid_order_placed` - orders being created
   - `order_placement_failed` - errors placing orders
   - `circuit_breaker_tripped` - risk limits triggered

### Dashboard Shows No Data

If dashboard loads but shows no metrics:

1. **Verify bot API is running**
   ```bash
   curl http://localhost:8080/health
   ```
   Should return: `{"status": "healthy", ...}`

2. **Check bot was started with API enabled**
   - Use `start_bot.bat` or `python -m crypto_bot.main --api-port 8080`
   - **Don't use** `--no-api` flag when running with dashboard

3. **Verify dashboard is configured correctly**
   - Check `.env`: `DASHBOARD_API_BASE_URL=http://localhost:8080`
   - Dashboard should show "HEALTHY" indicator when connected

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

## Startup Scripts

The repository includes convenience scripts for starting and stopping the bot:

### Windows (`.bat` files)
- **`start_bot.bat`** - Start bot with API on port 8080
- **`start_dashboard.bat`** - Start dashboard on port 8081
- **`stop_bot.bat`** - Cleanly stop all bot processes

### Linux/Mac (`.sh` files)
- **`start_bot.sh`** - Start bot with API on port 8080
- **`start_dashboard.sh`** - Start dashboard on port 8081
- **`stop_bot.sh`** - Cleanly stop all bot processes

All scripts:
- Check for existing processes before starting
- Create logs directory if missing
- Archive large log files automatically
- Append to logs (don't overwrite on restart)
- Handle port conflicts gracefully

## Project Documentation

Detailed documentation is available in the `docs/` folder:
- `docs/001-initial-setup-plan/` - Architecture and implementation plan
- `docs/002-streamlit-dashboard/` - Dashboard design and epics (historical - now using NiceGUI)
- `docs/stories/` - Change documentation and story files

### Recent Stories
- `20260107131500-fix-binance-timestamp-sync-for-clock-skew.md` - Clock skew handling
- Additional stories document all major changes and fixes

## License

MIT
