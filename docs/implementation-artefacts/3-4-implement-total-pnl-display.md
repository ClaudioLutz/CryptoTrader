# Story 3.4: Implement Total P&L Display

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **to see my total profit/loss for today prominently displayed**,
So that **I immediately know if I'm up or down**.

## Acceptance Criteria

1. **AC1:** P&L shows format: sign + currency + value (e.g., `+€47.32`)
2. **AC2:** Positive P&L uses green color `#00c853` with `+` sign
3. **AC3:** Negative P&L uses red color `#ff5252` with `-` sign
4. **AC4:** Zero P&L uses gray color `#a0a0a0`
5. **AC5:** Typography is monospace (Roboto Mono)
6. **AC6:** Upward arrow `▲` accompanies positive, downward `▼` for negative
7. **AC7:** Value updates when `DashboardState.total_pnl` changes

## Tasks / Subtasks

- [ ] Task 1: Create P&L display component (AC: 1, 5)
  - [ ] Create `dashboard/components/pnl_display.py`
  - [ ] Format value with sign, currency, decimals
  - [ ] Apply monospace font

- [ ] Task 2: Implement color coding (AC: 2, 3, 4)
  - [ ] Green for positive
  - [ ] Red for negative
  - [ ] Gray for zero

- [ ] Task 3: Add direction arrows (AC: 6)
  - [ ] ▲ for positive
  - [ ] ▼ for negative
  - [ ] No arrow for zero

- [ ] Task 4: Bind to state (AC: 7)
  - [ ] Connect to `state.total_pnl`
  - [ ] Update display on state change

## Dev Notes

### P&L Display Implementation

[Source: docs/planning-artefacts/ux-design-specification.md - P&L Indicators]

```python
"""CryptoTrader Dashboard - P&L Display Component.

Displays profit/loss with color coding and direction indicators.
"""

from decimal import Decimal

from nicegui import ui

from dashboard.state import state

# Currency symbol - could move to config
CURRENCY_SYMBOL = "€"


def pnl_display() -> None:
    """Create P&L display with color coding and direction arrow."""

    def format_pnl(value: Decimal) -> str:
        """Format P&L with sign, currency, and 2 decimal places."""
        if value > 0:
            return f"+{CURRENCY_SYMBOL}{value:.2f}"
        elif value < 0:
            return f"-{CURRENCY_SYMBOL}{abs(value):.2f}"
        else:
            return f"{CURRENCY_SYMBOL}0.00"

    def get_arrow(value: Decimal) -> str:
        """Get direction arrow based on P&L value."""
        if value > 0:
            return " ▲"
        elif value < 0:
            return " ▼"
        return ""

    def get_color_class(value: Decimal) -> str:
        """Get CSS class for P&L color."""
        if value > 0:
            return "pnl-positive"
        elif value < 0:
            return "pnl-negative"
        return "pnl-zero"

    with ui.row().classes("pnl-display items-center"):
        # P&L value with arrow
        pnl_label = ui.label().classes("pnl-value")

        # Reactive binding with formatting
        def update_pnl():
            value = state.total_pnl
            pnl_label.text = format_pnl(value) + get_arrow(value)
            # Update color class
            pnl_label.classes(remove="pnl-positive pnl-negative pnl-zero")
            pnl_label.classes(add=get_color_class(value))

        # Bind to state changes
        pnl_label.bind_text_from(
            state, "total_pnl",
            lambda v: format_pnl(v) + get_arrow(v)
        )
```

### CSS Styling

```css
.pnl-display {
  padding: 4px 8px;
}

.pnl-value {
  font-family: 'Roboto Mono', monospace;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.pnl-positive {
  color: var(--status-success); /* #00c853 */
}

.pnl-negative {
  color: var(--status-error); /* #ff5252 */
}

.pnl-zero {
  color: var(--text-secondary); /* #a0a0a0 */
}
```

### P&L Format Examples

| Value | Display |
|-------|---------|
| 47.32 | `+€47.32 ▲` |
| -23.50 | `-€23.50 ▼` |
| 0.00 | `€0.00` |
| 1234.56 | `+€1234.56 ▲` |

### Number Formatting

[Source: docs/planning-artefacts/architecture.md - Format Patterns]

- **P&L:** `+€123.45` (sign + currency + 2 decimals)
- Use `Decimal` type for financial calculations
- Thousands separator optional for header (keep compact)

### Integration with Header

Replace placeholder in header P&L slot:

```python
from dashboard.components.pnl_display import pnl_display

# In header.py, P&L slot:
with ui.element("div").classes("header-slot pnl-slot"):
    pnl_display()
```

### Project Structure Notes

- File location: `dashboard/components/pnl_display.py`
- Integrates with: `dashboard/components/header.py`
- Depends on: `dashboard/state.py`

### References

- [UX Design](docs/planning-artefacts/ux-design-specification.md#p&l-indicators)
- [Architecture](docs/planning-artefacts/architecture.md#format-patterns)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

