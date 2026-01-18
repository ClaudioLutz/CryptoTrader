# Dynamic Chart Candle Limit Calculation

## Summary

Replaced hardcoded OHLCV candle limits with dynamic calculation based on trade history timestamps, ensuring the price line always extends to cover all trade markers on the chart.

## Context / Problem

The chart had a gap on the left side where trade markers existed but the price line didn't reach. This was because:

1. **Hardcoded limits**: TIMEFRAME_LIMITS was set to fixed values (e.g., 84 candles for 4H)
2. **Trade history mismatch**: Trade history could extend further back than the OHLCV data
3. **Example**: If trades went back to Jan 7, but 4H candles only fetched 84 (~14 days), the chart x-axis extended to show trade markers but had no price data on the left

## What Changed

### Files Modified

- **`dashboard/components/pairs_table.py`**
  - Removed hardcoded `TIMEFRAME_LIMITS` dictionary
  - Added `TIMEFRAME_HOURS` for time-per-candle calculation
  - Added `MIN_CANDLE_LIMITS` for fallback when no trades exist
  - Added `MAX_CANDLES = 500` to prevent excessive API calls
  - New function `_calculate_candle_limit(trades, timeframe)` that:
    - Finds the earliest trade timestamp
    - Calculates time difference from now
    - Determines how many candles needed to cover that period
    - Adds 10% buffer + 5 extra candles for safety
  - Updated `on_expansion_change`, `change_timeframe`, and `_change_timeframe` to use dynamic calculation

### Technical Details

**Calculation Logic:**
```
candles_needed = (hours_since_earliest_trade / hours_per_candle) * 1.1 + 5
limit = max(min_limit, min(candles_needed, 500))
```

**Example for 4H timeframe with trades from 11 days ago:**
- Hours since earliest trade: 11 * 24 = 264
- Hours per 4H candle: 4
- Base candles: 264 / 4 = 66
- With buffer: 66 * 1.1 + 5 = 78 candles (capped at 500)

## How to Test

1. **Local testing:**
   ```bash
   cd dashboard
   python main.py
   # Open http://localhost:8081
   ```

2. **Verify chart coverage:**
   - Expand a trading pair with trade history
   - Select different timeframes (1H, 4H, 1D, 1W)
   - Expected: Price line extends to cover ALL trade markers (no gap on left)

3. **Check console logs:**
   - The calculated limit will be used for OHLCV API calls
   - Verify it matches the trade history timespan

## Risk / Rollback Notes

### Risks

- **More API calls**: Longer trade history = more candles fetched. Mitigated by MAX_CANDLES cap (500)
- **Performance**: More data to render on charts. Charts remain performant with up to 500 points

### Rollback

1. Revert `dashboard/components/pairs_table.py`
2. Restore the hardcoded `TIMEFRAME_LIMITS` dictionary
3. Rebuild and redeploy
