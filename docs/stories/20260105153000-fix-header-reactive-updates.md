# Fix Dashboard Data Display

## Summary
Fixed dashboard to properly display current prices and P&L by:
1. Making header components reactive (update every 2 seconds)
2. Fetching current prices from OHLCV data (like the old Streamlit dashboard)
3. Calculating P&L from actual trade history client-side

## Context / Problem
The dashboard was displaying €0.00 for P&L and $0.000000 for all prices despite trades being visible. Multiple issues were identified:

1. **Header not reactive**: Components were created once at startup and never updated
2. **Prices hardcoded to zero**: `get_pairs()` had `current_price=Decimal("0")` hardcoded
3. **P&L from wrong source**: The dashboard relied on `/api/pnl` backend endpoint which queries database trades that may not have `profit` fields populated, instead of calculating from actual exchange trades

The old Streamlit dashboard (`trading_dashboard/`) worked correctly because it:
- Fetches current prices from OHLCV data (`fetch_ohlcv(symbol, timeframe="1m", limit=1)`)
- Calculates P&L client-side from actual trade history using `calculate_pnl_from_trades()`

## What Changed

### 1. Header Reactive Updates
- **dashboard/components/header.py**:
  - Added container references and `refresh_header()` function
  - Added `ui.timer(2.0, refresh_header)` for auto-refresh
  - Renamed functions to `_create_*_content()` pattern

### 2. Current Price Fetching
- **dashboard/services/api_client.py**:
  - Added `_get_current_price(symbol)` method that fetches 1-minute OHLCV candle
  - Updated `get_pairs()` to call `_get_current_price()` for each symbol
  - Fixed logging syntax (removed structlog-style `error=` kwargs)

### 3. P&L Calculation from Trades
- **dashboard/services/pnl_calculator.py** (NEW):
  - Added `calculate_pnl_from_trades()` - mirrors old dashboard logic
  - Added `calculate_portfolio_pnl()` for aggregate calculation
  - Calculates realized P&L from buy/sell pairs
  - Calculates unrealized P&L from holdings × current price

- **dashboard/state.py**:
  - Added `_calculate_pnl_from_trades()` method
  - Fetches trades from `/api/trades` and calculates P&L per symbol
  - Updates `total_pnl`, `total_pnl_percent`, and per-pair P&L values

## How to Test
1. Start the trading bot on port 8080
2. Start the dashboard: `python -m dashboard.main`
3. Observe:
   - Header shows current prices (not $0.000000)
   - Header P&L updates every 2 seconds
   - Per-pair P&L in table shows calculated values
   - Timestamp updates every 2 seconds

## Risk / Rollback Notes
- **Risk**: Additional OHLCV requests per pair may increase API load
- **Risk**: Trade fetch timeout could cause stale P&L values
- **Mitigation**: P&L calculation has try/except to avoid crashing on errors
- **Rollback**: Revert these commits to restore previous behavior
