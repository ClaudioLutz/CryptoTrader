# Story 4.1: Create Pairs Table Component

Status: review

## Story

As a **trader (Claudio)**,
I want **to see all my trading pairs in a single table**,
So that **I can compare performance across pairs at a glance**.

## Acceptance Criteria

1. **AC1:** Table displays all 4-5 trading pairs
2. **AC2:** Each row is approximately 40px tall (compact density)
3. **AC3:** All rows are visible without scrolling the table itself
4. **AC4:** Table has dark theme styling matching `#0f3460` surface color
5. **AC5:** Table is positioned below the header strip
6. **AC6:** Column headers are: Symbol, Price, P&L, Position, Orders

## Tasks / Subtasks

- [x] Task 1: Create pairs table component (AC: 1, 5)
  - [x] Create `dashboard/components/pairs_table.py`
  - [x] Position below header strip via main.py
  - [x] Iterate over `state.pairs` to create rows

- [x] Task 2: Define table structure (AC: 6)
  - [x] Create column headers (COLUMNS constant)
  - [x] Symbol column (left aligned)
  - [x] Price column (right aligned)
  - [x] P&L column (right aligned)
  - [x] Position column (right aligned)
  - [x] Orders column (center aligned)

- [x] Task 3: Apply compact styling (AC: 2, 3, 4)
  - [x] Set row height to 40px via CSS
  - [x] Apply dark theme colors (#0f3460 surface)
  - [x] Hide pagination (not needed for 4-5 rows)

- [x] Task 4: Bind to state (AC: 1)
  - [x] Connect to `state.pairs`
  - [x] Update table via get_rows() function

## Dev Notes

### Pairs Table Implementation

[Source: docs/planning-artefacts/ux-design-specification.md - Component Strategy]

```python
"""CryptoTrader Dashboard - Pairs Table Component.

Displays all trading pairs in a compact table format.
"""

from nicegui import ui

from dashboard.state import state


COLUMNS = [
    {"name": "symbol", "label": "Symbol", "field": "symbol", "align": "left"},
    {"name": "price", "label": "Price", "field": "price", "align": "right"},
    {"name": "pnl", "label": "P&L", "field": "pnl", "align": "right"},
    {"name": "position", "label": "Position", "field": "position", "align": "right"},
    {"name": "orders", "label": "Orders", "field": "orders", "align": "center"},
]


def pairs_table() -> None:
    """Create the all-pairs table with compact rows."""

    def get_rows() -> list[dict]:
        """Convert state pairs to table row format."""
        return [
            {
                "symbol": pair.symbol,
                "price": f"${pair.current_price:,.2f}",
                "pnl": f"{'+' if pair.pnl_today >= 0 else ''}{pair.pnl_today:.2f}",
                "position": f"{pair.position_size}",
                "orders": str(pair.order_count),
            }
            for pair in state.pairs
        ]

    with ui.element("div").classes("pairs-table-container"):
        table = ui.table(
            columns=COLUMNS,
            rows=get_rows(),
            row_key="symbol",
        ).classes("pairs-table")

        # Bind rows to state
        table.bind_rows_from(state, "pairs", lambda pairs: [
            {
                "symbol": p.symbol,
                "price": f"${p.current_price:,.2f}",
                "pnl": f"{'+' if p.pnl_today >= 0 else ''}{p.pnl_today:.2f}",
                "position": f"{p.position_size}",
                "orders": str(p.order_count),
            }
            for p in pairs
        ])
```

### CSS Styling

```css
.pairs-table-container {
  margin-top: 16px;
  padding: 0 16px;
}

.pairs-table {
  width: 100%;
  background-color: var(--surface); /* #0f3460 */
}

.pairs-table .q-table__top,
.pairs-table .q-table__bottom {
  display: none; /* Hide pagination, etc. */
}

.pairs-table tbody tr {
  height: 40px;
}

.pairs-table th {
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
}

.pairs-table td {
  font-family: 'Roboto Mono', monospace;
  font-size: 14px;
  color: var(--text-primary);
}
```

### Table Layout

```
┌──────────┬────────────┬──────────┬──────────┬────────┐
│ Symbol   │ Price      │ P&L      │ Position │ Orders │
├──────────┼────────────┼──────────┼──────────┼────────┤
│ BTC/USDT │ $97,234.12 │ +€23.45  │ 0.15     │ 15     │
│ ETH/USDT │ $3,456.78  │ +€12.30  │ 2.5      │ 12     │
│ XRP/USDT │ $0.6234    │ -€5.20   │ 1000     │ 8      │
│ SOL/USDT │ $123.45    │ +€8.90   │ 10       │ 10     │
└──────────┴────────────┴──────────┴──────────┴────────┘
```

### NiceGUI Table Options

Consider using `ui.aggrid()` for more advanced features:
- Better performance with large datasets
- Built-in row selection
- Column resizing

For MVP with 4-5 rows, `ui.table()` is sufficient.

### Project Structure Notes

- File location: `dashboard/components/pairs_table.py`
- Integrates with: `dashboard/main.py`
- Depends on: `dashboard/state.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-41-create-pairs-table-component)
- [UX Design](docs/planning-artefacts/ux-design-specification.md#component-strategy)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created dashboard/components/pairs_table.py with create_pairs_table()
- Table uses NiceGUI ui.table() with COLUMNS constant
- Rows display: Symbol, Price, P&L, Position, Orders
- CSS styles added to theme.css: .pairs-table-container, .pairs-table
- Table positioned below header via main.py integration
- Used flat/bordered/dense props to hide pagination

### File List

- dashboard/components/pairs_table.py (created)
- dashboard/assets/css/theme.css (modified)
- dashboard/main.py (modified)

