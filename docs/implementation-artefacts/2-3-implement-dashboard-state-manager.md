# Story 2.3: Implement Dashboard State Manager

Status: review

## Story

As a **developer**,
I want **a centralized state class that holds current dashboard data**,
So that **all components can access the same data without redundant API calls**.

## Acceptance Criteria

1. **AC1:** `DashboardState` class holds health, pairs, total_pnl, last_update
2. **AC2:** State includes `connection_status` ("connected", "stale", "offline")
3. **AC3:** State includes async `refresh()` method that calls APIClient
4. **AC4:** `refresh()` updates `connection_status` based on API availability
5. **AC5:** Timestamps are converted to local timezone
6. **AC6:** State is accessible as singleton throughout application

## Tasks / Subtasks

- [x] Task 1: Create DashboardState class (AC: 1, 2)
  - [x] Define state attributes with type hints
  - [x] Initialize with default/empty values
  - [x] Add connection_status tracking

- [x] Task 2: Implement refresh method (AC: 3, 4, 5)
  - [x] Create async refresh() method
  - [x] Call APIClient to fetch data
  - [x] Update connection_status based on results
  - [x] Convert timestamps to local timezone

- [x] Task 3: Implement singleton pattern (AC: 6)
  - [x] Create module-level state instance
  - [x] Export for import by components

## Dev Notes

### State Manager Implementation

[Source: docs/planning-artefacts/architecture.md - State Update Pattern]

```python
"""CryptoTrader Dashboard - State Manager.

Centralized state management for dashboard data.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from dashboard.services.api_client import APIClient
from dashboard.services.data_models import HealthResponse, PairData

logger = logging.getLogger(__name__)

ConnectionStatus = Literal["connected", "stale", "offline"]


class DashboardState:
    """Centralized dashboard state container.

    Holds all dashboard data and provides refresh mechanism.
    NiceGUI automatically pushes changes to browser via WebSocket.
    """

    def __init__(self) -> None:
        """Initialize state with default values."""
        # Data state
        self.health: HealthResponse | None = None
        self.pairs: list[PairData] = []
        self.total_pnl: Decimal = Decimal("0")
        self.last_update: datetime | None = None

        # Connection state
        self.connection_status: ConnectionStatus = "offline"
        self._last_successful_update: datetime | None = None
        self._stale_threshold_seconds: int = 60

        # API client
        self._api_client: APIClient | None = None

    async def initialize(self) -> None:
        """Initialize API client. Call once on startup."""
        self._api_client = APIClient()
        await self._api_client.__aenter__()

    async def shutdown(self) -> None:
        """Shutdown API client. Call on application exit."""
        if self._api_client:
            await self._api_client.__aexit__(None, None, None)

    async def refresh(self) -> None:
        """Refresh all dashboard data from API.

        Updates connection_status based on API availability:
        - "connected": Successful API response
        - "stale": No successful response for >60 seconds
        - "offline": API unreachable
        """
        if not self._api_client:
            logger.warning("API client not initialized")
            self.connection_status = "offline"
            return

        try:
            dashboard_data = await self._api_client.get_dashboard_data()

            if dashboard_data.health is not None:
                # Successful update
                self.health = dashboard_data.health
                self.pairs = dashboard_data.pairs
                self.total_pnl = dashboard_data.total_pnl
                self.last_update = self._to_local_time(datetime.now(timezone.utc))
                self._last_successful_update = datetime.now(timezone.utc)
                self.connection_status = "connected"
                logger.debug("State refreshed successfully")
            else:
                # API returned but health is None (partial failure)
                self._update_connection_status()

        except Exception as e:
            logger.error("State refresh failed", error=str(e))
            self._update_connection_status()

    def _update_connection_status(self) -> None:
        """Update connection status based on last successful update."""
        if self._last_successful_update is None:
            self.connection_status = "offline"
            return

        elapsed = (datetime.now(timezone.utc) - self._last_successful_update).total_seconds()
        if elapsed > self._stale_threshold_seconds:
            self.connection_status = "stale"
        else:
            # Keep current status if recently successful
            pass

    @staticmethod
    def _to_local_time(dt: datetime) -> datetime:
        """Convert UTC datetime to local timezone."""
        return dt.astimezone()

    # Tier-specific refresh methods for timer-based polling
    async def refresh_tier1(self) -> None:
        """Refresh Tier 1 data only (health, P&L)."""
        await self.refresh()  # For MVP, refresh all

    async def refresh_tier2(self) -> None:
        """Refresh Tier 2 data only (chart, table)."""
        await self.refresh()  # For MVP, refresh all


# Singleton instance
state = DashboardState()
```

### Connection Status Logic

[Source: docs/planning-artefacts/architecture.md - Error Handling Strategy]

| Status | Condition | UI Display |
|--------|-----------|------------|
| `connected` | Last API call successful | Normal display |
| `stale` | No success for >60 seconds | Warning indicator |
| `offline` | API unreachable | Error indicator |

### Timer Integration (Story 6.1)

```python
from nicegui import ui
from dashboard.state import state

# Set up polling timers
ui.timer(2.0, state.refresh_tier1)   # Health, P&L
ui.timer(5.0, state.refresh_tier2)   # Chart, table
```

### Project Structure Notes

- File location: `dashboard/state.py`
- Depends on: `dashboard/services/api_client.py` (Story 2.2)
- Used by: All UI components (Epic 3-5)

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#state-update-pattern)
- [Architecture Document](docs/planning-artefacts/architecture.md#error-handling-strategy)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created DashboardState with health, pairs, total_pnl, last_update attributes
- connection_status: "connected", "stale", "offline" based on API availability
- Tiered refresh methods: refresh_tier1(), refresh_tier2() for polling
- On-demand refresh: refresh_orders(), refresh_trades(), refresh_ohlcv()
- Computed properties: is_connected, is_stale, is_offline, pair_count, is_healthy
- UI helper properties: uptime_formatted, last_update_formatted
- Row expansion state management for expanded details
- Singleton pattern with module-level `state` instance

### File List

- dashboard/state.py (modified)

