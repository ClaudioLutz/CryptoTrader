"""CryptoTrader Dashboard - Grid Visualization Component.

Adds grid level overlay to the price chart showing buy/sell levels
with different styling for open vs filled orders.

Story 10.1: Grid Visualization
- AC1: Buy levels shown as green horizontal lines
- AC2: Sell levels shown as red horizontal lines
- AC3: Current price is highlighted
- AC4: Filled orders indicated differently from open orders
- AC5: Visualization overlaid on the price chart
"""

import plotly.graph_objects as go

from dashboard.services.data_models import GridConfig, GridLevel


def add_grid_overlay(fig: go.Figure, grid: GridConfig) -> None:
    """Add grid level lines to price chart.

    Args:
        fig: Plotly figure to add grid overlay to.
        grid: Grid configuration with levels and current price.
    """
    if not grid or not grid.levels:
        return

    # Separate buy and sell levels
    buy_levels = [level for level in grid.levels if level.side == "buy"]
    sell_levels = [level for level in grid.levels if level.side == "sell"]

    # Add buy levels (green) - AC1
    for level in buy_levels:
        _add_grid_line(fig, level, "#00c853")

    # Add sell levels (red) - AC2
    for level in sell_levels:
        _add_grid_line(fig, level, "#ff5252")

    # Add current price line (accent blue, highlighted) - AC3
    fig.add_hline(
        y=float(grid.current_price),
        line=dict(color="#4a9eff", width=2, dash="solid"),
        annotation=dict(
            text=f"Current: ${grid.current_price:,.2f}",
            font=dict(color="#4a9eff", size=11),
            xanchor="right",
            xref="paper",
            x=1,
        ),
    )


def _add_grid_line(fig: go.Figure, level: GridLevel, color: str) -> None:
    """Add single grid level line to chart.

    Args:
        fig: Plotly figure to add line to.
        level: Grid level data.
        color: Line color (hex string).
    """
    # AC4: Solid for open, dashed for filled
    dash = "solid" if level.status == "open" else "dash"
    opacity = 1.0 if level.status == "open" else 0.5

    # Add annotation only for open orders
    annotation = None
    if level.status == "open":
        annotation = dict(
            text=f"${level.price:,.2f}",
            font=dict(size=9, color=color),
            xanchor="right",
            xref="paper",
            x=1,
        )

    fig.add_hline(
        y=float(level.price),
        line=dict(
            color=color,
            width=1,
            dash=dash,
        ),
        opacity=opacity,
        annotation=annotation,
    )


def create_grid_legend() -> dict:
    """Create legend data for grid visualization.

    Returns:
        Dict with legend item information for UI display.
    """
    return {
        "buy_open": {"color": "#00c853", "style": "solid", "label": "Buy (Open)"},
        "buy_filled": {"color": "#00c853", "style": "dashed", "label": "Buy (Filled)"},
        "sell_open": {"color": "#ff5252", "style": "solid", "label": "Sell (Open)"},
        "sell_filled": {"color": "#ff5252", "style": "dashed", "label": "Sell (Filled)"},
        "current": {"color": "#4a9eff", "style": "solid", "label": "Current Price"},
    }
