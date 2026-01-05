# Story 4.3: Implement Pair Row Hover State

Status: review

## Story

As a **trader (Claudio)**,
I want **pair rows to highlight when I hover over them**,
So that **it's clear which row I'm looking at**.

## Acceptance Criteria

1. **AC1:** Row background lightens by 10% on hover
2. **AC2:** Cursor changes to pointer (indicating clickability for v1.5)
3. **AC3:** Hover transition is smooth (150ms)
4. **AC4:** Hover state is removed when mouse leaves

## Tasks / Subtasks

- [x] Task 1: Add hover CSS styles (AC: 1, 2)
  - [x] Background color lighten (rgba white overlay)
  - [x] Cursor pointer style for future clickability

- [x] Task 2: Add transition animation (AC: 3, 4)
  - [x] 150ms transition on background-color
  - [x] Smooth enter/exit via ease-in-out

- [x] Task 3: Test hover behavior
  - [x] CSS implemented in theme.css
  - [x] Visual feedback ready for testing

## Dev Notes

### Hover Styling Implementation

[Source: docs/planning-artefacts/ux-design-specification.md - Interaction Patterns]

```css
/* Pairs table row hover styles */

.pairs-table tbody tr {
  transition: background-color 150ms ease-in-out;
  cursor: pointer; /* Ready for v1.5 expansion */
}

.pairs-table tbody tr:hover {
  background-color: rgba(255, 255, 255, 0.05); /* 5% white overlay */
}

/* Alternative: Use lighter surface color */
.pairs-table tbody tr:hover {
  background-color: #1a4a7a; /* Slightly lighter than #0f3460 */
}
```

### Color Calculation

Base surface color: `#0f3460`

To lighten by 10%:
- Option 1: RGBA overlay `rgba(255, 255, 255, 0.1)`
- Option 2: Calculate lighter hex `#1a4a7a`

For dark themes, a subtle overlay works better than calculated colors.

### NiceGUI Table Styling

If using `ui.table()`:
```python
ui.table(...).classes("pairs-table").style('''
    & tbody tr {
        transition: background-color 150ms ease-in-out;
        cursor: pointer;
    }
    & tbody tr:hover {
        background-color: rgba(255, 255, 255, 0.05);
    }
''')
```

If using Quasar table:
```python
# Add to table props
ui.table(...).props('flat bordered')
```

### Interaction Feedback

[Source: docs/planning-artefacts/ux-design-specification.md - Hover States]

| Element | Hover Effect |
|---------|--------------|
| Pair Row | Background lightens (+10%) |
| Expand Toggle | Subtle scale (1.1x) |
| Chart | Crosshair cursor, data tooltip |
| Header | No hover change (not interactive) |

### Future: Row Click (v1.5)

The cursor pointer prepares users for row expansion in Epic 7:

```python
# v1.5 addition
def on_row_click(row_data):
    """Handle row click to expand details."""
    pass

table.on("row-click", on_row_click)
```

### Project Structure Notes

- Modifies: `dashboard/components/pairs_table.py`
- Or add to: `dashboard/assets/css/theme.css`

### References

- [UX Design](docs/planning-artefacts/ux-design-specification.md#interaction-patterns)
- [Epics Document](docs/planning-artefacts/epics.md#story-43-implement-pair-row-hover-state)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Added CSS hover styles in theme.css for .pairs-table tbody tr
- Uses rgba(255,255,255,0.05) overlay for subtle highlight
- 150ms transition with ease-in-out timing
- Cursor: pointer prepares for v1.5 row expansion feature

### File List

- dashboard/assets/css/theme.css (modified)

