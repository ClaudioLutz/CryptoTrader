"""Trade History Page - View and analyze past trades with AgGrid."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from components.api_client import fetch_trades

# Try to import AgGrid, fallback to basic dataframe if not available
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

    AGGRID_AVAILABLE = True
except ImportError:
    AGGRID_AVAILABLE = False


st.title("📜 Trade History")

# =============================================================================
# Filters
# =============================================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    symbol_filter = st.selectbox(
        "Symbol",
        ["All", "BTC/USDT", "ETH/USDT", "SOL/USDT"],
        key="history_symbol_filter",
    )

with col2:
    side_filter = st.selectbox(
        "Side",
        ["All", "BUY", "SELL"],
        key="history_side_filter",
    )

with col3:
    # Date range filter
    date_options = ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Custom"]
    date_filter = st.selectbox("Date Range", date_options, key="history_date_filter")

with col4:
    pnl_filter = st.selectbox(
        "P&L",
        ["All", "Profitable", "Loss"],
        key="history_pnl_filter",
    )

# Custom date range
if date_filter == "Custom":
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
    with col_end:
        end_date = st.date_input("End Date", value=datetime.now())
else:
    start_date = None
    end_date = None

st.divider()

# =============================================================================
# Load and Filter Data
# =============================================================================

data = fetch_trades()
trades = data.get("trades", [])

if data.get("error"):
    st.error(f"Failed to fetch trades: {data['error']}")
    st.stop()

if not trades:
    st.info("No trade history available")
    st.stop()

df = pd.DataFrame(trades)

# Convert timestamp to datetime if present
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])

# Apply filters
if symbol_filter != "All" and "symbol" in df.columns:
    df = df[df["symbol"] == symbol_filter]

if side_filter != "All" and "side" in df.columns:
    df = df[df["side"].str.upper() == side_filter]

if pnl_filter != "All" and "pnl" in df.columns:
    if pnl_filter == "Profitable":
        df = df[df["pnl"] > 0]
    else:
        df = df[df["pnl"] <= 0]

# Date filtering
if date_filter != "All Time" and "timestamp" in df.columns:
    now = datetime.now()
    if date_filter == "Today":
        df = df[df["timestamp"].dt.date == now.date()]
    elif date_filter == "Last 7 Days":
        df = df[df["timestamp"] >= now - timedelta(days=7)]
    elif date_filter == "Last 30 Days":
        df = df[df["timestamp"] >= now - timedelta(days=30)]
    elif date_filter == "Custom" and start_date and end_date:
        df = df[
            (df["timestamp"].dt.date >= start_date) & (df["timestamp"].dt.date <= end_date)
        ]

# =============================================================================
# Summary Statistics
# =============================================================================

if not df.empty and "pnl" in df.columns:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", len(df), border=True)

    with col2:
        total_pnl = df["pnl"].sum()
        st.metric("Total P&L", f"${total_pnl:,.2f}", border=True)

    with col3:
        win_rate = (df["pnl"] > 0).mean() * 100 if len(df) > 0 else 0
        st.metric("Win Rate", f"{win_rate:.1f}%", border=True)

    with col4:
        avg_pnl = df["pnl"].mean()
        st.metric("Avg P&L", f"${avg_pnl:,.2f}", border=True)

    st.divider()

# =============================================================================
# Trade History Table
# =============================================================================

if df.empty:
    st.info("No trades match the selected filters")
    st.stop()

if AGGRID_AVAILABLE:
    # AgGrid for advanced features
    gb = GridOptionsBuilder.from_dataframe(df)

    # Enable core features
    gb.configure_default_column(filterable=True, sortable=True, resizable=True)
    gb.configure_pagination(enabled=True, paginationPageSize=25)
    gb.configure_selection(selection_mode="multiple", use_checkbox=True)

    # P&L conditional formatting
    pnl_style = JsCode(
        """
    function(params) {
        if (params.value > 0) return {'color': '#26a69a', 'fontWeight': 'bold'};
        if (params.value < 0) return {'color': '#ef5350', 'fontWeight': 'bold'};
        return {};
    }
    """
    )

    # Side column styling
    side_style = JsCode(
        """
    function(params) {
        if (params.value === 'BUY' || params.value === 'buy') {
            return {'backgroundColor': 'rgba(38,166,154,0.2)', 'color': '#26a69a'};
        }
        if (params.value === 'SELL' || params.value === 'sell') {
            return {'backgroundColor': 'rgba(239,83,80,0.2)', 'color': '#ef5350'};
        }
        return {};
    }
    """
    )

    # Configure specific columns
    if "pnl" in df.columns:
        gb.configure_column("pnl", cellStyle=pnl_style, type=["numericColumn"])

    if "side" in df.columns:
        gb.configure_column("side", cellStyle=side_style)

    grid_response = AgGrid(
        df,
        gridOptions=gb.build(),
        allow_unsafe_jscode=True,
        theme="balham-dark",
        height=500,
        fit_columns_on_grid_load=True,
    )

    # Export selected rows
    selected_rows = grid_response.get("selected_rows")
    if selected_rows is not None and len(selected_rows) > 0:
        st.divider()
        st.subheader("Selected Trades")

        selected_df = pd.DataFrame(selected_rows)

        col1, col2 = st.columns([3, 1])
        with col1:
            st.dataframe(selected_df, hide_index=True)

        with col2:
            csv = selected_df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                "selected_trades.csv",
                "text/csv",
                use_container_width=True,
            )

else:
    # Fallback to basic dataframe
    st.warning("Install streamlit-aggrid for advanced table features")

    st.dataframe(
        df,
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Time", format="YYYY-MM-DD HH:mm"),
            "symbol": st.column_config.TextColumn("Symbol"),
            "side": st.column_config.TextColumn("Side"),
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "amount": st.column_config.NumberColumn("Amount", format="%.4f"),
            "pnl": st.column_config.NumberColumn("P&L", format="$%.2f"),
        },
        hide_index=True,
        use_container_width=True,
        height=500,
    )

    # Export all
    csv = df.to_csv(index=False)
    st.download_button(
        "Download All Trades (CSV)",
        csv,
        "trade_history.csv",
        "text/csv",
    )
