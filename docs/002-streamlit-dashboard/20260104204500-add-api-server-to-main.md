# Add API Server to Main Entry Point

## Summary

Integrated the HealthCheckServer into the main bot startup so the Streamlit dashboard can connect and display live trading data.

## Context / Problem

The `HealthCheckServer` existed in `utils/health.py` with all necessary API endpoints, but was not started when running the bot. The Streamlit dashboard requires these endpoints to function.

## What Changed

### Modified Files:
- `src/crypto_bot/main.py`:
  - Added import for `HealthCheckServer`
  - Added `--api-port` CLI argument (default: 8080)
  - Added `--no-api` CLI argument to disable API server
  - Updated `display_banner()` to show API URL
  - Start `HealthCheckServer` before bot strategies
  - Stop `HealthCheckServer` on shutdown

- `src/crypto_bot/__main__.py` (NEW):
  - Created to enable `python -m crypto_bot` execution

### API Endpoints Now Available:
- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe
- `GET /api/trades` - Recent trade history
- `GET /api/positions` - Open positions
- `GET /api/pnl` - P&L summary
- `GET /api/equity` - Equity curve data
- `GET /api/status` - Bot status

## How to Test

1. Start the bot with API server:
   ```bash
   python -m crypto_bot --dry-run
   ```

2. Verify API is running:
   ```bash
   curl http://localhost:8080/health
   ```

3. Check API status:
   ```bash
   curl http://localhost:8080/api/status
   ```

4. Start the dashboard:
   ```bash
   cd trading_dashboard
   streamlit run app.py
   ```

## Risk / Rollback Notes

**Risks:**
- API server binds to 0.0.0.0 (all interfaces) - may need firewall rules in production
- Port 8080 may conflict with other services

**Rollback:**
- Use `--no-api` flag to disable API server
- Revert changes to `main.py`
