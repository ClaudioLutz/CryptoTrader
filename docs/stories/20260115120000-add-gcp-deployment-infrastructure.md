# Add Google Cloud Platform Deployment Infrastructure

## Summary

Added comprehensive Docker and Google Cloud Platform (GCP) deployment infrastructure to enable running CryptoTrader in the cloud with Cloud Run or Compute Engine.

## Context / Problem

The trading bot was only runnable locally via batch scripts. For production use, cloud deployment is needed to:
- Run 24/7 without local machine dependency
- Benefit from cloud reliability and monitoring
- Enable secure credential management via Secret Manager
- Support auto-scaling and CI/CD workflows

## What Changed

### New Files Created

- **`Dockerfile`** - Multi-stage production Docker image
  - Python 3.11-slim base for minimal footprint
  - Non-root user for security
  - Health check endpoint built-in
  - Supports running bot, dashboard, or both

- **`docker-entrypoint.sh`** - Container entrypoint script
  - Handles startup modes: `bot`, `dashboard`, `all`
  - Graceful shutdown signal handling
  - Safety warnings for live trading mode

- **`docker-compose.yml`** - Local development/testing
  - Separate `bot` and `dashboard` services
  - Combined `cryptotrader` service option
  - Persistent volumes for data and logs
  - Health checks and dependency ordering

- **`deploy/gcp/deploy.sh`** - GCP deployment automation
  - Project setup and API enabling
  - Secret Manager integration
  - Cloud Build image builds
  - Cloud Run deployment
  - Compute Engine VM deployment option

- **`deploy/gcp/cloudbuild.yaml`** - CI/CD pipeline
  - Automated Docker builds on push
  - Artifact Registry storage
  - Auto-deploy to Cloud Run

- **`deploy/gcp/README.md`** - Deployment documentation
  - Architecture diagram
  - Step-by-step instructions
  - Cost optimization tips
  - Security best practices

- **`README.md`** - Updated main documentation
  - Added Docker deployment section
  - Added Cloud Deployment (GCP) section
  - Region selection guidance (Binance geo-restrictions)

## How to Test

### Local Docker Testing

```bash
# Build and run locally
docker compose up -d bot dashboard

# Verify health
curl http://localhost:8080/health

# Check dashboard
open http://localhost:8081

# View logs
docker compose logs -f

# Cleanup
docker compose down
```

### GCP Deployment

```bash
# Set project
export GCP_PROJECT_ID="your-project-id"

# Full deployment
./deploy/gcp/deploy.sh all

# Or step by step
./deploy/gcp/deploy.sh setup
./deploy/gcp/deploy.sh secrets
./deploy/gcp/deploy.sh build
./deploy/gcp/deploy.sh deploy
```

## Risk / Rollback Notes

### Risks

- **Live trading exposure**: Default configuration uses testnet + dry-run mode. Changing to mainnet with real funds requires explicit environment variable changes.
- **Cloud costs**: Cloud Run with min-instances=1 incurs ~$10-30/month. Set to 0 to reduce costs (with cold start tradeoff).
- **Secret exposure**: API keys stored in Secret Manager. Ensure proper IAM permissions.

### Rollback

1. **Cloud Run**: Previous revisions are retained; use Cloud Console to roll back
2. **Delete deployment**: `gcloud run services delete cryptotrader --region=us-central1`
3. **Local**: Simply stop containers with `docker compose down`

### Safety Defaults

All deployments default to:
- `EXCHANGE__TESTNET=true`
- `TRADING__DRY_RUN=true`

This prevents accidental live trading. Must be explicitly changed to trade with real funds.
