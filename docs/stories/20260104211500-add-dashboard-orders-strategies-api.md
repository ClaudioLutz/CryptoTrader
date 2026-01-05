# Add Dashboard Orders and Strategies API Endpoints

## Summary

Added new API endpoints `/api/orders` and `/api/strategies` to provide the dashboard with real-time visibility into pending exchange orders and strategy performance.

## Context / Problem

The dashboard showed "No open positions" even when the bot was actively trading. Users had no visibility into:
1. Pending limit orders on the exchange
2. Strategy configuration and statistics
3. Completed grid cycles and profit

The bot was completing trades but the dashboard didn't display this important information.

## What Changed

### Backend API (src/crypto_bot/utils/health.py):
- Added `/api/orders` endpoint - Returns pending orders from the exchange for all trading symbols
- Added `/api/strategies` endpoint - Returns all strategies with their configuration and statistics

### Dashboard API Client (trading_dashboard/components/api_client.py):
- Added `fetch_orders()` function with 3s cache
- Added `fetch_strategies()` function with 5s cache

### Dashboard Pages:
- **dashboard.py**: Updated metrics panel to show:
  - Total profit from all strategies
  - Number of active strategies
  - Pending orders count (buy/sell breakdown)
  - Grid cycles completed
  - Strategy performance cards per symbol

- **positions_orders.py**: Fixed orders table to:
  - Use new `/api/orders` endpoint instead of non-existent `pending_orders`
  - Show order count summary (X buy / Y sell)
  - Support symbol and side filtering

## How to Test

1. Start the bot:
   ```bash
   python -m crypto_bot
   ```

2. Start the dashboard:
   ```bash
   cd trading_dashboard
   streamlit run app.py
   ```

3. Verify API endpoints:
   ```bash
   curl http://localhost:8080/api/orders
   curl http://localhost:8080/api/strategies
   ```

4. Check dashboard shows:
   - Pending orders in Positions & Orders page
   - Strategy cards on main dashboard

## Risk / Rollback Notes

**Risks:**
- `/api/orders` makes exchange API calls for each symbol (rate limiting consideration)
- New endpoints add load to health server

**Rollback:**
- Revert changes to health.py, api_client.py, dashboard.py, positions_orders.py
- Dashboard will show empty data but won't break
