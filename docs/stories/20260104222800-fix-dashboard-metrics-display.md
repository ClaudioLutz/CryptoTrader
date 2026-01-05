# Fix Dashboard Metrics Display and Reduce Flickering

## Summary

Fixed the dashboard to correctly display pending orders count by reading from actual orders data instead of empty strategy statistics. Also reduced page flickering by increasing refresh intervals.

## Context / Problem

The dashboard was showing incorrect information:
1. "0 buy / 0 sell" in the metrics panel even when orders existed
2. Strategy Performance cards showed "$0.00" profit because `GridTradingStrategy` doesn't implement `get_statistics()`
3. Page was "shaking" during auto-refresh due to aggressive 2-3 second refresh intervals

The root cause was that the dashboard was trying to read from `strategy.get_statistics()` which returned empty data, instead of using the actual orders from the `/api/orders` endpoint.

## What Changed

### trading_dashboard/pages/dashboard.py:
- **Live Metrics Panel**: Now counts buy/sell orders from actual orders data instead of empty strategy stats
- **Strategy Performance**: Changed from showing unavailable profit/cycles to showing pending orders per symbol
- **Refresh Intervals**: Increased from 2-3s to 5s for all fragments to reduce flickering
- Removed redundant profit/cycles metrics that weren't available

### Key code changes:
```python
# Before (reading from empty stats):
buy_orders = stats.get("active_buy_orders", 0)

# After (reading from actual orders):
orders_data = fetch_orders()
orders = orders_data.get("orders", [])
buy_orders = len([o for o in orders if o.get("side", "").lower() == "buy"])
```

## How to Test

1. Ensure bot is running: `uv run python -m crypto_bot`
2. Open dashboard at http://localhost:8501
3. Verify:
   - Top metrics show correct order counts (e.g., "15 Total Orders", "10 Buy", "5 Sell")
   - Strategy Performance cards show per-symbol order counts
   - Page refresh is smoother (5s intervals instead of 2-3s)

## Risk / Rollback Notes

**Risks:**
- None significant - purely UI display changes

**Rollback:**
- Revert changes to `trading_dashboard/pages/dashboard.py`
