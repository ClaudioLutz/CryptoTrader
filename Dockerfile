# =============================================================================
# CryptoTrader 3.0 - Production Dockerfile
# Optimized for Google Cloud Run / Compute Engine deployment
#
# Build: Das build_and_deploy.bat Skript kopiert coin_prediction Source-Code
# nach coin_prediction_src/ bevor Cloud Build gestartet wird.
# =============================================================================

FROM python:3.11-slim AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for better caching)
COPY pyproject.toml .
COPY src/ src/
COPY dashboard/ dashboard/

# Install CryptoTrader dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e ".[dashboard]"

# Copy coin_prediction source and install its dependencies
COPY coin_prediction_src/ /app/coin_prediction/
RUN cd /app/coin_prediction && pip install -e .

# =============================================================================
# Production image
# =============================================================================
FROM python:3.11-slim AS production

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Application defaults
    LOG_LEVEL=INFO \
    LOG_JSON=true \
    HEALTH__HOST=0.0.0.0 \
    HEALTH__PORT=8080 \
    DASHBOARD_PORT=8081 \
    COIN_PREDICTION_PATH=/app/coin_prediction \
    # coin_prediction Pipeline-Settings (BTC 1h-Strategie)
    PIPELINE__COINS=BTC \
    PIPELINE__TIMEFRAME=1h \
    PIPELINE__START_DATE=2020-01-01 \
    PIPELINE__HORIZONS=1,3,7 \
    PIPELINE__RANDOM_SEED=42 \
    # Safety defaults - ALWAYS start in safe mode
    EXCHANGE__TESTNET=true \
    TRADING__DRY_RUN=true

WORKDIR /app

# Install runtime dependencies only
# libgomp1 = OpenMP (fuer LightGBM/XGBoost), libpq5 = PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy coin_prediction source code (Daten werden zur Laufzeit heruntergeladen)
COPY --from=builder --chown=appuser:appuser /app/coin_prediction/ /app/coin_prediction/

# Copy application code
COPY --chown=appuser:appuser src/ src/
COPY --chown=appuser:appuser dashboard/ dashboard/
COPY --chown=appuser:appuser scripts/ scripts/
COPY --chown=appuser:appuser pyproject.toml .

# Copy and fix entrypoint script (convert Windows CRLF to Unix LF)
COPY docker-entrypoint.sh /app/
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

# Create necessary directories (inkl. coin_prediction data)
RUN mkdir -p /app/logs /app/data /app/coin_prediction/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose bot API port (Dashboard laeuft lokal, nicht im Container)
EXPOSE 8080

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${HEALTH__PORT:-8080}/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["bot"]
