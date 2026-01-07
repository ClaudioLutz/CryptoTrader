# Fix Binance Timestamp Sync for System Clock Skew

**Date:** 2026-01-07
**Author:** Claude + User
**Status:** Completed

## Summary

Fixed Binance API connection failures caused by system clock being ahead of server time by implementing CCXT's built-in time synchronization. Bot now successfully authenticates and places orders even with 3+ minute clock skew that cannot be corrected at the system level.

## Context / Problem

Bot was unable to connect to Binance API, failing with error:
```
InvalidNonce: binance {"code":-1021,"msg":"Timestamp for this request was 1000ms ahead of the server's time."}
```

**Root Cause:** User's system clock was 199+ seconds (3.3 minutes) ahead of Binance server time, locked by company policy and cannot be synced. Binance API rejects requests when timestamp is >1000ms ahead.

**Impact:** Bot completely unable to start trading, all order placement attempts failed at connection stage.

## What Changed

### Files Modified

**`src/crypto_bot/exchange/ccxt_wrapper.py` (lines 94-105)**
- Added explicit time synchronization using CCXT's `load_time_difference()` method
- Calls `await self._exchange.load_time_difference()` before loading markets
- Logs time difference for debugging: `time_difference_ms=199216`
- Gracefully handles sync failures with warning instead of crashing

**Before:**
```python
# Enable testnet/sandbox mode if configured
if self._settings.testnet:
    self._exchange.set_sandbox_mode(True)

# Pre-load markets to cache symbol info
self._markets = await self._exchange.load_markets()
```

**After:**
```python
# Enable testnet/sandbox mode if configured
if self._settings.testnet:
    self._exchange.set_sandbox_mode(True)

# Sync time with Binance server using CCXT's built-in method
# This is critical when system clock is ahead/behind server time
try:
    await self._exchange.load_time_difference()
    time_diff = self._exchange.options.get('timeDifference', 0)
    self._logger.info(
        "time_sync",
        time_difference_ms=time_diff,
        message="Synchronized with exchange server time",
    )
except Exception as e:
    self._logger.warning("time_sync_failed", error=str(e))

# Pre-load markets to cache symbol info
self._markets = await self._exchange.load_markets()
```

### Configuration Already Present

The following settings were already configured in `ccxt_wrapper.py:80-86` but weren't sufficient alone:
- `adjustForTimeDifference: True` - Auto-adjusts for time differences
- `recvWindow: 60000` - 60-second tolerance window

These settings help but require the initial time sync to succeed first.

## How to Test

### 1. Verify Time Sync on Startup

```bash
cd c:/Lokal_Code/CryptoTrader
python -m crypto_bot.main --api-port 8084
```

**Expected log output:**
```json
{
  "component":"binance_adapter",
  "testnet":false,
  "time_difference_ms":199216,
  "message":"Synchronized with exchange server time",
  "event":"time_sync",
  "level":"info"
}
```

### 2. Verify Order Placement Works

Check logs for successful order placement:
```bash
tail -50 logs/bot_output.log | grep "grid_order_placed"
```

**Expected output:**
```json
{
  "strategy":"grid",
  "symbol":"SOL/USDT",
  "side":"buy",
  "price":"120.00",
  "event":"grid_order_placed"
}
```

### 3. Test with Deliberately Skewed Clock

To test robustness, this fix handles clock differences up to several minutes:
1. System clock can be ahead or behind by 3+ minutes
2. Bot should still connect and place orders successfully
3. Check `time_difference_ms` value in logs to confirm sync

### 4. Verify on Binance Exchange

1. Log into Binance.com
2. Navigate to **Orders** → **Open Orders**
3. Verify SOL/USDT buy limit orders are present
4. Order IDs should match those in bot logs

## Risk / Rollback Notes

### Risks

1. **Network Latency Impact**
   - If network latency is very high (>60 seconds), initial time sync may fail
   - Mitigation: `recvWindow: 60000` provides large tolerance window
   - Fallback: Bot logs warning and attempts to continue

2. **Time Drift Over Long Runtime**
   - Time difference calculated at startup only
   - If system clock drifts further during runtime, could cause issues
   - Mitigation: Bot typically restarts daily; consider adding periodic re-sync

3. **Exchange API Changes**
   - CCXT `load_time_difference()` method could change behavior
   - Currently using ccxt async_support library
   - Mitigation: Method is stable and widely used

### Rollback Steps

If this change causes issues, revert `ccxt_wrapper.py`:

```bash
cd c:/Lokal_Code/CryptoTrader
git diff src/crypto_bot/exchange/ccxt_wrapper.py
git checkout src/crypto_bot/exchange/ccxt_wrapper.py
```

**Alternative Fix (if rollback needed):**
Use system-level time sync instead:
```bash
# Windows (requires admin)
w32tm /resync

# Linux
sudo ntpdate -s time.nist.gov
```

### Monitoring

**Watch for these indicators of problems:**
1. `time_sync_failed` warnings in logs
2. Continued `-1021` errors after startup
3. Orders failing with timestamp errors

**Log locations:**
- `logs/bot_output.log` - Main bot logs
- `logs/trading.log` - Detailed trading activity

## Additional Context

### Other Issues Fixed During Session

1. **Binance Testnet Down** - Switched from testnet to mainnet
2. **API Permissions** - Enabled "Spot & Margin Trading" on API key
3. **USD vs USDT** - User converted USD fiat to USDT cryptocurrency
4. **Insufficient Balance** - User purchased USDT to fund trading

### Related Files

- `.env:10` - `EXCHANGE__TESTNET=false` (switched to mainnet)
- `.env:8-9` - API keys updated for mainnet
- `src/crypto_bot/main.py:265-273` - Grid config adjusted for $50 balance

### Success Metrics

After fix deployment:
- ✅ Bot connects successfully to Binance mainnet
- ✅ Time sync shows 199+ second difference handled correctly
- ✅ 4 grid orders placed successfully (IDs: 16001105112, 16001105122, 16001105130, 16001105138)
- ✅ Bot running continuously without timestamp errors
- ✅ Total value traded: ~$36 USDT in SOL/USDT grid orders

## Future Improvements

1. **Periodic Time Re-sync** - Re-sync every N hours to handle drift
2. **Time Sync Health Check** - Monitor time difference and alert if exceeds threshold
3. **Retry Logic** - If initial sync fails, retry with exponential backoff
4. **Documentation** - Add time sync troubleshooting to README.md
