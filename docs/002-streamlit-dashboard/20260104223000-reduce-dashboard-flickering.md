# Reduce Dashboard Flickering and Improve Refresh UX

## Summary

Reduced dashboard flickering caused by frequent `st.fragment` auto-refreshes by increasing intervals, adding manual refresh control, and removing redundant API calls.

## Context / Problem

The Streamlit dashboard was experiencing annoying flickering/reloading every few seconds due to:
1. Multiple `st.fragment` decorators with `run_every="5s"` causing frequent re-renders
2. Dataframe components inside fragments known to flicker (Streamlit bug)
3. Redundant API calls at the end of the page triggering additional renders
4. Duplicate metrics appearing in the UI due to layout issues

## What Changed

### trading_dashboard/pages/dashboard.py:
- **Added manual "Refresh Data" button** - Users can control when to refresh data instead of relying solely on auto-refresh
- **Increased refresh intervals**:
  - `live_metrics_panel`: 5s -> 10s
  - `strategy_performance`: 5s -> 15s
- **Removed redundant API call** - Removed duplicate `fetch_strategies()` at the end of the page
- **Added `key` parameter to plotly chart** - Prevents chart from being recreated unnecessarily
- **Wrapped metrics in explicit container** - Helps Streamlit manage layout stability
- **Removed `pnl` column from dataframe** - Dataframe with `on_select` causes flickering (known bug)
- **Last updated timestamp** - Shows when data was last refreshed

### Why These Solutions?

Based on research from Streamlit forums and GitHub issues:
- Dataframes with `on_select` inside `st.fragment` have a known flickering bug
- Fragment re-renders cause visual "greyed out" states during reruns
- Longer intervals reduce perceived flickering
- Manual refresh gives users control over when updates happen

## How to Test

1. Start the bot and dashboard
2. Observe that metrics refresh every 10s (less frequent than before)
3. Click "Refresh Data" button to manually refresh all data
4. Verify no duplicate metrics panels appear
5. Verify chart doesn't flicker constantly

## Risk / Rollback Notes

**Risks:**
- Data is less "real-time" with 10-15s intervals (acceptable trade-off)
- Manual refresh requires user action for immediate updates

**Rollback:**
- Revert changes to dashboard.py
- Change intervals back to 5s if users prefer more frequent updates

## Sources

- [Streamlit Fragment Flickering Issue](https://discuss.streamlit.io/t/experimental-fragment-flickering-streamlit-chart-elements/74343)
- [Dataframe flickering with on_select bug](https://github.com/streamlit/streamlit/issues/9527)
- [st.empty for dynamic updates](https://docs.streamlit.io/develop/api-reference/layout/st.empty)
- [Streamlit 2025 Release Notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2025)
