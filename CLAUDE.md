# CLAUDE.md

## CRITICAL: Production Bot

This bot runs with **REAL MONEY on Binance Mainnet** (not testnet).
- **Dashboard**: https://cryptotrader-dashboard.com
- **GCP Project**: `cryptotrader-bot-20260115`
- **GCP VM**: `cryptotrader-vm` in `europe-west4-a`
- **Artifact Registry**: `europe-west6-docker.pkg.dev`
- **Trading pairs**: SOL/USDT (grid strategy)
- **VM OS**: Container-Optimized OS (COS)

## Deployment

### Full Deploy (Build + Push + Restart)
```bash
# Step 1: Build and push Docker image to Artifact Registry
gcloud builds submit --tag europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest

# Step 2: SSH to VM, authenticate Docker, pull new image, restart container
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker-credential-gcr configure-docker --registries=europe-west6-docker.pkg.dev && docker pull europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest && docker stop cryptotrader 2>/dev/null; docker rm cryptotrader 2>/dev/null; docker run -d --name cryptotrader --restart unless-stopped -p 8080:8080 -p 8081:8081 --env-file /home/cryptotrader/config/.env -v /home/cryptotrader/logs:/app/logs europe-west6-docker.pkg.dev/cryptotrader-bot-20260115/docker-repo-eu/cryptotrader:latest"
```

### Quick Restart (No Code Changes)
```bash
# Just restart the existing container
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker restart cryptotrader"
```

### Check Status
```bash
# View container status and recent logs
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker ps && docker logs cryptotrader --tail 30"

# Follow logs in real-time
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker logs cryptotrader -f --tail 50"
```

### Local Testing
```bash
# Run dashboard locally (connects to local bot API on port 8080)
python -m dashboard.main
# Dashboard available at http://localhost:8081
```

## Troubleshooting

### Docker Pull Authentication Error
If you see `unauthorized: authentication failed`, run:
```bash
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker-credential-gcr configure-docker --registries=europe-west6-docker.pkg.dev"
```

### Port Already Allocated
```bash
# Stop and remove any existing container first
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker stop cryptotrader; docker rm cryptotrader"
```

### Check What's Running
```bash
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="docker ps -a"
```

### View All Logs
```bash
gcloud compute ssh cryptotrader-vm --zone=europe-west4-a --project=cryptotrader-bot-20260115 --command="ls -la /home/cryptotrader/logs/"
```

## Key Configuration

| Item | Location |
|------|----------|
| API Keys (VM) | `/home/cryptotrader/config/.env` |
| API Keys (Local) | `.env` in project root |
| Grid Config | `config/config.yaml` |
| Logs (VM) | `/home/cryptotrader/logs/` |
| P&L Method | FIFO (First-In-First-Out) |

## Always Search the web for relevant information (it mostly is useful)

## Change Documentation (required)

For every change that modifies behavior, adds/removes features, changes dependencies, alters configuration, or impacts performance/security:
- Create **one** new Markdown file under `docs/stories/` in the **same PR/commit** as the code change.

### Filename format
- `docs/stories/YYYYMMddHHmmss-topic-of-the-code-change.md`
- `YYYYMMddHHmmss` is a **14-digit timestamp** (recommend **UTC** to avoid timezone ambiguity).
- `topic-of-the-code-change` is a short **kebab-case** slug (ASCII, no spaces, no underscores).

**Examples**
- `docs/stories/20251228143005-fix-dedup-merge-logic.md`
- `docs/stories/20251228160219-add-address-normalization-step.md`

### Minimum required contents
Each story file must include these sections:

#### Summary
1–3 sentences describing the change.

#### Context / Problem
Why this change is needed (bug, requirement, refactor driver).

#### What Changed
Bulleted list of key implementation changes (include modules/components touched).

#### How to Test
Exact commands and/or manual steps to validate.

#### Risk / Rollback Notes
What could go wrong, and how to revert/mitigate.

### When a story is NOT required
- Pure formatting (whitespace), typo fixes in comments/docs, or non-functional refactors that do not change behavior.
  - If in doubt, create a story.
