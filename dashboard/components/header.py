"""CryptoTrader Dashboard - Header Strip Component.

Fixed header that answers "Is everything okay?" in under 5 seconds.
Contains slots for: status, P&L, pair count, order count, timestamp.

Uses @ui.refreshable to enable reactive updates when state changes.
"""

from nicegui import ui

from dashboard.state import state


def create_header() -> None:
    """Create the fixed header strip with status slots.

    Layout: [Status] | [P&L] | [Pair Count] | [Order Count] | [Timestamp]

    The header uses sticky positioning to remain visible during scroll.
    Individual slots are populated by their respective components:
    - Story 3.2: RAG status indicator
    - Story 3.3: Last updated timestamp
    - Story 3.4: Total P&L display
    - Story 3.5: Pair count and order count

    Uses closures to ensure per-client container references for multi-client support.
    """
    # Create containers in local scope (per-client)
    with ui.header().classes("fixed-header"):
        with ui.row().classes("header-content items-center justify-between w-full"):
            # Status indicator slot (Story 3.2)
            with ui.element("div").classes("header-slot status-slot") as status_container:
                _create_status_content()

            # P&L display slot (Story 3.4)
            with ui.element("div").classes("header-slot pnl-slot") as pnl_container:
                _create_pnl_content()

            # Pair count slot (Story 3.5)
            with ui.element("div").classes("header-slot pairs-slot") as pairs_container:
                _create_pair_count_content()

            # Order count slot (Story 3.5)
            with ui.element("div").classes("header-slot orders-slot") as orders_container:
                _create_order_count_content()

            # Timestamp slot (Story 3.3)
            with ui.element("div").classes("header-slot timestamp-slot") as timestamp_container:
                _create_timestamp_content()

    # Create refresh function with closure over local containers
    def refresh_header() -> None:
        """Refresh all header components with current state data."""
        status_container.clear()
        with status_container:
            _create_status_content()

        pnl_container.clear()
        with pnl_container:
            _create_pnl_content()

        pairs_container.clear()
        with pairs_container:
            _create_pair_count_content()

        orders_container.clear()
        with orders_container:
            _create_order_count_content()

        timestamp_container.clear()
        with timestamp_container:
            _create_timestamp_content()

    # Set up auto-refresh timer (every 2 seconds to match tier1 polling)
    ui.timer(2.0, refresh_header)


def _create_status_content() -> None:
    """Create RAG status indicator with icon + text (Story 3.2, 6.4).

    Uses unique icons for accessibility (not color alone):
    - Healthy: circle icon (muted, receding)
    - Reconnecting: rotating arrows icon (auto-retry in progress)
    - Degraded/Stale: diamond icon (attention-drawing)
    - Error/Offline: triangle icon (demands attention)
    """
    # Determine status, icon, text, and class
    if state.is_reconnecting:
        icon = "\u21bb"  # Rotating arrows
        status_text = "RECONNECTING"
        status_class = "status-warning"
    elif state.is_offline:
        icon = "\u25b2"  # Triangle
        status_text = "OFFLINE"
        status_class = "status-error"
    elif state.is_stale:
        icon = "\u25c6"  # Diamond
        status_text = "STALE"
        status_class = "status-warning"
    elif state.is_healthy:
        icon = "\u25cf"  # Circle
        status_text = "HEALTHY"
        status_class = "status-healthy"
    elif state.health is not None and state.health.status == "degraded":
        icon = "\u25c6"  # Diamond
        status_text = "DEGRADED"
        status_class = "status-warning"
    else:
        icon = "\u25c6"  # Diamond
        status_text = "UNKNOWN"
        status_class = "status-warning"

    with ui.row().classes(f"status-indicator {status_class} items-center gap-2"):
        ui.label(icon).classes("status-icon")
        ui.label(status_text).classes("status-text")


def _create_pnl_content() -> None:
    """Create professional 3-value P&L display (Phase 1 hardening).

    Displays: Realized | Unrealized | Total
    - Realized: Locked-in grid profits from completed cycles
    - Unrealized: Mark-to-market floating P&L on open positions
    - Total: Sum of realized + unrealized
    """
    with ui.row().classes("pnl-breakdown gap-4"):
        # Realized (Grid Profit)
        with ui.column().classes("pnl-item"):
            ui.label("Realized").classes("pnl-label text-xs")
            _create_pnl_value(state.realized_pnl, "realized")

        # Unrealized (Floating)
        with ui.column().classes("pnl-item"):
            ui.label("Unrealized").classes("pnl-label text-xs")
            _create_pnl_value(state.unrealized_pnl, "unrealized")

        # Total
        with ui.column().classes("pnl-item"):
            ui.label("Total").classes("pnl-label text-xs font-bold")
            _create_pnl_value(state.total_pnl, "total")


def _create_pnl_value(pnl: float, pnl_type: str) -> None:
    """Create individual P&L value with styling.

    Args:
        pnl: P&L value (Decimal or float).
        pnl_type: Type of P&L (realized, unrealized, total) for CSS classes.
    """
    if pnl > 0:
        pnl_class = "pnl-positive"
        pnl_text = f"+\u20ac{pnl:.2f}"
    elif pnl < 0:
        pnl_class = "pnl-negative"
        pnl_text = f"-\u20ac{abs(pnl):.2f}"
    else:
        pnl_class = "pnl-neutral"
        pnl_text = "\u20ac0.00"

    ui.label(pnl_text).classes(f"pnl-value {pnl_class} {pnl_type}")


def _create_pair_count_content() -> None:
    """Create pair count display showing active/expected (Story 3.5).

    Format: "X/Y pairs" where X is active and Y is expected.
    - All pairs active: secondary text color
    - Fewer pairs: amber warning color
    """
    # Expected pairs - could be moved to config later
    expected_pairs = 4
    active_pairs = state.pair_count

    # Amber warning if fewer pairs than expected
    if active_pairs < expected_pairs:
        count_class = "count-warning"
    else:
        count_class = "pair-count"

    ui.label(f"{active_pairs}/{expected_pairs} pairs").classes(count_class)


def _create_order_count_content() -> None:
    """Create order count display (Story 3.5).

    Shows total open orders across all pairs.
    Prefers actual orders from exchange over strategy stats for accuracy.
    """
    # Prefer actual orders from orders_by_symbol (fetched from exchange)
    # over strategy stats which may not include manually placed orders
    total_from_orders = sum(len(orders) for orders in state.orders_by_symbol.values())
    if total_from_orders > 0:
        order_count = total_from_orders
    elif state.orders:
        order_count = len(state.orders)
    elif state.pairs:
        order_count = sum(p.order_count for p in state.pairs)
    else:
        order_count = 0

    ui.label(f"{order_count} ord").classes("order-count")


def _create_timestamp_content() -> None:
    """Create last update timestamp with staleness indication (Story 3.3).

    Format: HH:MM:SS in local timezone.
    - Normal (<60s): secondary text color
    - Stale (>60s): amber warning color
    """
    timestamp = state.last_update_formatted

    # Amber color if data is stale (>60 seconds old)
    if state.is_stale:
        timestamp_class = "timestamp-stale"
    else:
        timestamp_class = "timestamp-display"

    ui.label(timestamp).classes(timestamp_class)
