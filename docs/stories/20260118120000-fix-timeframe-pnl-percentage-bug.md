# Fix Timeframe P&L Percentage Bug (257% Bug)

## Summary

Fixed incorrect timeframe P&L percentage calculation that showed wildly wrong values (e.g., +257.1% for 7D). The bug was caused by using only recent buys as the percentage denominator while FIFO P&L used cost basis from older buys.

## Context / Problem

The 7D P&L showed "+257.1% €18" which is mathematically impossible for a €18 profit on any reasonable investment. The bug was in `_calculate_timeframe_pnl()`:

**Old logic:**
1. Filter trades to only those within timeframe (e.g., last 7 days)
2. Calculate FIFO P&L using only those filtered trades
3. Calculate percentage as: `P&L / sum_of_buys_within_timeframe * 100`

**Why it broke:**
- A sell within 7 days might match (via FIFO) against a buy from 30+ days ago
- The profit is calculated correctly using the old buy price
- But the percentage divides by only recent buys, which could be tiny or zero

Example:
- 30 days ago: Buy 1 SOL at $200
- 7 days ago: Buy 0.1 SOL at $200 ($20 cost)
- 7 days ago: Sell 1 SOL at $218 ($18 profit, matched against old buy)
- Old percentage: $18 / $20 = 90% (wrong!)
- Actual: $18 / $1000 total investment = 1.8%

## What Changed

### File: `dashboard/state.py`

**`_calculate_timeframe_pnl()` completely rewritten:**

1. Uses FULL trade history for FIFO (buy queue builds from all-time buys)
2. Processes all trades chronologically, building proper cost basis
3. Only counts realized P&L from sells that occurred within the timeframe
4. Uses total portfolio investment as percentage denominator (not recent buys)

```python
# Get total investment from strategy config
total_investment = sum(p.total_investment for p in self.pairs)

# For each sell within timeframe:
#   - Match against oldest buys (FIFO, using full history)
#   - Add realized P&L to timeframe total

# Percentage = tf_pnl / total_investment * 100
```

## How to Test

1. Deploy to GCP:
   ```bash
   gcloud builds submit --tag europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest

   gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker-credential-gcr configure-docker --registries=europe-west6-docker.pkg.dev && docker pull europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest && docker stop cryptotrader; docker rm cryptotrader; docker run -d --name cryptotrader --restart unless-stopped -p 8080:8080 -p 8081:8081 --env-file /home/cryptotrader/config/.env -v /home/cryptotrader/logs:/app/logs europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest"
   ```

2. Check dashboard at https://cryptotrader-dashboard.com
3. Verify timeframe percentages are reasonable (single-digit % for typical trading)
4. Verify the €18 7D profit shows ~1-2% (based on ~$1000 investment), not 257%

## Risk / Rollback Notes

### Risks
- Users will see different (lower) percentage values - this is correct behavior
- If `total_investment` is 0 or not set in config, falls back to €1000

### Rollback
Revert `dashboard/state.py` to previous version and redeploy.
