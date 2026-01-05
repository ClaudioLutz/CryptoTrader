# Story 9.2: Implement Trade History Table

Status: ready-for-dev

**Version:** v2.0

## Story

As a **trader (Claudio)**,
I want **to see a table of historical trades**,
So that **I can review execution details**.

## Acceptance Criteria

1. **AC1:** Table displays columns: Time, Pair, Side, Price, Amount, Fee, P&L
2. **AC2:** Trades are sorted newest first by default
3. **AC3:** Pagination is available for large datasets
4. **AC4:** Trade data comes from existing bot API endpoints

## Tasks / Subtasks

- [ ] Task 1: Define trade history data model
  - [ ] Include all required fields
  - [ ] Support pagination

- [ ] Task 2: Add API client method (AC: 4)
  - [ ] Fetch paginated trade history
  - [ ] Support sorting

- [ ] Task 3: Create history table component (AC: 1, 2)
  - [ ] Define columns
  - [ ] Sort by time descending

- [ ] Task 4: Implement pagination (AC: 3)
  - [ ] Page size selector
  - [ ] Page navigation
  - [ ] Total count display

## Dev Notes

### Trade History Data Model

```python
"""Trade history data models."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class HistoricalTrade(BaseModel):
    """Detailed trade record for history."""
    id: str
    timestamp: datetime
    symbol: str
    side: Literal["buy", "sell"]
    price: Decimal
    amount: Decimal
    fee: Decimal
    fee_currency: str
    pnl: Decimal | None = None  # May not be available for all trades


class TradeHistoryPage(BaseModel):
    """Paginated trade history response."""
    trades: list[HistoricalTrade]
    total: int
    page: int
    page_size: int
    total_pages: int
```

### API Client Method

```python
# In api_client.py
async def get_trade_history(
    self,
    page: int = 1,
    page_size: int = 20,
    symbol: str | None = None,
    side: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> TradeHistoryPage | None:
    """Fetch paginated trade history with filters."""
    try:
        params = {
            "page": page,
            "page_size": page_size,
        }
        if symbol:
            params["symbol"] = symbol
        if side:
            params["side"] = side
        if start_date:
            params["start"] = start_date.isoformat()
        if end_date:
            params["end"] = end_date.isoformat()

        response = await self._client.get("/trades/history", params=params)
        response.raise_for_status()
        return TradeHistoryPage.model_validate(response.json())
    except Exception as e:
        logger.error("Trade history fetch failed", error=str(e))
        return None
```

### Trade History Table Component

```python
"""Trade history table component."""

from nicegui import ui

from dashboard.state import state


COLUMNS = [
    {"name": "time", "label": "Time", "field": "time", "sortable": True},
    {"name": "pair", "label": "Pair", "field": "symbol", "sortable": True},
    {"name": "side", "label": "Side", "field": "side"},
    {"name": "price", "label": "Price", "field": "price", "sortable": True},
    {"name": "amount", "label": "Amount", "field": "amount"},
    {"name": "fee", "label": "Fee", "field": "fee"},
    {"name": "pnl", "label": "P&L", "field": "pnl"},
]


def trade_history_table() -> None:
    """Create trade history table with pagination."""
    # State for pagination
    page = 1
    page_size = 20

    def format_rows(trades: list) -> list[dict]:
        return [
            {
                "time": t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": t.symbol,
                "side": t.side.upper(),
                "side_class": "buy" if t.side == "buy" else "sell",
                "price": f"${t.price:,.2f}",
                "amount": str(t.amount),
                "fee": f"{t.fee} {t.fee_currency}",
                "pnl": f"€{t.pnl:,.2f}" if t.pnl else "-",
            }
            for t in trades
        ]

    table = ui.table(
        columns=COLUMNS,
        rows=[],
        row_key="time",
        pagination=page_size,
    ).classes("history-table")

    # Pagination controls
    with ui.row().classes("pagination-controls"):
        ui.button("Previous", on_click=lambda: load_page(page - 1))
        ui.label().bind_text_from(state, "history_page_info")
        ui.button("Next", on_click=lambda: load_page(page + 1))
```

### CSS Styling

```css
.history-table {
  width: 100%;
}

.history-table td.side.buy {
  color: var(--status-success);
}

.history-table td.side.sell {
  color: var(--status-error);
}

.history-table td.pnl {
  font-family: 'Roboto Mono', monospace;
}

.pagination-controls {
  justify-content: center;
  gap: 16px;
  padding: 16px;
}
```

### Project Structure Notes

- Creates: `dashboard/components/trade_history.py`
- Modifies: `dashboard/services/api_client.py`
- Modifies: `dashboard/services/data_models.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-92-implement-trade-history-table)
- [NiceGUI Table](https://nicegui.io/documentation#table)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

