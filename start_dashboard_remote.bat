@echo off
REM ============================================================================
REM Dashboard (lokal) mit SSH-Tunnel zur GCP VM
REM ============================================================================

REM Ins Projektverzeichnis wechseln (Verzeichnis der BAT-Datei)
cd /d "%~dp0"

echo ============================================
echo   CryptoTrader Dashboard (Remote-Modus)
echo   %date% %time%
echo ============================================
echo.

set GCP_PROJECT=cryptotrader-bot-20260115
set GCP_ACCOUNT=billwilson.rip2012@gmail.com
set GCP_ZONE=europe-west4-a
set GCP_VM=cryptotrader-vm
set BOT_API_PORT=8082
set DASHBOARD_PORT=8081

REM Venv aktivieren
echo [1/4] Aktiviere Python venv...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo   OK.
) else (
    echo   FEHLER: venv nicht gefunden!
    pause
    exit /b 1
)

REM SSH-Tunnel starten (eigenes Fenster, sichtbar)
echo [2/4] Starte SSH-Tunnel...
start "CryptoTrader SSH-Tunnel" cmd /c "gcloud compute ssh %GCP_VM% --zone=%GCP_ZONE% --project=%GCP_PROJECT% --account=%GCP_ACCOUNT% -- -L %BOT_API_PORT%:localhost:%BOT_API_PORT% -N"
echo   Warte 15s auf Verbindung...
timeout /t 15 /nobreak >NUL

REM Pruefen ob Tunnel steht
echo [3/4] Pruefe Bot-API...
curl -s http://localhost:%BOT_API_PORT%/health >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Noch nicht bereit, warte nochmal 15s...
    timeout /t 15 /nobreak >NUL
    curl -s http://localhost:%BOT_API_PORT%/health >NUL 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo   WARNUNG: Bot-API nicht erreichbar!
        echo   Pruefe ob das SSH-Tunnel-Fenster offen ist.
        echo   Druecke eine Taste um trotzdem fortzufahren...
        pause
    ) else (
        echo   Bot-API erreichbar!
    )
) else (
    echo   Bot-API erreichbar!
)

REM Dashboard starten
echo [4/4] Starte Dashboard...
echo.
echo   ============================================
echo   Dashboard: http://localhost:%DASHBOARD_PORT%
echo   Beenden:   Dieses Fenster schliessen
echo   ============================================
echo.

set DASHBOARD_API_BASE_URL=http://localhost:%BOT_API_PORT%
if not exist logs mkdir logs
python -m dashboard.main

REM Aufraemen
echo.
echo Dashboard gestoppt. Schliesse SSH-Tunnel...
taskkill /FI "WINDOWTITLE eq CryptoTrader SSH-Tunnel" /F >NUL 2>&1
echo Fertig.
pause
