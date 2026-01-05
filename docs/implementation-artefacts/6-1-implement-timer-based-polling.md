# Story 6.1: Implement Timer-Based Polling

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **the dashboard to automatically update data**,
So that **I always see current information without manual refresh**.

## Acceptance Criteria

1. **AC1:** Tier 1 data (health, total P&L) refreshes every 2 seconds
2. **AC2:** Tier 2 data (pairs table, chart) refreshes every 5 seconds
3. **AC3:** Updates are triggered by `ui.timer()` NiceGUI mechanism
4. **AC4:** Updates happen silently without full page refresh
5. **AC5:** Only changed DOM elements update (surgical updates via WebSocket)
6. **AC6:** There is zero visible flickering during updates

## Tasks / Subtasks

- [ ] Task 1: Set up Tier 1 polling (AC: 1, 3)
  - [ ] Create 2-second timer for health/P&L
  - [ ] Connect to state.refresh_tier1()
  - [ ] Verify timer fires correctly

- [ ] Task 2: Set up Tier 2 polling (AC: 2, 3)
  - [ ] Create 5-second timer for table/chart
  - [ ] Connect to state.refresh_tier2()
  - [ ] Verify timer fires correctly

- [ ] Task 3: Verify silent updates (AC: 4, 5, 6)
  - [ ] Test that updates don't cause page refresh
  - [ ] Verify only changed elements update
  - [ ] Confirm zero flickering

## Dev Notes

### Timer Implementation

[Source: docs/planning-artefacts/architecture.md - Timer Setup]

```python
"""Timer-based polling setup in main.py."""

from nicegui import ui

from dashboard.state import state
from dashboard.config import config


async def setup_polling() -> None:
    """Set up timer-based polling for data refresh."""
    # Initialize state and API client
    await state.initialize()

    # Tier 1: Health, P&L (2 seconds)
    ui.timer(
        config.poll_interval_tier1,
        state.refresh_tier1,
    )

    # Tier 2: Pairs table, Chart (5 seconds)
    ui.timer(
        config.poll_interval_tier2,
        state.refresh_tier2,
    )


def create_ui() -> None:
    """Create dashboard UI with polling."""
    ui.dark_mode(True)

    # Components
    header()
    pairs_table()
    price_chart()

    # Start polling after UI is ready
    ui.on_startup(setup_polling)
```

### Polling Intervals

[Source: docs/planning-artefacts/architecture.md - Polling Intervals]

| Data Tier | Interval | Data | Rationale |
|-----------|----------|------|-----------|
| Tier 1 | 2 seconds | Health, P&L | Critical, real-time feel |
| Tier 2 | 5 seconds | Pairs table, Chart | Important but less urgent |
| Tier 3 | On-demand | Expanded details | Only when user expands row |

### NiceGUI Timer Behavior

`ui.timer()` characteristics:
- Runs in background automatically
- Async callbacks supported
- Does NOT cause full page refresh
- Updates pushed via WebSocket to specific elements

```python
# Timer with async callback
ui.timer(2.0, async_callback)

# Timer with active flag (can be paused)
timer = ui.timer(2.0, callback, active=True)
timer.active = False  # Pause
timer.active = True   # Resume
```

### Silent Updates (Zero Flicker)

NiceGUI achieves flicker-free updates via:
1. **WebSocket connection** - Persistent connection to browser
2. **Surgical DOM updates** - Only changed elements modified
3. **Reactive bindings** - `bind_text_from()` auto-updates

Key: Do NOT use `ui.run_javascript('location.reload()')` or similar.

### Integration with State

State methods for tiered refresh:
```python
class DashboardState:
    async def refresh_tier1(self) -> None:
        """Refresh Tier 1 data (health, P&L)."""
        await self.refresh()  # MVP: refresh all

    async def refresh_tier2(self) -> None:
        """Refresh Tier 2 data (table, chart)."""
        await self.refresh()  # MVP: refresh all
```

### Lifecycle Management

```python
async def on_shutdown() -> None:
    """Clean up on dashboard shutdown."""
    await state.shutdown()

ui.on_shutdown(on_shutdown)
```

### Project Structure Notes

- Modifies: `dashboard/main.py`
- Depends on: `dashboard/state.py`, `dashboard/config.py`

### References

- [Architecture](docs/planning-artefacts/architecture.md#timer-setup)
- [NiceGUI Timer](https://nicegui.io/documentation#timer)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

