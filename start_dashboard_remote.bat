@echo off
REM ============================================================================
REM Dashboard (lokal) mit SSH-Tunnel zur GCP VM
REM
REM Startet einen SSH-Tunnel zur GCP VM und dann das Dashboard lokal.
REM Das Dashboard verbindet sich via localhost:8082 zum Bot auf der VM.
REM ============================================================================

echo ============================================
echo   CryptoTrader Dashboard (Remote-Modus)
echo   %date% %time%
echo ============================================
echo.

set GCP_PROJECT=cryptotrader-bot-20260115
set GCP_ZONE=europe-west4-a
set GCP_VM=cryptotrader-vm
set BOT_API_PORT=8082
set DASHBOARD_PORT=8081

REM Step 1: Pruefen ob gcloud verfuegbar
echo [1/4] Pruefe gcloud CLI...
gcloud --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   FEHLER: gcloud CLI nicht gefunden. Bitte installieren:
    echo   https://cloud.google.com/sdk/docs/install
    pause
    exit /b 1
)
echo   OK.

REM Step 2: SSH-Tunnel starten (im Hintergrund)
echo [2/4] Starte SSH-Tunnel (localhost:%BOT_API_PORT% -^> VM:%BOT_API_PORT%)...
start "SSH-Tunnel" /MIN cmd /c "gcloud compute ssh %GCP_VM% --zone=%GCP_ZONE% --project=%GCP_PROJECT% -- -L %BOT_API_PORT%:localhost:%BOT_API_PORT% -N"
timeout /t 5 /nobreak >NUL

REM Step 3: Pruefen ob Tunnel steht
echo [3/4] Pruefe Verbindung zur Bot-API...
curl -s http://localhost:%BOT_API_PORT%/health >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   WARNUNG: Bot-API auf Port %BOT_API_PORT% nicht erreichbar.
    echo   Moegliche Ursachen:
    echo     - SSH-Tunnel noch nicht bereit (warte 10s und versuche nochmal)
    echo     - Bot laeuft nicht auf der VM
    echo     - Falscher Port
    timeout /t 10 /nobreak >NUL
    curl -s http://localhost:%BOT_API_PORT%/health >NUL 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo   Bot-API immer noch nicht erreichbar. Dashboard startet trotzdem...
    ) else (
        echo   Bot-API jetzt erreichbar!
    )
) else (
    echo   Bot-API erreichbar auf localhost:%BOT_API_PORT%
)

REM Step 4: Dashboard starten
echo [4/4] Starte Dashboard auf Port %DASHBOARD_PORT%...
echo.
echo   Dashboard: http://localhost:%DASHBOARD_PORT%
echo   Bot-API:   http://localhost:%BOT_API_PORT% (via SSH-Tunnel)
echo.
echo   Zum Beenden: Ctrl+C (schliesst Dashboard und SSH-Tunnel)
echo ============================================
echo.

set DASHBOARD_API_BASE_URL=http://localhost:%BOT_API_PORT%
if not exist logs mkdir logs
python -m dashboard.main

REM Aufraemen: SSH-Tunnel schliessen
echo.
echo Dashboard gestoppt. Schliesse SSH-Tunnel...
taskkill /FI "WINDOWTITLE eq SSH-Tunnel" /F >NUL 2>&1
echo Fertig.
