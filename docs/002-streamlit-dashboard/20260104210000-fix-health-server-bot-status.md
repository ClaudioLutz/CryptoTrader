# Fix Health Server Bot Status Tracking

## Summary

Fixed the HealthCheckServer integration so `/api/status` and `/ready` endpoints correctly report bot running status by passing bot references to the health server.

## Context / Problem

The backend API showed "bot not running" even when bots were active because:
1. `main.py` called `health_server.set_database(database)` but never called `health_server.set_bot(bot)`
2. The `/ready` endpoint returned 503 "Bot not initialized"
3. The `/api/status` endpoint reported `"bot": {"running": false}`

The dashboard was unable to display correct bot status because the health server had no reference to the running bots.

## What Changed

### Modified Files:
- `src/crypto_bot/main.py`:
  - Added `MultiBotTracker` class to track multiple bot instances and expose aggregate status
  - Refactored `run_single_bot()` into `create_bot()` (creates bot) and `run_bot()` (starts bot)
  - Changed bot creation flow: now bots are created before starting async tasks
  - Added `health_server.set_bot(bot_tracker)` to pass bot references to health server

### MultiBotTracker Features:
- `_running`: Returns `True` if any tracked bot is running
- `_strategy`: Returns first bot's strategy for status display
- `_exchange`: Returns first bot's exchange for status display
- `_dry_run`: Returns dry run mode status
- `get_all_strategies()`: Returns list of all strategies from tracked bots

## How to Test

1. Start the bot with API server:
   ```bash
   python -m crypto_bot --dry-run
   ```

2. Verify `/ready` returns 200:
   ```bash
   curl http://localhost:8080/ready
   ```
   Expected: `{"status": "ready", ...}`

3. Verify `/api/status` shows bot running:
   ```bash
   curl http://localhost:8080/api/status
   ```
   Expected: `"bot": {"running": true, ...}`

4. Verify dashboard shows correct status

## Risk / Rollback Notes

**Risks:**
- Low risk: Only affects status reporting, not trading logic
- No changes to exchange interactions or order placement

**Rollback:**
- Revert changes to `main.py`
- Bot will continue to trade correctly, only status endpoints will be affected
