# Story 6.2: Verify Sub-Second Update Latency

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **Tier 1 data to update within 1 second of API response**,
So that **I trust the data I'm seeing is current**.

## Acceptance Criteria

1. **AC1:** Header strip updates within 1 second of API response
2. **AC2:** Timestamp updates to reflect the new fetch time
3. **AC3:** P&L changes are reflected immediately
4. **AC4:** Health status changes are reflected immediately
5. **AC5:** Latency can be measured via console logging

## Tasks / Subtasks

- [ ] Task 1: Add latency measurement (AC: 5)
  - [ ] Log timestamp before API call
  - [ ] Log timestamp after UI update
  - [ ] Calculate and log latency

- [ ] Task 2: Verify header updates (AC: 1, 2)
  - [ ] Test timestamp component updates
  - [ ] Measure time from API response to DOM

- [ ] Task 3: Verify P&L updates (AC: 3)
  - [ ] Test P&L component updates
  - [ ] Verify color changes apply

- [ ] Task 4: Verify health status updates (AC: 4)
  - [ ] Test status indicator updates
  - [ ] Verify RAG color changes

## Dev Notes

### Latency Measurement

```python
"""Add latency logging to state refresh."""

import time
import logging

logger = logging.getLogger(__name__)


async def refresh_tier1(self) -> None:
    """Refresh Tier 1 data with latency measurement."""
    start_time = time.perf_counter()

    # API call
    dashboard_data = await self._api_client.get_dashboard_data()

    api_time = time.perf_counter()
    api_latency = (api_time - start_time) * 1000  # ms

    # Update state (triggers UI via reactive binding)
    if dashboard_data.health is not None:
        self.health = dashboard_data.health
        self.total_pnl = dashboard_data.total_pnl
        self.last_update = datetime.now()

    update_time = time.perf_counter()
    total_latency = (update_time - start_time) * 1000  # ms

    logger.debug(
        "Tier 1 refresh complete",
        api_latency_ms=f"{api_latency:.1f}",
        total_latency_ms=f"{total_latency:.1f}",
    )
```

### Performance Requirements

[Source: docs/planning-artefacts/prd.md - NFR3]

| Metric | Target | Measurement |
|--------|--------|-------------|
| API call | <500ms | Time from request to response |
| State update | <50ms | Time to update Python objects |
| DOM update | <100ms | Time for NiceGUI to push via WebSocket |
| **Total** | **<1000ms** | API response to visible change |

### Reactive Binding Performance

NiceGUI's reactive bindings (`bind_text_from`) update automatically when state changes:

```python
# Binding set up once
label.bind_text_from(state, "total_pnl", lambda v: f"+€{v:.2f}")

# When state.total_pnl changes, NiceGUI:
# 1. Detects the change
# 2. Calls the lambda
# 3. Sends WebSocket message to browser
# 4. Browser updates just that element
```

This is inherently fast (<100ms for DOM update).

### Manual Testing Steps

1. **Change API response** - Modify bot to return different health status
2. **Watch dashboard** - Observe header status change
3. **Check console** - Verify latency log <1000ms

### Browser DevTools Verification

```javascript
// In browser console, monitor WebSocket messages
// NiceGUI uses Socket.io, messages are small JSON patches
```

### Potential Latency Issues

| Issue | Solution |
|-------|----------|
| Slow API | Increase timeout, check bot performance |
| Too much data | Only fetch Tier 1 data, not full dashboard |
| Complex bindings | Simplify lambda transformations |
| WebSocket delay | Check network, usually not an issue on localhost |

### Project Structure Notes

- Modifies: `dashboard/state.py` (add logging)
- Optional: Add metrics collection for ongoing monitoring

### References

- [PRD NFRs](docs/planning-artefacts/prd.md#non-functional-requirements)
- [Architecture](docs/planning-artefacts/architecture.md#polling-intervals)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

