"""Grid Strategy Page - Visualize grid levels and configuration."""

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd

from components.api_client import fetch_status, fetch_positions


st.title("📐 Grid Strategy")

# =============================================================================
# Grid Parameters (Auto-refresh)
# =============================================================================


@st.fragment(run_every="5s")
def grid_parameters():
    """Display current grid parameters."""
    status = fetch_status()
    grid_config = status.get("grid_config", {})

    if not grid_config:
        st.warning("No grid configuration found. Configure your grid strategy first.")
        return

    st.subheader("Grid Parameters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Lower Price",
            f"${grid_config.get('lower_price', 0):,.2f}",
            border=True,
        )

    with col2:
        st.metric(
            "Upper Price",
            f"${grid_config.get('upper_price', 0):,.2f}",
            border=True,
        )

    with col3:
        st.metric(
            "Grid Count",
            grid_config.get("num_grids", 0),
            border=True,
        )

    with col4:
        st.metric(
            "Grid Step",
            f"${grid_config.get('grid_step', 0):,.2f}",
            border=True,
        )

    # Additional info
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        st.metric(
            "Investment",
            f"${grid_config.get('total_investment', 0):,.2f}",
            border=True,
        )

    with col6:
        st.metric(
            "Per Grid",
            f"${grid_config.get('investment_per_grid', 0):,.2f}",
            border=True,
        )

    with col7:
        spacing = grid_config.get("spacing_type", "arithmetic")
        st.metric(
            "Spacing",
            spacing.capitalize(),
            border=True,
        )

    with col8:
        symbol = grid_config.get("symbol", "BTC/USDT")
        st.metric(
            "Symbol",
            symbol,
            border=True,
        )


grid_parameters()

st.divider()

# =============================================================================
# Grid Visualization
# =============================================================================


