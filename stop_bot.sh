#!/bin/bash
# Bot shutdown script for Linux/Mac

echo "=== Trading Bot Shutdown Script ==="
echo "Time: $(date)"
echo ""

# Step 1: Find and stop bot processes
echo "[1/2] Stopping bot processes..."

if pgrep -f "crypto_bot.main" > /dev/null; then
    echo "  Found crypto_bot processes, stopping..."
    pkill -TERM -f "crypto_bot.main"

    # Wait for graceful shutdown
    sleep 2

    # Force kill if still running
    if pgrep -f "crypto_bot.main" > /dev/null; then
        echo "  Force stopping remaining processes..."
        pkill -9 -f "crypto_bot.main"
    fi

    echo "  Bot stopped."
else
    echo "  No crypto_bot processes found."
fi

# Step 2: Confirm shutdown
echo "[2/2] Verifying shutdown..."
if pgrep -f "crypto_bot.main" > /dev/null; then
    echo "  WARNING: Some bot processes still running"
else
    echo "  All bot processes stopped."
fi

echo ""
echo "=== Bot Shutdown Complete ==="
echo ""
echo "Note: All open orders remain on the exchange."
echo "To cancel orders, log into Binance and cancel manually,"
echo "or use the dashboard Configuration tab."
