# Add High Severity Security Fixes

## Summary

Added high severity security fixes including bcrypt password hashing, login rate limiting, API input validation bounds, and request logging for audit trail.

## Context / Problem

Following the critical security fixes (API authentication, CORS, rate limiting, security headers), the security review identified several high severity issues:

1. **Dashboard authentication weakness**: Plain-text password comparison without hashing
2. **No login rate limiting**: Brute force attacks possible on dashboard login
3. **Unbounded input validation**: Query parameters like `limit` and `days` could be set to extremely large values causing DoS
4. **No request logging**: No audit trail for who accessed what API data

## What Changed

### Dashboard Authentication (`dashboard/auth.py`)

- Added bcrypt password hashing support
  - Passwords starting with `$2b$` or `$2a$` are treated as bcrypt hashes
  - Plain-text comparison still supported for backward compatibility (using constant-time comparison)
- Added login rate limiting
  - 5 attempts per 15-minute window per IP
  - Lockout message shows remaining time
  - Rate limit cleared on successful login
- Added `hash_password()` helper function for generating bcrypt hashes
- Added `_is_rate_limited()`, `_record_login_attempt()`, `_get_remaining_lockout_time()` helpers

### API Input Validation (`src/crypto_bot/utils/health.py`)

- Added validation constants:
  - `_MAX_LIMIT = 1000` (max records per request)
  - `_MAX_DAYS = 365` (max days for equity data)
  - `_VALID_PERIODS` = daily, weekly, monthly, all
  - `_VALID_TIMEFRAMES` = 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
  - `_SYMBOL_PATTERN` for validating trading pair format (e.g., BTC/USDT)

- Added validation functions:
  - `_validate_limit()` - Clamps to 1-1000
  - `_validate_days()` - Clamps to 1-365
  - `_validate_symbol()` - Validates format, returns None if invalid
  - `_validate_period()` - Validates against allowed periods
  - `_validate_timeframe()` - Validates against allowed timeframes

- Updated handlers to use validators:
  - `_trades_handler` - limit, symbol
  - `_pnl_handler` - period
  - `_equity_handler` - days
  - `_orders_handler` - symbol
  - `_ohlcv_handler` - symbol, timeframe, limit

### Request Logging (`src/crypto_bot/utils/health.py`)

- Added `_request_logging_middleware` for audit trail
- Logs all `/api/*` requests with:
  - Client IP address
  - HTTP method
  - Request path
  - Response status code
  - Duration in milliseconds
  - User-Agent (truncated to 100 chars)
- Health probes (`/health`, `/ready`) excluded to reduce log noise
- Error requests logged at ERROR level

### Dependencies (`pyproject.toml`)

- Added `bcrypt>=4.0.0` to dashboard extras

## How to Test

### Password Hashing

```bash
# Generate a bcrypt hash for testing
python -c "from dashboard.auth import hash_password; print(hash_password('your-password'))"

# Set hashed password in .env
DASHBOARD_AUTH_PASSWORD=$2b$12$...hash...
```

### Login Rate Limiting

```bash
# Attempt 6 failed logins - should get rate limited
for i in {1..6}; do curl -X POST -d "password=wrong" http://localhost:8081/login; done
# Should see: "Too many attempts. Try again in X minutes."
```

### Input Validation

```bash
# Test limit clamping - should return max 1000 records
curl -H "X-API-Key: $API_KEY" "http://localhost:8080/api/trades?limit=999999"

# Test invalid symbol - should be rejected/ignored
curl -H "X-API-Key: $API_KEY" "http://localhost:8080/api/trades?symbol=invalid"

# Test days clamping - should use max 365
curl -H "X-API-Key: $API_KEY" "http://localhost:8080/api/equity?days=9999"
```

### Request Logging

```bash
# Make an API request and check logs
curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/status

# Check logs for api_request event
docker logs cryptotrader | grep api_request
# Should see: {"event": "api_request", "client_ip": "...", "method": "GET", "path": "/api/status", ...}
```

## Risk / Rollback Notes

### Risks

- **bcrypt performance**: bcrypt is intentionally slow (~100ms per hash). This is a feature for security but could impact high-volume scenarios.
- **Rate limiting memory**: Login attempts stored in-memory. In a multi-process deployment, rate limiting wouldn't be shared.
- **Backward compatibility**: Plain-text passwords still work but should be migrated to bcrypt hashes.

### Rollback

1. Revert changes to `dashboard/auth.py`, `src/crypto_bot/utils/health.py`, `pyproject.toml`
2. Or, to disable individual features:
   - Remove bcrypt check in `verify_password()` to use only plain-text
   - Comment out rate limiting checks in `verify_password()`
   - Remove `_request_logging_middleware` from middleware list
   - Remove validation calls from handlers (use raw `int()` and `.get()`)
