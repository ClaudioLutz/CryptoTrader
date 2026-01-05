# Story 2.2: Implement API Client

Status: review

## Story

As a **developer**,
I want **an async HTTP client that fetches data from the bot API**,
So that **the dashboard can retrieve health, P&L, and pair data**.

## Acceptance Criteria

1. **AC1:** API client uses httpx with async methods
2. **AC2:** Client includes methods: `get_health()`, `get_pairs()`, `get_total_pnl()`, `get_dashboard_data()`
3. **AC3:** All requests use configured timeout (5 seconds default)
4. **AC4:** HTTP errors are caught and logged (not raised)
5. **AC5:** On error, methods return `None` or last known value
6. **AC6:** All API calls use existing bot endpoints (no new endpoints)

## Tasks / Subtasks

- [x] Task 1: Create APIClient class (AC: 1, 3)
  - [x] Initialize httpx.AsyncClient with timeout
  - [x] Use config.api_base_url for base URL
  - [x] Implement context manager for client lifecycle

- [x] Task 2: Implement API methods (AC: 2, 6)
  - [x] Implement `get_health() -> HealthResponse | None`
  - [x] Implement `get_pairs() -> list[PairData]`
  - [x] Implement `get_total_pnl() -> Decimal`
  - [x] Implement `get_dashboard_data() -> DashboardData`

- [x] Task 3: Add error handling (AC: 4, 5)
  - [x] Catch httpx.RequestError
  - [x] Catch httpx.HTTPStatusError
  - [x] Log errors with structlog pattern
  - [x] Return None/empty on error

## Dev Notes

### API Client Implementation

[Source: docs/planning-artefacts/architecture.md - Error Handling Strategy]

```python
"""CryptoTrader Dashboard - API Client.

Async HTTP client for fetching data from the trading bot API.
"""

import logging
from datetime import datetime
from decimal import Decimal

import httpx

from dashboard.config import config
from dashboard.services.data_models import (
    DashboardData,
    HealthResponse,
    PairData,
)

logger = logging.getLogger(__name__)


class APIClient:
    """Async client for bot REST API."""

    def __init__(self) -> None:
        """Initialize API client with configured timeout."""
        self._client: httpx.AsyncClient | None = None
        self._base_url = config.api_base_url
        self._timeout = config.api_timeout

    async def __aenter__(self) -> "APIClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()

    async def get_health(self) -> HealthResponse | None:
        """Fetch bot health status.

        Returns:
            HealthResponse or None if request fails.
        """
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            return HealthResponse.model_validate(response.json())
        except httpx.RequestError as e:
            logger.error("Health request failed", error=str(e))
            return None
        except httpx.HTTPStatusError as e:
            logger.error("Health request returned error", status=e.response.status_code)
            return None

    async def get_pairs(self) -> list[PairData]:
        """Fetch all trading pair data.

        Returns:
            List of PairData or empty list if request fails.
        """
        try:
            response = await self._client.get("/pairs")
            response.raise_for_status()
            data = response.json()
            return [PairData.model_validate(p) for p in data]
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Pairs request failed", error=str(e))
            return []

    async def get_total_pnl(self) -> Decimal:
        """Fetch total P&L across all pairs.

        Returns:
            Total P&L as Decimal, or 0 if request fails.
        """
        try:
            response = await self._client.get("/pnl")
            response.raise_for_status()
            data = response.json()
            return Decimal(str(data.get("total", 0)))
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("PnL request failed", error=str(e))
            return Decimal("0")

    async def get_dashboard_data(self) -> DashboardData:
        """Fetch aggregated dashboard data.

        Makes multiple API calls and aggregates results.

        Returns:
            DashboardData with all available data.
        """
        health = await self.get_health()
        pairs = await self.get_pairs()
        total_pnl = await self.get_total_pnl()

        return DashboardData(
            health=health,
            pairs=pairs,
            total_pnl=total_pnl,
            last_update=datetime.now() if health else None,
        )
```

### Error Handling Strategy

[Source: docs/planning-artefacts/architecture.md - Error Handling Strategy]

| Scenario | Response | UI Feedback |
|----------|----------|-------------|
| API timeout (>5s) | Return None | Header shows "Stale data" |
| API unavailable | Return None/empty | Header shows "API Offline" |
| Partial API failure | Return available data | Affected section shows error |

### Bot API Endpoints

Check existing bot API for actual endpoint paths:
- Health: `/health` or `/api/health`
- Pairs: `/pairs` or `/api/pairs`
- P&L: `/pnl` or derived from pairs data

**Important:** No modifications to bot API for MVP.

### Project Structure Notes

- File location: `dashboard/services/api_client.py`
- Depends on: `dashboard/services/data_models.py` (Story 2.1)
- Depends on: `dashboard/config.py` (Story 1.4)

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#error-handling-strategy)
- [httpx Documentation](https://www.python-httpx.org/)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created APIClient class with async context manager pattern
- Mapped to actual bot API endpoints: /health, /api/status, /api/strategies, /api/orders, /api/trades, /api/pnl, /api/ohlcv
- All methods return None/empty list on error (graceful degradation)
- Added get_api_client() singleton function
- Error logging uses standard logging module
- Integrated with data_models for type-safe responses

### File List

- dashboard/services/api_client.py (created)

