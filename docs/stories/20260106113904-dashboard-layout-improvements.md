# Dashboard Layout Improvements

## Summary
Improved dashboard card layout to use more horizontal screen space, reduced trade row heights for better density, and documented the orders count discrepancy between header and cards.

## Context / Problem
User feedback indicated:
1. Cards were not using enough horizontal screen space (max-width was 1200px)
2. Trade list rows took too much vertical space, limiting visible trades
3. Orders count in header (15 ord) didn't match card order counts (0/0 for BTC/ETH)

## What Changed

### CSS Layout Improvements (`dashboard/assets/css/theme.css`)
- Changed `.centered-container` max-width from 1200px to 95% for wider cards
- Reduced `.trade-row` padding from 6px 12px to 3px 8px for compact rows
- Reduced `.trades-list` gap from 4px to 2px
- Reduced `.trade-icon` font-size from 14px to 12px
- Increased `.mini-chart-section` flex to 2 and min-width to 400px
- Made `.trades-section` flexible with flex: 1 and max-width: 450px
- Reduced `.order-details-section` max-width from 180px to 160px
- Increased `.expansion-grid-3col` gap from 16px to 24px
- Added width: 100% to `.expansion-content` and `.pair-expansion`
- Increased chart height from 150px to 180px

### Component Updates (`dashboard/components/pairs_table.py`)
- Reduced trade row gap from gap-3 to gap-2
- Changed timestamp format from HH:MM:SS to HH:MM for compactness
- Updated Plotly chart height to 180px

### Orders Count Discrepancy (Documented)
The header uses `sum(p.order_count for p in state.pairs)` from the status API, while cards use actual orders from `/api/orders`. This can differ due to:
- Stale data in status API
- Different counting logic (scheduled vs open orders)
- API response caching

## How to Test
1. Run the dashboard: `python dashboard/main.py`
2. Open in browser at http://localhost:8081
3. Verify cards now use ~95% of screen width
4. Expand a card and verify:
   - Trade rows are more compact
   - Chart is taller (180px)
   - 3-column layout uses full width
   - More trades visible in scrollable container

## Risk / Rollback Notes
- Low risk: CSS-only changes for layout
- Rollback: Revert CSS values to previous settings
- No backend changes required
