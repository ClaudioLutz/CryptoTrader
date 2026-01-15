# CryptoTrader 3.0 - Google Cloud Platform Deployment Guide

This guide covers deploying CryptoTrader to Google Cloud Platform (GCP).

## Deployment Options

| Option | Best For | Cost | Complexity |
|--------|----------|------|------------|
| **Cloud Run** | Serverless, auto-scaling | ~$10-30/month | Low |
| **Compute Engine** | 24/7 operation, full control | ~$6-15/month | Medium |

## Prerequisites

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed (for local builds)
4. **Binance API credentials** (testnet recommended initially)

## Quick Start

### 1. Set Environment Variables

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
```

### 2. Run Setup

```bash
# Make script executable
chmod +x deploy/gcp/deploy.sh

# Setup GCP project and APIs
./deploy/gcp/deploy.sh setup

# Add your secrets (Binance API keys)
./deploy/gcp/deploy.sh secrets
```

### 3. Build and Deploy

```bash
# Full deployment (setup + build + deploy)
./deploy/gcp/deploy.sh all

# Or deploy to Compute Engine VM
./deploy/gcp/deploy.sh deploy-vm
```

## Deployment Commands

| Command | Description |
|---------|-------------|
| `setup` | Enable GCP APIs, create Artifact Registry |
| `secrets` | Create/update secrets in Secret Manager |
| `build` | Build image via Cloud Build |
| `build-local` | Build locally with Docker |
| `deploy` | Deploy to Cloud Run |
| `deploy-vm` | Deploy to Compute Engine VM |
| `logs` | View recent logs |
| `all` | Run setup + build + deploy |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Google Cloud Platform                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Cloud Build  │───▶│  Artifact    │───▶│  Cloud Run   │  │
│  │   (CI/CD)    │    │  Registry    │    │  or GCE VM   │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘  │
│                                                  │          │
│  ┌──────────────┐    ┌──────────────┐           │          │
│  │   Secret     │◀───│              │◀──────────┘          │
│  │   Manager    │    │  Container   │                      │
│  │  (API Keys)  │    │ ┌──────────┐ │                      │
│  └──────────────┘    │ │   Bot    │ │                      │
│                      │ │ (8080)   │ │                      │
│  ┌──────────────┐    │ ├──────────┤ │                      │
│  │    Cloud     │◀───│ │Dashboard │ │                      │
│  │   Logging    │    │ │ (8081)   │ │                      │
│  └──────────────┘    │ └──────────┘ │                      │
│                      └──────────────┘                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Binance API     │
                    │  (Testnet/Main)  │
                    └──────────────────┘
```

## Configuration

### Environment Variables

These are set during deployment:

| Variable | Default | Description |
|----------|---------|-------------|
| `EXCHANGE__TESTNET` | `true` | Use Binance testnet |
| `TRADING__DRY_RUN` | `true` | Simulation mode |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `MIN_INSTANCES` | `1` | Minimum Cloud Run instances |

### Secrets (via Secret Manager)

| Secret Name | Description |
|-------------|-------------|
| `binance-api-key` | Binance API key |
| `binance-api-secret` | Binance API secret |
| `dashboard-password` | Optional dashboard auth |

## Enabling Live Trading

> **WARNING**: Only enable live trading after thorough testing on testnet!

1. Update environment variables in Cloud Run:
   ```bash
   gcloud run services update cryptotrader \
     --region=us-central1 \
     --set-env-vars="EXCHANGE__TESTNET=false,TRADING__DRY_RUN=false"
   ```

2. Ensure your Binance API key:
   - Has trading permissions enabled
   - Has IP whitelisting configured for your Cloud Run egress IP
   - Does NOT have withdrawal permissions

## Monitoring

### View Logs

```bash
# Recent logs
./deploy/gcp/deploy.sh logs

# Stream logs
gcloud logging tail "resource.type=cloud_run_revision"
```

### Health Check

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe cryptotrader \
  --region=us-central1 --format="value(status.url)")

# Check health
curl ${SERVICE_URL}/health
```

## Cost Optimization

### Cloud Run

- Set `MIN_INSTANCES=0` if you can tolerate cold starts
- Use committed use discounts for predictable workloads

### Compute Engine

- Use `e2-micro` (free tier eligible) for testing
- Use preemptible VMs for non-critical testing (~80% cheaper)
- Consider sustained use discounts for 24/7 operation

## Troubleshooting

### Container won't start

```bash
# Check logs
gcloud logging read "resource.type=cloud_run_revision" --limit=20

# Verify secrets exist
gcloud secrets list
```

### API connection errors

- Verify Binance API credentials are correct
- Check if testnet vs mainnet matches your API keys
- Ensure Cloud Run has outbound internet access

### Dashboard not accessible

- Cloud Run only exposes port 8080 by default
- For dashboard access, use the combined container or set up Cloud Load Balancer

## Security Best Practices

1. **Never** commit API keys to git
2. **Always** use Secret Manager for credentials
3. **Enable** IP whitelisting on Binance
4. **Start** with testnet + dry-run mode
5. **Monitor** logs for suspicious activity
6. **Rotate** API keys every 3-6 months

## Local Testing with Docker

Before deploying to GCP, test locally:

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Run with docker-compose
docker compose up -d bot dashboard

# Or run combined container
docker compose --profile combined up cryptotrader

# View logs
docker compose logs -f

# Stop
docker compose down
```
