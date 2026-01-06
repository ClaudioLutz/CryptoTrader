"""CryptoTrader Dashboard - Pairs Table Component.

Displays all trading pairs in a compact table format with expandable row details.
Stories 4.1-4.3: Table structure, data display, hover state.
Stories 7.1-7.3: Row expansion toggle, order details, recent trades.
Includes mini price chart inside each card for better visualization.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import plotly.graph_objects as go
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
    Clicking a row expands it to show order details, mini chart, and recent trades.
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

    # Get order counts for this specific pair
    symbol_orders = [o for o in state.orders if o.symbol == symbol]
    order_count = len(symbol_orders)

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
                # Orders count for this pair specifically
                ui.label(str(order_count)).classes("pair-orders text-center")

        # Expansion content - Orders, Chart, and Recent trades
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
        await state.refresh_trades(symbol, limit=10)
        await state.refresh_ohlcv(symbol, timeframe="1h", limit=48)
        state.expanded_rows.add(symbol)
    else:
        state.expanded_rows.discard(symbol)


def _create_expansion_content(symbol: str) -> None:
    """Create expansion panel content with orders, mini chart, and recent trades.

    Uses a 3-column layout to better utilize horizontal space:
    [Orders] | [Mini Price Chart] | [Recent Trades]

    Args:
        symbol: Trading pair symbol.
    """
    with ui.row().classes("expansion-grid-3col w-full gap-4"):
        # Left column: Order details section (Story 7.2)
        with ui.column().classes("order-details-section"):
            _create_order_details(symbol)

        # Center column: Mini price chart with trade markers
        with ui.column().classes("mini-chart-section flex-grow"):
            _create_mini_chart(symbol)

        # Right column: Recent trades section (Story 7.3)
        with ui.column().classes("trades-section"):
            _create_recent_trades(symbol)


def _create_mini_chart(symbol: str) -> None:
    """Create a mini price chart for the trading pair with trade markers.

    Args:
        symbol: Trading pair symbol.
    """
    # Get OHLCV data for this symbol
    ohlcv_data = state.ohlcv if state.ohlcv else []

    # Get trades for this symbol
    symbol_trades = [t for t in state.trades if t.symbol == symbol]

    # Create the mini chart figure
    fig = _create_mini_figure(symbol, ohlcv_data, symbol_trades)

    # Create the chart
    chart = ui.plotly(fig).classes("mini-price-chart")
    chart._props["config"] = {
        "scrollZoom": False,
        "displayModeBar": False,
        "displaylogo": False,
        "responsive": True,
        "staticPlot": False,
    }


def _create_mini_figure(
    symbol: str,
    ohlcv_data: list[dict[str, Any]],
    trades: list[TradeData],
) -> go.Figure:
    """Create a mini Plotly figure for the pair card.

    Args:
        symbol: Trading pair symbol.
        ohlcv_data: OHLCV candlestick data.
        trades: Trade data for markers.

    Returns:
        Configured Plotly figure.
    """
    fig = go.Figure()

    # Extract price data
    if ohlcv_data:
        timestamps = [d.get("timestamp", d.get("time")) for d in ohlcv_data]
        closes = [float(d.get("close", d.get("price", 0))) for d in ohlcv_data]
    else:
        # Generate sample data if no OHLCV available
        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(hours=i) for i in range(48, 0, -1)]
        closes = [97000.0] * 48  # Placeholder

    # Add price line
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=closes,
        mode="lines",
        name="Price",
        line=dict(color="#4a9eff", width=1.5),
        hovertemplate="$%{y:,.2f}<extra></extra>",
    ))

    # Calculate y-axis range to include both prices and trade markers
    all_prices = list(closes)
    if trades:
        trade_prices = [float(t.price) for t in trades]
        all_prices.extend(trade_prices)

    if all_prices:
        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price
        # Add 5% padding
        y_min = min_price - price_range * 0.05
        y_max = max_price + price_range * 0.05
    else:
        y_min = None
        y_max = None

    # Add trade markers
    if trades:
        buys = [t for t in trades if t.side.lower() == "buy"]
        sells = [t for t in trades if t.side.lower() == "sell"]

        if buys:
            fig.add_trace(go.Scatter(
                x=[t.timestamp for t in buys],
                y=[float(t.price) for t in buys],
                mode="markers",
                name="Buy",
                marker=dict(
                    symbol="triangle-up",
                    size=8,
                    color="#00c853",
                ),
                hovertemplate="BUY $%{y:,.2f}<extra></extra>",
            ))

        if sells:
            fig.add_trace(go.Scatter(
                x=[t.timestamp for t in sells],
                y=[float(t.price) for t in sells],
                mode="markers",
                name="Sell",
                marker=dict(
                    symbol="triangle-down",
                    size=8,
                    color="#ff5252",
                ),
                hovertemplate="SELL $%{y:,.2f}<extra></extra>",
            ))

    # Compact layout for mini chart
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=150,
        margin=dict(l=45, r=10, t=5, b=25),
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickfont=dict(color="#6b7280", size=9),
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(15, 52, 96, 0.5)",
            tickfont=dict(color="#6b7280", size=9),
            fixedrange=True,
            range=[y_min, y_max] if y_min is not None else None,
        ),
        hovermode="x unified",
    )

    return fig


def _create_order_details(symbol: str) -> None:
    """Create order details panel showing buy/sell counts and price range.

    Args:
        symbol: Trading pair symbol.
    """
    ui.label("ORDERS").classes("section-label")

    # Filter orders for this symbol
    symbol_orders = [o for o in state.orders if o.symbol == symbol]
    buy_orders = [o for o in symbol_orders if o.side.lower() == "buy"]
    sell_orders = [o for o in symbol_orders if o.side.lower() == "sell"]

    buy_count = len(buy_orders)
    sell_count = len(sell_orders)

    # Calculate price range (Story 7.2 AC3)
    lowest_buy = min((o.price for o in buy_orders), default=Decimal("0"))
    highest_sell = max((o.price for o in sell_orders), default=Decimal("0"))

    with ui.row().classes("order-summary gap-6"):
        # Buy orders count
        with ui.column().classes("order-group"):
            ui.label("BUY").classes("order-label text-xs")
            ui.label(str(buy_count)).classes("order-count buy-count")
            if lowest_buy > 0:
                ui.label(f"from ${lowest_buy:,.2f}").classes("price-range-text")

        # Sell orders count
        with ui.column().classes("order-group"):
            ui.label("SELL").classes("order-label text-xs")
            ui.label(str(sell_count)).classes("order-count sell-count")
            if highest_sell > 0:
                ui.label(f"up to ${highest_sell:,.2f}").classes("price-range-text")


def _create_recent_trades(symbol: str) -> None:
    """Create recent trades list showing last 5 trades.

    Args:
        symbol: Trading pair symbol.
    """
    ui.label("RECENT TRADES").classes("section-label")

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
    side_class = "trade-buy" if trade.side.lower() == "buy" else "trade-sell"
    side_icon = "arrow_upward" if trade.side.lower() == "buy" else "arrow_downward"

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
