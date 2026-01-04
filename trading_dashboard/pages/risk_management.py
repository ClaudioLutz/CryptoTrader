"""Risk Management Page - Monitor risk metrics and circuit breaker status."""

import streamlit as st

from components.api_client import fetch_status, fetch_health


st.title("⚠️ Risk Management")

# =============================================================================
# System Status Indicators (Auto-refresh)
# =============================================================================


@st.fragment(run_every="5s")
def status_indicators():
    """Auto-refreshing system status indicators."""
    status = fetch_status()
    health = fetch_health()

    def status_icon(healthy: bool) -> str:
        return "🟢" if healthy else "🔴"

    st.subheader("System Status")

    cols = st.columns(5)

    with cols[0]:
        is_healthy = health.get("healthy", False)
        st.markdown(f"{status_icon(is_healthy)} **API Health**")
        st.caption("Backend connection")

    with cols[1]:
        ws_connected = status.get("ws_connected", False)
        st.markdown(f"{status_icon(ws_connected)} **WebSocket**")
        st.caption("Real-time feed")

    with cols[2]:
        circuit_ok = not status.get("circuit_breaker_active", False)
        st.markdown(f"{status_icon(circuit_ok)} **Circuit Breaker**")
        st.caption("Trading protection")

    with cols[3]:
        trading_enabled = status.get("trading_enabled", False)
        st.markdown(f"{status_icon(trading_enabled)} **Trading**")
        st.caption("Order execution")

    with cols[4]:
        db_connected = status.get("db_connected", False)
        st.markdown(f"{status_icon(db_connected)} **Database**")
        st.caption("Data persistence")


status_indicators()

st.divider()

# =============================================================================
# Risk Metrics (Auto-refresh)
# =============================================================================


@st.fragment(run_every="5s")
def risk_metrics():
    """Auto-refreshing risk metrics panel."""
    status = fetch_status()

    st.subheader("Risk Metrics")

    col1, col2, col3 = st.columns(3)

    # Drawdown
    with col1:
        drawdown = status.get("current_drawdown", 0)
        max_drawdown = status.get("max_drawdown_limit", 10)
        drawdown_pct = (drawdown / max_drawdown) * 100 if max_drawdown > 0 else 0

        st.metric(
            "Current Drawdown",
            f"{drawdown:.2f}%",
            delta=f"Limit: {max_drawdown}%",
            delta_color="off",
            border=True,
        )

        # Progress bar (red when high)
        if drawdown_pct > 80:
            st.progress(min(drawdown_pct / 100, 1.0), text="CRITICAL")
        elif drawdown_pct > 50:
            st.progress(min(drawdown_pct / 100, 1.0), text="Warning")
        else:
            st.progress(min(drawdown_pct / 100, 1.0))

    # Daily Loss
    with col2:
        daily_loss = status.get("daily_loss", 0)
        daily_limit = status.get("daily_loss_limit", 1000)
        daily_pct = (abs(daily_loss) / daily_limit) * 100 if daily_limit > 0 else 0

        st.metric(
            "Daily Loss",
            f"${daily_loss:,.2f}",
            delta=f"Limit: ${daily_limit:,.2f}",
            delta_color="off",
            border=True,
        )

        if daily_pct > 80:
            st.progress(min(daily_pct / 100, 1.0), text="CRITICAL")
        elif daily_pct > 50:
            st.progress(min(daily_pct / 100, 1.0), text="Warning")
        else:
            st.progress(min(daily_pct / 100, 1.0))

    # Circuit Breaker
    with col3:
        circuit_breaker = status.get("circuit_breaker_active", False)
        consecutive_losses = status.get("consecutive_losses", 0)
        max_consecutive = status.get("max_consecutive_losses", 5)

        st.metric(
            "Circuit Breaker",
            "ACTIVE" if circuit_breaker else "Inactive",
            delta="Trading halted" if circuit_breaker else "Normal",
            delta_color="inverse" if circuit_breaker else "off",
            border=True,
        )

        st.caption(f"Consecutive losses: {consecutive_losses}/{max_consecutive}")


