@echo off
REM Proper bot startup script for Windows

echo === Trading Bot Startup Script ===
echo Time: %date% %time%
echo.

set BOT_PORT=8080
REM Dashboard uses 8081
set LOG_FILE=logs\bot_output.log
set PID_FILE=logs\bot.pid

REM Step 1: Kill any existing bot processes
echo [1/5] Checking for existing bot processes...
tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *crypto_bot*" 2>NUL | find /I "python.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo   Found running bot process^(es^), stopping...
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq *crypto_bot*" 2>NUL
    timeout /t 2 /nobreak >NUL
    echo   Stopped.
) else (
    echo   No existing processes found.
)

REM Step 2: Ensure logs directory exists
echo [2/5] Ensuring logs directory exists...
if not exist logs mkdir logs
echo   Done.

REM Step 3: Archive old log if too large
echo [3/5] Checking log file size...
if exist %LOG_FILE% (
    for %%A in (%LOG_FILE%) do set LOG_SIZE=%%~zA
    if !LOG_SIZE! GTR 10485760 (
        echo   Log file is large, archiving...
        ren %LOG_FILE% bot_output_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
        echo   Archived.
    ) else (
        echo   Log file size OK.
    )
)

REM Step 4: Start the bot (APPEND to logs with >>)
echo [4/5] Starting bot on port %BOT_PORT%...
start /B python -m crypto_bot.main --api-port %BOT_PORT% >> %LOG_FILE% 2>&1

REM Wait a moment
timeout /t 5 /nobreak >NUL

echo [5/5] Bot started
echo.
echo === Bot Started ===
echo   Port: %BOT_PORT%
echo   Logs: %LOG_FILE%
echo.
echo Monitor logs: type %LOG_FILE%
echo Stop bot: Use Task Manager or taskkill
