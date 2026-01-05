# Story 6.3: Implement 24-Hour Runtime Stability

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **the dashboard to run continuously for 24+ hours**,
So that **I can rely on it for overnight monitoring**.

## Acceptance Criteria

1. **AC1:** Memory usage stays within 100MB of startup baseline after 24 hours
2. **AC2:** No memory leaks occur in timers or state objects
3. **AC3:** WebSocket connection remains stable
4. **AC4:** All components continue updating correctly
5. **AC5:** Browser tab can be backgrounded and foregrounded without issues

## Tasks / Subtasks

- [ ] Task 1: Review for memory leaks (AC: 1, 2)
  - [ ] Check timer cleanup on shutdown
  - [ ] Check API client cleanup
  - [ ] Verify state object lifecycle
  - [ ] No accumulating lists/dicts

- [ ] Task 2: Implement proper cleanup (AC: 2)
  - [ ] Add shutdown handlers
  - [ ] Close async resources properly
  - [ ] Clear references to allow GC

- [ ] Task 3: WebSocket stability (AC: 3)
  - [ ] Handle reconnection gracefully
  - [ ] Test connection recovery

- [ ] Task 4: Background tab handling (AC: 4, 5)
  - [ ] Test tab backgrounding
  - [ ] Verify updates resume on foreground

- [ ] Task 5: Long-running test (AC: 1-5)
  - [ ] Run for 24 hours
  - [ ] Monitor memory usage
  - [ ] Verify functionality

## Dev Notes

### Memory Leak Prevention

[Source: docs/planning-artefacts/prd.md - NFR7]

Common leak sources and prevention:

```python
# BAD: Accumulating history without limit
class DashboardState:
    def __init__(self):
        self.price_history = []  # Grows forever!

    def add_price(self, price):
        self.price_history.append(price)  # Memory leak!


# GOOD: Fixed-size buffer
from collections import deque

class DashboardState:
    def __init__(self):
        self.price_history = deque(maxlen=1000)  # Fixed size

    def add_price(self, price):
        self.price_history.append(price)  # Old items auto-removed
```

### Resource Cleanup

```python
"""Proper cleanup implementation."""

class DashboardState:
    async def shutdown(self) -> None:
        """Clean up all resources."""
        # Close API client
        if self._api_client:
            await self._api_client.__aexit__(None, None, None)
            self._api_client = None

        # Clear data references
        self.pairs.clear()
        self.health = None

        logger.info("Dashboard state shutdown complete")


# In main.py
ui.on_shutdown(state.shutdown)
```

### Timer Lifecycle

NiceGUI timers are managed automatically, but verify:

```python
# Timers are stopped when their parent element is removed
# For page-level timers, they persist until shutdown

# If needed, manual control:
timer = ui.timer(2.0, callback)
# later...
timer.deactivate()  # Stop the timer
```

### WebSocket Stability

NiceGUI handles WebSocket reconnection automatically:
- Built on Socket.io with reconnection logic
- No custom handling needed for localhost

For monitoring:
```python
@ui.on_connect
def on_connect():
    logger.info("Client connected")

@ui.on_disconnect
def on_disconnect():
    logger.info("Client disconnected")
```

### Browser Tab Backgrounding

Chrome throttles background tabs:
- Timers may fire less frequently
- WebSocket remains connected but dormant

NiceGUI behavior:
- Updates queue while backgrounded
- Apply when tab returns to foreground
- No data loss

### 24-Hour Test Plan

1. **Start dashboard** with memory baseline
2. **Monitor hourly:**
   - `ps aux | grep python` for memory
   - Dashboard responsiveness
   - Console for errors
3. **Test interactions:**
   - Hover, click, zoom throughout
   - Background/foreground tab
4. **Final check:**
   - Memory within 100MB of baseline
   - All functions working

### Memory Monitoring Script

```bash
# Linux/Mac
while true; do
  ps -o rss= -p $(pgrep -f "dashboard/main.py") | \
    awk '{print strftime("%H:%M:%S"), $1/1024 " MB"}'
  sleep 3600
done
```

### Project Structure Notes

- Modifies: `dashboard/state.py` (cleanup)
- Modifies: `dashboard/main.py` (shutdown handlers)

### References

- [PRD NFR6, NFR7](docs/planning-artefacts/prd.md#non-functional-requirements)
- [Architecture](docs/planning-artefacts/architecture.md#infrastructure--deployment)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

