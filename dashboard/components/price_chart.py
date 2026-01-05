"""CryptoTrader Dashboard - Price Chart Component.

Interactive Plotly chart for price visualization with dark theme styling.
Stories 5.1-5.4: Basic chart, tooltips, zoom/pan, pair selection.
Stories 8.2-8.3: Trade markers, candlestick toggle.
Story 10.1: Grid visualization overlay.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import plotly.graph_objects as go
from nicegui import ui

from dashboard.components.grid_visualization import add_grid_overlay
from dashboard.services.data_models import GridConfig, TradeData
from dashboard.state import state


def create_figure(
    symbol: str | None = None,
    ohlcv_data: list[dict[str, Any]] | None = None,
    trades: list[TradeData] | None = None,
    chart_mode: str = "line",
    grid_config: GridConfig | None = None,
    show_grid: bool = True,
) -> go.Figure:
    """Create Plotly figure with dark theme styling.

    Args:
        symbol: Trading pair symbol for title.
        ohlcv_data: List of OHLCV data dicts with timestamp and OHLC prices.
        trades: List of trades to show as markers (Story 8.2).
        chart_mode: "line" or "candlestick" (Story 8.3).
        grid_config: Grid configuration for overlay (Story 10.1).
        show_grid: Whether to show grid overlay (Story 10.1).

    Returns:
        Configured Plotly figure.
    """
    fig = go.Figure()

    # Extract data if provided
    if ohlcv_data:
        timestamps = [d.get("timestamp", d.get("time")) for d in ohlcv_data]
        opens = [float(d.get("open", d.get("close", 0))) for d in ohlcv_data]
        highs = [float(d.get("high", d.get("close", 0))) for d in ohlcv_data]
        lows = [float(d.get("low", d.get("close", 0))) for d in ohlcv_data]
        closes = [float(d.get("close", d.get("price", 0))) for d in ohlcv_data]
    else:
        # Generate sample data for demo when no data available
        now = datetime.now(timezone.utc)
        timestamps = [now - timedelta(hours=i) for i in range(24, 0, -1)]
        # Simulated price data
        base_price = 97000.0
        import random
        random.seed(42)
        closes = [base_price + random.uniform(-500, 500) for _ in range(24)]
        opens = [c + random.uniform(-100, 100) for c in closes]
        highs = [max(o, c) + random.uniform(0, 200) for o, c in zip(opens, closes)]
        lows = [min(o, c) - random.uniform(0, 200) for o, c in zip(opens, closes)]

    # Add price trace based on chart mode (Story 8.3)
    if chart_mode == "candlestick":
        fig.add_trace(go.Candlestick(
            x=timestamps,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="Price",
            increasing=dict(line=dict(color="#00c853"), fillcolor="#00c853"),
            decreasing=dict(line=dict(color="#ff5252"), fillcolor="#ff5252"),
        ))
    else:
        # Line chart (default)
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=closes,
            mode="lines",
            name="Price",
            line=dict(color="#4a9eff", width=2),
            hovertemplate=(
                "<b>Price:</b> $%{y:,.2f}<br>"
                "<b>Time:</b> %{x|%H:%M:%S}<br>"
                "<extra></extra>"  # Hide trace name
            ),
        ))

    # Add trade markers if provided (Story 8.2)
    if trades:
        _add_trade_markers(fig, trades)

    # Add grid overlay if provided (Story 10.1)
    if show_grid and grid_config:
        add_grid_overlay(fig, grid_config)

    # Chart title
    title_text = f"{symbol} Price" if symbol else "Price Chart"

    # Dark theme layout
    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(color="#e8e8e8", size=16),
            x=0.02,
        ),
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        height=350,
        margin=dict(l=50, r=20, t=50, b=40),

        # X-axis configuration
        xaxis=dict(
            title=dict(text="Time", font=dict(color="#e8e8e8")),
            gridcolor="#0f3460",
            showgrid=True,
            tickfont=dict(color="#a0a0a0"),
            fixedrange=False,  # Allow zoom
            rangeslider=dict(visible=False),
            showspikes=True,
            spikecolor="#4a9eff",
            spikethickness=1,
            spikedash="dot",
            spikemode="across",
        ),

        # Y-axis configuration
        yaxis=dict(
            title=dict(text="Price ($)", font=dict(color="#e8e8e8")),
            gridcolor="#0f3460",
            showgrid=True,
            tickfont=dict(color="#a0a0a0"),
            fixedrange=False,
            autorange=True,
            showspikes=True,
            spikecolor="#4a9eff",
            spikethickness=1,
            spikedash="dot",
            spikemode="across",
        ),

        # Hover settings
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#16213e",
            bordercolor="#0f3460",
            font=dict(
                family="Roboto Mono, monospace",
                size=12,
                color="#e8e8e8",
            ),
        ),

        # Interaction settings
        dragmode="pan",  # Default to pan mode
        showlegend=False,
    )

    return fig


def _add_trade_markers(fig: go.Figure, trades: list[TradeData]) -> None:
    """Add trade execution markers to chart (Story 8.2).

    Args:
        fig: Plotly figure to add markers to.
        trades: List of trades to display.
    """
    buys = [t for t in trades if t.side == "buy"]
    sells = [t for t in trades if t.side == "sell"]

    # Buy markers (green triangles up) - Story 8.2 AC1
    if buys:
        fig.add_trace(go.Scatter(
            x=[t.timestamp for t in buys],
            y=[float(t.price) for t in buys],
            mode="markers",
            name="Buys",
            marker=dict(
                symbol="triangle-up",
                size=12,
                color="#00c853",
                line=dict(width=1, color="#008837"),
            ),
            hovertemplate=(
                "<b>BUY</b><br>"
                "Price: $%{y:,.2f}<br>"
                "Amount: %{customdata[0]}<br>"
                "Time: %{x|%H:%M:%S}<br>"
                "<extra></extra>"
            ),
            customdata=[[float(t.amount)] for t in buys],
        ))

    # Sell markers (red triangles down) - Story 8.2 AC2
    if sells:
        fig.add_trace(go.Scatter(
            x=[t.timestamp for t in sells],
            y=[float(t.price) for t in sells],
            mode="markers",
            name="Sells",
            marker=dict(
                symbol="triangle-down",
                size=12,
                color="#ff5252",
                line=dict(width=1, color="#c41c00"),
            ),
            hovertemplate=(
                "<b>SELL</b><br>"
                "Price: $%{y:,.2f}<br>"
                "Amount: %{customdata[0]}<br>"
                "Time: %{x|%H:%M:%S}<br>"
                "<extra></extra>"
            ),
            customdata=[[float(t.amount)] for t in sells],
        ))


def create_price_chart() -> None:
    """Create the price chart component with pair selection and mode toggle.

    Features:
    - Dark theme styling matching dashboard
    - Hover tooltips with price and time
    - Crosshair cursor
    - Scroll zoom and drag pan
    - Double-click to reset view
    - Chart title shows selected pair
    - Line/Candlestick toggle (Story 8.3)
    - Trade markers (Story 8.2)
    - Grid overlay toggle (Story 10.1)
    """
    with ui.element("div").classes("chart-container"):
        # Chart header with title and controls
        with ui.row().classes("chart-header items-center justify-between w-full"):
            # Left: Title and pair
            with ui.row().classes("items-center gap-2"):
                ui.label("Price Chart").classes("chart-title text-primary")
                pair_label = ui.label()
                pair_label.classes("chart-pair text-secondary")

                # Show selected pair or default
                def get_pair_text() -> str:
                    if state.selected_pair:
                        return f"({state.selected_pair})"
                    elif state.pairs:
                        return f"({state.pairs[0].symbol})"
                    return "(No pair selected)"

                pair_label.text = get_pair_text()

            # Right: Chart controls (Story 8.3, 10.1)
            with ui.row().classes("chart-toggle items-center gap-4"):
                # Grid overlay toggle (Story 10.1)
                grid_checkbox = ui.checkbox(
                    "Grid",
                    value=state.show_grid_overlay,
                ).classes("grid-toggle").props("dense")

                # Chart mode toggle (Story 8.3)
                ui.label("Chart:").classes("toggle-label text-sm text-secondary")
                toggle = ui.toggle(
                    ["Line", "Candles"],
                    value="Line" if state.chart_mode == "line" else "Candles",
                ).classes("chart-mode-toggle").props("dense")

        # Create the Plotly chart
        symbol = state.selected_pair or (state.pairs[0].symbol if state.pairs else "BTC/USDT")

        # Filter trades for selected pair (Story 8.2)
        pair_trades = [t for t in state.trades if t.symbol == symbol] if state.trades else None

        fig = create_figure(
            symbol=symbol,
            ohlcv_data=state.ohlcv if state.ohlcv else None,
            trades=pair_trades,
            chart_mode=state.chart_mode,
            grid_config=state.grid_config,
            show_grid=state.show_grid_overlay,
        )

        chart = ui.plotly(fig).classes("price-chart")

        # Configure chart interactions (zoom, pan, reset)
        chart._props["config"] = {
            "scrollZoom": True,  # Enable scroll zoom
            "doubleClick": "reset",  # Double-click resets view
            "displayModeBar": False,  # Hide toolbar
            "displaylogo": False,
            "responsive": True,
        }

        # Rebuild chart helper
        def rebuild_chart() -> None:
            new_fig = create_figure(
                symbol=symbol,
                ohlcv_data=state.ohlcv if state.ohlcv else None,
                trades=pair_trades,
                chart_mode=state.chart_mode,
                grid_config=state.grid_config,
                show_grid=state.show_grid_overlay,
            )
            chart.update_figure(new_fig)

        # Handle chart mode toggle (Story 8.3 AC3)
        def on_toggle_change(e) -> None:
            state.chart_mode = "line" if e.value == "Line" else "candlestick"
            rebuild_chart()

        toggle.on_value_change(on_toggle_change)

        # Handle grid overlay toggle (Story 10.1)
        def on_grid_toggle(e) -> None:
            state.show_grid_overlay = e.value
            rebuild_chart()

        grid_checkbox.on_value_change(on_grid_toggle)


def create_price_chart_placeholder() -> None:
    """Create a placeholder when chart cannot be displayed."""
    with ui.element("div").classes("chart-container"):
        with ui.card().classes("chart-placeholder"):
            ui.label("Price Chart").classes("text-h6 text-primary")
            ui.label("Chart data unavailable").classes("text-secondary")
            ui.label("Connect to trading bot to view price data.").classes(
                "text-tertiary text-sm"
            )
