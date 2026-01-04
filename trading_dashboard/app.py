"""Grid Trading Dashboard - Main Application Entry Point.

Run with: streamlit run app.py
"""

import streamlit as st

from components.auth import check_auth, logout
from components.state import init_state, get_state
from components.api_client import clear_all_caches, fetch_health

# =============================================================================
# Page Configuration (MUST be first Streamlit call)
# =============================================================================

st.set_page_config(
    page_title="Grid Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# Initialize State
# =============================================================================

init_state()

# =============================================================================
# Authentication Gate
# =============================================================================

if not check_auth():
    st.stop()

# =============================================================================
# Page Definitions
# =============================================================================

dashboard = st.Page(
    "pages/dashboard.py",
    title="Dashboard",
    icon="📊",
    default=True,
)
positions = st.Page(
    "pages/positions_orders.py",
    title="Positions",
    icon="📋",
)
history = st.Page(
    "pages/trade_history.py",
    title="Trade History",
    icon="📜",
)
risk = st.Page(
    "pages/risk_management.py",
    title="Risk Management",
    icon="⚠️",
)
grid = st.Page(
    "pages/grid_strategy.py",
    title="Grid Strategy",
    icon="📐",
)
config = st.Page(
    "pages/configuration.py",
    title="Configuration",
    icon="⚙️",
)

# =============================================================================
# Navigation
# =============================================================================

pg = st.navigation(
    {
        "Trading": [dashboard, positions, history],
        "Strategy": [grid, risk],
        "System": [config],
    }
)

# =============================================================================
# Sidebar Components (Shared across all pages)
# =============================================================================

with st.sidebar:
    st.divider()

    # User info
    username = st.session_state.get("username", "Unknown")
    st.caption(f"👤 User: **{username}**")

    # Connection status
    health = fetch_health()
    if health.get("healthy"):
        st.caption("🟢 Backend: Connected")
    else:
        st.caption("🔴 Backend: Disconnected")

    # Read-only mode indicator
    state = get_state()
    if state.read_only_mode:
        st.caption("🔒 Mode: Read-Only")
    else:
        st.caption("🔓 Mode: Edit Enabled")

    st.divider()

    # Actions
    if st.button("🔄 Refresh All Data", use_container_width=True):
        clear_all_caches()
        st.rerun()

    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()

# =============================================================================
# Run Selected Page
# =============================================================================

pg.run()
