#!/bin/bash
# =============================================================================
# CryptoTrader Docker Entrypoint
# Handles starting bot, dashboard, or both services
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Ensure logs directory exists
mkdir -p /app/logs

# Function to start the trading bot
start_bot() {
    log_info "Starting CryptoTrader Bot..."
    exec python -m crypto_bot.main --api-port ${HEALTH__PORT:-8080}
}

# Function to start the dashboard
start_dashboard() {
    log_info "Starting Dashboard..."
    exec python -m dashboard.main
}

# Function to start both services
start_all() {
    log_info "Starting CryptoTrader Bot and Dashboard..."

    # Start bot in background
    python -m crypto_bot.main --api-port ${HEALTH__PORT:-8080} &
    BOT_PID=$!
    log_info "Bot started with PID: $BOT_PID"

    # Wait for bot API to be ready
    log_info "Waiting for bot API to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:${HEALTH__PORT:-8080}/health > /dev/null 2>&1; then
            log_info "Bot API is ready!"
            break
        fi
        sleep 1
    done

    # Start dashboard in foreground (main process)
    python -m dashboard.main &
    DASHBOARD_PID=$!
    log_info "Dashboard started with PID: $DASHBOARD_PID"

    # Handle shutdown signals
    trap 'log_info "Shutting down..."; kill $BOT_PID $DASHBOARD_PID 2>/dev/null; exit 0' SIGTERM SIGINT

    # Wait for either process to exit
    wait -n $BOT_PID $DASHBOARD_PID
    EXIT_CODE=$?

    log_error "A process exited with code: $EXIT_CODE"
    kill $BOT_PID $DASHBOARD_PID 2>/dev/null || true
    exit $EXIT_CODE
}

# Display startup banner
echo "=============================================="
echo "  CryptoTrader 3.0 - Docker Container"
echo "=============================================="
echo "  Mode: $1"
echo "  Testnet: ${EXCHANGE__TESTNET:-true}"
echo "  Dry Run: ${TRADING__DRY_RUN:-true}"
echo "  Bot Port: ${HEALTH__PORT:-8080}"
echo "  Dashboard Port: ${DASHBOARD_PORT:-8081}"
echo "=============================================="

# Safety check
if [ "${EXCHANGE__TESTNET}" = "false" ] && [ "${TRADING__DRY_RUN}" = "false" ]; then
    log_warn "!!! RUNNING IN LIVE TRADING MODE !!!"
    log_warn "Real money is at risk. Proceed with caution."
    sleep 3
fi

# Route to appropriate startup function
case "$1" in
    bot)
        start_bot
        ;;
    dashboard)
        start_dashboard
        ;;
    all|"")
        start_all
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Usage: docker-entrypoint.sh [bot|dashboard|all]"
        exit 1
        ;;
esac
