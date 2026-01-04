"""Shared state management for the dashboard."""

import streamlit as st
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DashboardState:
    """Dashboard state container.

    Attributes:
        config: Current bot configuration
        read_only_mode: Whether configuration editing is locked
        last_refresh: Timestamp of last data refresh
        selected_symbol: Currently selected trading symbol
    """

    config: dict[str, Any] = field(default_factory=dict)
    read_only_mode: bool = True
    last_refresh: str | None = None
    selected_symbol: str = "BTC/USDT"


def init_state() -> None:
    """Initialize session state on app startup.

    Call this in app.py before any other Streamlit operations.
    """
    if "dashboard_state" not in st.session_state:
        st.session_state.dashboard_state = DashboardState()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "username" not in st.session_state:
        st.session_state.username = None

    if "pending_config" not in st.session_state:
        st.session_state.pending_config = None


def get_state() -> DashboardState:
    """Get the current dashboard state.

    Returns:
        DashboardState: The current state object
    """
    if "dashboard_state" not in st.session_state:
        init_state()
    return st.session_state.dashboard_state


def clear_state() -> None:
    """Clear all session state (for logout)."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()
