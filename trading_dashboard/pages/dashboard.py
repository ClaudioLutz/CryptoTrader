"""Dashboard Overview Page - Live metrics and equity curve."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from components.api_client import (
    fetch_positions,
    fetch_trades,
    fetch_strategies,
    fetch_orders,
    fetch_ohlcv,
    fetch_status,
)


st.title("Trading Dashboard")

# =============================================================================
# Helper Functions
# =============================================================================


def calculate_pnl_from_trades(trades: list, current_price: float = 0) -> dict:
    """Calculate realized and unrealized P&L from actual trade history.

    For grid trading:
    - Realized P&L = total sell value - total buy value (for closed positions)
    - Unrealized P&L = (current price - avg buy price) * holdings

    Returns dict with realized_pnl, unrealized_pnl, total_pnl, holdings, avg_cost, cycles
    """
    total_buy_cost = 0.0
    total_sell_cost = 0.0
    total_buy_amount = 0.0
    total_sell_amount = 0.0
    buy_count = 0
    sell_count = 0

    for trade in trades:
        try:
            cost = float(trade.get("cost", 0) or 0)
            amount = float(trade.get("amount", 0) or 0)
            side = trade.get("side", "").lower()
            if side == "buy":
                total_buy_cost += cost
                total_buy_amount += amount
                buy_count += 1
            elif side == "sell":
                total_sell_cost += cost
                total_sell_amount += amount
                sell_count += 1
        except (ValueError, TypeError):
            continue

    # Current holdings (what we bought minus what we sold)
    holdings = total_buy_amount - total_sell_amount

    # Average cost basis for current holdings
    avg_cost = total_buy_cost / total_buy_amount if total_buy_amount > 0 else 0

    # Realized P&L = sell proceeds - cost of sold units
    realized_pnl = (
        total_sell_cost - (avg_cost * total_sell_amount) if total_sell_amount > 0 else 0
    )

    # Unrealized P&L = (current price - avg cost) * holdings
    unrealized_pnl = (
        (current_price - avg_cost) * holdings
        if current_price > 0 and holdings > 0
        else 0
    )

    # Total P&L
    total_pnl = realized_pnl + unrealized_pnl

    return {
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "holdings": holdings,
        "avg_cost": avg_cost,
        "cycles": min(buy_count, sell_count),
        "buy_count": buy_count,
        "sell_count": sell_count,
    }


# =============================================================================
# Refresh Controls - Manual refresh to avoid constant flickering
# =============================================================================

col_refresh, col_status = st.columns([1, 3])
with col_refresh:
    if st.button("Refresh Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col_status:
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

# =============================================================================
# Live Metrics Panel - Using st.empty() for smoother updates
# =============================================================================

# Create placeholder containers that will be updated in place
metrics_container = st.container()


@st.fragment(run_every="10s")
def live_metrics_panel():
    """Auto-refreshing metrics panel with reduced flicker."""
    # Fetch all data at once
    strategies_data = fetch_strategies()
    orders_data = fetch_orders()
    trades_data = fetch_trades()
    ohlcv_data = fetch_ohlcv(symbol="BTC/USDT", timeframe="1m", limit=1)

    strategies = strategies_data.get("strategies", [])
    orders = orders_data.get("orders", [])
    trades = trades_data.get("trades", [])

    # Get current price from latest candle
    ohlcv = ohlcv_data.get("ohlcv", [])
    current_price = ohlcv[-1]["close"] if ohlcv else 0

    # Count buy/sell orders from actual orders data
    buy_orders = len([o for o in orders if o.get("side", "").lower() == "buy"])
    sell_orders = len([o for o in orders if o.get("side", "").lower() == "sell"])

    # Calculate P&L from actual Binance trades
    pnl_data = calculate_pnl_from_trades(trades, current_price)

    # First row: P&L metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_pnl = pnl_data["total_pnl"]
        st.metric(
            "Total P&L",
            f"${total_pnl:,.2f}",
            f"{pnl_data['cycles']} cycles",
            delta_color="normal" if total_pnl >= 0 else "inverse",
            border=True,
        )

    with col2:
        realized = pnl_data["realized_pnl"]
        st.metric(
            "Realized P&L",
            f"${realized:,.2f}",
            f"{pnl_data['sell_count']} sells",
            delta_color="normal" if realized >= 0 else "inverse",
            border=True,
        )

    with col3:
        unrealized = pnl_data["unrealized_pnl"]
        holdings = pnl_data["holdings"]
        st.metric(
            "Unrealized P&L",
            f"${unrealized:,.2f}",
            f"{holdings:.6f} BTC" if holdings > 0 else "No holdings",
            delta_color="normal" if unrealized >= 0 else "inverse",
            border=True,
        )

    with col4:
        avg_cost = pnl_data["avg_cost"]
        price_diff = current_price - avg_cost if avg_cost > 0 else 0
        st.metric(
            "Current Price",
            f"${current_price:,.2f}",
            f"${price_diff:+,.2f} vs avg" if avg_cost > 0 else None,
            delta_color="normal" if price_diff >= 0 else "inverse",
            border=True,
        )

    # Second row: Order counts
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        st.metric("Active Strategies", len(strategies), border=True)

    with col6:
        st.metric("Buy Orders", buy_orders, border=True)

    with col7:
        st.metric("Sell Orders", sell_orders, border=True)

    with col8:
        total_trades = pnl_data["buy_count"] + pnl_data["sell_count"]
        st.metric("Total Trades", total_trades, border=True)


# Render the metrics panel
with metrics_container:
    live_metrics_panel()

st.divider()

# =============================================================================
# Price Chart with Orders (Static - doesn't need frequent updates)
# =============================================================================


def render_price_chart_with_orders(
    ohlcv_data: list, orders: list, trades: list, grid_config: dict
):
    """Render candlestick chart with order markers and grid levels."""
    if not ohlcv_data:
        st.info("No price data available. Waiting for OHLCV data from exchange...")
        return

    df = pd.DataFrame(ohlcv_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig = go.Figure()

    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        )
    )

    # Add grid level lines if available
    if grid_config:
        lower = grid_config.get("lower_price", 0)
        upper = grid_config.get("upper_price", 0)
        num_grids = grid_config.get("num_grids", 0)

        if lower and upper and num_grids:
            grid_step = (upper - lower) / num_grids
            for i in range(num_grids + 1):
                level_price = lower + (i * grid_step)
                fig.add_hline(
                    y=level_price,
                    line=dict(color="rgba(100,100,100,0.3)", width=1, dash="dot"),
                    annotation_text=f"${level_price:,.0f}",
                    annotation_position="right",
                    annotation_font_size=8,
                    annotation_font_color="gray",
                )

    # Add buy order markers (pending orders)
    buy_orders = [
        o for o in orders if o.get("side", "").lower() == "buy" and o.get("price")
    ]
    if buy_orders:
        latest_time = df["timestamp"].max()
        fig.add_trace(
            go.Scatter(
                x=[latest_time] * len(buy_orders),
                y=[float(o["price"]) for o in buy_orders],
                mode="markers",
                marker=dict(
                    symbol="triangle-right",
                    color="#26a69a",
                    size=10,
                    line=dict(width=1, color="white"),
                ),
                name=f"Buy Orders ({len(buy_orders)})",
                hovertemplate="Buy @ $%{y:,.2f}<extra></extra>",
            )
        )

    # Add sell order markers (pending orders)
    sell_orders = [
        o for o in orders if o.get("side", "").lower() == "sell" and o.get("price")
    ]
    if sell_orders:
        latest_time = df["timestamp"].max()
        fig.add_trace(
            go.Scatter(
                x=[latest_time] * len(sell_orders),
                y=[float(o["price"]) for o in sell_orders],
                mode="markers",
                marker=dict(
                    symbol="triangle-left",
                    color="#ef5350",
                    size=10,
                    line=dict(width=1, color="white"),
                ),
                name=f"Sell Orders ({len(sell_orders)})",
                hovertemplate="Sell @ $%{y:,.2f}<extra></extra>",
            )
        )

    # Add executed trade markers
    buy_trades = [t for t in trades if t.get("side", "").lower() == "buy"]
    sell_trades = [t for t in trades if t.get("side", "").lower() == "sell"]

    if buy_trades:
        fig.add_trace(
            go.Scatter(
                x=[pd.to_datetime(t.get("timestamp")) for t in buy_trades],
                y=[float(t.get("price", 0)) for t in buy_trades],
                mode="markers",
                marker=dict(
                    symbol="triangle-up",
                    color="#26a69a",
                    size=12,
                    line=dict(width=2, color="white"),
                ),
                name=f"Bought ({len(buy_trades)})",
                hovertemplate="Bought @ $%{y:,.2f}<br>%{x}<extra></extra>",
            )
        )

    if sell_trades:
        fig.add_trace(
            go.Scatter(
                x=[pd.to_datetime(t.get("timestamp")) for t in sell_trades],
                y=[float(t.get("price", 0)) for t in sell_trades],
                mode="markers",
                marker=dict(
                    symbol="triangle-down",
                    color="#ef5350",
                    size=12,
                    line=dict(width=2, color="white"),
                ),
                name=f"Sold ({len(sell_trades)})",
                hovertemplate="Sold @ $%{y:,.2f}<br>%{x}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Price Chart with Orders",
        yaxis_title="Price ($)",
        xaxis_title="Time",
        height=450,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=0, r=60, t=40, b=0),
    )

    st.plotly_chart(fig, use_container_width=True, key="price_chart")


col_chart, col_trades = st.columns([2, 1])

with col_chart:
    st.subheader("Price Chart")
    # Fetch data for chart (cached, so won't cause flicker)
    status_data = fetch_status()
    ohlcv_data = fetch_ohlcv(
        symbol="BTC/USDT", timeframe="15m", limit=96
    )  # 24 hours of 15m candles
    orders_data = fetch_orders()
    trades_data = fetch_trades()

    render_price_chart_with_orders(
        ohlcv_data.get("ohlcv", []),
        orders_data.get("orders", []),
        trades_data.get("trades", []),
        status_data.get("grid_config", {}),
    )

# =============================================================================
# Recent Trades (Static table - no auto-refresh to reduce flicker)
# =============================================================================

with col_trades:
    st.subheader("Recent Trades")
    trades = trades_data.get("trades", [])

    if trades:
        # Show last 10 trades
        df_trades = pd.DataFrame(trades[-10:])

        # Format for display
        if not df_trades.empty:
            display_cols = ["timestamp", "symbol", "side", "amount", "price"]
            available_cols = [c for c in display_cols if c in df_trades.columns]

            st.dataframe(
                df_trades[available_cols],
                column_config={
                    "timestamp": st.column_config.DatetimeColumn(
                        "Time", format="HH:mm:ss"
                    ),
                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                },
                hide_index=True,
                use_container_width=True,
            )
    else:
        st.info("No trades yet")

# =============================================================================
# Strategy Performance (Single fragment with longer interval)
# =============================================================================

st.divider()
st.subheader("Strategy Performance")


@st.fragment(run_every="15s")
def strategy_performance():
    """Auto-refreshing strategy performance cards."""
    strategies_data = fetch_strategies()
    orders_data = fetch_orders()
    trades_data = fetch_trades()
    strategies = strategies_data.get("strategies", [])
    all_orders = orders_data.get("orders", [])
    all_trades = trades_data.get("trades", [])

    if strategies_data.get("error"):
        st.error(f"Failed to fetch strategies: {strategies_data['error']}")
        return

    if not strategies:
        st.info("No active strategies")
        return

    cols = st.columns(min(len(strategies), 4))  # Max 4 columns

    for i, strat in enumerate(strategies):
        col_idx = i % 4
        with cols[col_idx]:
            config = strat.get("config", {})
            symbol = strat.get("symbol", "Unknown")

            # Calculate P&L from actual trades for this symbol
            symbol_trades = [t for t in all_trades if t.get("symbol") == symbol]
            pnl_result = calculate_pnl_from_trades(symbol_trades)
            profit = pnl_result["realized_pnl"]
            cycles = pnl_result["cycles"]

            # Count orders for this specific symbol
            symbol_orders = [o for o in all_orders if o.get("symbol") == symbol]
            buy_count = len(
                [o for o in symbol_orders if o.get("side", "").lower() == "buy"]
            )
            sell_count = len(
                [o for o in symbol_orders if o.get("side", "").lower() == "sell"]
            )

            # Strategy card
            st.markdown(f"**{symbol}**")

            st.metric(
                "Realized P&L",
                f"${profit:,.2f}",
                f"{cycles} trades" if cycles > 0 else None,
                delta_color="normal" if profit >= 0 else "inverse",
                border=True,
            )

            st.caption(f"Orders: {buy_count} buy / {sell_count} sell")

            if config:
                lower = config.get("lower_price", "?")
                upper = config.get("upper_price", "?")
                grids = config.get("num_grids", "?")
                st.caption(f"Grid: ${lower} - ${upper} ({grids} levels)")


strategy_performance()
