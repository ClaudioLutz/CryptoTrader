# Fix Dashboard Order Count Display

## Summary
Fixed dashboard header to show accurate order count by fetching actual orders from exchange instead of relying on strategy statistics which may not include manually placed orders.

## Context / Problem
The dashboard header showed "3 ord" when there were actually 4 open orders (3 buys + 1 sell). This happened because:

1. The order count came from strategy stats (`active_buy_orders + active_sell_orders`)
2. Manually placed orders (outside the grid strategy) were not counted
3. The strategy's internal state didn't know about external orders

Additionally, the expanded pair view showed correct order counts (BUY: 3, SELL: 1) but the header total was wrong.

## What Changed
- **dashboard/components/header.py**: Modified `_create_order_count_content()` to prefer actual orders from `orders_by_symbol` cache over strategy stats
- **dashboard/state.py**: Modified `refresh_tier2()` to fetch orders for each pair during the periodic refresh, ensuring `orders_by_symbol` is populated

### Code Changes

**header.py** - Use actual orders when available:
```python
def _create_order_count_content() -> None:
    # Prefer actual orders from orders_by_symbol (fetched from exchange)
    total_from_orders = sum(len(orders) for orders in state.orders_by_symbol.values())
    if total_from_orders > 0:
        order_count = total_from_orders
    elif state.orders:
        order_count = len(state.orders)
    elif state.pairs:
        order_count = sum(p.order_count for p in state.pairs)
    else:
        order_count = 0
```

**state.py** - Fetch orders during tier 2 refresh:
```python
async def refresh_tier2(self) -> None:
    # Fetch orders for each pair to ensure accurate header count
    for pair in self.pairs:
        symbol = pair.symbol
        orders = await self._api_client.get_orders(symbol)
        self.orders_by_symbol[symbol] = orders
```

## How to Test
1. Restart the dashboard: `python -m dashboard.main`
2. Place a manual order on Binance that the bot doesn't know about
3. Refresh the dashboard - header should show correct total order count
4. Verify the expanded pair view also shows correct buy/sell breakdown

## Risk / Rollback Notes
- **Low risk**: Changes only affect display logic, not trading functionality
- **Performance**: Adds API calls to fetch orders every 5 seconds (tier 2 refresh)
- **Rollback**: Revert changes to header.py and state.py

## Known Limitation
The realized P&L showing €0.00 instead of previous €37.01 is a **data persistence issue**, not a display bug. Trades are fetched from the exchange API which only returns recent trades. Historical trades that contributed to the €37.01 profit are not persisted in the local database. This would require a larger architectural change to fix (storing all trades in the database).
