# =============================================================================
# CryptoTrader 3.0 - Production Dockerfile
# Optimized for Google Cloud Run / Compute Engine deployment
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

# Install dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e ".[dashboard]"

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
    # Safety defaults - ALWAYS start in safe mode
    EXCHANGE__TESTNET=true \
    TRADING__DRY_RUN=true

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser src/ src/
COPY --chown=appuser:appuser dashboard/ dashboard/
COPY --chown=appuser:appuser pyproject.toml .

# Copy and fix entrypoint script (convert Windows CRLF to Unix LF)
COPY docker-entrypoint.sh /app/
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
# 8080 - Bot health check API
# 8081 - Dashboard web UI
EXPOSE 8080 8081

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["all"]
