"""CryptoTrader Dashboard - Pairs Table Component.

Displays all trading pairs in a compact table format with expandable row details.
Stories 4.1-4.3: Table structure, data display, hover state.
Stories 7.1-7.3: Row expansion toggle, order details, recent trades.
"""

from decimal import Decimal

from nicegui import ui

from dashboard.state import state
from dashboard.services.data_models import OrderData, TradeData


# Column definitions for the pairs table
COLUMNS = [
    {"name": "expand", "label": "", "field": "expand", "align": "center"},
    {"name": "symbol", "label": "Symbol", "field": "symbol", "align": "left"},
    {"name": "price", "label": "Price", "field": "price", "align": "right"},
    {"name": "pnl", "label": "P&L", "field": "pnl", "align": "right"},
    {"name": "position", "label": "Position", "field": "position", "align": "right"},
    {"name": "orders", "label": "Orders", "field": "orders", "align": "center"},
]


def format_price(price: Decimal, symbol: str) -> str:
    """Format price with appropriate precision based on magnitude.

    Args:
        price: The current price.
        symbol: Trading pair symbol (for context).

    Returns:
        Formatted price string with $ prefix and thousands separator.
    """
    if price >= 100:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    else:
        return f"${price:,.6f}"


def format_pnl(pnl: Decimal) -> tuple[str, str]:
    """Format P&L with sign and color class.

    Args:
        pnl: Profit/loss value.

    Returns:
        Tuple of (formatted_text, css_class).
    """
    if pnl > 0:
        return f"+\u20ac{pnl:.2f}", "pnl-positive"
    elif pnl < 0:
        return f"-\u20ac{abs(pnl):.2f}", "pnl-negative"
    else:
        return "\u20ac0.00", "pnl-neutral"


def format_position(size: Decimal, symbol: str) -> str:
    """Format position size with base asset symbol.

    Args:
        size: Position size.
        symbol: Trading pair symbol.

    Returns:
        Formatted position string with asset suffix.
    """
    base_asset = symbol.split("/")[0] if "/" in symbol else symbol
    return f"{size} {base_asset}"


def create_pairs_table() -> None:
    """Create the all-pairs table with expandable row details (Epic 7).

    Displays trading pairs with: Symbol, Price, P&L, Position, Orders.
    Clicking a row expands it to show order details and recent trades.
    """
    with ui.element("div").classes("pairs-table-container"):
        # Create expandable rows for each pair
        for pair in state.pairs:
            _create_pair_row(pair.symbol)


def _create_pair_row(symbol: str) -> None:
    """Create a single expandable pair row.

    Args:
        symbol: Trading pair symbol.
    """
    pair = next((p for p in state.pairs if p.symbol == symbol), None)
    if not pair:
        return

    pnl_text, pnl_class = format_pnl(pair.pnl_today)
    is_expanded = state.is_row_expanded(symbol)

    # Icon rotates when expanded (Story 7.1 AC5)
    expand_icon = "expand_more" if is_expanded else "chevron_right"

    with ui.expansion(
        text=symbol,
        icon=expand_icon,
        value=is_expanded,
    ).classes("pair-expansion").props("dense") as expansion:
        # Header content (custom slot)
        with expansion.add_slot("header"):
            with ui.row().classes("pair-row-header items-center w-full gap-4"):
                # Expand icon
                ui.icon(expand_icon).classes(
                    f"expand-icon {'rotated' if is_expanded else ''}"
                )
                # Symbol
                ui.label(symbol).classes("pair-symbol")
                # Price
                ui.label(format_price(pair.current_price, symbol)).classes(
                    "pair-price text-right"
                )
                # P&L
                ui.label(pnl_text).classes(f"pair-pnl {pnl_class} text-right")
                # Position
                ui.label(format_position(pair.position_size, symbol)).classes(
                    "pair-position text-right"
                )
                # Orders
                ui.label(str(pair.order_count)).classes("pair-orders text-center")

        # Expansion content - Order details and Recent trades (Stories 7.2, 7.3)
        with ui.element("div").classes("expansion-content"):
            _create_expansion_content(symbol)

        # Handle expansion toggle (Story 7.1 AC3, AC4)
        expansion.on_value_change(lambda e, s=symbol: _on_expansion_change(e, s))


