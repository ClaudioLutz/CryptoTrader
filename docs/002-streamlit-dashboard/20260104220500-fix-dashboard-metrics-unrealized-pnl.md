# Fix Dashboard Metrics Panel - Unrealized P&L and Column Bug

## Summary

Fixed the dashboard metrics panel to correctly display unrealized P&L and fixed a bug where the Sell Orders metric was using the wrong column.

## Context / Problem

The dashboard had two issues:
1. **Column assignment bug**: The "Sell Orders" metric was incorrectly assigned to `col4` (which was already used for "Current Price"), causing it to overwrite that metric
2. **Strategy performance crash**: The `strategy_performance()` function was trying to unpack `calculate_pnl_from_trades()` as a tuple, but it now returns a dict with realized/unrealized P&L

## What Changed

### trading_dashboard/pages/dashboard.py:
- **Line 166**: Fixed column reference from `col4` to `col7` for "Sell Orders" metric
- **Line 173-179**: Added "Total Trades" metric to `col8` to utilize all 4 columns in the second row
- **Lines 409-411**: Fixed `strategy_performance()` to properly extract values from the dict returned by `calculate_pnl_from_trades()`

### Dashboard Metrics Layout (2 rows x 4 columns):
| Row 1 | Total P&L | Realized P&L | Unrealized P&L | Current Price |
|-------|-----------|--------------|----------------|---------------|
| Row 2 | Active Strategies | Buy Orders | Sell Orders | Total Trades |

## How to Test

1. Start the bot: `uv run python -m crypto_bot --dry-run`
2. Start the dashboard: `cd trading_dashboard && uv run streamlit run main.py`
3. Open http://localhost:8501 and verify:
   - All 8 metrics are visible in 2 rows
   - Current Price shows actual BTC price
   - Sell Orders shows correct count (not overwriting Current Price)
   - Strategy Performance section doesn't crash

## Risk / Rollback Notes

**Risks:**
- None significant - this is a display-only fix

**Rollback:**
- Revert changes to dashboard.py
