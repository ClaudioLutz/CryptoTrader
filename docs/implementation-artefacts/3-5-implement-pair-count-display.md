# Story 3.5: Implement Pair Count Display

Status: review

## Story

As a **trader (Claudio)**,
I want **to see how many trading pairs are active**,
So that **I know all my pairs are running as expected**.

## Acceptance Criteria

1. **AC1:** Display shows active/expected pairs (e.g., "4/4 pairs")
2. **AC2:** If all pairs active, text is secondary color `#a0a0a0`
3. **AC3:** If fewer pairs active than expected, text turns amber `#ffc107`
4. **AC4:** Component also shows total open order count (e.g., "7 ord")
5. **AC5:** Values update when `DashboardState.pairs` changes

## Tasks / Subtasks

- [x] Task 1: Create pair count component (AC: 1)
  - [x] Enhanced _create_pair_count() in header.py
  - [x] Display expected pair count (hardcoded: 4)
  - [x] Format as "X/Y pairs"

- [x] Task 2: Implement color logic (AC: 2, 3)
  - [x] Secondary color (pair-count) when all active
  - [x] Amber (count-warning) when fewer than expected
  - [x] Expected count hardcoded for MVP

- [x] Task 3: Add order count display (AC: 4)
  - [x] Enhanced _create_order_count() in header.py
  - [x] Sum order_count from all pairs
  - [x] Display as "N ord"

- [x] Task 4: Bind to state (AC: 5)
  - [x] Connect to state.pair_count and state.pairs
  - [x] Recalculate counts on state change

## Dev Notes

### Pair Count Implementation

[Source: docs/planning-artefacts/epics.md - Story 3.5]

```python
"""CryptoTrader Dashboard - Pair Count Display Component.

Shows active pair count and total open orders in header.
"""

from nicegui import ui

from dashboard.config import config
from dashboard.state import state

# Expected pairs - could be in config or derived from bot
EXPECTED_PAIRS = 4  # Or get from config


def pair_count_display() -> None:
    """Create pair and order count display."""

    def get_active_pairs() -> int:
        return len(state.pairs)

    def get_total_orders() -> int:
        return sum(p.order_count for p in state.pairs)

    def get_pairs_color() -> str:
        active = get_active_pairs()
        if active >= EXPECTED_PAIRS:
            return "count-normal"
        return "count-warning"

    with ui.row().classes("counts-display items-center gap-4"):
        # Pairs count
        pairs_label = ui.label().classes("pairs-count")
        pairs_label.bind_text_from(
            state, "pairs",
            lambda _: f"{get_active_pairs()}/{EXPECTED_PAIRS} pairs"
        )

        # Order count
        orders_label = ui.label().classes("orders-count")
        orders_label.bind_text_from(
            state, "pairs",
            lambda _: f"{get_total_orders()} ord"
        )
```

### CSS Styling

```css
.counts-display {
  gap: 16px;
}

.pairs-count,
.orders-count {
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
  color: var(--text-secondary);
}

.count-normal {
  color: var(--text-secondary); /* #a0a0a0 */
}

.count-warning {
  color: var(--status-warning); /* #ffc107 */
}
```

### Display Format

| Condition | Pairs Display | Color |
|-----------|--------------|-------|
| All active (4/4) | "4/4 pairs" | `#a0a0a0` |
| Partial (3/4) | "3/4 pairs" | `#ffc107` |
| None (0/4) | "0/4 pairs" | `#ffc107` |

| Orders | Display |
|--------|---------|
| 7 total | "7 ord" |
| 0 total | "0 ord" |
| 15 total | "15 ord" |

### Expected Pairs Configuration

Options for determining expected pairs:
1. **Hardcoded:** Set `EXPECTED_PAIRS = 4` based on known setup
2. **Config:** Add to `DashboardConfig`
3. **Inferred:** Track maximum seen pairs during session

For MVP, hardcoded value is acceptable. Can be made configurable later.

### Integration with Header

Replace placeholders in header:

```python
from dashboard.components.pair_count import pair_count_display

# In header.py:
with ui.element("div").classes("header-slot counts-slot"):
    pair_count_display()
```

### Project Structure Notes

- File location: `dashboard/components/pair_count.py`
- Integrates with: `dashboard/components/header.py`
- Depends on: `dashboard/state.py`, `dashboard/config.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-35-implement-pair-count-display)
- [UX Design](docs/planning-artefacts/ux-design-specification.md#the-5-second-header-strip)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Enhanced _create_pair_count() with "X/Y pairs" format
- Expected pairs hardcoded to 4 for MVP (can be made configurable)
- Amber warning when fewer pairs active than expected
- Enhanced _create_order_count() to sum from all pairs
- Added count-warning CSS class for amber styling

### File List

- dashboard/components/header.py (modified)
- dashboard/assets/css/theme.css (modified)

