# Story 3.3: Implement Last Updated Timestamp

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **to see when data was last updated**,
So that **I can trust the data is current and not stale**.

## Acceptance Criteria

1. **AC1:** Timestamp displays in format `HH:MM:SS`
2. **AC2:** Time is shown in local timezone
3. **AC3:** Normal state shows secondary text color `#a0a0a0`
4. **AC4:** If data is >60 seconds old, timestamp turns amber `#ffc107`
5. **AC5:** Timestamp updates each time `DashboardState.refresh()` succeeds
6. **AC6:** Relative time option available (e.g., "5s ago")

## Tasks / Subtasks

- [ ] Task 1: Create timestamp component (AC: 1, 2)
  - [ ] Create timestamp display function
  - [ ] Format datetime as HH:MM:SS
  - [ ] Use local timezone

- [ ] Task 2: Implement staleness styling (AC: 3, 4)
  - [ ] Normal: secondary text color
  - [ ] Stale (>60s): amber color
  - [ ] Calculate elapsed time since last update

- [ ] Task 3: Bind to state (AC: 5)
  - [ ] Connect to `state.last_update`
  - [ ] Update display on state change

- [ ] Task 4: Add relative time option (AC: 6)
  - [ ] Calculate "Xs ago" format
  - [ ] Option to toggle between formats

## Dev Notes

### Timestamp Implementation

[Source: docs/planning-artefacts/ux-design-specification.md - Data Update Patterns]

```python
"""CryptoTrader Dashboard - Timestamp Component.

Displays last update time with staleness indication.
"""

from datetime import datetime, timezone

from nicegui import ui

from dashboard.state import state

STALE_THRESHOLD_SECONDS = 60


def timestamp_display(show_relative: bool = False) -> None:
    """Create timestamp display with staleness indication.

    Args:
        show_relative: If True, show "Xs ago" format instead of HH:MM:SS
    """
    def format_time() -> str:
        if state.last_update is None:
            return "--:--:--"
        if show_relative:
            return _relative_time(state.last_update)
        return state.last_update.strftime("%H:%M:%S")

    def get_color() -> str:
        if state.last_update is None:
            return "var(--text-secondary)"
        elapsed = (datetime.now(timezone.utc) - state.last_update.astimezone(timezone.utc)).total_seconds()
        if elapsed > STALE_THRESHOLD_SECONDS:
            return "var(--status-warning)"  # #ffc107
        return "var(--text-secondary)"  # #a0a0a0

    timestamp_label = ui.label().classes("timestamp-display")
    timestamp_label.bind_text_from(state, "last_update", lambda _: format_time())

    # Note: Color binding requires style update approach
    # Will be handled via periodic timer or state observer


def _relative_time(dt: datetime) -> str:
    """Convert datetime to relative time string."""
    now = datetime.now(timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    elapsed = int((now - dt_utc).total_seconds())

    if elapsed < 60:
        return f"{elapsed}s ago"
    elif elapsed < 3600:
        return f"{elapsed // 60}m ago"
    else:
        return f"{elapsed // 3600}h ago"
```

### CSS Styling

```css
.timestamp-display {
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
  color: var(--text-secondary);
  transition: color 0.3s ease;
}

.timestamp-display.stale {
  color: var(--status-warning);
}
```

### Staleness Indication

[Source: docs/planning-artefacts/ux-design-specification.md - Staleness Indication]

| Condition | Display | Color |
|-----------|---------|-------|
| Normal (<60s) | HH:MM:SS | `#a0a0a0` (secondary) |
| Warning (>60s) | HH:MM:SS | `#ffc107` (amber) |
| No data | --:--:-- | `#a0a0a0` (secondary) |

### Integration with Header

Replace placeholder in header timestamp slot:

```python
from dashboard.components.timestamp import timestamp_display

# In header.py, timestamp slot:
with ui.element("div").classes("header-slot timestamp-slot"):
    timestamp_display()
```

### Project Structure Notes

- File location: `dashboard/components/timestamp.py`
- Integrates with: `dashboard/components/header.py`
- Depends on: `dashboard/state.py`

### References

- [UX Design](docs/planning-artefacts/ux-design-specification.md#data-update-patterns)
- [Architecture](docs/planning-artefacts/architecture.md#format-patterns)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

