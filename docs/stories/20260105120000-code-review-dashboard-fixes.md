# Code Review: Dashboard Fixes and Improvements

## Summary

Fixed 9 issues identified during adversarial code review of the Streamlit trading dashboard: implemented missing API calls, added equity curve chart, fixed hardcoded symbols, resolved asyncio issues, added input validation, improved error logging, and added unit tests.

## Context / Problem

An adversarial code review of the Streamlit dashboard implementation identified multiple issues:
1. Manual control buttons showed "API call would go here" instead of actually calling the backend (safety-critical)
2. Equity curve chart was missing despite being in the acceptance criteria
3. Hardcoded "BTC/USDT" symbol throughout the dashboard
4. `asyncio.run()` inside cached function causing potential runtime errors
5. Unused dependencies in requirements.txt
6. Silent error swallowing in API response parsing
7. No input validation on configuration forms
8. Positions table missing sortability (AC gap)
9. P&L calculation logic had no unit tests

## What Changed

### trading_dashboard/pages/risk_management.py:
- **Implemented API calls** for Reset Circuit Breaker, Reset Daily Counters, and Emergency Stop
- Actions now call actual backend endpoints with proper error handling

### trading_dashboard/pages/configuration.py:
- **Implemented API calls** for Trading Toggle, Restart Strategy, and Clear Orders
- **Added input validation** for grid configuration:
  - Validates upper_price > lower_price
  - Validates num_grids >= 2
  - Validates total_investment > 0
  - Validates lower_price > 0

### trading_dashboard/pages/dashboard.py:
- **Added Portfolio Summary (All Pairs)** - aggregate P&L across all trading pairs
  - Total P&L, Realized P&L, Unrealized P&L calculated per-symbol with correct current prices
  - Per-symbol breakdown showing individual pair P&L
  - Open orders summary
- **Added Selected Symbol Details** - filtered metrics for currently selected symbol only
- **Added equity curve chart** with drawdown overlay using Plotly
- **Added symbol selector** - dynamic dropdown that fetches symbols from strategies
- **Replaced hardcoded BTC/USDT** with `state.selected_symbol` throughout
- Added `fetch_equity` import and `get_state` for state management

### trading_dashboard/components/api_client.py:
- **Added logging** for API errors (previously silently swallowed)
- **Fixed asyncio.run() issue** - replaced with synchronous calls in `get_all_data()`
- Improved `_parse_response()` with specific error logging

### trading_dashboard/pages/positions_orders.py:
- **Added AgGrid support** for positions table with sorting/filtering
- P&L columns now color-coded (green/red)
- Side column styled (LONG green, SHORT red)
- Fallback to basic dataframe if AgGrid not installed

### trading_dashboard/requirements.txt:
- Removed unused `streamlit-lightweight-charts` dependency
- Removed unused `orjson` dependency
- Added note about using Plotly for all charts

### trading_dashboard/tests/ (NEW):
- Created test package with `__init__.py`
- Added `test_pnl_calculation.py` with 12 test cases:
  - Empty trades
  - Single buy scenarios
  - Buy and sell cycles
  - Multiple buys (average cost)
  - Partial sells
  - Grid trading scenarios
  - Invalid data handling
  - Case insensitivity
  - Edge cases

## How to Test

1. **Run unit tests:**
   ```bash
   cd trading_dashboard
   pytest tests/ -v
   ```

2. **Test API calls manually:**
   - Start the backend API server
   - Navigate to Risk Management page
   - Click "Reset Circuit Breaker" - should call `/api/risk/reset-circuit-breaker`
   - Click "Emergency Stop" - should call `/api/risk/emergency-stop`

3. **Test symbol selector:**
   - Open dashboard
   - Use symbol dropdown to change trading pair
   - Verify chart and metrics update for selected symbol

4. **Test equity curve:**
   - Dashboard should display equity curve below price chart
   - If no equity data, shows informative message

5. **Test input validation:**
   - Navigate to Configuration page
   - Try to save with upper_price < lower_price - should show error
   - Try to save with num_grids = 1 - should show error

6. **Test positions table sorting:**
   - Navigate to Positions page
   - Click column headers to sort
   - Verify P&L colors (green/red)

## Risk / Rollback Notes

**Risks:**
- API endpoints for risk controls must exist in backend
- If backend endpoints don't match expected paths, API calls will fail with proper error messages

**Rollback:**
- Revert changes to individual files
- Tests can be removed independently without affecting functionality

**New Dependencies:**
- None added (AgGrid was already in requirements)

**Breaking Changes:**
- None - all changes are backwards compatible
