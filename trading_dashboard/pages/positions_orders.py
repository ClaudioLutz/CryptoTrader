"""Positions & Orders Page - View and manage open positions."""

import streamlit as st
import pandas as pd

from components.api_client import fetch_positions, fetch_orders, get_http_client


st.title("📋 Positions & Orders")

# =============================================================================
# Filters
# =============================================================================

col1, col2 = st.columns(2)

with col1:
    symbol_filter = st.selectbox(
        "Symbol",
        ["All", "BTC/USDT", "ETH/USDT", "SOL/USDT"],
        key="positions_symbol_filter",
    )

with col2:
    side_filter = st.selectbox(
        "Side",
        ["All", "LONG", "SHORT"],
        key="positions_side_filter",
    )

st.divider()

# =============================================================================
# Positions Table (Auto-refresh)
# =============================================================================


@st.fragment(run_every="3s")
def positions_table():
    """Auto-refreshing positions table."""
    data = fetch_positions()
    positions = data.get("positions", [])

    if data.get("error"):
        st.error(f"Failed to fetch positions: {data['error']}")
        return

    if not positions:
        st.info("No open positions")
        return

    df = pd.DataFrame(positions)

    # Apply filters
    if symbol_filter != "All" and "symbol" in df.columns:
        df = df[df["symbol"] == symbol_filter]

    if side_filter != "All" and "side" in df.columns:
        df = df[df["side"].str.upper() == side_filter]

    if df.empty:
        st.info("No positions match the selected filters")
        return

    # Display with formatting
    st.dataframe(
        df,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol", width="medium"),
            "side": st.column_config.TextColumn("Side", width="small"),
            "amount": st.column_config.NumberColumn("Amount", format="%.4f"),
            "entry_price": st.column_config.NumberColumn("Entry", format="$%.2f"),
            "current_price": st.column_config.NumberColumn("Current", format="$%.2f"),
            "pnl": st.column_config.NumberColumn("P&L", format="$%.2f"),
            "pnl_pct": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
        },
        hide_index=True,
        use_container_width=True,
    )


positions_table()

st.divider()

# =============================================================================
# Pending Orders
# =============================================================================

st.subheader("Pending Orders")


@st.fragment(run_every="3s")
def orders_table():
    """Auto-refreshing orders table."""
    # Get symbol filter value
    selected_symbol = None if symbol_filter == "All" else symbol_filter
    data = fetch_orders(selected_symbol)
    orders = data.get("orders", [])

    if data.get("error"):
        st.error(f"Failed to fetch orders: {data['error']}")
        return

    if not orders:
        st.info("No pending orders")
        return

    df = pd.DataFrame(orders)

    # Apply side filter
    if side_filter != "All" and "side" in df.columns:
        df = df[df["side"].str.upper() == side_filter.upper()]

    if df.empty:
        st.info("No orders match the selected filters")
        return

    # Show order count
    buy_orders = len(df[df["side"].str.lower() == "buy"]) if "side" in df.columns else 0
    sell_orders = len(df[df["side"].str.lower() == "sell"]) if "side" in df.columns else 0
    st.caption(f"**{len(df)}** pending orders ({buy_orders} buy, {sell_orders} sell)")

    # Display with formatting
    st.dataframe(
        df,
        column_config={
            "id": st.column_config.TextColumn("Order ID", width="medium"),
            "symbol": st.column_config.TextColumn("Symbol", width="medium"),
            "side": st.column_config.TextColumn("Side", width="small"),
            "type": st.column_config.TextColumn("Type", width="small"),
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "amount": st.column_config.NumberColumn("Amount", format="%.6f"),
            "filled": st.column_config.NumberColumn("Filled", format="%.6f"),
            "remaining": st.column_config.NumberColumn("Remaining", format="%.6f"),
            "status": st.column_config.TextColumn("Status", width="small"),
        },
        hide_index=True,
        use_container_width=True,
    )


orders_table()

# =============================================================================
# Order Actions (Non-auto-refresh fragment)
# =============================================================================

st.divider()
st.subheader("Order Actions")


@st.fragment
def order_actions():
    """Order management actions."""
    col1, col2 = st.columns(2)

    with col1:
        order_id = st.text_input("Order ID to Cancel", key="cancel_order_id")

        if st.button("Cancel Order", type="secondary", disabled=not order_id):
            st.session_state.pending_cancel = order_id

    with col2:
        if st.button("Cancel All Orders", type="secondary"):
            st.session_state.pending_cancel_all = True


order_actions()

# =============================================================================
# Confirmation Dialogs
# =============================================================================


@st.dialog("Confirm Order Cancellation")
def confirm_cancel():
    """Confirmation dialog for order cancellation."""
    order_id = st.session_state.get("pending_cancel")
    st.write(f"Are you sure you want to cancel order **{order_id}**?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Cancel", type="primary"):
            try:
                response = get_http_client().post(
                    "/api/orders/cancel",
                    json={"order_id": order_id},
                )
                if response.status_code == 200:
                    st.success(f"Order {order_id} cancelled")
                else:
                    st.error(f"Failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_cancel = None
                st.rerun()

    with col2:
        if st.button("No, Keep"):
            st.session_state.pending_cancel = None
            st.rerun()


@st.dialog("Confirm Cancel All Orders")
def confirm_cancel_all():
    """Confirmation dialog for cancelling all orders."""
    st.warning("This will cancel ALL pending orders!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Cancel All", type="primary"):
            try:
                response = get_http_client().post("/api/orders/cancel-all")
                if response.status_code == 200:
                    st.success("All orders cancelled")
                else:
                    st.error(f"Failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_cancel_all = False
                st.rerun()

    with col2:
        if st.button("No, Keep"):
            st.session_state.pending_cancel_all = False
            st.rerun()


# Trigger dialogs
if st.session_state.get("pending_cancel"):
    confirm_cancel()

if st.session_state.get("pending_cancel_all"):
    confirm_cancel_all()
