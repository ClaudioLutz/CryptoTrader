# Story 5.4: Implement Chart Pair Selection

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **to select which trading pair the chart displays**,
So that **I can investigate any pair's price action**.

## Acceptance Criteria

1. **AC1:** Clicking on a pair row in the table updates the chart to show that pair
2. **AC2:** Visual indicator shows which pair is selected (highlighted row)
3. **AC3:** Chart title updates to show the selected pair symbol
4. **AC4:** Chart transition is smooth (no flicker)

## Tasks / Subtasks

- [ ] Task 1: Add selected pair state (AC: 1, 2)
  - [ ] Add `selected_pair` to DashboardState
  - [ ] Initialize with first pair or default

- [ ] Task 2: Handle pair row click (AC: 1)
  - [ ] Add click handler to pairs table
  - [ ] Update selected_pair on click

- [ ] Task 3: Highlight selected row (AC: 2)
  - [ ] Add selected state CSS class
  - [ ] Style selected row differently

- [ ] Task 4: Update chart on selection (AC: 3, 4)
  - [ ] Bind chart to selected_pair
  - [ ] Fetch/display selected pair's price data
  - [ ] Update chart title
  - [ ] Smooth data transition

## Dev Notes

### Selected Pair State

```python
# In dashboard/state.py
class DashboardState:
    def __init__(self) -> None:
        # ... existing state ...
        self.selected_pair: str | None = None  # Symbol of selected pair

    def select_pair(self, symbol: str) -> None:
        """Select a pair for chart display."""
        self.selected_pair = symbol
```

### Pairs Table Click Handler

```python
# In dashboard/components/pairs_table.py
from dashboard.state import state

def pairs_table() -> None:
    def on_row_click(row_data: dict) -> None:
        """Handle pair row click to select for chart."""
        state.select_pair(row_data["symbol"])

    table = ui.table(
        columns=COLUMNS,
        rows=get_rows(),
        row_key="symbol",
        selection="single",  # Enable single row selection
        on_select=lambda e: on_row_click(e.selection[0]) if e.selection else None,
    ).classes("pairs-table")

    # Or using row-click event
    table.on("row-click", lambda e: on_row_click(e.args))
```

### Selected Row Styling

```css
.pairs-table tbody tr.selected {
  background-color: rgba(74, 158, 255, 0.15); /* Accent with transparency */
  border-left: 3px solid var(--accent);
}

.pairs-table tbody tr:hover:not(.selected) {
  background-color: rgba(255, 255, 255, 0.05);
}
```

### Chart Binding to Selection

```python
# In dashboard/components/price_chart.py

def price_chart() -> None:
    def update_chart_for_pair(symbol: str) -> None:
        """Update chart data for selected pair."""
        # Fetch price data for symbol
        # Update figure data
        pass

    with ui.element("div").classes("chart-container"):
        # Chart title showing selected pair
        title_label = ui.label().classes("chart-title")
        title_label.bind_text_from(
            state, "selected_pair",
            lambda s: f"{s} Price" if s else "Select a pair"
        )

        # Chart
        chart = ui.plotly(create_figure()).classes("price-chart")

        # React to pair selection changes
        # NiceGUI will trigger update via reactive binding
```

### Smooth Transition

To prevent flicker during chart update:
```python
def update_chart_data(fig, new_data):
    """Update chart data without full redraw."""
    with fig.batch_update():
        fig.data[0].x = new_data['timestamps']
        fig.data[0].y = new_data['prices']
```

### Default Selection

Initialize with first pair:
```python
async def initialize_selection():
    if state.pairs and not state.selected_pair:
        state.select_pair(state.pairs[0].symbol)
```

### Project Structure Notes

- Modifies: `dashboard/state.py`
- Modifies: `dashboard/components/pairs_table.py`
- Modifies: `dashboard/components/price_chart.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-54-implement-chart-pair-selection)
- [NiceGUI Table Selection](https://nicegui.io/documentation#table)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

