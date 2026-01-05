"""Configuration Page - Bot settings with safety controls."""

import streamlit as st

from components.state import get_state
from components.api_client import fetch_status, get_http_client


st.title("⚙️ Configuration")

state = get_state()

# =============================================================================
# Safety Toggle (in page, not sidebar to ensure visibility)
# =============================================================================

col_toggle, col_info = st.columns([1, 3])

with col_toggle:
    state.read_only_mode = st.toggle(
        "🔒 Read-Only Mode",
        value=state.read_only_mode,
        key="config_read_only_toggle",
    )

with col_info:
    if state.read_only_mode:
        st.info("Configuration is **read-only**. Disable the lock to make changes.")
    else:
        st.warning("Edit mode **enabled**. Changes will be applied to the live bot!")

st.divider()

# =============================================================================
# Current Configuration Display
# =============================================================================

status = fetch_status()
current_config = status.get("grid_config", {})

# =============================================================================
# Grid Parameters Form
# =============================================================================

st.subheader("Grid Parameters")

with st.form("grid_config_form"):
    col1, col2 = st.columns(2)

    with col1:
        symbol = st.selectbox(
            "Trading Pair",
            ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            index=0,
            disabled=state.read_only_mode,
        )

        lower_price = st.number_input(
            "Lower Price ($)",
            min_value=0.0,
            value=float(current_config.get("lower_price", 40000)),
            step=100.0,
            disabled=state.read_only_mode,
        )

        upper_price = st.number_input(
            "Upper Price ($)",
            min_value=0.0,
            value=float(current_config.get("upper_price", 50000)),
            step=100.0,
            disabled=state.read_only_mode,
        )

        num_grids = st.number_input(
            "Number of Grids",
            min_value=2,
            max_value=100,
            value=int(current_config.get("num_grids", 10)),
            disabled=state.read_only_mode,
        )

    with col2:
        total_investment = st.number_input(
            "Total Investment ($)",
            min_value=0.0,
            value=float(current_config.get("total_investment", 1000)),
            step=100.0,
            disabled=state.read_only_mode,
        )

        spacing_type = st.selectbox(
            "Grid Spacing",
            ["arithmetic", "geometric"],
            index=0 if current_config.get("spacing_type", "arithmetic") == "arithmetic" else 1,
            disabled=state.read_only_mode,
        )

        # Calculated values (display only)
        if upper_price > lower_price and num_grids > 1:
            grid_step = (upper_price - lower_price) / (num_grids - 1)
            investment_per_grid = total_investment / num_grids
        else:
            grid_step = 0
            investment_per_grid = 0

        st.metric("Grid Step (calculated)", f"${grid_step:,.2f}")
        st.metric("Investment per Grid", f"${investment_per_grid:,.2f}")

    submitted = st.form_submit_button(
        "Save Grid Configuration",
        disabled=state.read_only_mode,
        type="primary",
    )

    if submitted:
        # Validate inputs before proceeding
        validation_errors = []

        if upper_price <= lower_price:
            validation_errors.append("Upper price must be greater than lower price")

        if num_grids < 2:
            validation_errors.append("Number of grids must be at least 2")

        if total_investment <= 0:
            validation_errors.append("Total investment must be greater than 0")

        if lower_price <= 0:
            validation_errors.append("Lower price must be greater than 0")

        if validation_errors:
            for error in validation_errors:
                st.error(f"❌ {error}")
        else:
            st.session_state.pending_config = {
                "symbol": symbol,
                "lower_price": lower_price,
                "upper_price": upper_price,
                "num_grids": num_grids,
                "total_investment": total_investment,
                "spacing_type": spacing_type,
                "grid_step": grid_step,
                "investment_per_grid": investment_per_grid,
            }

st.divider()

# =============================================================================
# Risk Parameters Form
# =============================================================================

st.subheader("Risk Parameters")

with st.form("risk_config_form"):
    col1, col2 = st.columns(2)

    with col1:
        stop_loss_pct = st.number_input(
            "Stop Loss (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(status.get("stop_loss_pct", 5.0)),
            step=0.5,
            disabled=state.read_only_mode,
            help="Stop loss below lower grid boundary",
        )

        max_drawdown = st.number_input(
            "Max Drawdown (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(status.get("max_drawdown_limit", 10.0)),
            step=1.0,
            disabled=state.read_only_mode,
        )

    with col2:
        daily_loss_limit = st.number_input(
            "Daily Loss Limit ($)",
            min_value=0.0,
            value=float(status.get("daily_loss_limit", 500)),
            step=50.0,
            disabled=state.read_only_mode,
        )

        max_consecutive_losses = st.number_input(
            "Max Consecutive Losses",
            min_value=1,
            max_value=20,
            value=int(status.get("max_consecutive_losses", 5)),
            disabled=state.read_only_mode,
        )

    risk_submitted = st.form_submit_button(
        "Save Risk Configuration",
        disabled=state.read_only_mode,
        type="primary",
    )

    if risk_submitted:
        st.session_state.pending_risk_config = {
            "stop_loss_pct": stop_loss_pct,
            "max_drawdown_limit": max_drawdown,
            "daily_loss_limit": daily_loss_limit,
            "max_consecutive_losses": max_consecutive_losses,
        }

