# Story 7.2: Display Order Details in Expansion

Status: review

**Version:** v1.5

## Story

As a **trader (Claudio)**,
I want **to see open orders for a pair in the expanded view**,
So that **I can understand the grid setup for that pair**.

## Acceptance Criteria

1. **AC1:** Expanded panel shows buy order count
2. **AC2:** Expanded panel shows sell order count
3. **AC3:** Expanded panel shows order price range (lowest buy to highest sell)
4. **AC4:** Orders are fetched on-demand (only when expanded)
5. **AC5:** Data uses the same formatting as the main table

## Tasks / Subtasks

- [x] Task 1: Add order details API method (AC: 4)
  - [x] Add `get_pair_orders(symbol)` to APIClient
  - [x] Define PairOrders data model

- [x] Task 2: Create order details component (AC: 1, 2, 3)
  - [x] Display buy order count
  - [x] Display sell order count
  - [x] Display price range

- [x] Task 3: Implement on-demand fetching (AC: 4)
  - [x] Fetch when row expands
  - [x] Cache results during session

- [x] Task 4: Apply formatting (AC: 5)
  - [x] Use same price formatting
  - [x] Monospace typography

## Dev Notes

### Order Details Data Model

```python
"""Order details model for expansion panel."""

from decimal import Decimal
from pydantic import BaseModel


class OrderSummary(BaseModel):
    """Summary of orders for a trading pair."""
    symbol: str
    buy_count: int
    sell_count: int
    lowest_buy: Decimal
    highest_sell: Decimal
```

### API Client Addition

```python
# In api_client.py
async def get_pair_orders(self, symbol: str) -> OrderSummary | None:
    """Fetch order summary for a specific pair."""
    try:
        response = await self._client.get(f"/orders/{symbol}")
        response.raise_for_status()
        return OrderSummary.model_validate(response.json())
    except Exception as e:
        logger.error("Order fetch failed", symbol=symbol, error=str(e))
        return None
```

### Expansion Content Component

```python
"""Order details in expansion panel."""

from nicegui import ui

from dashboard.services.api_client import api_client
from dashboard.services.data_models import OrderSummary


async def order_details_panel(symbol: str) -> None:
    """Display order details for a trading pair."""
    # Fetch on-demand
    orders = await api_client.get_pair_orders(symbol)

    if orders is None:
        ui.label("Unable to load order details").classes("error-text")
        return

    with ui.row().classes("order-details gap-8"):
        # Buy orders
        with ui.column().classes("order-section"):
            ui.label("Buy Orders").classes("section-label")
            ui.label(str(orders.buy_count)).classes("order-count buy-count")
            ui.label(f"from ${orders.lowest_buy:,.2f}").classes("price-range")

        # Sell orders
        with ui.column().classes("order-section"):
            ui.label("Sell Orders").classes("section-label")
            ui.label(str(orders.sell_count)).classes("order-count sell-count")
            ui.label(f"up to ${orders.highest_sell:,.2f}").classes("price-range")
```

### CSS Styling

```css
.order-details {
  padding: 16px;
  background-color: var(--bg-secondary);
}

.order-section {
  min-width: 120px;
}

.section-label {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.order-count {
  font-family: 'Roboto Mono', monospace;
  font-size: 24px;
  font-weight: 600;
}

.buy-count {
  color: var(--status-success);
}

.sell-count {
  color: var(--status-error);
}

.price-range {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  color: var(--text-secondary);
}
```

### On-Demand Fetching

Orders are only fetched when the row is expanded:

```python
def pair_expansion(pair: PairData) -> None:
    with ui.expansion(pair.symbol) as expansion:
        @expansion.on_value_change
        async def on_expand(e):
            if e.value:  # Expanding
                await order_details_panel(pair.symbol)
```

### Caching Strategy

For v1.5, simple session-level caching:
```python
_order_cache: dict[str, OrderSummary] = {}

async def get_cached_orders(symbol: str) -> OrderSummary | None:
    if symbol not in _order_cache:
        _order_cache[symbol] = await api_client.get_pair_orders(symbol)
    return _order_cache.get(symbol)
```

### Project Structure Notes

- Modifies: `dashboard/services/api_client.py`
- Creates: `dashboard/components/order_details.py`
- Modifies: `dashboard/components/pairs_table.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-72-display-order-details-in-expansion)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Used existing get_orders(symbol) API method via state.refresh_orders()
- Created _create_order_details() component showing buy/sell counts
- Calculates lowest buy and highest sell price range from orders
- On-demand fetching in _on_expansion_change handler
- Monospace typography with color-coded counts (green buy, red sell)

### File List

- dashboard/components/pairs_table.py (modified)
- dashboard/assets/css/theme.css (modified)

