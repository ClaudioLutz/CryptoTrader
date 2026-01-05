# Story 7.1: Implement Row Expansion Toggle

Status: ready-for-dev

**Version:** v1.5

## Story

As a **trader (Claudio)**,
I want **to click a pair row to expand it**,
So that **I can see more details about that specific pair**.

## Acceptance Criteria

1. **AC1:** Clicking a row opens an expansion panel below the row
2. **AC2:** Expansion animation takes ~200ms
3. **AC3:** Only one row can be expanded at a time (previous collapses)
4. **AC4:** Clicking again collapses the row
5. **AC5:** An expand/collapse icon indicates the state

## Tasks / Subtasks

- [ ] Task 1: Add expansion state tracking (AC: 3, 4)
  - [ ] Track expanded_pair in state
  - [ ] Toggle logic for click

- [ ] Task 2: Implement expansion panel (AC: 1)
  - [ ] Create expansion container below row
  - [ ] Add placeholder content

- [ ] Task 3: Add animation (AC: 2)
  - [ ] CSS transition for height
  - [ ] Smooth open/close

- [ ] Task 4: Add expand icon (AC: 5)
  - [ ] Chevron or arrow icon
  - [ ] Rotate on expand state

## Dev Notes

### Expansion Implementation

```python
"""Row expansion for pairs table."""

from nicegui import ui

from dashboard.state import state


def pairs_table_with_expansion() -> None:
    """Create pairs table with expandable rows."""

    def toggle_expansion(symbol: str) -> None:
        """Toggle expansion for a pair."""
        if state.expanded_pair == symbol:
            state.expanded_pair = None
        else:
            state.expanded_pair = symbol

    for pair in state.pairs:
        with ui.expansion(
            pair.symbol,
            icon="expand_more",
        ).classes("pair-expansion") as expansion:
            # Bind expansion state
            expansion.bind_value_from(
                state, "expanded_pair",
                lambda ep, s=pair.symbol: ep == s
            )

            # Expansion content (Stories 7.2, 7.3)
            with ui.element("div").classes("expansion-content"):
                ui.label(f"Details for {pair.symbol}")
```

### Alternative: Custom Expansion

```python
def pair_row_expandable(pair: PairData) -> None:
    """Create expandable pair row."""
    is_expanded = state.expanded_pair == pair.symbol

    with ui.column().classes("pair-row-container"):
        # Main row
        with ui.row().classes("pair-row").on(
            "click",
            lambda: toggle_expansion(pair.symbol)
        ):
            # Expand icon
            icon = ui.icon("chevron_right").classes("expand-icon")
            if is_expanded:
                icon.classes(add="rotated")

            # Row content
            ui.label(pair.symbol)
            # ... other columns

        # Expansion panel
        if is_expanded:
            with ui.element("div").classes("expansion-panel"):
                # Content from Stories 7.2, 7.3
                pass
```

### CSS Styling

```css
.pair-expansion {
  margin: 0;
  border-radius: 0;
}

.pair-expansion .q-expansion-item__content {
  transition: max-height 200ms ease-in-out;
}

.expansion-content {
  padding: 16px;
  background-color: var(--bg-secondary);
}

.expand-icon {
  transition: transform 200ms ease-in-out;
}

.expand-icon.rotated {
  transform: rotate(90deg);
}
```

### State Addition

```python
# In dashboard/state.py
class DashboardState:
    def __init__(self):
        # ... existing ...
        self.expanded_pair: str | None = None
```

### Single Expansion Logic

Only one row expanded at a time:
- Clicking new row: close previous, open new
- Clicking same row: close it (toggle)

### Project Structure Notes

- Modifies: `dashboard/components/pairs_table.py`
- Modifies: `dashboard/state.py` (add expanded_pair)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-71-implement-row-expansion-toggle)
- [NiceGUI Expansion](https://nicegui.io/documentation#expansion)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