def render_grid_levels(current_price: float, grid_config: dict):
    """Render grid strategy price levels visualization."""
    grid_start = grid_config.get("lower_price", 0)
    grid_end = grid_config.get("upper_price", 0)
    grid_step = grid_config.get("grid_step", 0)

    if not all([grid_start, grid_end, grid_step]) or grid_step <= 0:
        st.warning("Invalid grid configuration")
        return

    # Calculate grid levels
    levels = np.arange(grid_start, grid_end + grid_step, grid_step)
    buy_levels = levels[levels < current_price]
    sell_levels = levels[levels > current_price]

    fig = go.Figure()

    # Add grid zone background
    fig.add_shape(
        type="rect",
        x0=0,
        x1=1,
        y0=grid_start,
        y1=grid_end,
        xref="paper",
        fillcolor="rgba(128,128,128,0.1)",
        line=dict(color="rgba(128,128,128,0.5)", width=1, dash="dash"),
    )

    # Current price line
    fig.add_hline(
        y=current_price,
        line=dict(color="#FFD700", width=3, dash="dash"),
        annotation_text=f"Current: ${current_price:,.2f}",
        annotation_position="right",
    )

    # Buy levels (green)
    for i, level in enumerate(buy_levels):
        fig.add_hline(
            y=level,
            line=dict(color="rgba(38,166,154,0.6)", width=1),
        )
        # Add shaded zone
        if i < len(buy_levels) - 1:
            fig.add_shape(
                type="rect",
                x0=0,
                x1=0.4,
                y0=level,
                y1=buy_levels[i + 1] if i + 1 < len(buy_levels) else level + grid_step,
                xref="paper",
                fillcolor="rgba(38,166,154,0.1)",
                line_width=0,
            )

    # Sell levels (red)
    for i, level in enumerate(sell_levels):
        fig.add_hline(
            y=level,
            line=dict(color="rgba(239,83,80,0.6)", width=1),
        )
        # Add shaded zone
        if i < len(sell_levels) - 1:
            fig.add_shape(
                type="rect",
                x0=0.6,
                x1=1,
                y0=level,
                y1=sell_levels[i + 1] if i + 1 < len(sell_levels) else level + grid_step,
                xref="paper",
                fillcolor="rgba(239,83,80,0.1)",
                line_width=0,
            )

    # Add annotations
    fig.add_annotation(
        x=0.2,
        y=grid_start + (current_price - grid_start) / 2,
        text="BUY ZONE",
        showarrow=False,
        font=dict(color="#26a69a", size=14),
        xref="paper",
    )

    fig.add_annotation(
        x=0.8,
        y=current_price + (grid_end - current_price) / 2,
        text="SELL ZONE",
        showarrow=False,
        font=dict(color="#ef5350", size=14),
        xref="paper",
    )

    fig.update_layout(
        title=f"Grid Levels - {grid_config.get('symbol', 'BTC/USDT')}",
        yaxis_title="Price ($)",
        height=500,
        showlegend=False,
        template="plotly_dark",
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(tickformat="$,.0f"),
        margin=dict(l=80, r=20, t=40, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)


st.subheader("Grid Levels Visualization")

status = fetch_status()
grid_config = status.get("grid_config", {})

if grid_config:
    # Get current price from positions or use midpoint
    positions_data = fetch_positions()
    current_price = positions_data.get("current_price", 0)

    if current_price == 0:
        # Fallback to grid midpoint
        current_price = (
            grid_config.get("lower_price", 0) + grid_config.get("upper_price", 0)
        ) / 2

    if current_price > 0:
        render_grid_levels(current_price, grid_config)
    else:
        st.info("Current price not available")
else:
    st.info("Configure grid strategy to see visualization")

st.divider()

# =============================================================================
# Grid Levels Table
# =============================================================================

st.subheader("Grid Levels Detail")


@st.fragment(run_every="10s")
def grid_levels_table():
    """Display grid levels with order status."""
    status = fetch_status()
    grid_config = status.get("grid_config", {})

    if not grid_config:
        st.info("No grid configuration")
        return

    grid_start = grid_config.get("lower_price", 0)
    grid_end = grid_config.get("upper_price", 0)
    grid_step = grid_config.get("grid_step", 0)

    if not all([grid_start, grid_end, grid_step]) or grid_step <= 0:
        return

    # Generate levels
    levels = np.arange(grid_start, grid_end + grid_step, grid_step)

    # Get current orders/fills from status
    filled_levels = set(status.get("filled_levels", []))
    pending_levels = set(status.get("pending_levels", []))

    # Build table data
    data = []
    for level in levels:
        level_rounded = round(level, 2)
        if level_rounded in filled_levels:
            order_status = "Filled"
        elif level_rounded in pending_levels:
            order_status = "Pending"
        else:
            order_status = "Not Placed"

        data.append(
            {
                "Level": f"${level:,.2f}",
                "Type": "BUY" if level < (grid_start + grid_end) / 2 else "SELL",
                "Status": order_status,
            }
        )

    df = pd.DataFrame(data)

    st.dataframe(
        df,
        column_config={
            "Level": st.column_config.TextColumn("Price Level", width="medium"),
            "Type": st.column_config.TextColumn("Order Type", width="small"),
            "Status": st.column_config.TextColumn("Status", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        height=300,
    )


grid_levels_table()

# =============================================================================
# Grid Statistics
# =============================================================================

st.divider()
st.subheader("Grid Statistics")


@st.fragment(run_every="10s")
def grid_statistics():
    """Display grid trading statistics."""
    status = fetch_status()
    grid_stats = status.get("grid_stats", {})

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Completed Cycles",
            grid_stats.get("completed_cycles", 0),
            border=True,
        )

    with col2:
        st.metric(
            "Total Grid Profit",
            f"${grid_stats.get('total_profit', 0):,.2f}",
            border=True,
        )

    with col3:
        st.metric(
            "Avg Profit/Cycle",
            f"${grid_stats.get('avg_profit_per_cycle', 0):,.2f}",
            border=True,
        )

    with col4:
        st.metric(
            "Active Levels",
            f"{grid_stats.get('active_levels', 0)}/{grid_stats.get('total_levels', 0)}",
            border=True,
        )


grid_statistics()
