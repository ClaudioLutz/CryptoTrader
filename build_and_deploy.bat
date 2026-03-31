@echo off
REM ============================================================================
REM Build und Deploy des CryptoTrader Bot auf GCP
REM
REM 1. Kopiert coin_prediction Source-Code in den Build-Context
REM 2. Baut Docker-Image via Cloud Build
REM 3. Deployed auf die GCP VM
REM ============================================================================

echo ============================================
echo   CryptoTrader Build + Deploy
echo   %date% %time%
echo ============================================
echo.

set GCP_PROJECT=cryptotrader-bot-20260115
set GCP_ACCOUNT=billwilson.rip2012@gmail.com
set GCP_ZONE=europe-west4-a
set GCP_VM=cryptotrader-vm
set IMAGE=europe-west6-docker.pkg.dev/%GCP_PROJECT%/docker-repo-eu/cryptotrader:latest
set COIN_PREDICTION_SRC=C:\Codes\coin_prediction

REM Step 1: coin_prediction Source-Code kopieren
echo [1/4] Kopiere coin_prediction Source-Code...
if exist coin_prediction_src rmdir /s /q coin_prediction_src
mkdir coin_prediction_src
xcopy "%COIN_PREDICTION_SRC%\src" "coin_prediction_src\src\" /E /Q >NUL
copy "%COIN_PREDICTION_SRC%\pyproject.toml" "coin_prediction_src\" >NUL
if exist "%COIN_PREDICTION_SRC%\.env.example" copy "%COIN_PREDICTION_SRC%\.env.example" "coin_prediction_src\" >NUL
echo   Done.

REM Step 2: Docker-Image bauen
echo [2/4] Baue Docker-Image (Cloud Build)...
gcloud builds submit --tag %IMAGE% --project=%GCP_PROJECT% --account=%GCP_ACCOUNT%
if %ERRORLEVEL% NEQ 0 (
    echo   FEHLER: Build fehlgeschlagen!
    goto cleanup
)
echo   Image gebaut und gepusht.

REM Step 3: Deploy auf VM
echo [3/4] Deploye auf VM...
gcloud compute ssh %GCP_VM% --zone=%GCP_ZONE% --project=%GCP_PROJECT% --account=%GCP_ACCOUNT% --command="docker-credential-gcr configure-docker --registries=europe-west6-docker.pkg.dev && docker pull %IMAGE% && docker stop cryptotrader 2>/dev/null; docker rm cryptotrader 2>/dev/null; docker run -d --name cryptotrader --restart unless-stopped -p 8082:8082 --env-file /home/cryptotrader/config/.env -v /home/cryptotrader/logs:/app/logs -v /home/cryptotrader/data:/app/coin_prediction/data %IMAGE% prediction"
if %ERRORLEVEL% NEQ 0 (
    echo   FEHLER: Deployment fehlgeschlagen!
    goto cleanup
)

REM Step 4: Pruefen
echo [4/4] Pruefe Status...
timeout /t 15 /nobreak >NUL
gcloud compute ssh %GCP_VM% --zone=%GCP_ZONE% --project=%GCP_PROJECT% --account=%GCP_ACCOUNT% --command="docker ps && echo '---' && docker logs cryptotrader --tail 10"

:cleanup
echo.
echo Raeume auf...
if exist coin_prediction_src rmdir /s /q coin_prediction_src
echo.
echo Fertig.
