#!/bin/bash
# Proper bot startup script that fixes common issues

set -e  # Exit on error

BOT_PORT=8081  # Dashboard uses 8080
LOG_FILE="logs/bot_output.log"
PID_FILE="logs/bot.pid"

echo "=== Trading Bot Startup Script ==="
echo "Time: $(date)"
echo ""

# Step 1: Kill any existing bot processes
echo "[1/5] Checking for existing bot processes..."
if pgrep -f "crypto_bot.main" > /dev/null; then
    echo "  Found running bot process(es), stopping..."
    pkill -9 -f "crypto_bot.main" || true
    sleep 2
    echo "  Stopped."
else
    echo "  No existing processes found."
fi

# Step 2: Ensure logs directory exists
echo "[2/5] Ensuring logs directory exists..."
mkdir -p logs
echo "  Done."

# Step 3: Archive old log if it's too large (> 10MB)
echo "[3/5] Checking log file size..."
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt 10485760 ]; then
        echo "  Log file is large ($(($LOG_SIZE / 1024 / 1024))MB), archiving..."
        mv "$LOG_FILE" "${LOG_FILE}.$(date +%Y%m%d_%H%M%S)"
        echo "  Archived."
    else
        echo "  Log file size OK ($(($LOG_SIZE / 1024))KB)."
    fi
fi

# Step 4: Start the bot (APPEND to logs with >>)
echo "[4/5] Starting bot on port $BOT_PORT..."
nohup python -m crypto_bot.main --api-port $BOT_PORT >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Save PID for later
echo $BOT_PID > "$PID_FILE"
echo "  Bot started with PID: $BOT_PID"

# Step 5: Wait and verify it's running
echo "[5/5] Verifying bot started successfully..."
sleep 5

if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "  ✓ Bot is running (PID: $BOT_PID)"
    echo ""
    echo "=== Bot Started Successfully ==="
    echo "  Port: $BOT_PORT"
    echo "  Logs: $LOG_FILE"
    echo "  PID: $BOT_PID"
    echo ""
    echo "Monitor logs: tail -f $LOG_FILE"
    echo "Stop bot: kill $BOT_PID"
else
    echo "  ✗ Bot failed to start! Check logs:"
    tail -50 "$LOG_FILE"
    exit 1
fi
