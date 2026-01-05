# Story 9.3: Implement Trade History Filtering

Status: review

**Version:** v2.0

## Story

As a **trader (Claudio)**,
I want **to filter trade history by pair and date range**,
So that **I can find specific trades**.

## Acceptance Criteria

1. **AC1:** Trades can be filtered by trading pair (dropdown)
2. **AC2:** Trades can be filtered by date range (start/end date pickers)
3. **AC3:** Trades can be filtered by side (buy/sell/all)
4. **AC4:** Filters update the table without page refresh
5. **AC5:** Filter state is preserved during session

## Tasks / Subtasks

- [x] Task 1: Add filter state (AC: 5)
  - [x] Track filter selections in state
  - [x] Preserve across tab switches

- [x] Task 2: Create filter controls (AC: 1, 2, 3)
  - [x] Trading pair dropdown
  - [x] Date range pickers
  - [x] Side selector

- [x] Task 3: Apply filters to API call (AC: 4)
  - [x] Pass filters to get_trade_history()
  - [x] Refresh table on filter change

- [x] Task 4: Create filter UI layout
  - [x] Horizontal filter bar
  - [x] Clear filters button

## Dev Notes

### Filter State

```python
# In dashboard/state.py
from datetime import datetime


class TradeHistoryFilters:
    """Trade history filter state."""

    def __init__(self):
        self.symbol: str | None = None
        self.side: str | None = None  # "buy", "sell", or None for all
        self.start_date: datetime | None = None
        self.end_date: datetime | None = None


class DashboardState:
    def __init__(self):
        # ... existing ...
        self.history_filters = TradeHistoryFilters()
```

### Filter Controls Component

```python
"""Trade history filter controls."""

from datetime import date

from nicegui import ui

from dashboard.state import state


def history_filters() -> None:
    """Create filter controls for trade history."""
    with ui.row().classes("history-filters items-end gap-4"):
        # Trading pair dropdown
        pairs = ["All Pairs"] + [p.symbol for p in state.pairs]
        ui.select(
            pairs,
            value="All Pairs",
            label="Pair",
            on_change=lambda e: set_pair_filter(e.value),
        ).classes("filter-select")

        # Side filter
        ui.select(
            ["All", "Buy", "Sell"],
            value="All",
            label="Side",
            on_change=lambda e: set_side_filter(e.value),
        ).classes("filter-select")

        # Date range
        with ui.column().classes("date-range"):
            ui.label("Date Range").classes("filter-label")
            with ui.row().classes("gap-2"):
                ui.date(
                    label="From",
                    on_change=lambda e: set_start_date(e.value),
                ).classes("date-picker")
                ui.date(
                    label="To",
                    on_change=lambda e: set_end_date(e.value),
                ).classes("date-picker")

        # Clear filters
        ui.button(
            "Clear Filters",
            on_click=clear_filters,
        ).classes("clear-button")


def set_pair_filter(value: str) -> None:
    state.history_filters.symbol = None if value == "All Pairs" else value
    refresh_history()


def set_side_filter(value: str) -> None:
    state.history_filters.side = None if value == "All" else value.lower()
    refresh_history()


def set_start_date(value: date) -> None:
    state.history_filters.start_date = datetime.combine(value, datetime.min.time())
    refresh_history()


def set_end_date(value: date) -> None:
    state.history_filters.end_date = datetime.combine(value, datetime.max.time())
    refresh_history()


def clear_filters() -> None:
    state.history_filters = TradeHistoryFilters()
    refresh_history()


async def refresh_history() -> None:
    """Refresh trade history with current filters."""
    history = await api_client.get_trade_history(
        page=1,
        page_size=20,
        symbol=state.history_filters.symbol,
        side=state.history_filters.side,
        start_date=state.history_filters.start_date,
        end_date=state.history_filters.end_date,
    )
    state.trade_history = history
```

### CSS Styling

```css
.history-filters {
  padding: 16px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--surface);
}

.filter-select {
  min-width: 150px;
}

.filter-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.date-picker {
  width: 130px;
}

.clear-button {
  background-color: transparent;
  color: var(--text-secondary);
}

.clear-button:hover {
  color: var(--text-primary);
}
```

### Filter Bar Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Pair: [All Pairs ▼]  Side: [All ▼]  From: [____]  To: [____]  │
│                                                    [Clear]     │
└─────────────────────────────────────────────────────────────────┘
```

### Integration with History Table

```python
def trade_history_view() -> None:
    """Complete trade history view."""
    # Filter bar
    history_filters()

    # Table (from Story 9.2)
    trade_history_table()
```

### Project Structure Notes

- Modifies: `dashboard/components/trade_history.py`
- Modifies: `dashboard/state.py` (add TradeHistoryFilters)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-93-implement-trade-history-filtering)
- [NiceGUI Select](https://nicegui.io/documentation#select)
- [NiceGUI Date](https://nicegui.io/documentation#date)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Added filter state fields to state.py (history_filter_symbol, side, start, end)
- Created _create_filter_bar() with dropdowns and date inputs
- Pair dropdown populated from state.pairs
- Side dropdown: All, Buy, Sell
- Date filters use text input with YYYY-MM-DD format
- Clear Filters button resets all filter state
- Filters applied in _get_filtered_rows() function

### File List

- dashboard/state.py (modified)
- dashboard/components/trade_history.py (modified)
- dashboard/assets/css/theme.css (modified)

