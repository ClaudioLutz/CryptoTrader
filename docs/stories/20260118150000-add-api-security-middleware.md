# Add API Security Middleware

## Summary

Added comprehensive security middleware to the bot API endpoints including authentication, CORS protection, rate limiting, and security headers. This protects sensitive trading data from unauthorized access.

## Context / Problem

The bot API (port 8080) was completely unauthenticated, allowing anyone with network access to view:
- Trade history and positions
- Open orders and P&L data
- Bot status and risk metrics
- Equity curves and strategy configurations

This was a critical security vulnerability for a production trading bot handling real money on Binance Mainnet.

## What Changed

### Bot API Security (`src/crypto_bot/utils/health.py`)
- Added `RateLimiter` class for sliding window rate limiting
- Added `_auth_middleware` - requires `X-API-Key` header for `/api/*` endpoints
- Added `_cors_middleware` - restricts cross-origin requests to configured origins
- Added `_rate_limit_middleware` - limits requests per IP (default 100/minute)
- Added `_security_headers_middleware` - adds X-Frame-Options, CSP, etc.
- Health/ready/metrics endpoints remain unauthenticated for k8s probes

### Configuration (`src/crypto_bot/config/settings.py`)
- Added `HealthSettings` class with fields:
  - `api_key`: SecretStr for API authentication
  - `cors_origins`: Comma-separated allowed CORS origins
  - `rate_limit_requests`: Max requests per window (default 100)
  - `rate_limit_window`: Window in seconds (default 60)

### Main Entry Point (`src/crypto_bot/main.py`)
- Updated `HealthCheckServer` initialization to pass security settings

### Dashboard (`dashboard/config.py`, `dashboard/services/api_client.py`)
- Added `api_key` field to dashboard config
- Updated `APIClient` to include `X-API-Key` header in all requests

### Environment Configuration (`.env.example`)
- Documented new security settings with generation instructions
- Added security notes for production deployment

## How to Test

1. Start the bot with API key configured:
   ```bash
   HEALTH__API_KEY=test-key python -m crypto_bot
   ```

2. Test unauthenticated access (should return 401):
   ```bash
   curl http://localhost:8080/api/status
   # Returns: {"error": "Unauthorized", "message": "Valid API key required"}
   ```

3. Test authenticated access (should return 200):
   ```bash
   curl -H "X-API-Key: test-key" http://localhost:8080/api/status
   # Returns bot status JSON
   ```

4. Test health probes work without auth:
   ```bash
   curl http://localhost:8080/health
   # Returns: {"status": "healthy", ...}
   ```

5. Test rate limiting (send 101+ requests):
   ```bash
   for i in {1..105}; do curl -s -H "X-API-Key: test-key" http://localhost:8080/api/status | head -1; done
   # After 100 requests: {"error": "Rate limit exceeded", ...}
   ```

6. Verify security headers:
   ```bash
   curl -I -H "X-API-Key: test-key" http://localhost:8080/api/status
   # Should include: X-Frame-Options, X-Content-Type-Options, CSP, etc.
   ```

## Risk / Rollback Notes

**Risks:**
- Existing deployments will need to configure `HEALTH__API_KEY` and `DASHBOARD_API_KEY`
- Without API key configuration, API endpoints remain accessible (backward compatible)
- Rate limiting may affect high-frequency dashboard polling (adjust limits if needed)

**Rollback:**
- Remove `HEALTH__API_KEY` from environment to disable authentication
- Revert to previous version if issues arise
- Rate limiting and CORS can be disabled by not configuring their respective settings

**Migration Steps for Production:**
1. Generate secure API key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Add to VM environment: `HEALTH__API_KEY=<generated-key>`
3. Add to dashboard: `DASHBOARD_API_KEY=<same-key>`
4. Redeploy bot and dashboard
5. Verify dashboard can still connect to bot API
