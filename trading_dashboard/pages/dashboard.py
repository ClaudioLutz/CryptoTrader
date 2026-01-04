"""Dashboard Overview Page - Live metrics and equity curve."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.api_client import fetch_pnl, fetch_positions, fetch_equity, fetch_trades


st.title("📊 Trading Dashboard")

# =============================================================================
# Live Metrics Panel (Auto-refresh every 2s)
# =============================================================================


@st.fragment(run_every="2s")
def live_metrics_panel():
    """Auto-refreshing metrics panel."""
    pnl = fetch_pnl()
    positions = fetch_positions()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_pnl = pnl.get("total", 0)
        change_pct = pnl.get("change_pct", 0)
        st.metric(
            "Total P&L",
            f"${total_pnl:,.2f}",
            f"{change_pct:+.2f}%",
            delta_color="normal",
            border=True,
        )

    with col2:
        unrealized = pnl.get("unrealized", 0)
        st.metric(
            "Unrealized P&L",
            f"${unrealized:,.2f}",
            border=True,
        )

    with col3:
        position_list = positions.get("positions", [])
        st.metric(
            "Open Positions",
            len(position_list),
            border=True,
        )

    with col4:
        cycles = pnl.get("cycles", 0)
        st.metric(
            "Grid Cycles",
            cycles,
            border=True,
        )


live_metrics_panel()

st.divider()

# =============================================================================
# Equity Curve Chart
# =============================================================================


def render_equity_curve(equity_data: list):
    """Render equity curve with drawdown overlay."""
    if not equity_data:
        st.info("No equity data available yet. Start trading to see your equity curve.")
        return

    df = pd.DataFrame(equity_data)

    # Ensure timestamp column exists and is datetime
    if "timestamp" not in df.columns:
        st.warning("Equity data missing timestamp column")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"] * 100

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Equity line
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["equity"],
            name="Equity",
            line=dict(color="#2962FF", width=2),
            hovertemplate="$%{y:,.2f}<extra></extra>",
        ),
        secondary_y=False,
    )

    # Drawdown area
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["drawdown"],
            name="Drawdown %",
            fill="tozeroy",
            fillcolor="rgba(239,83,80,0.3)",
            line=dict(color="#ef5350", width=1),
            hovertemplate="%{y:.2f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="Equity Curve with Drawdown",
        hovermode="x unified",
        height=400,
        template="plotly_dark",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    fig.update_yaxes(title_text="Equity ($)", secondary_y=False)
    fig.update_yaxes(title_text="Drawdown (%)", secondary_y=True)

    st.plotly_chart(fig, use_container_width=True)


col_chart, col_trades = st.columns([2, 1])

with col_chart:
    st.subheader("Equity Curve")
    equity_data = fetch_equity()
    render_equity_curve(equity_data.get("data", []))

# =============================================================================
# Recent Trades
# =============================================================================

with col_trades:
    st.subheader("Recent Trades")
    trades_data = fetch_trades()
    trades = trades_data.get("trades", [])

    if trades:
        # Show last 10 trades
        df_trades = pd.DataFrame(trades[-10:])

        # Format for display
        if not df_trades.empty:
            display_cols = ["timestamp", "symbol", "side", "amount", "price", "pnl"]
            available_cols = [c for c in display_cols if c in df_trades.columns]

            st.dataframe(
                df_trades[available_cols],
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Time", format="HH:mm:ss"),
                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "pnl": st.column_config.NumberColumn("P&L", format="$%.2f"),
                },
                hide_index=True,
                use_container_width=True,
            )
    else:
        st.info("No trades yet")

# =============================================================================
# Error Display
# =============================================================================

# Check for API errors
pnl = fetch_pnl()
if pnl.get("error"):
    st.warning(f"API Warning: {pnl['error']}")
