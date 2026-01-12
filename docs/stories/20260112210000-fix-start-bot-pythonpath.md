# Fix start_bot.bat PYTHONPATH for Module Import

## Summary
Fixed `start_bot.bat` to set `PYTHONPATH` to the `src` directory before launching the bot, resolving `ModuleNotFoundError: No module named 'crypto_bot'`.

## Context / Problem
The trading bot failed to start when using `start_bot.bat` because the `crypto_bot` module is located in `src/crypto_bot/`, but Python was looking for it in the project root. This caused the bot to crash immediately on startup with:

```
ModuleNotFoundError: No module named 'crypto_bot'
```

The dashboard (which lives in `dashboard/` at root level) worked fine, but the bot did not. This went unnoticed because only the dashboard was being actively used, while the bot silently failed.

## What Changed
- **start_bot.bat**: Added `set PYTHONPATH=%CD%\src` before the Python command to ensure the `src` directory is in the module search path.

```batch
REM Step 4: Start the bot (APPEND to logs with >>)
echo [4/5] Starting bot on port %BOT_PORT%...
set PYTHONPATH=%CD%\src
start /B python -m crypto_bot.main --api-port %BOT_PORT% >> %LOG_FILE% 2>&1
```

## How to Test
1. Stop any running bot processes: `taskkill /F /IM python.exe`
2. Run `start_bot.bat`
3. Check `logs/bot_output.log` - should not contain `ModuleNotFoundError`
4. Verify bot API responds: `curl http://localhost:8080/health`

## Risk / Rollback Notes
- **Low risk**: Only affects the startup script, not the bot code itself.
- **Rollback**: Remove the `set PYTHONPATH=%CD%\src` line from `start_bot.bat`.
- **Note**: If running the bot manually from command line, users should either:
  - Run from the `src` directory: `cd src && python -m crypto_bot.main`
  - Or set PYTHONPATH: `set PYTHONPATH=src && python -m crypto_bot.main`
