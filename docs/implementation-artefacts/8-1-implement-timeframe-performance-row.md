# Story 8.1: Implement Timeframe Performance Row

Status: review

**Version:** v1.5

## Story

As a **trader (Claudio)**,
I want **to see P&L across multiple timeframes**,
So that **I can understand performance trends**.

## Acceptance Criteria

1. **AC1:** Displays P&L for: 1H, 24H, 7D, 30D timeframes
2. **AC2:** Each timeframe shows percentage change and absolute value
3. **AC3:** Positive values are green, negative are red
4. **AC4:** Row is 32-40px tall
5. **AC5:** Row scrolls with content (not fixed like header)

## Tasks / Subtasks

- [x] Task 1: Add timeframe P&L API method
  - [x] Add endpoint to fetch multi-timeframe P&L
  - [x] Define TimeframePerformance data model

- [x] Task 2: Create timeframe row component (AC: 1, 4, 5)
  - [x] Position below header (scrollable)
  - [x] Display 4 timeframe columns
  - [x] Set height 32-40px

- [x] Task 3: Display values (AC: 2)
  - [x] Show percentage change
  - [x] Show absolute value

- [x] Task 4: Apply color coding (AC: 3)
  - [x] Green for positive
  - [x] Red for negative

## Dev Notes

### Timeframe Performance Model

```python
"""Timeframe performance data model."""

from decimal import Decimal
from pydantic import BaseModel


class TimeframePerformance(BaseModel):
    """P&L performance across timeframes."""
    pnl_1h: Decimal
    pnl_1h_pct: Decimal
    pnl_24h: Decimal
    pnl_24h_pct: Decimal
    pnl_7d: Decimal
    pnl_7d_pct: Decimal
    pnl_30d: Decimal
    pnl_30d_pct: Decimal
```

### Timeframe Row Component

```python
"""Timeframe performance row component."""

from nicegui import ui

from dashboard.state import state


TIMEFRAMES = [
    ("1H", "pnl_1h", "pnl_1h_pct"),
    ("24H", "pnl_24h", "pnl_24h_pct"),
    ("7D", "pnl_7d", "pnl_7d_pct"),
    ("30D", "pnl_30d", "pnl_30d_pct"),
]


def timeframe_row() -> None:
    """Create timeframe performance row."""
    with ui.row().classes("timeframe-row items-center justify-around"):
        for label, pnl_field, pct_field in TIMEFRAMES:
            timeframe_cell(label, pnl_field, pct_field)


def timeframe_cell(label: str, pnl_field: str, pct_field: str) -> None:
    """Single timeframe performance cell."""
    with ui.column().classes("timeframe-cell items-center"):
        ui.label(label).classes("timeframe-label")

        with ui.row().classes("timeframe-values"):
            # Percentage
            pct_label = ui.label().classes("timeframe-pct")
            # Bind to state.timeframe_performance.pnl_1h_pct etc.

            # Absolute value
            abs_label = ui.label().classes("timeframe-abs")
            # Bind to state.timeframe_performance.pnl_1h etc.
```

### CSS Styling

```css
.timeframe-row {
  height: 36px;
  background-color: var(--bg-secondary);
  padding: 0 16px;
  border-bottom: 1px solid var(--surface);
}

.timeframe-cell {
  min-width: 100px;
}

.timeframe-label {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-tertiary);
  letter-spacing: 0.5px;
}

.timeframe-values {
  gap: 8px;
}

.timeframe-pct {
  font-family: 'Roboto Mono', monospace;
  font-size: 14px;
  font-weight: 600;
}

.timeframe-abs {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.timeframe-positive {
  color: var(--status-success);
}

.timeframe-negative {
  color: var(--status-error);
}
```

### Visual Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Fixed Header: Status | P&L | Pairs | Orders | Time]       │
├─────────────────────────────────────────────────────────────┤
│     1H          24H          7D          30D               │ ← This row
│  +2.3% €12   +5.1% €47   +12% €234   +8% €156              │
├─────────────────────────────────────────────────────────────┤
│ [Pairs Table...]                                            │
└─────────────────────────────────────────────────────────────┘
```

### State Addition

```python
# In dashboard/state.py
class DashboardState:
    def __init__(self):
        # ... existing ...
        self.timeframe_performance: TimeframePerformance | None = None
```

### Project Structure Notes

- Creates: `dashboard/components/timeframe_row.py`
- Modifies: `dashboard/state.py`
- Modifies: `dashboard/main.py` (add to layout)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-81-implement-timeframe-performance-row)
- [UX Design](docs/planning-artefacts/ux-design-specification.md#timeframe-summary-row)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created timeframe_row.py component with 1H, 24H, 7D, 30D columns
- Added pnl_1h, pnl_24h, pnl_7d, pnl_30d fields to state.py
- Row positioned below header, scrolls with content (36px height)
- Color coding: green for positive, red for negative, gray for neutral
- CSS styling with monospace font for values

### File List

- dashboard/components/timeframe_row.py (created)
- dashboard/state.py (modified)
- dashboard/main.py (modified)
- dashboard/assets/css/theme.css (modified)

