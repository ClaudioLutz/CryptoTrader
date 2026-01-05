"""CryptoTrader Dashboard - Trade History Component.

Displays historical trades with filtering and pagination.
Epic 9: Stories 9.1-9.3 - Tab navigation, history table, filtering.
"""

from datetime import datetime
from decimal import Decimal

from nicegui import ui

from dashboard.state import state


# Table columns for trade history
COLUMNS = [
    {"name": "time", "label": "Time", "field": "time", "align": "left", "sortable": True},
    {"name": "pair", "label": "Pair", "field": "symbol", "align": "left", "sortable": True},
    {"name": "side", "label": "Side", "field": "side", "align": "center"},
    {"name": "price", "label": "Price", "field": "price", "align": "right", "sortable": True},
    {"name": "amount", "label": "Amount", "field": "amount", "align": "right"},
    {"name": "fee", "label": "Fee", "field": "fee", "align": "right"},
    {"name": "pnl", "label": "P&L", "field": "pnl", "align": "right"},
]


def create_trade_history_view() -> None:
    """Create complete trade history view with filters and table.

    Story 9.1-9.3: Tab content for trade history.
    """
    with ui.column().classes("trade-history-view w-full"):
        # Filter bar (Story 9.3)
        _create_filter_bar()

        # History table (Story 9.2)
        _create_history_table()


def _create_filter_bar() -> None:
    """Create filter controls for trade history (Story 9.3)."""
    with ui.row().classes("history-filters items-end gap-4 w-full p-4"):
        # Trading pair dropdown (AC1)
        pairs_options = ["All Pairs"]
        if state.pairs:
            pairs_options.extend([p.symbol for p in state.pairs])

        ui.select(
            pairs_options,
            value=state.history_filter_symbol or "All Pairs",
            label="Pair",
            on_change=lambda e: _set_pair_filter(e.value),
        ).classes("filter-select").props("dense outlined dark")

        # Side filter (AC3)
        ui.select(
            ["All", "Buy", "Sell"],
            value=_get_side_display(state.history_filter_side),
            label="Side",
            on_change=lambda e: _set_side_filter(e.value),
        ).classes("filter-select").props("dense outlined dark")

        # Date range (AC2)
        with ui.row().classes("date-range items-end gap-2"):
            ui.input(
                label="From Date",
                placeholder="YYYY-MM-DD",
                value=state.history_filter_start.strftime("%Y-%m-%d") if state.history_filter_start else "",
                on_change=lambda e: _set_start_date(e.value),
            ).classes("date-input").props("dense outlined dark")

            ui.input(
                label="To Date",
                placeholder="YYYY-MM-DD",
                value=state.history_filter_end.strftime("%Y-%m-%d") if state.history_filter_end else "",
                on_change=lambda e: _set_end_date(e.value),
            ).classes("date-input").props("dense outlined dark")

        # Clear filters button
        ui.button(
            "Clear Filters",
            on_click=_clear_filters,
        ).classes("clear-button").props("flat")


def _create_history_table() -> None:
    """Create trade history table with pagination (Story 9.2)."""
    # Get filtered trades
    rows = _get_filtered_rows()

    with ui.element("div").classes("history-table-container p-4"):
        if not rows:
            ui.label("No trades found matching filters").classes("text-secondary text-center py-8")
            return

        table = ui.table(
            columns=COLUMNS,
            rows=rows,
            row_key="time",
            pagination=20,
        ).classes("history-table w-full")

        # Add styling props
        table.props("flat bordered dense dark")


def _get_filtered_rows() -> list[dict]:
    """Get trade history rows with current filters applied."""
    rows = []

    for trade in state.trades:
        # Apply symbol filter
        if state.history_filter_symbol and trade.symbol != state.history_filter_symbol:
            continue

        # Apply side filter
        if state.history_filter_side and trade.side != state.history_filter_side:
            continue

        # Apply date filters
        if state.history_filter_start and trade.timestamp < state.history_filter_start:
            continue
        if state.history_filter_end and trade.timestamp > state.history_filter_end:
            continue

        # Format row data
        side_class = "trade-buy" if trade.side == "buy" else "trade-sell"
        pnl_class = ""
        pnl_text = "-"

        # Estimate P&L if not provided
        if hasattr(trade, "pnl") and trade.pnl is not None:
            pnl_value = trade.pnl
            if pnl_value > 0:
                pnl_class = "pnl-positive"
                pnl_text = f"+\u20ac{pnl_value:.2f}"
            elif pnl_value < 0:
                pnl_class = "pnl-negative"
                pnl_text = f"-\u20ac{abs(pnl_value):.2f}"
            else:
                pnl_text = "\u20ac0.00"

        rows.append({
            "time": trade.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": trade.symbol,
            "side": trade.side.upper(),
            "side_class": side_class,
            "price": f"${float(trade.price):,.2f}",
            "amount": str(trade.amount),
            "fee": f"${float(trade.fee):.4f}" if hasattr(trade, "fee") else "-",
            "pnl": pnl_text,
            "pnl_class": pnl_class,
        })

    # Sort by time descending (newest first)
    rows.sort(key=lambda r: r["time"], reverse=True)
    return rows


def _get_side_display(side: str | None) -> str:
    """Convert side filter value to display string."""
    if side is None:
        return "All"
    return side.capitalize()


def _set_pair_filter(value: str) -> None:
    """Set pair filter and refresh (Story 9.3 AC1)."""
    state.history_filter_symbol = None if value == "All Pairs" else value


def _set_side_filter(value: str) -> None:
    """Set side filter and refresh (Story 9.3 AC3)."""
    state.history_filter_side = None if value == "All" else value.lower()


def _set_start_date(value: str) -> None:
    """Set start date filter (Story 9.3 AC2)."""
    try:
        if value:
            state.history_filter_start = datetime.strptime(value, "%Y-%m-%d")
        else:
            state.history_filter_start = None
    except ValueError:
        pass  # Invalid date format, ignore


def _set_end_date(value: str) -> None:
    """Set end date filter (Story 9.3 AC2)."""
    try:
        if value:
            # Set to end of day
            state.history_filter_end = datetime.strptime(value, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        else:
            state.history_filter_end = None
    except ValueError:
        pass  # Invalid date format, ignore


def _clear_filters() -> None:
    """Clear all filters and refresh (Story 9.3)."""
    state.history_filter_symbol = None
    state.history_filter_side = None
    state.history_filter_start = None
    state.history_filter_end = None