risk_metrics()

st.divider()

# =============================================================================
# Risk Limits Configuration (Read-only display)
# =============================================================================

st.subheader("Risk Limits")


@st.fragment(run_every="30s")
def risk_limits_display():
    """Display current risk limit configuration."""
    status = fetch_status()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Drawdown Protection**")
        st.markdown(f"- Max Drawdown: `{status.get('max_drawdown_limit', 10)}%`")
        st.markdown(f"- Current Drawdown: `{status.get('current_drawdown', 0):.2f}%`")
        st.markdown(f"- Peak Equity: `${status.get('peak_equity', 0):,.2f}`")

    with col2:
        st.markdown("**Loss Limits**")
        st.markdown(f"- Daily Loss Limit: `${status.get('daily_loss_limit', 1000):,.2f}`")
        st.markdown(f"- Max Consecutive Losses: `{status.get('max_consecutive_losses', 5)}`")
        st.markdown(f"- Current Daily Loss: `${status.get('daily_loss', 0):,.2f}`")


risk_limits_display()

st.divider()

# =============================================================================
# Circuit Breaker Events
# =============================================================================

st.subheader("Circuit Breaker History")


@st.fragment(run_every="30s")
def circuit_breaker_history():
    """Display circuit breaker event history."""
    status = fetch_status()
    events = status.get("circuit_breaker_events", [])

    if not events:
        st.info("No circuit breaker events recorded")
        return

    for event in events[-5:]:  # Show last 5 events
        with st.expander(f"{event.get('timestamp', 'Unknown time')} - {event.get('reason', 'Unknown')}"):
            st.json(event)


circuit_breaker_history()

# =============================================================================
# Manual Controls
# =============================================================================

st.divider()
st.subheader("Manual Controls")


@st.fragment
def manual_controls():
    """Manual risk control actions."""
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Reset Circuit Breaker", type="secondary", use_container_width=True):
            st.session_state.pending_reset_cb = True

    with col2:
        if st.button("Reset Daily Counters", type="secondary", use_container_width=True):
            st.session_state.pending_reset_daily = True

    with col3:
        if st.button("Emergency Stop", type="primary", use_container_width=True):
            st.session_state.pending_emergency_stop = True


manual_controls()

# =============================================================================
# Confirmation Dialogs
# =============================================================================


@st.dialog("Confirm Circuit Breaker Reset")
def confirm_reset_cb():
    """Confirmation for circuit breaker reset."""
    st.warning("This will reset the circuit breaker and allow trading to resume.")
    st.info("Make sure you understand why the circuit breaker was triggered before resetting.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Reset", type="primary"):
            st.success("Circuit breaker reset (API call would go here)")
            st.session_state.pending_reset_cb = False
            st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_reset_cb = False
            st.rerun()


@st.dialog("Emergency Stop")
def confirm_emergency_stop():
    """Confirmation for emergency stop."""
    st.error("EMERGENCY STOP will immediately:")
    st.markdown("- Cancel all pending orders")
    st.markdown("- Close all open positions (at market)")
    st.markdown("- Disable trading")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("CONFIRM EMERGENCY STOP", type="primary"):
            st.error("Emergency stop executed (API call would go here)")
            st.session_state.pending_emergency_stop = False
            st.rerun()

    with col2:
        if st.button("Cancel"):
            st.session_state.pending_emergency_stop = False
            st.rerun()


# Trigger dialogs
if st.session_state.get("pending_reset_cb"):
    confirm_reset_cb()

if st.session_state.get("pending_reset_daily"):
    st.success("Daily counters reset (API call would go here)")
    st.session_state.pending_reset_daily = False

if st.session_state.get("pending_emergency_stop"):
    confirm_emergency_stop()
