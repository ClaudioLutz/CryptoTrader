#!/bin/bash
# =============================================================================
# CryptoTrader 3.0 - Google Cloud Platform Deployment Script
# =============================================================================
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. Docker installed (for local builds)
#   3. GCP project created with billing enabled
#
# Usage:
#   ./deploy.sh [setup|build|deploy|secrets|all]
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration - EDIT THESE VALUES
# -----------------------------------------------------------------------------
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="cryptotrader"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Cloud Run configuration
MIN_INSTANCES=1          # Keep at least 1 instance warm (avoid cold starts)
MAX_INSTANCES=2          # Scale limit
MEMORY="512Mi"           # Memory allocation
CPU="1"                  # CPU allocation
TIMEOUT="3600"           # Request timeout in seconds (1 hour max for Cloud Run)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# -----------------------------------------------------------------------------
# Setup GCP Project and Enable APIs
# -----------------------------------------------------------------------------
setup_gcp() {
    log_step "Setting up GCP project: ${PROJECT_ID}"

    # Set project
    gcloud config set project ${PROJECT_ID}

    # Enable required APIs
    log_info "Enabling required APIs..."
    gcloud services enable \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        secretmanager.googleapis.com \
        artifactregistry.googleapis.com \
        logging.googleapis.com \
        monitoring.googleapis.com

    # Create Artifact Registry repository (if not exists)
    log_info "Creating Artifact Registry repository..."
    gcloud artifacts repositories create docker-repo \
        --repository-format=docker \
        --location=${REGION} \
        --description="Docker images for CryptoTrader" \
        2>/dev/null || log_info "Repository already exists"

    # Configure Docker auth for Artifact Registry
    gcloud auth configure-docker ${REGION}-docker.pkg.dev

    log_info "GCP setup complete!"
}

# -----------------------------------------------------------------------------
# Create Secrets in Secret Manager
# -----------------------------------------------------------------------------
setup_secrets() {
    log_step "Setting up secrets in Secret Manager..."

    echo "You will be prompted to enter secret values."
    echo "Press Ctrl+C to cancel at any time."
    echo ""

    # Binance API Key
    read -p "Enter Binance API Key: " BINANCE_API_KEY
    echo -n "${BINANCE_API_KEY}" | gcloud secrets create binance-api-key \
        --data-file=- \
        --replication-policy="automatic" \
        2>/dev/null || \
    echo -n "${BINANCE_API_KEY}" | gcloud secrets versions add binance-api-key --data-file=-

    # Binance API Secret
    read -sp "Enter Binance API Secret: " BINANCE_API_SECRET
    echo ""
    echo -n "${BINANCE_API_SECRET}" | gcloud secrets create binance-api-secret \
        --data-file=- \
        --replication-policy="automatic" \
        2>/dev/null || \
    echo -n "${BINANCE_API_SECRET}" | gcloud secrets versions add binance-api-secret --data-file=-

    # Dashboard password (optional)
    read -sp "Enter Dashboard Password (optional, press Enter to skip): " DASHBOARD_PASSWORD
    echo ""
    if [ -n "${DASHBOARD_PASSWORD}" ]; then
        echo -n "${DASHBOARD_PASSWORD}" | gcloud secrets create dashboard-password \
            --data-file=- \
            --replication-policy="automatic" \
            2>/dev/null || \
        echo -n "${DASHBOARD_PASSWORD}" | gcloud secrets versions add dashboard-password --data-file=-
    fi

    # Grant Cloud Run access to secrets
    log_info "Granting Cloud Run access to secrets..."
    PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

    for SECRET in binance-api-key binance-api-secret dashboard-password; do
        gcloud secrets add-iam-policy-binding ${SECRET} \
            --member="serviceAccount:${SERVICE_ACCOUNT}" \
            --role="roles/secretmanager.secretAccessor" \
            2>/dev/null || true
    done

    log_info "Secrets setup complete!"
}

# -----------------------------------------------------------------------------
# Build and Push Docker Image
# -----------------------------------------------------------------------------
build_image() {
    log_step "Building Docker image..."

    # Navigate to project root
    cd "$(dirname "$0")/../.."

    # Build using Cloud Build (recommended for CI/CD)
    log_info "Submitting build to Cloud Build..."
    gcloud builds submit \
        --config=deploy/gcp/cloudbuild.yaml \
        --substitutions=_REGION=${REGION}

    log_info "Image built and pushed successfully!"
}

# -----------------------------------------------------------------------------
# Build Locally (alternative to Cloud Build)
# -----------------------------------------------------------------------------
build_local() {
    log_step "Building Docker image locally..."

    cd "$(dirname "$0")/../.."

    # Build image
    docker build -t ${IMAGE_NAME}:latest .

    # Push to GCR
    log_info "Pushing to Container Registry..."
    docker push ${IMAGE_NAME}:latest

    log_info "Local build and push complete!"
}

