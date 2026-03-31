# Bot-only Deployment mit lokalem Dashboard

## Summary
Bot laeuft nur noch als einziger Service auf der GCP VM. Das Dashboard wird lokal gestartet
und verbindet sich per SSH-Tunnel zur Bot-API. Spart RAM auf der VM und ermoeglicht
schnelleres UI ohne Netzwerk-Roundtrip.

## Context / Problem
Bisher liefen Bot und Dashboard zusammen im selben Docker-Container auf der VM.
Das Dashboard verbraucht unnoetig RAM auf der VM (~50-100 MB), obwohl es nur 1-2 Nutzer
hat und nicht 24/7 laufen muss. Ausserdem ist die UI-Responsiveness ueber das Internet
schlechter als lokal.

## What Changed

- **Dockerfile**: Default CMD von `all` auf `bot` geaendert, nur noch Port 8080 exponiert,
  Healthcheck nutzt `HEALTH__PORT` Env-Variable
- **CLAUDE.md**: Deployment-Dokumentation komplett ueberarbeitet:
  - Architektur-Diagramm (VM: Bot, Lokal: Dashboard)
  - Docker-Run mit `bot` CMD und nur Port 8082
  - SSH-Tunnel-Anleitung (manuell + Batch-Skript)
  - Lokale Entwicklungs-Anleitung
- **start_dashboard_remote.bat**: Neues Startup-Skript fuer Windows:
  - Oeffnet SSH-Tunnel zur VM automatisch (gcloud compute ssh mit -L Port-Forwarding)
  - Prueft Verbindung zur Bot-API
  - Startet Dashboard lokal mit `DASHBOARD_API_BASE_URL=http://localhost:8082`
  - Raeummt SSH-Tunnel beim Beenden auf

## How to Test
```bash
# 1. Bot auf VM deployen (nur Bot, kein Dashboard)
gcloud builds submit --tag europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker stop cryptotrader; docker rm cryptotrader; docker run -d --name cryptotrader --restart unless-stopped -p 8082:8082 --env-file /home/cryptotrader/config/.env -v /home/cryptotrader/logs:/app/logs europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest bot"

# 2. Dashboard lokal starten
start_dashboard_remote.bat
# -> Oeffnet SSH-Tunnel + Dashboard auf http://localhost:8081

# 3. Pruefen: Dashboard zeigt Bot-Status, Predictions, Trades
```

## Risk / Rollback Notes
- **Rollback**: Docker-Container mit `all` statt `bot` starten, Port 8081 wieder mappen
- **Risiko**: SSH-Tunnel muss manuell gestartet werden (kein auto-reconnect bei Verbindungsabbruch)
- **Firewall**: Kein Port muss in der GCP-Firewall geoeffnet werden (SSH-Tunnel laeuft ueber Port 22)
- Dashboard-Code unveraendert — funktioniert weiterhin mit lokalem Bot oder per SSH-Tunnel