async def _on_expansion_change(event, symbol: str) -> None:
    """Handle expansion toggle with on-demand data fetching.

    Args:
        event: NiceGUI value change event.
        symbol: Trading pair symbol.
    """
    if event.value:
        # Expanding - fetch data on demand (Story 7.2 AC4, Story 7.3 AC7)
        await state.refresh_orders(symbol)
        await state.refresh_trades(symbol, limit=5)
        state.expanded_rows.add(symbol)
    else:
        state.expanded_rows.discard(symbol)


def _create_expansion_content(symbol: str) -> None:
    """Create expansion panel content with order details and recent trades.

    Args:
        symbol: Trading pair symbol.
    """
    with ui.row().classes("expansion-grid gap-8 p-4"):
        # Order details section (Story 7.2)
        with ui.column().classes("order-details-section"):
            _create_order_details(symbol)

        # Recent trades section (Story 7.3)
        with ui.column().classes("trades-section"):
            _create_recent_trades(symbol)


def _create_order_details(symbol: str) -> None:
    """Create order details panel showing buy/sell counts and price range.

    Args:
        symbol: Trading pair symbol.
    """
    ui.label("Orders").classes("section-label")

    # Filter orders for this symbol
    symbol_orders = [o for o in state.orders if o.symbol == symbol]
    buy_orders = [o for o in symbol_orders if o.side == "buy"]
    sell_orders = [o for o in symbol_orders if o.side == "sell"]

    buy_count = len(buy_orders)
    sell_count = len(sell_orders)

    # Calculate price range (Story 7.2 AC3)
    lowest_buy = min((o.price for o in buy_orders), default=Decimal("0"))
    highest_sell = max((o.price for o in sell_orders), default=Decimal("0"))

    with ui.row().classes("order-summary gap-6"):
        # Buy orders count
        with ui.column().classes("order-group"):
            ui.label("Buy").classes("order-label text-xs")
            ui.label(str(buy_count)).classes("order-count buy-count")
            if lowest_buy > 0:
                ui.label(f"from ${lowest_buy:,.2f}").classes("price-range-text")

        # Sell orders count
        with ui.column().classes("order-group"):
            ui.label("Sell").classes("order-label text-xs")
            ui.label(str(sell_count)).classes("order-count sell-count")
            if highest_sell > 0:
                ui.label(f"up to ${highest_sell:,.2f}").classes("price-range-text")


def _create_recent_trades(symbol: str) -> None:
    """Create recent trades list showing last 5 trades.

    Args:
        symbol: Trading pair symbol.
    """
    ui.label("Recent Trades").classes("section-label")

    # Filter trades for this symbol and limit to 5 (Story 7.3 AC1)
    symbol_trades = [t for t in state.trades if t.symbol == symbol][:5]

    if not symbol_trades:
        ui.label("No recent trades").classes("text-tertiary text-sm")
        return

    with ui.column().classes("trades-list gap-1"):
        for trade in symbol_trades:
            _create_trade_row(trade)


def _create_trade_row(trade: TradeData) -> None:
    """Create a single trade row with direction, price, amount, timestamp.

    Args:
        trade: Trade data.
    """
    # Direction styling (Story 7.3 AC2, AC6)
    side_class = "trade-buy" if trade.side == "buy" else "trade-sell"
    side_icon = "arrow_upward" if trade.side == "buy" else "arrow_downward"

    with ui.row().classes(f"trade-row {side_class} items-center gap-3"):
        # Direction icon
        ui.icon(side_icon).classes("trade-icon text-sm")
        # Side label
        ui.label(trade.side.upper()).classes("trade-side")
        # Price (Story 7.3 AC3)
        ui.label(f"${trade.price:,.2f}").classes("trade-price")
        # Amount (Story 7.3 AC4)
        ui.label(f"{trade.amount}").classes("trade-amount")
        # Timestamp (Story 7.3 AC5)
        ui.label(trade.timestamp.strftime("%H:%M:%S")).classes("trade-time")


def create_pairs_table_placeholder() -> None:
    """Create a placeholder table when no data is available."""
    with ui.element("div").classes("pairs-table-container"):
        with ui.card().classes("pairs-table-empty"):
            ui.label("No trading pairs available").classes("text-secondary")
            ui.label("Waiting for data from trading bot...").classes(
                "text-tertiary text-sm"
            )