# -----------------------------------------------------------------------------
# Deploy to Cloud Run
# -----------------------------------------------------------------------------
deploy_cloudrun() {
    log_step "Deploying to Cloud Run..."

    # Get secret versions
    API_KEY_SECRET="binance-api-key:latest"
    API_SECRET_SECRET="binance-api-secret:latest"

    gcloud run deploy ${SERVICE_NAME} \
        --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/docker-repo/${SERVICE_NAME}:latest \
        --platform=managed \
        --region=${REGION} \
        --port=8080 \
        --min-instances=${MIN_INSTANCES} \
        --max-instances=${MAX_INSTANCES} \
        --memory=${MEMORY} \
        --cpu=${CPU} \
        --timeout=${TIMEOUT} \
        --allow-unauthenticated \
        --set-env-vars="EXCHANGE__NAME=binance" \
        --set-env-vars="EXCHANGE__TESTNET=true" \
        --set-env-vars="TRADING__DRY_RUN=true" \
        --set-env-vars="DB__URL=sqlite+aiosqlite:///./data/trading.db" \
        --set-env-vars="HEALTH__HOST=0.0.0.0" \
        --set-env-vars="HEALTH__PORT=8080" \
        --set-env-vars="DASHBOARD_PORT=8081" \
        --set-env-vars="DASHBOARD_API_BASE_URL=http://localhost:8080" \
        --set-env-vars="LOG_LEVEL=INFO" \
        --set-env-vars="LOG_JSON=true" \
        --set-secrets="EXCHANGE__API_KEY=${API_KEY_SECRET}" \
        --set-secrets="EXCHANGE__API_SECRET=${API_SECRET_SECRET}"

    # Get service URL
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
        --region=${REGION} \
        --format="value(status.url)")

    log_info "Deployment complete!"
    echo ""
    echo "=============================================="
    echo "  CryptoTrader deployed successfully!"
    echo "=============================================="
    echo "  Service URL: ${SERVICE_URL}"
    echo "  Dashboard:   ${SERVICE_URL}:8081"
    echo "  Health:      ${SERVICE_URL}/health"
    echo "=============================================="
    echo ""
    log_warn "Remember: Currently running in TESTNET + DRY_RUN mode"
    log_warn "To enable live trading, update environment variables"
}

# -----------------------------------------------------------------------------
# Deploy to Compute Engine (alternative for 24/7 operation)
# -----------------------------------------------------------------------------
deploy_compute_engine() {
    log_step "Deploying to Compute Engine..."

    INSTANCE_NAME="${SERVICE_NAME}-vm"
    ZONE="${REGION}-a"
    MACHINE_TYPE="e2-small"

    # Create instance with Container-Optimized OS
    gcloud compute instances create-with-container ${INSTANCE_NAME} \
        --zone=${ZONE} \
        --machine-type=${MACHINE_TYPE} \
        --container-image=${REGION}-docker.pkg.dev/${PROJECT_ID}/docker-repo/${SERVICE_NAME}:latest \
        --container-env="EXCHANGE__NAME=binance" \
        --container-env="EXCHANGE__TESTNET=true" \
        --container-env="TRADING__DRY_RUN=true" \
        --container-env="LOG_LEVEL=INFO" \
        --tags=http-server,https-server \
        --scopes=cloud-platform

    # Create firewall rule for dashboard access
    gcloud compute firewall-rules create allow-cryptotrader \
        --allow=tcp:8080,tcp:8081 \
        --target-tags=http-server \
        2>/dev/null || log_info "Firewall rule already exists"

    # Get external IP
    EXTERNAL_IP=$(gcloud compute instances describe ${INSTANCE_NAME} \
        --zone=${ZONE} \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

    log_info "Compute Engine deployment complete!"
    echo ""
    echo "=============================================="
    echo "  CryptoTrader VM deployed!"
    echo "=============================================="
    echo "  Instance:   ${INSTANCE_NAME}"
    echo "  Zone:       ${ZONE}"
    echo "  External IP: ${EXTERNAL_IP}"
    echo "  Bot API:    http://${EXTERNAL_IP}:8080"
    echo "  Dashboard:  http://${EXTERNAL_IP}:8081"
    echo "=============================================="
}

# -----------------------------------------------------------------------------
# View Logs
# -----------------------------------------------------------------------------
view_logs() {
    log_step "Viewing Cloud Run logs..."

    gcloud logging read \
        "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
        --limit=50 \
        --format="table(timestamp,textPayload)"
}

# -----------------------------------------------------------------------------
# Print Help
# -----------------------------------------------------------------------------
print_help() {
    echo "CryptoTrader GCP Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup      - Enable GCP APIs and create Artifact Registry"
    echo "  secrets    - Create/update secrets in Secret Manager"
    echo "  build      - Build and push Docker image via Cloud Build"
    echo "  build-local- Build locally and push (requires Docker)"
    echo "  deploy     - Deploy to Cloud Run"
    echo "  deploy-vm  - Deploy to Compute Engine VM"
    echo "  logs       - View recent logs"
    echo "  all        - Run setup, build, and deploy"
    echo ""
    echo "Environment Variables:"
    echo "  GCP_PROJECT_ID  - Your GCP project ID (required)"
    echo "  GCP_REGION      - GCP region (default: us-central1)"
    echo ""
    echo "Examples:"
    echo "  GCP_PROJECT_ID=my-project ./deploy.sh all"
    echo "  GCP_PROJECT_ID=my-project ./deploy.sh deploy-vm"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
case "${1:-help}" in
    setup)
        setup_gcp
        ;;
    secrets)
        setup_secrets
        ;;
    build)
        build_image
        ;;
    build-local)
        build_local
        ;;
    deploy)
        deploy_cloudrun
        ;;
    deploy-vm)
        deploy_compute_engine
        ;;
    logs)
        view_logs
        ;;
    all)
        setup_gcp
        build_image
        deploy_cloudrun
        ;;
    help|*)
        print_help
        ;;
esac