st.divider()

# =============================================================================
# Trading Controls
# =============================================================================

st.subheader("Trading Controls")

col1, col2, col3 = st.columns(3)

with col1:
    trading_enabled = status.get("trading_enabled", False)
    if st.button(
        "Disable Trading" if trading_enabled else "Enable Trading",
        disabled=state.read_only_mode,
        type="secondary" if trading_enabled else "primary",
        use_container_width=True,
    ):
        st.session_state.pending_trading_toggle = not trading_enabled

with col2:
    if st.button(
        "Restart Strategy",
        disabled=state.read_only_mode,
        type="secondary",
        use_container_width=True,
    ):
        st.session_state.pending_restart = True

with col3:
    if st.button(
        "Clear All Orders",
        disabled=state.read_only_mode,
        type="secondary",
        use_container_width=True,
    ):
        st.session_state.pending_clear_orders = True

# =============================================================================
# Confirmation Dialogs
# =============================================================================


@st.dialog("Confirm Configuration Change")
def confirm_config_save():
    """Confirmation dialog for grid config changes."""
    st.write("Apply these grid configuration changes?")
    st.json(st.session_state.pending_config)

    st.warning("This may affect live trading. Existing orders may be cancelled.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm", type="primary"):
            try:
                response = get_http_client().post(
                    "/api/config/grid",
                    json=st.session_state.pending_config,
                )
                if response.status_code == 200:
                    st.success("Configuration saved!")
                    state.config.update(st.session_state.pending_config)
                else:
                    st.error(f"Failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_config = None
                st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_config = None
            st.rerun()


@st.dialog("Confirm Risk Configuration Change")
def confirm_risk_save():
    """Confirmation dialog for risk config changes."""
    st.write("Apply these risk configuration changes?")
    st.json(st.session_state.pending_risk_config)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm", type="primary"):
            try:
                response = get_http_client().post(
                    "/api/config/risk",
                    json=st.session_state.pending_risk_config,
                )
                if response.status_code == 200:
                    st.success("Risk configuration saved!")
                else:
                    st.error(f"Failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_risk_config = None
                st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_risk_config = None
            st.rerun()


@st.dialog("Confirm Trading Toggle")
def confirm_trading_toggle():
    """Confirmation for enabling/disabling trading."""
    action = "Enable" if st.session_state.pending_trading_toggle else "Disable"
    st.warning(f"Are you sure you want to **{action}** trading?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"Yes, {action}", type="primary"):
            try:
                response = get_http_client().post(
                    "/api/trading/toggle",
                    json={"enabled": st.session_state.pending_trading_toggle},
                )
                if response.status_code == 200:
                    st.success(f"Trading {action.lower()}d successfully!")
                else:
                    st.error(f"Failed to {action.lower()} trading: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_trading_toggle = None
                st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_trading_toggle = None
            st.rerun()


@st.dialog("Confirm Strategy Restart")
def confirm_restart():
    """Confirmation for strategy restart."""
    st.warning("Restarting the strategy will:")
    st.markdown("- Cancel all pending orders")
    st.markdown("- Recalculate grid levels")
    st.markdown("- Place new orders based on current price")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm Restart", type="primary"):
            try:
                response = get_http_client().post("/api/strategy/restart")
                if response.status_code == 200:
                    st.success("Strategy restarted successfully!")
                else:
                    st.error(f"Failed to restart strategy: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_restart = False
                st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_restart = False
            st.rerun()


@st.dialog("Confirm Clear All Orders")
def confirm_clear_orders():
    """Confirmation for clearing all orders."""
    st.warning("This will cancel ALL pending grid orders!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Clear All", type="primary"):
            try:
                response = get_http_client().post("/api/orders/cancel-all")
                if response.status_code == 200:
                    st.success("All orders cleared successfully!")
                else:
                    st.error(f"Failed to clear orders: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                st.session_state.pending_clear_orders = False
                st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_clear_orders = False
            st.rerun()


# Trigger dialogs
if st.session_state.get("pending_config"):
    confirm_config_save()

if st.session_state.get("pending_risk_config"):
    confirm_risk_save()

if st.session_state.get("pending_trading_toggle") is not None:
    confirm_trading_toggle()

if st.session_state.get("pending_restart"):
    confirm_restart()

if st.session_state.get("pending_clear_orders"):
    confirm_clear_orders()
