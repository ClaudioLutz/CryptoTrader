# Dashboard Enhanced Information Display

## Summary
Enhanced the dashboard to show more detailed trading information including TP/SL distances, grid strategy details, and per-trade P&L calculations.

## Context / Problem
The dashboard showed minimal information about trading activity:
- No visibility into grid strategy configuration
- No distance-to-target information for pending orders
- Trade history showed "-" for P&L instead of calculated values

Users needed quick visibility into:
- How far the price is from their next buy/sell orders
- Grid strategy parameters (range, levels, investment)
- Unrealized P&L for each open position

## What Changed

### 1. Data Models (`dashboard/services/data_models.py`)
Extended `PairData` with grid strategy fields:
- `lower_price`: Grid lower bound
- `upper_price`: Grid upper bound
- `num_grids`: Number of grid levels
- `total_investment`: Total invested amount

### 2. API Client (`dashboard/services/api_client.py`)
Updated `get_pairs()` to populate grid config from strategy data.

### 3. Pairs Table (`dashboard/components/pairs_table.py`)
Enhanced the expanded row view with:

**DISTANCES section** - Shows distance to next orders:
```
Next BUY: $131.20 (+7.1%)
TP: $143.45 (+1.6%)
```

**GRID STRATEGY section** - Shows strategy config:
```
Range: $120 - $150
Levels: 6
Investment: $45
```

**Trade rows** - Now show unrealized P&L:
```
BUY $137.19 0.065 +$0.26 (+2.9%) 14:30
```

### 4. Trade History (`dashboard/components/trade_history.py`)
Updated `_get_filtered_rows()` to calculate unrealized P&L for buy trades based on current price. The P&L column now shows actual values instead of "-".

## How to Test
1. Restart the dashboard: `restart_dashboard.bat`
2. Expand a trading pair (click on SOL/USDT)
3. Verify you see:
   - DISTANCES section with Next BUY and TP prices
   - GRID STRATEGY section with range, levels, investment
   - Recent trades with P&L values
4. Go to Trade History tab - verify P&L column shows calculated values

## Risk / Rollback Notes
- **Low risk**: Display-only changes, no trading logic affected
- **Performance**: Additional data now populated in API calls
- **Rollback**: Revert changes to data_models.py, api_client.py, pairs_table.py, trade_history.py
