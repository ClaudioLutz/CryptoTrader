# Grid Level Visualization on Price Chart

## Summary
Added horizontal grid lines to the dashboard price chart showing all configured grid levels.

## Context / Problem
Users couldn't visualize where their grid buy/sell levels were positioned relative to the current price and historical price action. This made it difficult to understand the strategy's coverage and how price movements relate to grid levels.

## What Changed

### `dashboard/components/pairs_table.py`
- Added `_calculate_grid_levels()` function to compute geometric grid prices
- Updated `_create_mini_figure()` to accept optional `grid_levels` parameter
- Added horizontal dotted lines (amber/yellow) at each grid level with price annotations
- Updated y-axis range calculation to include grid levels (ensures full grid is visible)
- Updated `_create_mini_chart()` to pass grid config to figure creation

### Visual Design
- Grid lines: Dotted amber lines (`rgba(255, 193, 7, 0.4)`)
- Annotations: Price labels on left side in matching color
- Y-axis auto-scales to show entire grid range

## How to Test
1. Restart dashboard: `restart_dashboard.bat`
2. Click to expand SOL/USDT pair
3. Verify horizontal lines appear at grid levels ($120, $125.48, $131.20, $137.19, $143.45, $150)
4. Lines should be visible across all timeframes (1H, 4H, 1D, 1W)
5. Price labels should appear on left side of each line

## Risk / Rollback Notes
- Low risk: Display-only change, no trading logic affected
- Performance: Adds 6 horizontal lines per chart (minimal impact)
- Rollback: Revert changes to `pairs_table.py`
