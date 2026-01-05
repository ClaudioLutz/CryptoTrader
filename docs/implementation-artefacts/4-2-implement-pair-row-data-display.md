# Story 4.2: Implement Pair Row Data Display

Status: ready-for-dev

## Story

As a **trader (Claudio)**,
I want **each pair row to show key metrics**,
So that **I can quickly assess each pair's status**.

## Acceptance Criteria

1. **AC1:** Symbol displays trading pair name (e.g., "BTC/USDT") in primary text color
2. **AC2:** Price displays current price with appropriate decimal precision (e.g., $97,234.12)
3. **AC3:** P&L displays per-pair P&L with color coding (green/red) and sign
4. **AC4:** Position displays current position size (e.g., "0.15 BTC")
5. **AC5:** Orders displays open order count (e.g., "15")
6. **AC6:** All numerical values use monospace font
7. **AC7:** Prices include thousands separator for readability
8. **AC8:** P&L shows currency symbol (EUR)

## Tasks / Subtasks

- [ ] Task 1: Enhance symbol display (AC: 1)
  - [ ] Primary text color
  - [ ] Bold or medium weight

- [ ] Task 2: Format price display (AC: 2, 7)
  - [ ] Currency symbol ($)
  - [ ] Thousands separator
  - [ ] Appropriate decimal precision per symbol

- [ ] Task 3: Format P&L display (AC: 3, 8)
  - [ ] Color coding (green/red)
  - [ ] Sign prefix (+/-)
  - [ ] Currency symbol (€)
  - [ ] 2 decimal places

- [ ] Task 4: Format position display (AC: 4)
  - [ ] Asset amount with symbol
  - [ ] Appropriate decimal precision

- [ ] Task 5: Apply monospace styling (AC: 5, 6)
  - [ ] Roboto Mono for all numbers
  - [ ] Consistent alignment

## Dev Notes

### Row Data Formatting

[Source: docs/planning-artefacts/architecture.md - Format Patterns]

```python
"""Enhanced row formatting for pairs table."""

from decimal import Decimal

from dashboard.services.data_models import PairData


def format_price(price: Decimal, symbol: str) -> str:
    """Format price with appropriate precision.

    BTC, ETH: 2 decimals (e.g., $97,234.12)
    XRP, others: 4 decimals (e.g., $0.6234)
    """
    # Determine precision based on price magnitude
    if price >= 100:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    else:
        return f"${price:,.6f}"


def format_pnl(pnl: Decimal) -> tuple[str, str]:
    """Format P&L with sign and return (text, css_class).

    Returns:
        Tuple of (formatted_text, css_class)
    """
    if pnl > 0:
        return f"+€{pnl:.2f}", "pnl-positive"
    elif pnl < 0:
        return f"-€{abs(pnl):.2f}", "pnl-negative"
    else:
        return "€0.00", "pnl-zero"


def format_position(size: Decimal, symbol: str) -> str:
    """Format position size with asset symbol.

    Extracts base asset from pair symbol (e.g., BTC from BTC/USDT)
    """
    base_asset = symbol.split("/")[0] if "/" in symbol else symbol
    return f"{size} {base_asset}"


def format_orders(count: int) -> str:
    """Format order count."""
    return str(count)
```

### CSS Classes for Formatting

```css
/* Symbol column */
.pairs-table td.symbol {
  color: var(--text-primary);
  font-weight: 500;
}

/* Price column */
.pairs-table td.price {
  font-family: 'Roboto Mono', monospace;
  text-align: right;
}

/* P&L column */
.pairs-table td.pnl {
  font-family: 'Roboto Mono', monospace;
  text-align: right;
}

.pnl-positive { color: var(--status-success); }
.pnl-negative { color: var(--status-error); }
.pnl-zero { color: var(--text-secondary); }

/* Position column */
.pairs-table td.position {
  font-family: 'Roboto Mono', monospace;
  text-align: right;
}

/* Orders column */
.pairs-table td.orders {
  font-family: 'Roboto Mono', monospace;
  text-align: center;
}
```

### Price Precision by Asset

| Asset | Price Range | Precision | Example |
|-------|-------------|-----------|---------|
| BTC | >$10,000 | 2 decimals | $97,234.12 |
| ETH | >$1,000 | 2 decimals | $3,456.78 |
| XRP | <$1 | 4 decimals | $0.6234 |
| Memecoins | <$0.01 | 6 decimals | $0.000012 |

### Integration with Table Component

Update `pairs_table.py` from Story 4.1:

```python
def get_rows() -> list[dict]:
    return [
        {
            "symbol": pair.symbol,
            "price": format_price(pair.current_price, pair.symbol),
            "pnl": format_pnl(pair.pnl_today)[0],
            "pnl_class": format_pnl(pair.pnl_today)[1],
            "position": format_position(pair.position_size, pair.symbol),
            "orders": format_orders(pair.order_count),
        }
        for pair in state.pairs
    ]
```

### Project Structure Notes

- Modifies: `dashboard/components/pairs_table.py`
- Add helpers to: `dashboard/services/formatters.py` (optional)

### References

- [Architecture](docs/planning-artefacts/architecture.md#format-patterns)
- [Epics Document](docs/planning-artefacts/epics.md#story-42-implement-pair-row-data-display)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

