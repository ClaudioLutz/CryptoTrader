"""CryptoTrader Dashboard - Pairs Table Component.

Displays all trading pairs in expandable cards with:
- Mini price chart with timeframe selector
- Orders summary
- Scrollable recent trades list
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import plotly.graph_objects as go
from nicegui import ui

from dashboard.state import state
from dashboard.services.data_models import OrderData, TradeData


# Available chart timeframes
TIMEFRAMES = ["1h", "4h", "1d", "1w"]
TIMEFRAME_LABELS = {"1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W"}


def format_price(price: Decimal, symbol: str) -> str:
    """Format price with appropriate precision based on magnitude."""
    if price >= 100:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    else:
        return f"${price:,.6f}"


def format_pnl(pnl: Decimal) -> tuple[str, str]:
    """Format P&L with sign and color class."""
    if pnl > 0:
        return f"+\u20ac{pnl:.2f}", "pnl-positive"
    elif pnl < 0:
        return f"-\u20ac{abs(pnl):.2f}", "pnl-negative"
    else:
        return "\u20ac0.00", "pnl-neutral"


def format_position(size: Decimal, symbol: str) -> str:
    """Format position size with base asset symbol."""
    base_asset = symbol.split("/")[0] if "/" in symbol else symbol
    return f"{size} {base_asset}"


def create_pairs_table() -> None:
    """Create the all-pairs table with expandable row details."""
    with ui.element("div").classes("pairs-table-container centered-container"):
        for pair in state.pairs:
            _create_pair_row(pair.symbol)


def _create_pair_row(symbol: str) -> None:
    """Create a single expandable pair row with closure-based container management."""
    pair = next((p for p in state.pairs if p.symbol == symbol), None)
    if not pair:
        return

    pnl_text, pnl_class = format_pnl(pair.pnl_today)
    is_expanded = state.is_row_expanded(symbol)

    # Get order counts for this specific pair from per-symbol cache
    symbol_orders = state.orders_by_symbol.get(symbol, [])
    order_count = len(symbol_orders)

    expand_icon = "expand_more" if is_expanded else "chevron_right"

    with ui.expansion(
        text=symbol,
        icon=expand_icon,
        value=is_expanded,
    ).classes("pair-expansion").props("dense") as expansion:
        # Header content
        with expansion.add_slot("header"):
            with ui.row().classes("pair-row-header items-center w-full gap-4"):
                ui.icon(expand_icon).classes(
                    f"expand-icon {'rotated' if is_expanded else ''}"
                )
                ui.label(symbol).classes("pair-symbol")
                ui.label(format_price(pair.current_price, symbol)).classes(
                    "pair-price text-right"
                )
                ui.label(pnl_text).classes(f"pair-pnl {pnl_class} text-right")
                ui.label(format_position(pair.position_size, symbol)).classes(
                    "pair-position text-right"
                )
                ui.label(str(order_count)).classes("pair-orders text-center")

        # Expansion content container (local scope for closure)
        with ui.element("div").classes("expansion-content") as container:
            _render_expansion_content(symbol)

        # Create async handlers with closure over container
        async def on_expansion_change(event, sym=symbol, cont=container) -> None:
            """Handle expansion toggle with on-demand data fetching."""
            if event.value:
                # Fetch data on demand
                await state.refresh_orders(sym)
                await state.refresh_trades(sym, limit=100)

                # Get current timeframe or default to 1h
                timeframe = state.chart_timeframe_by_symbol.get(sym, "1h")
                await state.refresh_ohlcv(sym, timeframe=timeframe, limit=48)
                state.expanded_rows.add(sym)

                # Rebuild the expansion content with new data
                cont.clear()
                with cont:
                    _render_expansion_content(sym)
            else:
                state.expanded_rows.discard(sym)

        async def change_timeframe(timeframe: str, sym=symbol, cont=container) -> None:
            """Change chart timeframe and refresh data."""
            state.chart_timeframe_by_symbol[sym] = timeframe
            await state.refresh_ohlcv(sym, timeframe=timeframe, limit=48)

            # Rebuild the expansion content
            cont.clear()
            with cont:
                _render_expansion_content(sym)

        # Store the change_timeframe function for use in chart controls
        container.change_timeframe = change_timeframe

        expansion.on_value_change(on_expansion_change)


def _render_expansion_content(symbol: str) -> None:
    """Render expansion content with current data."""
    with ui.row().classes("expansion-grid-3col w-full gap-4"):
        with ui.column().classes("order-details-section"):
            _create_order_details(symbol)

        with ui.column().classes("mini-chart-section flex-grow"):
            _create_chart_with_controls(symbol)

        with ui.column().classes("trades-section"):
            _create_recent_trades(symbol)


def _create_chart_with_controls(symbol: str) -> None:
    """Create chart with timeframe selector that updates dynamically."""
    # Create chart container first (will be populated by rebuild function)
    with ui.element("div").classes("chart-wrapper") as chart_container:
        pass  # Will be filled by _rebuild_chart

    def _rebuild_chart(sym: str = symbol, cont: ui.element = chart_container) -> None:
        """Rebuild the chart with current data."""
        cont.clear()
        with cont:
            _create_mini_chart(sym)

    async def _change_timeframe(
        timeframe: str,
        sym: str = symbol,
        rebuild_fn=_rebuild_chart,
        buttons_cont: ui.element = None,
    ) -> None:
        """Change timeframe, fetch new data, and rebuild chart."""
        state.chart_timeframe_by_symbol[sym] = timeframe
        await state.refresh_ohlcv(sym, timeframe=timeframe, limit=48)
        rebuild_fn()
        # Update button styles
        if buttons_cont:
            buttons_cont.clear()
            with buttons_cont:
                _create_timeframe_buttons(sym, _change_timeframe, buttons_cont)

    # Timeframe selector row
    with ui.row().classes("chart-controls items-center gap-2 mb-2") as buttons_container:
        _create_timeframe_buttons(symbol, _change_timeframe, buttons_container)

    # Initial chart render
    _rebuild_chart()


def _create_timeframe_buttons(
    symbol: str, change_fn, buttons_cont: ui.element
) -> None:
    """Create timeframe selector buttons."""
    current_tf = state.chart_timeframe_by_symbol.get(symbol, "1h")
    for tf in TIMEFRAMES:
        is_active = tf == current_tf
        btn = ui.button(
            TIMEFRAME_LABELS[tf],
            on_click=lambda t=tf: change_fn(t, symbol, buttons_cont=buttons_cont),
        ).props(f"dense {'flat' if not is_active else ''} size=sm")
        if is_active:
            btn.classes("timeframe-active")
        else:
            btn.classes("timeframe-btn")


def _create_mini_chart(symbol: str) -> None:
    """Create a mini price chart for the trading pair."""
    ohlcv_data = state.ohlcv_by_symbol.get(symbol, [])
    symbol_trades = state.trades_by_symbol.get(symbol, [])

    fig = _create_mini_figure(symbol, ohlcv_data, symbol_trades)

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
    """Create a mini Plotly figure for the pair card."""
    fig = go.Figure()

    if ohlcv_data:
        timestamps = [d.get("timestamp", d.get("time")) for d in ohlcv_data]
        closes = [float(d.get("close", d.get("price", 0))) for d in ohlcv_data]
    else:
        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(hours=i) for i in range(48, 0, -1)]
        closes = []

    if closes:
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=closes,
            mode="lines",
            name="Price",
            line=dict(color="#4a9eff", width=1.5),
            hovertemplate="$%{y:,.2f}<extra></extra>",
        ))

    # Calculate y-axis range
    all_prices = list(closes) if closes else []
    if trades:
        trade_prices = [float(t.price) for t in trades]
        all_prices.extend(trade_prices)

    if all_prices:
        min_price = min(all_prices)
        max_price = max(all_prices)
        price_range = max_price - min_price if max_price > min_price else max_price * 0.01
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
                marker=dict(symbol="triangle-up", size=8, color="#00c853"),
                hovertemplate="BUY $%{y:,.2f}<extra></extra>",
            ))

        if sells:
            fig.add_trace(go.Scatter(
                x=[t.timestamp for t in sells],
                y=[float(t.price) for t in sells],
                mode="markers",
                name="Sell",
                marker=dict(symbol="triangle-down", size=8, color="#ff5252"),
                hovertemplate="SELL $%{y:,.2f}<extra></extra>",
            ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=180,
        margin=dict(l=50, r=10, t=5, b=25),
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

    if not closes:
        fig.add_annotation(
            text="Loading chart data...",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(color="#6b7280", size=12),
        )

    return fig


def _create_order_details(symbol: str) -> None:
    """Create order details panel with strategy info - compact horizontal layout."""
    pair = next((p for p in state.pairs if p.symbol == symbol), None)
    current_price = pair.current_price if pair else Decimal("0")

    # Use per-symbol orders cache
    symbol_orders = state.orders_by_symbol.get(symbol, [])
    buy_orders = [o for o in symbol_orders if o.side.lower() == "buy"]
    sell_orders = [o for o in symbol_orders if o.side.lower() == "sell"]

    buy_count = len(buy_orders)
    sell_count = len(sell_orders)

    highest_buy = max((o.price for o in buy_orders), default=Decimal("0"))
    lowest_sell = min((o.price for o in sell_orders), default=Decimal("0"))

    # Compact horizontal layout
    with ui.row().classes("items-start gap-8 w-full"):
        # Orders column
        with ui.column().classes("gap-1"):
            ui.label("ORDERS").classes("section-label text-xs")
            with ui.row().classes("gap-4"):
                with ui.column().classes("items-center"):
                    ui.label(str(buy_count)).classes("text-2xl font-bold text-green-400")
                    ui.label("BUY").classes("text-xs text-gray-500")
                with ui.column().classes("items-center"):
                    ui.label(str(sell_count)).classes("text-2xl font-bold text-red-400")
                    ui.label("SELL").classes("text-xs text-gray-500")

        # Distances column
        if current_price > 0 and (highest_buy > 0 or lowest_sell > 0):
            with ui.column().classes("gap-1"):
                ui.label("DISTANCES").classes("section-label text-xs")
                if highest_buy > 0:
                    dist_buy_pct = ((current_price - highest_buy) / current_price) * 100
                    ui.label(f"Next BUY: ${highest_buy:,.2f} ({dist_buy_pct:+.1f}%)").classes("text-xs text-green-400")
                if lowest_sell > 0:
                    dist_tp_pct = ((lowest_sell - current_price) / current_price) * 100
                    ui.label(f"TP: ${lowest_sell:,.2f} ({dist_tp_pct:+.1f}%)").classes("text-xs text-green-400")

        # Grid strategy column
        if pair and pair.lower_price > 0:
            with ui.column().classes("gap-1"):
                ui.label("GRID").classes("section-label text-xs")
                ui.label(f"${pair.lower_price:,.0f} - ${pair.upper_price:,.0f}").classes("text-xs text-gray-400")
                ui.label(f"{pair.num_grids} levels | ${pair.total_investment:,.0f}").classes("text-xs text-gray-400")


def _create_recent_trades(symbol: str) -> None:
    """Create scrollable recent trades list."""
    ui.label("RECENT TRADES").classes("section-label")

    # Get current price for P&L calculation
    pair = next((p for p in state.pairs if p.symbol == symbol), None)
    current_price = pair.current_price if pair else Decimal("0")

    # Use per-symbol trades cache - show all trades (scrollable)
    symbol_trades = state.trades_by_symbol.get(symbol, [])

    if not symbol_trades:
        ui.label("No recent trades").classes("text-tertiary text-sm")
        return

    # Scrollable container for trades
    with ui.element("div").classes("trades-scroll-container"):
        with ui.column().classes("trades-list gap-1"):
            for trade in symbol_trades:
                _create_trade_row(trade, current_price)


def _create_trade_row(trade: TradeData, current_price: Decimal = Decimal("0")) -> None:
    """Create a single trade row with P&L."""
    side_class = "trade-buy" if trade.side.lower() == "buy" else "trade-sell"
    side_icon = "arrow_upward" if trade.side.lower() == "buy" else "arrow_downward"

    # Calculate unrealized P&L for buy trades
    pnl_text = ""
    pnl_class = ""
    if trade.side.lower() == "buy" and current_price > 0:
        pnl = (current_price - trade.price) * trade.amount
        pnl_pct = ((current_price - trade.price) / trade.price) * 100
        if pnl >= 0:
            pnl_text = f"+${pnl:.2f} ({pnl_pct:+.1f}%)"
            pnl_class = "text-green-400"
        else:
            pnl_text = f"-${abs(pnl):.2f} ({pnl_pct:+.1f}%)"
            pnl_class = "text-red-400"

    with ui.row().classes(f"trade-row {side_class} items-center gap-2"):
        ui.icon(side_icon).classes("trade-icon")
        ui.label(trade.side.upper()).classes("trade-side")
        ui.label(f"${trade.price:,.2f}").classes("trade-price")
        ui.label(f"{trade.amount}").classes("trade-amount")
        if pnl_text:
            ui.label(pnl_text).classes(f"trade-pnl text-xs {pnl_class}")
        ui.label(trade.timestamp.strftime("%H:%M")).classes("trade-time")


def create_pairs_table_placeholder() -> None:
    """Create a placeholder table when no data is available."""
    with ui.element("div").classes("pairs-table-container centered-container"):
        with ui.card().classes("pairs-table-empty"):
            ui.label("No trading pairs available").classes("text-secondary")
            ui.label("Waiting for data from trading bot...").classes(
                "text-tertiary text-sm"
            )
