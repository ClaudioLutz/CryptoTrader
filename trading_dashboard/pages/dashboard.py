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
    fetch_equity,
)
from components.state import get_state


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
# Refresh Controls and Symbol Selection
# =============================================================================

state = get_state()

col_symbol, col_refresh, col_status = st.columns([1, 1, 2])

with col_symbol:
    # Get symbols from strategies if available, else use defaults
    strategies_data = fetch_strategies()
    available_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]  # Defaults
    strategy_symbols = [s.get("symbol") for s in strategies_data.get("strategies", []) if s.get("symbol")]
    if strategy_symbols:
        available_symbols = list(set(strategy_symbols + available_symbols))

    selected_symbol = st.selectbox(
        "Symbol",
        available_symbols,
        index=available_symbols.index(state.selected_symbol) if state.selected_symbol in available_symbols else 0,
        key="dashboard_symbol",
        label_visibility="collapsed",
    )
    state.selected_symbol = selected_symbol

with col_refresh:
    if st.button("Refresh Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col_status:
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

# =============================================================================
# Portfolio Summary (All Pairs Aggregate)
# =============================================================================

st.subheader("Portfolio Summary (All Pairs)")


@st.fragment(run_every="10s")
def portfolio_summary():
    """Aggregate P&L across all trading pairs."""
    trades_data = fetch_trades()
    strategies_data = fetch_strategies()
    orders_data = fetch_orders()

    all_trades = trades_data.get("trades", [])
    strategies = strategies_data.get("strategies", [])
    orders = orders_data.get("orders", [])

    # Group trades by symbol
    symbols = set(t.get("symbol") for t in all_trades if t.get("symbol"))
    if not symbols:
        symbols = {"BTC/USDT"}  # Default

    # Calculate P&L per symbol with proper current prices
    total_realized = 0.0
    total_unrealized = 0.0
    total_cycles = 0
    total_buy_count = 0
    total_sell_count = 0
    symbol_summaries = []

    for symbol in symbols:
        symbol_trades = [t for t in all_trades if t.get("symbol") == symbol]
        if not symbol_trades:
            continue

        # Get current price for this symbol
        ohlcv_data = fetch_ohlcv(symbol=symbol, timeframe="1m", limit=1)
        ohlcv = ohlcv_data.get("ohlcv", [])
        current_price = ohlcv[-1]["close"] if ohlcv else 0

        # Calculate P&L for this symbol
        pnl = calculate_pnl_from_trades(symbol_trades, current_price)

        total_realized += pnl["realized_pnl"]
        total_unrealized += pnl["unrealized_pnl"]
        total_cycles += pnl["cycles"]
        total_buy_count += pnl["buy_count"]
        total_sell_count += pnl["sell_count"]

        symbol_summaries.append({
            "symbol": symbol,
            "realized": pnl["realized_pnl"],
            "unrealized": pnl["unrealized_pnl"],
            "total": pnl["total_pnl"],
            "cycles": pnl["cycles"],
        })

    total_pnl = total_realized + total_unrealized

    # Display aggregate metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total P&L (All Pairs)",
            f"${total_pnl:,.2f}",
            f"{total_cycles} cycles",
            delta_color="normal" if total_pnl >= 0 else "inverse",
            border=True,
        )

    with col2:
        st.metric(
            "Realized P&L",
            f"${total_realized:,.2f}",
            f"{total_sell_count} sells",
            delta_color="normal" if total_realized >= 0 else "inverse",
            border=True,
        )

    with col3:
        st.metric(
            "Unrealized P&L",
            f"${total_unrealized:,.2f}",
            f"{len(symbols)} pairs",
            delta_color="normal" if total_unrealized >= 0 else "inverse",
            border=True,
        )

    with col4:
        total_orders = len(orders)
        buy_orders = len([o for o in orders if o.get("side", "").lower() == "buy"])
        sell_orders = len([o for o in orders if o.get("side", "").lower() == "sell"])
        st.metric(
            "Open Orders",
            f"{total_orders}",
            f"{buy_orders} buy / {sell_orders} sell",
            border=True,
        )

    # Per-symbol breakdown table
    if symbol_summaries:
        st.caption("**P&L by Symbol:**")
        cols = st.columns(len(symbol_summaries))
        for i, summary in enumerate(sorted(symbol_summaries, key=lambda x: x["total"], reverse=True)):
            with cols[i % len(cols)]:
                color = "green" if summary["total"] >= 0 else "red"
                st.markdown(
                    f"**{summary['symbol']}**: "
                    f"<span style='color:{color}'>${summary['total']:,.2f}</span>",
                    unsafe_allow_html=True,
                )


portfolio_summary()

st.divider()

# =============================================================================
# Selected Symbol Details
# =============================================================================

st.subheader(f"Selected: {state.selected_symbol}")


