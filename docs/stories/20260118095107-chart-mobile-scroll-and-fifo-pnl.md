# Chart Mobile Scroll Fix and FIFO P&L Implementation

## Summary

Fixed mobile chart scrolling issues by disabling zoom/pan interactions and added CSS touch-action properties. Also increased chart data limits and switched P&L calculation from average cost to FIFO method.

## Context / Problem

1. **Mobile scroll blocking**: On mobile devices, the Plotly.js chart captured touch events, preventing users from scrolling the page when their finger was over the chart.

2. **Chart data gaps**: The price line didn't extend to the left edge because trade markers extended the x-axis beyond the OHLCV data range. Trade history went back to Jan 7, but 4H candles only fetched 42 (~7 days back to Jan 11).

3. **P&L calculation method**: The previous average cost method didn't match Binance's standard FIFO (First-In-First-Out) approach used for tax reporting and position tracking.

## What Changed

### Files Modified

- **`dashboard/components/pairs_table.py`**
  - Doubled `TIMEFRAME_LIMITS` from ~7 days to ~14 days of data
  - Changed chart config: `scrollZoom: False`, removed pan2d/zoom2d from toolbar
  - Updated figure layout: `fixedrange: True` on both axes, `dragmode: False`

- **`dashboard/assets/css/theme.css`**
  - Added `touch-action: pan-y` to `.mini-price-chart` for vertical page scrolling
  - Added mobile-specific styles for chart touch handling

- **`dashboard/services/pnl_calculator.py`**
  - Replaced average cost method with FIFO (First-In-First-Out)
  - FIFO matches sells against oldest buys first
  - Added fee deduction from realized P&L
  - Improved accuracy for tax reporting compliance

### Technical Details

**FIFO P&L Calculation:**
```
For each SELL:
1. Match quantity against oldest BUY in queue
2. Calculate cost basis from matched BUY prices
3. Realized P&L = Sell Proceeds - Cost Basis
4. Remove depleted BUYs from queue

Remaining holdings = sum of unmatched BUY quantities
```

**Chart Timeframe Limits (new):**
| Timeframe | Old Limit | New Limit | Coverage |
|-----------|-----------|-----------|----------|
| 1h        | 168       | 336       | ~14 days |
| 4h        | 42        | 84        | ~14 days |
| 1d        | 30        | 60        | ~60 days |
| 1w        | 12        | 24        | ~24 weeks|

## How to Test

1. **Mobile scroll test:**
   - Open dashboard on mobile device or use Chrome DevTools device mode
   - Expand a trading pair to show the chart
   - Try to scroll the page with finger on the chart
   - Expected: Page scrolls normally, chart does NOT zoom/pan

2. **Chart data test:**
   - Expand a trading pair
   - Select 4H timeframe
   - Expected: Price line extends to cover trade markers (no gaps on left)

3. **P&L test:**
   - Check realized P&L matches expected FIFO calculation
   - For 2 buys at $100, $110 and 1 sell at $115:
     - FIFO: Profit = $115 - $100 = $15 (uses oldest buy)
     - Avg Cost: Profit = $115 - $105 = $10 (uses average)

4. **Local testing:**
   ```bash
   cd dashboard
   python main.py
   # Open http://localhost:8081 in browser
   ```

## Risk / Rollback Notes

### Risks

- **P&L calculation change**: Users may see different P&L values after this update. FIFO is more accurate for tax purposes but may show different numbers than before.
- **Chart interactivity reduced**: Desktop users lose zoom/pan capability on the mini charts. If this is problematic, could add a fullscreen mode later.

### Rollback

1. Revert the three modified files:
   - `dashboard/components/pairs_table.py`
   - `dashboard/assets/css/theme.css`
   - `dashboard/services/pnl_calculator.py`

2. Rebuild and redeploy:
   ```bash
   gcloud builds submit --tag europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest
   ```
