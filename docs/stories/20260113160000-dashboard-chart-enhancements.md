# Dashboard Chart Enhancements

## Summary
Enhanced the dashboard price chart with grid level visualization, zoom/pan controls, and improved data coverage across timeframes.

## Context / Problem
The dashboard chart had several limitations:
1. No visualization of grid trading levels - users couldn't see where buy/sell orders would trigger
2. 1H timeframe only showed 48 hours of data, leaving gaps when trades occurred earlier
3. Chart was static with no zoom/pan capability for detailed analysis
4. Chart overflow was causing the RECENT TRADES section to overlap

## What Changed

### 1. Grid Level Visualization (`dashboard/components/pairs_table.py`)
- Added `_calculate_grid_levels()` function to compute geometric grid prices
- Grid levels displayed as horizontal amber/yellow dotted lines on the chart
- Lines only appear when grid config is available for the pair
- Y-axis auto-scales to price data (grid lines visible when in view)

### 2. Timeframe-Specific Candle Limits (`dashboard/components/pairs_table.py`)
- Added `TIMEFRAME_LIMITS` mapping for appropriate data coverage:
  - 1H: 168 candles (7 days)
  - 4H: 42 candles (7 days)
  - 1D: 30 candles (30 days)
  - 1W: 12 candles (12 weeks)
- Previously all timeframes used 48 candles, causing 1H to show only 2 days

### 3. Zoom/Pan Controls (`dashboard/components/pairs_table.py`)
- Enabled scroll-to-zoom on chart (`scrollZoom: true`)
- Enabled drag-to-pan on both axes (`fixedrange: false`)
- Mode bar appears on hover with zoom/pan/reset buttons
- Removed lasso and select tools (not useful for price charts)

### 4. Layout Fix (`dashboard/assets/css/theme.css`)
- Added `overflow: hidden` and `max-width` to `.mini-chart-section` to contain Plotly chart
- Added `z-index: 10` and solid background to `.trades-section` to prevent chart overlap
- Ensures proper 3-column layout separation (Orders | Chart | Trades)

## How to Test
1. Restart dashboard: `restart_dashboard.bat`
2. Expand SOL/USDT pair
3. Verify:
   - Grid lines appear as amber dotted horizontal lines at $120, $125, $131, $137, $143, $150
   - 1H chart shows ~7 days of data (back to Jan 7)
   - Scroll wheel zooms in/out
   - Click and drag to pan
   - Hover over chart to see toolbar
   - RECENT TRADES section does not overlap chart
4. Switch timeframes (1H, 4H, 1D, 1W) and verify each loads appropriate data range

## Risk / Rollback Notes
- **Low risk**: Display-only changes, no trading logic affected
- **Performance**: 1H now fetches 168 candles instead of 48 (slightly more API calls)
- **Rollback**: Revert changes to `pairs_table.py` and `theme.css`

## Technical Details

### Grid Level Calculation (Geometric Spacing)
```python
ratio = (upper_price / lower_price) ** (1 / (num_grids - 1))
levels = [lower_price * (ratio ** i) for i in range(num_grids)]
```

### Plotly Config for Zoom/Pan
```python
chart._props["config"] = {
    "scrollZoom": True,
    "displayModeBar": "hover",
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}
```
