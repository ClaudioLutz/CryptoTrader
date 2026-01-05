# Story 6.4: Implement Connection Recovery

Status: review

## Story

As a **trader (Claudio)**,
I want **the dashboard to recover from network interruptions**,
So that **temporary connectivity issues don't require manual intervention**.

## Acceptance Criteria

1. **AC1:** Dashboard automatically resumes updates when network is restored
2. **AC2:** No manual refresh is required
3. **AC3:** Header shows "Reconnecting..." during recovery attempts
4. **AC4:** Successful reconnection shows normal status
5. **AC5:** Multiple retry attempts occur with backoff (1s, 2s, 4s)

## Tasks / Subtasks

- [x] Task 1: Implement retry logic (AC: 1, 5)
  - [x] Add retry with exponential backoff
  - [x] Configure max retries
  - [x] Reset backoff on success

- [x] Task 2: Add reconnecting state (AC: 3)
  - [x] Add "reconnecting" connection_status
  - [x] Update UI to show reconnecting state

- [x] Task 3: Auto-recovery behavior (AC: 2, 4)
  - [x] Resume normal polling on success
  - [x] Clear reconnecting state
  - [x] Update status indicator

- [x] Task 4: Test recovery scenarios
  - [x] Simulate network loss
  - [x] Verify automatic recovery
  - [x] Test edge cases

## Dev Notes

### Retry Logic Implementation

```python
"""Connection recovery with exponential backoff."""

import asyncio
from typing import Literal

ConnectionStatus = Literal["connected", "reconnecting", "stale", "offline"]


class DashboardState:
    def __init__(self):
        # ... existing ...
        self._retry_count: int = 0
        self._max_retries: int = 5
        self._base_backoff: float = 1.0  # seconds

    async def refresh_with_retry(self) -> None:
        """Refresh with automatic retry on failure."""
        try:
            await self.refresh()

            # Success - reset retry count
            if self.connection_status == "connected":
                self._retry_count = 0

        except Exception as e:
            logger.warning("Refresh failed, will retry", error=str(e))
            await self._handle_retry()

    async def _handle_retry(self) -> None:
        """Handle failed refresh with backoff."""
        self._retry_count += 1

        if self._retry_count <= self._max_retries:
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s
            backoff = self._base_backoff * (2 ** (self._retry_count - 1))
            self.connection_status = "reconnecting"

            logger.info(
                "Attempting reconnection",
                attempt=self._retry_count,
                backoff_seconds=backoff,
            )

            await asyncio.sleep(backoff)
            await self.refresh_with_retry()  # Recursive retry
        else:
            # Max retries exceeded
            self.connection_status = "offline"
            logger.error("Max retries exceeded, marking offline")
```

### UI Reconnecting State

Update status indicator (Story 3.2) to handle reconnecting:

```python
STATUS_CONFIG = {
    "healthy": {...},
    "degraded": {...},
    "error": {...},
    "reconnecting": {
        "icon": "⟳",  # Or use animated spinner
        "text": "RECONNECTING",
        "color": "#ffc107",  # Amber
        "opacity": 1.0,
    },
}

def status_indicator() -> None:
    def get_status() -> str:
        # Check connection_status first
        if state.connection_status == "reconnecting":
            return "reconnecting"
        if state.connection_status == "offline":
            return "error"
        # Then check health
        if state.health is None:
            return "error"
        return state.health.status
```

### Backoff Schedule

| Attempt | Delay | Total Time |
|---------|-------|------------|
| 1 | 1s | 1s |
| 2 | 2s | 3s |
| 3 | 4s | 7s |
| 4 | 8s | 15s |
| 5 | 16s | 31s |

After 5 attempts (~30 seconds), mark as offline.

### Integration with Timers

The regular timer continues firing; retry logic handles failures:

```python
# Timer calls this every 2 seconds
async def refresh_tier1(self) -> None:
    await self.refresh_with_retry()
```

### Recovery Indicators

[Source: docs/planning-artefacts/architecture.md - Error Handling Strategy]

| State | Header Display | User Action |
|-------|---------------|-------------|
| Reconnecting | "⟳ RECONNECTING" (amber) | None needed, auto-retry |
| Recovered | Normal status | None needed |
| Offline | "▲ OFFLINE" (red) | Check bot/network |

### Testing Recovery

1. **Simulate network loss:**
   - Stop bot API
   - Watch dashboard enter reconnecting state

2. **Restore network:**
   - Start bot API
   - Verify auto-recovery within backoff period

3. **Extended outage:**
   - Keep API down >30 seconds
   - Verify offline state
   - Restore API
   - Verify recovery on next poll

### Project Structure Notes

- Modifies: `dashboard/state.py` (retry logic)
- Modifies: `dashboard/components/status_indicator.py` (reconnecting state)

### References

- [Architecture](docs/planning-artefacts/architecture.md#error-handling-strategy)
- [Epics Document](docs/planning-artefacts/epics.md#story-64-implement-connection-recovery)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Added ConnectionStatus type: "connected", "reconnecting", "stale", "offline"
- Implemented _refresh_with_retry() with exponential backoff (1s, 2s, 4s, 8s, 16s)
- Added _handle_retry() for automatic reconnection attempts
- Header status indicator shows "RECONNECTING" with rotating arrow icon
- Retry count resets on successful connection
- Max 5 retries before marking offline

### File List

- dashboard/state.py (modified - retry logic, ConnectionStatus)
- dashboard/components/header.py (modified - reconnecting state display)

