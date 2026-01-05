# Fix Dashboard API - Trade History, P&L, and Price Chart with Orders

## Summary

Enhanced the dashboard API to fetch trade history from Binance exchange, calculate P&L from actual trades, and display a candlestick price chart with order markers and grid levels.

## Context / Problem

The dashboard had several issues:
1. Trade history was empty because `fetch_my_trades()` was not implemented
2. Risk Management page showed red indicators for all status fields (ws_connected, trading_enabled, etc.)
3. Grid Strategy page showed "No grid configuration found" because status endpoint didn't include grid data
4. Import error in ccxt_wrapper.py: `timezone` was not imported but used in code

## What Changed

### src/crypto_bot/exchange/base_exchange.py:
- Added `Trade` dataclass for representing trade data from exchange
- Added abstract `fetch_my_trades()` method to `BaseExchange` class

### src/crypto_bot/exchange/ccxt_wrapper.py:
- Implemented `fetch_my_trades()` to fetch trades from Binance
- Fixed import: changed `timezone.utc` to `UTC` (matches the import statement)

### src/crypto_bot/utils/health.py:
- **`_trades_handler`**: Updated to fetch trades from Binance exchange via `fetch_my_trades()`
- **`_ohlcv_handler`**: New endpoint to fetch OHLCV candlestick data from exchange
- **`_status_handler`**: Added comprehensive status fields:
  - Risk Management: `ws_connected`, `trading_enabled`, `db_connected`, `circuit_breaker_active`, `current_drawdown`, `max_drawdown_limit`, `daily_loss`, `daily_loss_limit`, `consecutive_losses`, `max_consecutive_losses`, `peak_equity`, `circuit_breaker_events`
  - Grid Strategy: `grid_config` (symbol, lower_price, upper_price, num_grids, grid_step, total_investment, investment_per_grid, spacing_type), `grid_stats` (completed_cycles, total_profit, active_levels, total_levels, avg_profit_per_cycle), `pending_levels`, `filled_levels`

### src/crypto_bot/strategies/grid_trading.py (from earlier session):
- Added `GridStrategyStats` dataclass
- Added `get_statistics()` method to expose P&L data to API

### trading_dashboard/pages/dashboard.py:
- **P&L Calculation**: Now calculates P&L from actual Binance trades (sell cost - buy cost)
- **Price Chart**: Replaced equity curve with candlestick chart showing:
  - OHLCV candlesticks (15m timeframe, 24 hours)
  - Grid level horizontal lines
  - Pending buy/sell order markers (triangles on right edge)
  - Executed trade markers (triangles at trade timestamps)

### trading_dashboard/components/api_client.py:
- Added `fetch_ohlcv()` function to fetch candlestick data

## How to Test

1. Start the bot: `uv run python -m crypto_bot --dry-run`
2. Verify trades API returns data from Binance:
   ```bash
   curl http://localhost:8080/api/trades?limit=5
   ```
3. Verify status API includes all fields:
   ```bash
   curl http://localhost:8080/api/status
   ```
4. Open dashboard at http://localhost:8501 and verify:
   - Risk Management page shows green indicators
   - Grid Strategy page shows grid configuration and visualization
   - Trade History shows actual trades from Binance

## Risk / Rollback Notes

**Risks:**
- `/api/trades` makes exchange API calls for each symbol (rate limiting consideration)
- Trade history is fetched on-demand, not cached (may be slow for many symbols)

**Rollback:**
- Revert changes to health.py, ccxt_wrapper.py, base_exchange.py
- Dashboard will show empty/default data but won't break
