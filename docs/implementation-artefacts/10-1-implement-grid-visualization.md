# Story 10.1: Implement Grid Visualization

Status: ready-for-dev

**Version:** v2.0

## Story

As a **trader (Claudio)**,
I want **to see a visual representation of my grid levels**,
So that **I can understand the buy/sell grid structure**.

## Acceptance Criteria

1. **AC1:** Buy levels shown as green horizontal lines
2. **AC2:** Sell levels shown as red horizontal lines
3. **AC3:** Current price is highlighted
4. **AC4:** Filled orders indicated differently from open orders
5. **AC5:** Visualization overlaid on or adjacent to the price chart

## Tasks / Subtasks

- [ ] Task 1: Fetch grid configuration data
  - [ ] Add API method for grid levels
  - [ ] Define GridLevel data model

- [ ] Task 2: Create grid overlay on chart (AC: 1, 2, 5)
  - [ ] Add horizontal lines for buy levels
  - [ ] Add horizontal lines for sell levels
  - [ ] Position relative to price chart

- [ ] Task 3: Highlight current price (AC: 3)
  - [ ] Add current price line
  - [ ] Style distinctively

- [ ] Task 4: Distinguish order states (AC: 4)
  - [ ] Solid lines for open orders
  - [ ] Dashed lines for filled orders

## Dev Notes

### Grid Level Data Model

```python
"""Grid level data models."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class GridLevel(BaseModel):
    """Single grid level."""
    price: Decimal
    side: Literal["buy", "sell"]
    status: Literal["open", "filled", "canceled"]
    order_id: str | None = None


class GridConfig(BaseModel):
    """Grid configuration for a trading pair."""
    symbol: str
    levels: list[GridLevel]
    current_price: Decimal
    grid_spacing: Decimal
    total_levels: int
```

### Grid Overlay Implementation

```python
"""Grid visualization overlay for price chart."""

import plotly.graph_objects as go

from dashboard.services.data_models import GridConfig, GridLevel


def add_grid_overlay(fig: go.Figure, grid: GridConfig) -> None:
    """Add grid level lines to price chart."""
    # Buy levels (green)
    buy_levels = [l for l in grid.levels if l.side == "buy"]
    for level in buy_levels:
        add_grid_line(fig, level, "#00c853")

    # Sell levels (red)
    sell_levels = [l for l in grid.levels if l.side == "sell"]
    for level in sell_levels:
        add_grid_line(fig, level, "#ff5252")

    # Current price line (accent)
    fig.add_hline(
        y=float(grid.current_price),
        line=dict(color="#4a9eff", width=2),
        annotation=dict(
            text=f"Current: ${grid.current_price:,.2f}",
            font=dict(color="#4a9eff"),
        ),
    )


def add_grid_line(fig: go.Figure, level: GridLevel, color: str) -> None:
    """Add single grid level line."""
    dash = "solid" if level.status == "open" else "dash"
    opacity = 1.0 if level.status == "open" else 0.5

    fig.add_hline(
        y=float(level.price),
        line=dict(
            color=color,
            width=1,
            dash=dash,
        ),
        opacity=opacity,
        annotation=dict(
            text=f"${level.price:,.2f}",
            font=dict(size=10, color=color),
            xanchor="right",
        ) if level.status == "open" else None,
    )
```

### Alternative: Separate Grid Panel

```python
def grid_visualization_panel(grid: GridConfig) -> None:
    """Standalone grid visualization panel."""
    with ui.element("div").classes("grid-panel"):
        # Visual representation
        fig = go.Figure()

        # Add levels as markers
        for level in grid.levels:
            marker_color = "#00c853" if level.side == "buy" else "#ff5252"
            marker_symbol = "circle" if level.status == "open" else "circle-open"

            fig.add_trace(go.Scatter(
                x=[level.side],
                y=[float(level.price)],
                mode="markers",
                marker=dict(
                    color=marker_color,
                    symbol=marker_symbol,
                    size=12,
                ),
            ))

        # Current price horizontal line
        fig.add_hline(y=float(grid.current_price))

        ui.plotly(fig)
```

### CSS Styling

```css
.grid-panel {
  background-color: var(--bg-secondary);
  padding: 16px;
  border-radius: 4px;
}

.grid-legend {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
```

### Visual Layout

```
Price
  ↑
$98,500 ─────────── SELL (filled, dashed)
$98,200 ═══════════ SELL (open, solid)
$98,000 ═══════════ SELL (open, solid)
         ▬▬▬▬▬▬▬▬▬▬ Current Price
$97,500 ═══════════ BUY (open, solid)
$97,200 ═══════════ BUY (open, solid)
$97,000 ─────────── BUY (filled, dashed)
```

### Project Structure Notes

- Creates: `dashboard/components/grid_visualization.py`
- Modifies: `dashboard/components/price_chart.py` (add overlay option)
- Modifies: `dashboard/services/api_client.py` (add grid endpoint)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-101-implement-grid-visualization)
- [Plotly Horizontal Lines](https://plotly.com/python/horizontal-vertical-shapes/)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

