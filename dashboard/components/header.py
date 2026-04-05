"""CryptoTrader Dashboard - Header Strip Component.

Fixed header for BTC 1h Prediction-Strategie.
Shows: Status | Current Prediction | P&L | Uptime | Timestamp
"""

from nicegui import ui

from dashboard.state import state


def create_header() -> None:
    """Create the fixed header strip with status slots.

    Layout: [Status] | [Prediction] | [P&L] | [Uptime] | [Timestamp]
    """
    with ui.header().classes("fixed-header"):
        with ui.row().classes("header-content items-center justify-between w-full"):
            # Status indicator
            with ui.element("div").classes("header-slot status-slot") as status_container:
                _create_status_content()

            # Current prediction
            with ui.element("div").classes("header-slot prediction-slot") as pred_container:
                _create_prediction_content()

            # P&L display
            with ui.element("div").classes("header-slot pnl-slot") as pnl_container:
                _create_pnl_content()

            # Uptime
            with ui.element("div").classes("header-slot uptime-slot") as uptime_container:
                _create_uptime_content()

            # Timestamp
            with ui.element("div").classes("header-slot timestamp-slot") as timestamp_container:
                _create_timestamp_content()

    def refresh_header() -> None:
        status_container.clear()
        with status_container:
            _create_status_content()

        pred_container.clear()
        with pred_container:
            _create_prediction_content()

        pnl_container.clear()
        with pnl_container:
            _create_pnl_content()

        uptime_container.clear()
        with uptime_container:
            _create_uptime_content()

        timestamp_container.clear()
        with timestamp_container:
            _create_timestamp_content()

    ui.timer(2.0, refresh_header)


def _create_status_content() -> None:
    """Create RAG status indicator."""
    if state.is_reconnecting:
        icon, text, cls = "\u21bb", "RECONNECTING", "status-warning"
    elif state.is_offline:
        icon, text, cls = "\u25b2", "OFFLINE", "status-error"
    elif state.is_stale:
        icon, text, cls = "\u25c6", "STALE", "status-warning"
    elif state.is_healthy:
        icon, text, cls = "\u25cf", "HEALTHY", "status-healthy"
    else:
        icon, text, cls = "\u25c6", "UNKNOWN", "status-warning"

    with ui.row().classes(f"status-indicator {cls} items-center gap-2"):
        ui.label(icon).classes("status-icon")
        ui.label(text).classes("status-text")


def _create_prediction_content() -> None:
    """Show current BTC prediction (direction + confidence)."""
    pred = state.current_prediction
    if not pred:
        ui.label("BTC: --").classes("text-secondary text-xs")
        return

    direction = pred.get("direction", "?")
    confidence = pred.get("confidence", 0)
    min_conf = 0.65  # Default

    if state.model_info:
        min_conf = state.model_info.get("min_confidence", 0.65)

    if direction == "up" and confidence >= min_conf:
        arrow = "\u25b2"
        color = "#4caf50"
    elif direction == "down":
        arrow = "\u25bc"
        color = "#f44336"
    else:
        arrow = "\u25b6"
        color = "#9e9e9e"

    with ui.row().classes("items-center gap-1"):
        ui.label(f"BTC {arrow}").style(f"color: {color}; font-weight: 600; font-size: 0.85em")
        ui.label(f"{confidence:.0%}").style(f"color: {color}; font-size: 0.8em")


def _create_pnl_content() -> None:
    """P&L display: Realized | Unrealized | Total."""
    with ui.row().classes("pnl-breakdown gap-4"):
        with ui.column().classes("pnl-item"):
            ui.label("Realized").classes("pnl-label text-xs")
            _create_pnl_value(state.realized_pnl)

        with ui.column().classes("pnl-item"):
            ui.label("Unrealized").classes("pnl-label text-xs")
            _create_pnl_value(state.unrealized_pnl)

        with ui.column().classes("pnl-item"):
            ui.label("Total").classes("pnl-label text-xs font-bold")
            _create_pnl_value(state.total_pnl)


def _create_pnl_value(pnl: float) -> None:
    if pnl > 0:
        ui.label(f"+${pnl:.2f}").classes("pnl-value pnl-positive")
    elif pnl < 0:
        ui.label(f"-${abs(pnl):.2f}").classes("pnl-value pnl-negative")
    else:
        ui.label("$0.00").classes("pnl-value pnl-neutral")


def _create_uptime_content() -> None:
    """Show bot uptime."""
    ui.label(state.uptime_formatted).classes("text-secondary text-xs")


def _create_timestamp_content() -> None:
    """Last update timestamp with staleness indication."""
    timestamp = state.last_update_formatted
    cls = "timestamp-stale" if state.is_stale else "timestamp-display"
    ui.label(timestamp).classes(cls)
