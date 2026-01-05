# Story 7.3: Display Recent Trades in Expansion

Status: review

**Version:** v1.5

## Story

As a **trader (Claudio)**,
I want **to see recent trades for a pair**,
So that **I can understand recent trading activity**.

## Acceptance Criteria

1. **AC1:** Expanded panel shows last 5 trades
2. **AC2:** Each trade shows direction (buy/sell)
3. **AC3:** Each trade shows price
4. **AC4:** Each trade shows amount
5. **AC5:** Each trade shows timestamp
6. **AC6:** Buys are shown in green, sells in red
7. **AC7:** Trade data is fetched on-demand

## Tasks / Subtasks

- [x] Task 1: Add trades API method (AC: 7)
  - [x] Add `get_pair_trades(symbol, limit)` to APIClient
  - [x] Define Trade data model

- [x] Task 2: Create trades list component (AC: 1-5)
  - [x] Display trade direction
  - [x] Display trade price
  - [x] Display trade amount
  - [x] Display trade timestamp
  - [x] Limit to 5 trades

- [x] Task 3: Apply color coding (AC: 6)
  - [x] Green for buys
  - [x] Red for sells

- [x] Task 4: Integrate with expansion panel (AC: 7)
  - [x] Fetch when expanded
  - [x] Show alongside order details

## Dev Notes

### Trade Data Model

```python
"""Trade model for expansion panel."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class Trade(BaseModel):
    """Individual trade record."""
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    price: Decimal
    amount: Decimal
    timestamp: datetime
```

### API Client Addition

```python
# In api_client.py
async def get_pair_trades(
    self,
    symbol: str,
    limit: int = 5
) -> list[Trade]:
    """Fetch recent trades for a specific pair."""
    try:
        response = await self._client.get(
            f"/trades/{symbol}",
            params={"limit": limit}
        )
        response.raise_for_status()
        data = response.json()
        return [Trade.model_validate(t) for t in data]
    except Exception as e:
        logger.error("Trades fetch failed", symbol=symbol, error=str(e))
        return []
```

### Recent Trades Component

```python
"""Recent trades list in expansion panel."""

from nicegui import ui

from dashboard.services.api_client import api_client
from dashboard.services.data_models import Trade


async def recent_trades_panel(symbol: str) -> None:
    """Display recent trades for a trading pair."""
    trades = await api_client.get_pair_trades(symbol, limit=5)

    if not trades:
        ui.label("No recent trades").classes("text-secondary")
        return

    ui.label("Recent Trades").classes("section-label")

    with ui.column().classes("trades-list"):
        for trade in trades:
            trade_row(trade)


def trade_row(trade: Trade) -> None:
    """Display single trade row."""
    side_class = "trade-buy" if trade.side == "buy" else "trade-sell"
    side_icon = "arrow_upward" if trade.side == "buy" else "arrow_downward"

    with ui.row().classes(f"trade-row {side_class}"):
        ui.icon(side_icon).classes("trade-icon")
        ui.label(trade.side.upper()).classes("trade-side")
        ui.label(f"${trade.price:,.2f}").classes("trade-price")
        ui.label(f"{trade.amount}").classes("trade-amount")
        ui.label(trade.timestamp.strftime("%H:%M:%S")).classes("trade-time")
```

### CSS Styling

```css
.trades-list {
  gap: 4px;
  margin-top: 8px;
}

.trade-row {
  padding: 8px 12px;
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  align-items: center;
  gap: 12px;
}

.trade-buy {
  border-left: 3px solid var(--status-success);
}

.trade-buy .trade-icon,
.trade-buy .trade-side {
  color: var(--status-success);
}

.trade-sell {
  border-left: 3px solid var(--status-error);
}

.trade-sell .trade-icon,
.trade-sell .trade-side {
  color: var(--status-error);
}

.trade-side {
  font-weight: 600;
  font-size: 11px;
  width: 40px;
}

.trade-price,
.trade-amount,
.trade-time {
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
}

.trade-time {
  color: var(--text-secondary);
  margin-left: auto;
}
```

### Integration with Expansion Panel

```python
async def expansion_content(symbol: str) -> None:
    """Full expansion panel content."""
    with ui.row().classes("expansion-content gap-8"):
        # Order summary (Story 7.2)
        with ui.column().classes("orders-section"):
            await order_details_panel(symbol)

        # Recent trades (this story)
        with ui.column().classes("trades-section"):
            await recent_trades_panel(symbol)
```

### Visual Layout

```
┌─────────────────────────────────────────────────────────────┐
│ BTC/USDT                                              [▼]  │
├─────────────────────────────────────────────────────────────┤
│  Buy Orders    Sell Orders     │  Recent Trades            │
│  ───────────   ───────────     │  ────────────────────────  │
│     15             12          │  ▲ BUY  $97,234 0.01 14:32 │
│  from $96,000   up to $98,500  │  ▼ SELL $97,250 0.02 14:28 │
│                                │  ▲ BUY  $97,100 0.01 14:15 │
│                                │  ▼ SELL $97,300 0.01 14:10 │
│                                │  ▲ BUY  $97,050 0.03 14:05 │
└─────────────────────────────────────────────────────────────┘
```

### Project Structure Notes

- Modifies: `dashboard/services/api_client.py`
- Creates: `dashboard/components/recent_trades.py`
- Modifies: `dashboard/components/pairs_table.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-73-display-recent-trades-in-expansion)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Used existing get_trades(symbol, limit) API method via state.refresh_trades()
- Created _create_recent_trades() showing last 5 trades per symbol
- Each trade row shows: direction icon, side label, price, amount, timestamp
- Color coding: green border/text for buys, red for sells
- On-demand fetching when row expands via _on_expansion_change handler

### File List

- dashboard/components/pairs_table.py (modified)
- dashboard/assets/css/theme.css (modified)

