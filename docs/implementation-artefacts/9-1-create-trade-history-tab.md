# Story 9.1: Create Trade History Tab

Status: ready-for-dev

**Version:** v2.0

## Story

As a **trader (Claudio)**,
I want **a dedicated area for viewing trade history**,
So that **I can review past trades without cluttering the main view**.

## Acceptance Criteria

1. **AC1:** Tab or collapsible section added for "Trade History"
2. **AC2:** Main dashboard view remains unchanged when history is hidden
3. **AC3:** Tab navigation uses NiceGUI's built-in tab components

## Tasks / Subtasks

- [ ] Task 1: Implement tab navigation (AC: 1, 3)
  - [ ] Add tabs container to main layout
  - [ ] Create "Dashboard" tab (existing content)
  - [ ] Create "Trade History" tab

- [ ] Task 2: Preserve main view (AC: 2)
  - [ ] Dashboard tab contains header, table, chart
  - [ ] History tab separate content area

- [ ] Task 3: Style tabs for dark theme
  - [ ] Apply theme colors
  - [ ] Active tab indicator

## Dev Notes

### Tab Implementation

```python
"""Tab navigation for dashboard."""

from nicegui import ui


def dashboard_layout() -> None:
    """Main dashboard layout with tabs."""
    with ui.tabs().classes("dashboard-tabs") as tabs:
        dashboard_tab = ui.tab("Dashboard", icon="dashboard")
        history_tab = ui.tab("Trade History", icon="history")

    with ui.tab_panels(tabs, value=dashboard_tab).classes("tab-panels"):
        with ui.tab_panel(dashboard_tab):
            # Existing dashboard content
            header()
            pairs_table()
            price_chart()

        with ui.tab_panel(history_tab):
            # Trade history content (Stories 9.2, 9.3)
            trade_history_view()
```

### CSS Styling

```css
.dashboard-tabs {
  background-color: var(--bg-secondary);
}

.dashboard-tabs .q-tab {
  color: var(--text-secondary);
}

.dashboard-tabs .q-tab--active {
  color: var(--accent);
}

.tab-panels {
  background-color: transparent;
}

.tab-panels .q-tab-panel {
  padding: 0;
}
```

### Alternative: Collapsible Section

```python
def dashboard_with_collapsible() -> None:
    """Dashboard with collapsible history section."""
    # Main content
    header()
    pairs_table()
    price_chart()

    # Collapsible history
    with ui.expansion("Trade History", icon="history").classes("history-expansion"):
        trade_history_view()
```

### Layout Considerations

Tabs are preferred for v2.0 because:
- Clear separation of concerns
- History doesn't push content down
- Familiar navigation pattern

### Project Structure Notes

- Modifies: `dashboard/main.py`
- Creates: `dashboard/components/trade_history.py` (in Story 9.2)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-91-create-trade-history-tab)
- [NiceGUI Tabs](https://nicegui.io/documentation#tabs)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

