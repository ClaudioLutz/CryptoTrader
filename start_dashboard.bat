@echo off
REM Dashboard startup script for Windows

echo === Dashboard Startup Script ===
echo Time: %date% %time%
echo.

set DASHBOARD_PORT=8081
set BOT_API_PORT=8080
set LOG_FILE=logs\dashboard_output.log

REM Step 1: Check if bot API is running
echo [1/3] Checking if bot API is available...
curl -s http://localhost:%BOT_API_PORT%/health >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   WARNING: Bot API not detected on port %BOT_API_PORT%
    echo   Dashboard will have limited functionality without bot API
    echo.
) else (
    echo   Bot API detected on port %BOT_API_PORT%
)

REM Step 2: Ensure logs directory exists
echo [2/3] Ensuring logs directory exists...
if not exist logs mkdir logs
echo   Done.

REM Step 3: Start dashboard
echo [3/3] Starting dashboard on port %DASHBOARD_PORT%...
echo   Logging to: %LOG_FILE%
echo.

REM Run dashboard and append logs
python -m dashboard.main >> %LOG_FILE% 2>&1

echo.
echo Dashboard stopped.
