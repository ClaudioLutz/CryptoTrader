"""CryptoTrader Dashboard - Timeframe Performance Row Component.

Displays P&L across multiple timeframes (1H, 24H, 7D, 30D).
Story 8.1: Implement timeframe performance row.
"""

from decimal import Decimal

from nicegui import ui

from dashboard.state import state


# Timeframe configuration: (label, pnl_attr, pct_attr)
TIMEFRAMES = [
    ("1H", "pnl_1h", "pnl_1h_pct"),
    ("24H", "pnl_24h", "pnl_24h_pct"),
    ("7D", "pnl_7d", "pnl_7d_pct"),
    ("30D", "pnl_30d", "pnl_30d_pct"),
]


def create_timeframe_row() -> None:
    """Create timeframe performance row showing P&L across timeframes.

    Displays 1H, 24H, 7D, 30D performance with percentage and absolute values.
    Row is 36px tall and scrolls with content (not fixed like header).
    """
    with ui.row().classes("timeframe-row items-center justify-around w-full"):
        for label, pnl_attr, pct_attr in TIMEFRAMES:
            _create_timeframe_cell(label, pnl_attr, pct_attr)


def _create_timeframe_cell(label: str, pnl_attr: str, pct_attr: str) -> None:
    """Create a single timeframe performance cell.

    Args:
        label: Timeframe label (e.g., "1H", "24H").
        pnl_attr: State attribute name for absolute P&L.
        pct_attr: State attribute name for percentage P&L.
    """
    # Get values from state
    pnl_value: Decimal = getattr(state, pnl_attr, Decimal("0"))
    pct_value: Decimal = getattr(state, pct_attr, Decimal("0"))

    # Determine color class based on value
    if pnl_value > 0:
        color_class = "timeframe-positive"
    elif pnl_value < 0:
        color_class = "timeframe-negative"
    else:
        color_class = "timeframe-neutral"

    # Format values
    pct_text = f"+{pct_value:.1f}%" if pct_value >= 0 else f"{pct_value:.1f}%"
    pnl_text = f"\u20ac{pnl_value:,.0f}" if pnl_value >= 0 else f"-\u20ac{abs(pnl_value):,.0f}"

    with ui.column().classes("timeframe-cell items-center"):
        # Timeframe label
        ui.label(label).classes("timeframe-label")

        # Values row
        with ui.row().classes("timeframe-values items-baseline gap-2"):
            # Percentage change (prominent)
            ui.label(pct_text).classes(f"timeframe-pct {color_class}")
            # Absolute value (secondary)
            ui.label(pnl_text).classes(f"timeframe-abs {color_class}")
