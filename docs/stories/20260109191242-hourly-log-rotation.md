# Hourly Log Rotation with 30 File Limit

## Summary
Changed log rotation from size-based to time-based (hourly) with a maximum of 30 backup files.

## Context / Problem
The previous logging configuration used `RotatingFileHandler` which rotated logs based on file size (10MB default). This made it difficult to correlate logs with specific time periods. Users needed time-based rotation for easier debugging and log management.

## What Changed
- Modified `src/crypto_bot/config/logging_config.py`:
  - Replaced `RotatingFileHandler` with `TimedRotatingFileHandler`
  - Changed `configure_logging()` parameters: removed `max_bytes`, added `rotation_interval` (default: 'H' for hourly)
  - Updated `add_file_handler()` to use time-based rotation with `when` parameter
  - Default `backup_count` changed from 5 to 30
  - Rotation uses UTC timestamps for consistency

## How to Test
1. Start the bot with file logging enabled
2. Check that log files are created in the `logs/` directory
3. Wait for an hour (or manually test by changing system time) to verify rotation
4. Verify old log files are named with timestamp suffixes (e.g., `crypto_bot.log.2026-01-09_19`)
5. Confirm only 30 backup files are retained after extended operation

## Risk / Rollback Notes
- Low risk change - only affects log file management
- To rollback: revert `logging_config.py` to use `RotatingFileHandler` with `maxBytes` parameter
- Existing log files will remain; new rotation pattern will apply to new logs only
