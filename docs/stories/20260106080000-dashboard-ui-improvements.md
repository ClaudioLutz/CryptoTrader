# Dashboard UI Improvements

## Summary
Improved dashboard layout and fixed several display issues:
1. Moved charts inside pair cards with 3-column layout (Orders | Chart | Trades)
2. Fixed timeframe performance row (1H, 24H, 7D, 30D) to calculate P&L from trades
3. Fixed trade marker positioning to scale chart y-axis correctly
4. Fixed orders count to show per-pair count instead of total

## Context / Problem
User feedback identified several issues with the dashboard:
- Orders count showed wrong values (total instead of per-pair)
- Timeframe performance row (1H, 24H, etc.) showed 0% for all timeframes
- Trade markers on chart appeared at incorrect positions relative to price line
- Chart was at the bottom of the page instead of inside each pair card
- Unused space on right side of expanded pair cards

## What Changed

### 1. Pair Cards with Embedded Charts
- **dashboard/components/pairs_table.py**:
  - Added `_create_mini_chart()` function for per-pair price charts
  - Added `_create_mini_figure()` for compact Plotly figures
  - Changed expansion content to 3-column layout: Orders | Chart | Trades
  - Chart y-axis now scales to include both OHLCV prices and trade marker prices
  - On expansion, fetches OHLCV data for the specific pair

### 2. Timeframe P&L Calculation
- **dashboard/state.py**:
  - Added `_calculate_timeframe_pnl()` method
  - Filters trades by timestamp for each timeframe (1H, 24H, 7D, 30D)
  - Handles both timezone-aware and naive timestamps
  - Updates `pnl_1h`, `pnl_24h`, `pnl_7d`, `pnl_30d` state attributes

### 3. Orders Count Fix
- **dashboard/components/pairs_table.py**:
  - Orders count in pair row header now filters orders by symbol
  - Shows actual order count for that specific pair

### 4. CSS Updates
- **dashboard/assets/css/theme.css**:
  - Added `.expansion-grid-3col` for 3-column layout
  - Added `.mini-chart-section` for center chart column
  - Updated `.order-details-section` and `.trades-section` with fixed widths
  - Added `.mini-price-chart` styling

### 5. Main Layout
- **dashboard/main.py**:
  - Removed bottom chart (charts now inside pair cards)
  - Removed unused `create_price_chart` import

## How to Test
1. Start the trading bot on port 8080
2. Start the dashboard: `python -m dashboard.main`
3. Verify:
   - Timeframe row (1H, 24H, 7D, 30D) shows calculated values (not all 0%)
   - Click on pair cards to expand them
   - Expanded cards show 3-column layout: Orders | Chart | Trades
   - Mini chart shows price line and trade markers at correct positions
   - Orders count in header shows total across all pairs
   - Orders count in pair row shows orders for that pair only

## Risk / Rollback Notes
- **Risk**: Mini chart adds extra API call (OHLCV) on card expansion
- **Risk**: Timeframe calculation adds slight overhead to refresh cycle
- **Mitigation**: OHLCV only fetched on-demand when card expanded
- **Rollback**: Revert these commits to restore previous behavior