@st.fragment(run_every="10s")
def selected_symbol_metrics():
    """Metrics for the currently selected symbol."""
    current_symbol = get_state().selected_symbol

    # Fetch data for selected symbol
    trades_data = fetch_trades()
    orders_data = fetch_orders()
    ohlcv_data = fetch_ohlcv(symbol=current_symbol, timeframe="1m", limit=1)

    all_trades = trades_data.get("trades", [])
    orders = orders_data.get("orders", [])

    # Filter trades for selected symbol
    symbol_trades = [t for t in all_trades if t.get("symbol") == current_symbol]

    # Get current price
    ohlcv = ohlcv_data.get("ohlcv", [])
    current_price = ohlcv[-1]["close"] if ohlcv else 0

    # Filter orders for selected symbol
    symbol_orders = [o for o in orders if o.get("symbol") == current_symbol]
    buy_orders = len([o for o in symbol_orders if o.get("side", "").lower() == "buy"])
    sell_orders = len([o for o in symbol_orders if o.get("side", "").lower() == "sell"])

    # Calculate P&L for selected symbol
    pnl_data = calculate_pnl_from_trades(symbol_trades, current_price)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_pnl = pnl_data["total_pnl"]
        st.metric(
            f"{current_symbol} P&L",
            f"${total_pnl:,.2f}",
            f"{pnl_data['cycles']} cycles",
            delta_color="normal" if total_pnl >= 0 else "inverse",
            border=True,
        )

    with col2:
        realized = pnl_data["realized_pnl"]
        st.metric(
            "Realized",
            f"${realized:,.2f}",
            f"{pnl_data['sell_count']} sells",
            delta_color="normal" if realized >= 0 else "inverse",
            border=True,
        )

    with col3:
        unrealized = pnl_data["unrealized_pnl"]
        holdings = pnl_data["holdings"]
        # Determine the asset name from symbol
        asset = current_symbol.split("/")[0] if "/" in current_symbol else "units"
        st.metric(
            "Unrealized",
            f"${unrealized:,.2f}",
            f"{holdings:.6f} {asset}" if holdings > 0 else "No holdings",
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

    # Second row: orders for this symbol
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        st.metric("Buy Orders", buy_orders, border=True)

    with col6:
        st.metric("Sell Orders", sell_orders, border=True)

    with col7:
        total_symbol_trades = pnl_data["buy_count"] + pnl_data["sell_count"]
        st.metric("Total Trades", total_symbol_trades, border=True)

    with col8:
        avg_cost_display = pnl_data["avg_cost"]
        st.metric("Avg Cost", f"${avg_cost_display:,.2f}" if avg_cost_display > 0 else "N/A", border=True)


selected_symbol_metrics()

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
    st.subheader(f"Price Chart ({state.selected_symbol})")
    # Fetch data for chart (cached, so won't cause flicker)
    status_data = fetch_status()
    ohlcv_data = fetch_ohlcv(
        symbol=state.selected_symbol, timeframe="15m", limit=96
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
# Equity Curve (Static - refreshes with page)
# =============================================================================

st.divider()
st.subheader("Equity Curve")


def render_equity_curve():
    """Render equity curve with drawdown overlay."""
    equity_data = fetch_equity()
    data = equity_data.get("data", [])

    if equity_data.get("error"):
        st.warning(f"Could not fetch equity data: {equity_data['error']}")
        return

    if not data:
        st.info("No equity history available yet. Start trading to see your portfolio growth.")
        return

    df = pd.DataFrame(data)

    # Ensure we have the required columns
    if "timestamp" not in df.columns or "equity" not in df.columns:
        st.info("Equity data format not available")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Calculate drawdown if not provided
    if "drawdown" not in df.columns:
        df["peak"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"] * 100

    fig = go.Figure()

    # Add equity line
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["equity"],
            mode="lines",
            name="Portfolio Value",
            line=dict(color="#26a69a", width=2),
            fill="tozeroy",
            fillcolor="rgba(38,166,154,0.1)",
        )
    )

    # Add peak equity line
    if "peak" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["peak"],
                mode="lines",
                name="Peak Value",
                line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"),
            )
        )

    # Add drawdown on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["drawdown"],
            mode="lines",
            name="Drawdown %",
            line=dict(color="#ef5350", width=1),
            fill="tozeroy",
            fillcolor="rgba(239,83,80,0.1)",
            yaxis="y2",
        )
    )

    fig.update_layout(
        title="Portfolio Equity & Drawdown",
        yaxis=dict(
            title="Portfolio Value ($)",
            titlefont=dict(color="#26a69a"),
            tickfont=dict(color="#26a69a"),
            tickformat="$,.0f",
        ),
        yaxis2=dict(
            title="Drawdown (%)",
            titlefont=dict(color="#ef5350"),
            tickfont=dict(color="#ef5350"),
            overlaying="y",
            side="right",
            tickformat=".1f",
            range=[min(df["drawdown"].min() * 1.2, -1), 0],
        ),
        height=350,
        template="plotly_dark",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=0, r=60, t=40, b=0),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, key="equity_curve")

    # Summary metrics below chart
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            current_equity = df["equity"].iloc[-1]
            st.metric("Current Equity", f"${current_equity:,.2f}")

        with col2:
            peak_equity = df["equity"].max()
            st.metric("Peak Equity", f"${peak_equity:,.2f}")

        with col3:
            max_dd = df["drawdown"].min()
            st.metric("Max Drawdown", f"{max_dd:.2f}%")

        with col4:
            if len(df) > 1:
                total_return = (df["equity"].iloc[-1] / df["equity"].iloc[0] - 1) * 100
                st.metric("Total Return", f"{total_return:+.2f}%")


render_equity_curve()

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
