# Story 2.4: Implement Error State Handling

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **the dashboard to gracefully handle API errors**,
So that **I see the last known data with a warning rather than a broken dashboard**.

## Acceptance Criteria

1. **AC1:** Existing state data is preserved on API error (not cleared)
2. **AC2:** `connection_status` changes to "stale" after 60 seconds without successful update
3. **AC3:** `connection_status` changes to "offline" if API is unreachable
4. **AC4:** `last_update` shows timestamp of last successful fetch
5. **AC5:** Warning is logged but no exception is raised to UI
6. **AC6:** Dashboard continues to function with stale data

## Tasks / Subtasks

- [ ] Task 1: Enhance error handling in state.refresh() (AC: 1, 5)
  - [ ] Preserve existing data on error
  - [ ] Log warning without raising exception
  - [ ] Handle network errors gracefully

- [ ] Task 2: Implement staleness detection (AC: 2, 3, 4)
  - [ ] Track last successful update timestamp
  - [ ] Check elapsed time on each refresh
  - [ ] Update connection_status appropriately

- [ ] Task 3: Test error scenarios (AC: 6)
  - [ ] Test API timeout behavior
  - [ ] Test API unavailable behavior
  - [ ] Test recovery after reconnection

## Dev Notes

### Error Handling Enhancement

[Source: docs/planning-artefacts/architecture.md - Error Handling Strategy]

This story enhances the `DashboardState` class from Story 2.3 with robust error handling.

### Error Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| API timeout (>5s) | Keep existing data, log warning, mark as potential stale |
| API returns error status | Keep existing data, log error, update status |
| Network unreachable | Keep existing data, mark as offline |
| Partial data returned | Update available fields, keep others |
| Recovery after outage | Resume normal updates, clear stale status |

### Implementation Details

```python
async def refresh(self) -> None:
    """Refresh with graceful error handling."""
    try:
        dashboard_data = await self._api_client.get_dashboard_data()

        if dashboard_data.health is not None:
            # Success - update all data
            self._apply_update(dashboard_data)
            self.connection_status = "connected"
        else:
            # Partial failure - keep existing data
            logger.warning("Partial API response, keeping existing data")
            self._check_staleness()

    except httpx.TimeoutException:
        logger.warning("API request timed out")
        self._check_staleness()

    except httpx.ConnectError:
        logger.error("Cannot connect to API")
        self.connection_status = "offline"

    except Exception as e:
        logger.error("Unexpected error during refresh", error=str(e))
        self._check_staleness()

def _check_staleness(self) -> None:
    """Check if data is stale based on last successful update."""
    if self._last_successful_update is None:
        self.connection_status = "offline"
        return

    elapsed = (datetime.now(timezone.utc) - self._last_successful_update).total_seconds()
    if elapsed > self._stale_threshold_seconds:
        self.connection_status = "stale"
        logger.warning("Data is stale", elapsed_seconds=elapsed)
```

### Graceful Degradation UX

[Source: docs/planning-artefacts/ux-design-specification.md - Data Update Patterns]

**Staleness Indication:**
- Normal: Timestamp displays last update time
- Warning (>60s): Timestamp turns amber
- Critical (>120s): Consider connection warning

**User Experience:**
- Dashboard never crashes due to API errors
- User always sees some data (even if stale)
- Clear visual indication of data freshness

### Logging Pattern

```python
# Warning level for expected issues
logger.warning("API request timed out", timeout=config.api_timeout)

# Error level for unexpected issues
logger.error("Unexpected error", error=str(e), traceback=True)

# NEVER raise exception to UI layer
# Let the UI display stale/offline status instead
```

### Project Structure Notes

- Modifies: `dashboard/state.py` (Story 2.3)
- Tested by: Manual testing with API offline

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#error-handling-strategy)
- [UX Design](docs/planning-artefacts/ux-design-specification.md#staleness-indication)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

