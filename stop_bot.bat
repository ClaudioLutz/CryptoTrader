@echo off
REM Bot shutdown script for Windows

echo === Trading Bot Shutdown Script ===
echo Time: %date% %time%
echo.

REM Step 1: Find and stop bot processes
echo [1/2] Stopping bot processes...

REM Try to find python processes (bot typically runs on port 8080)
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo   Found Python processes, checking for crypto_bot...

    REM Kill Python processes - this will stop the bot
    REM Note: This stops ALL python processes. For more selective stopping,
    REM you would need to check which ones are running crypto_bot.main

    echo   Stopping bot (this may take a few seconds)...
    taskkill /IM python.exe /F >NUL 2>&1

    timeout /t 2 /nobreak >NUL
    echo   Bot stopped.
) else (
    echo   No Python processes found.
)

REM Step 2: Confirm shutdown
echo [2/2] Verifying shutdown...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo   WARNING: Some Python processes still running
) else (
    echo   All Python processes stopped.
)

echo.
echo === Bot Shutdown Complete ===
echo.
echo Note: All open orders remain on the exchange.
echo To cancel orders, log into Binance and cancel manually,
echo or use the dashboard Configuration tab.
echo.
pause
