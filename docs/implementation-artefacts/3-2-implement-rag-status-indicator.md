# Story 3.2: Implement RAG Status Indicator

Status: review

## Story

As a **trader (Claudio)**,
I want **a Red/Amber/Green status indicator showing bot health**,
So that **I instantly know if the trading bot is healthy, degraded, or in error state**.

## Acceptance Criteria

1. **AC1:** Status displays icon + colored badge + text label
2. **AC2:** Healthy state: `#00c853` green, circle icon `●`, text "HEALTHY"
3. **AC3:** Degraded state: `#ffc107` amber, diamond icon `◆`, text "DEGRADED"
4. **AC4:** Error state: `#ff5252` red, triangle icon `▲`, text "ERROR"
5. **AC5:** Healthy status is visually muted (doesn't demand attention)
6. **AC6:** Indicator updates when `DashboardState.health` changes

## Tasks / Subtasks

- [x] Task 1: Create status indicator component (AC: 1-4)
  - [x] Enhanced `dashboard/components/header.py` with icon+text
  - [x] Define icons for each status (circle, diamond, triangle)
  - [x] Define colors for each status
  - [x] Define text labels for each status

- [x] Task 2: Implement visual styling (AC: 5)
  - [x] Make healthy state muted/receding (opacity: 0.8)
  - [x] Make warning state attention-drawing (full opacity)
  - [x] Make error state impossible to miss (full opacity)

- [x] Task 3: Bind to state (AC: 6)
  - [x] Connect to `state.is_offline`, `state.is_stale`, `state.is_healthy`
  - [x] Update display on state change

- [x] Task 4: Integrate with header (AC: 1)
  - [x] Implemented in header status slot

## Dev Notes

### Status Indicator Implementation

[Source: docs/planning-artefacts/ux-design-specification.md - RAG Status System]

```python
"""CryptoTrader Dashboard - RAG Status Indicator.

Displays health status with icon + color + text.
Never uses color alone for accessibility.
"""

from nicegui import ui

from dashboard.state import state

# Status configuration
STATUS_CONFIG = {
    "healthy": {
        "icon": "●",
        "text": "HEALTHY",
        "color": "#00c853",
        "opacity": 0.8,  # Muted
    },
    "degraded": {
        "icon": "◆",
        "text": "DEGRADED",
        "color": "#ffc107",
        "opacity": 1.0,  # Full attention
    },
    "error": {
        "icon": "▲",
        "text": "ERROR",
        "color": "#ff5252",
        "opacity": 1.0,  # Full attention
    },
}


def status_indicator() -> None:
    """Create RAG status indicator with reactive binding."""
    def get_status() -> str:
        if state.health is None:
            return "error"
        return state.health.status

    def get_config():
        return STATUS_CONFIG.get(get_status(), STATUS_CONFIG["error"])

    with ui.row().classes("status-indicator items-center gap-2"):
        # Icon
        icon_label = ui.label().classes("status-icon")
        icon_label.bind_text_from(state, "health", lambda h: STATUS_CONFIG.get(
            h.status if h else "error", STATUS_CONFIG["error"]
        )["icon"])

        # Text label
        text_label = ui.label().classes("status-text")
        text_label.bind_text_from(state, "health", lambda h: STATUS_CONFIG.get(
            h.status if h else "error", STATUS_CONFIG["error"]
        )["text"])

    # Dynamic styling based on status
    ui.add_css('''
        .status-indicator {
            padding: 4px 12px;
            border-radius: 4px;
        }
        .status-icon {
            font-size: 16px;
        }
        .status-text {
            font-family: 'Roboto Mono', monospace;
            font-weight: 500;
            font-size: 13px;
            letter-spacing: 0.5px;
        }
    ''')
```

### Status Visual Behavior

[Source: docs/planning-artefacts/ux-design-specification.md - Emotional Design Principles]

| Status | Visual Treatment | Attention Level |
|--------|-----------------|-----------------|
| Healthy | Muted green, lower opacity | Recedes into background |
| Degraded | Bright amber, full opacity | Draws the eye |
| Error | High-contrast red, full opacity | Demands immediate attention |

**Key Principle:** Green should fade; only yellow/red should draw the eye.

### Accessibility Note

**Never use color alone.** Each status has:
- Unique icon shape (●, ◆, ▲)
- Color indicator
- Text label

This ensures colorblind users can still understand the status.

### Integration with Header

Replace placeholder in `header.py`:

```python
from dashboard.components.status_indicator import status_indicator

def header() -> None:
    with ui.header().classes("fixed-header"):
        with ui.row().classes("header-content"):
            # Status indicator (was placeholder)
            status_indicator()
            # ... rest of slots
```

### Project Structure Notes

- File location: `dashboard/components/status_indicator.py`
- Integrates with: `dashboard/components/header.py`
- Depends on: `dashboard/state.py`

### References

- [UX Design](docs/planning-artefacts/ux-design-specification.md#rag-status-system)
- [UX Design](docs/planning-artefacts/ux-design-specification.md#status--feedback-patterns)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Enhanced _create_status_indicator() in header.py with icon+text display
- Uses Unicode icons: circle (healthy), diamond (degraded/stale), triangle (error/offline)
- Added CSS classes: status-icon, status-text with proper styling
- Healthy state has opacity: 0.8 to recede into background
- Warning/error states have full opacity for attention

### File List

- dashboard/components/header.py (modified)
- dashboard/assets/css/theme.css (modified)

