# Story 3.1: Create Fixed Header Strip Layout

Status: review

## Story

As a **trader (Claudio)**,
I want **a fixed header strip that stays visible at all times**,
So that **I can see critical status information without scrolling**.

## Acceptance Criteria

1. **AC1:** Header strip is 48-56px height displayed at the top
2. **AC2:** Header has position `sticky` with `top: 0`
3. **AC3:** Header uses background color `#16213e`
4. **AC4:** Header contains placeholder slots for: status, P&L, pair count, order count, timestamp
5. **AC5:** Scrolling the page keeps the header fixed at the top
6. **AC6:** Header is the first element to render (before table and chart)

## Tasks / Subtasks

- [x] Task 1: Create header component file (AC: 1, 3, 6)
  - [x] Create `dashboard/components/header.py`
  - [x] Implement header with fixed height
  - [x] Apply background color from theme

- [x] Task 2: Implement sticky positioning (AC: 2, 5)
  - [x] Add CSS for position sticky
  - [x] Set z-index for proper layering
  - [x] Test scrolling behavior

- [x] Task 3: Create slot layout (AC: 4)
  - [x] Add slot for RAG status indicator
  - [x] Add slot for P&L display
  - [x] Add slot for pair count
  - [x] Add slot for order count
  - [x] Add slot for timestamp

- [x] Task 4: Integrate with main.py (AC: 6)
  - [x] Import header component
  - [x] Render header first in page structure

## Dev Notes

### Header Component Implementation

[Source: docs/planning-artefacts/ux-design-specification.md - The Defining Interaction]

```python
"""CryptoTrader Dashboard - Header Strip Component.

Fixed header that answers "Is everything okay?" in under 5 seconds.
"""

from nicegui import ui

from dashboard.state import state


def header() -> None:
    """Create the fixed header strip with status slots.

    Layout: [Status] | [P&L] | [Pair Count] | [Order Count] | [Timestamp]
    """
    with ui.header().classes("fixed-header"):
        with ui.row().classes("header-content items-center justify-between w-full"):
            # Status indicator slot (Story 3.2)
            with ui.element("div").classes("header-slot status-slot"):
                ui.label("HEALTHY").classes("status-placeholder")

            # P&L display slot (Story 3.4)
            with ui.element("div").classes("header-slot pnl-slot"):
                ui.label("+€0.00").classes("pnl-placeholder")

            # Pair count slot (Story 3.5)
            with ui.element("div").classes("header-slot pairs-slot"):
                ui.label("0/0 pairs").classes("pairs-placeholder")

            # Order count slot (Story 3.5)
            with ui.element("div").classes("header-slot orders-slot"):
                ui.label("0 ord").classes("orders-placeholder")

            # Timestamp slot (Story 3.3)
            with ui.element("div").classes("header-slot timestamp-slot"):
                ui.label("--:--:--").classes("timestamp-placeholder")
```

### CSS Styling

Add to `theme.css`:

```css
.fixed-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  height: 48px;
  min-height: 48px;
  max-height: 56px;
  background-color: var(--bg-secondary); /* #16213e */
  padding: 0 16px;
  border-bottom: 1px solid var(--surface);
}

.header-content {
  height: 100%;
  gap: 24px;
}

.header-slot {
  display: flex;
  align-items: center;
}

/* Placeholder styles - will be replaced in subsequent stories */
.status-placeholder,
.pnl-placeholder,
.pairs-placeholder,
.orders-placeholder,
.timestamp-placeholder {
  font-family: 'Roboto Mono', monospace;
  font-size: 14px;
  color: var(--text-secondary);
}
```

### Header Visual Pattern

[Source: docs/planning-artefacts/ux-design-specification.md - The 5-Second Header Strip]

```
┌─────────────────────────────────────────────────────────────────┐
│ 🟢 HEALTHY │ +€47.32 ▲ │ 4/4 pairs │ 7 ord │ 16:42:05        │
└─────────────────────────────────────────────────────────────────┘
```

**Design Principles:**
- Header answers "Is everything okay?" without scrolling
- Information flows left-to-right: Status → P&L → Counts → Time
- Monospace typography for all numerical data

### Project Structure Notes

- File location: `dashboard/components/header.py`
- Imported by: `dashboard/main.py`
- Depends on: `dashboard/state.py` (for data binding in future stories)

### References

- [UX Design](docs/planning-artefacts/ux-design-specification.md#the-defining-interaction)
- [Architecture](docs/planning-artefacts/architecture.md#component-boundaries)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created dashboard/components/header.py with create_header() function
- Header uses ui.header() with .fixed-header class for sticky positioning
- All 5 slots implemented: status, P&L, pair count, order count, timestamp
- CSS added to theme.css: .fixed-header with position: sticky, z-index: 1000
- Header height: 48-56px with #16213e background (--bg-secondary)
- main.py updated to render header first via create_header()

### File List

- dashboard/components/header.py (created)
- dashboard/assets/css/theme.css (modified)
- dashboard/main.py (modified)

