#!/bin/bash
# Dashboard startup script for Linux/Mac

set -e  # Exit on error

DASHBOARD_PORT=8081
BOT_API_PORT=8080
LOG_FILE="logs/dashboard_output.log"

echo "=== Dashboard Startup Script ==="
echo "Time: $(date)"
echo ""

# Step 1: Check if bot API is running
echo "[1/3] Checking if bot API is available..."
if curl -s http://localhost:$BOT_API_PORT/health > /dev/null 2>&1; then
    echo "  ✓ Bot API detected on port $BOT_API_PORT"
else
    echo "  ⚠ WARNING: Bot API not detected on port $BOT_API_PORT"
    echo "  Dashboard will have limited functionality without bot API"
    echo ""
fi

# Step 2: Ensure logs directory exists
echo "[2/3] Ensuring logs directory exists..."
mkdir -p logs
echo "  Done."

# Step 3: Start dashboard
echo "[3/3] Starting dashboard on port $DASHBOARD_PORT..."
echo "  Logging to: $LOG_FILE"
echo ""

# Run dashboard and append logs
python -m dashboard.main >> "$LOG_FILE" 2>&1

echo ""
echo "Dashboard stopped."
