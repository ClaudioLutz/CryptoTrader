# Story 8.2: Add Trade Markers to Chart

Status: ready-for-dev

**Version:** v1.5

## Story

As a **trader (Claudio)**,
I want **to see where trades executed on the price chart**,
So that **I can correlate price action with bot activity**.

## Acceptance Criteria

1. **AC1:** Buy trades appear as green upward triangles
2. **AC2:** Sell trades appear as red downward triangles
3. **AC3:** Hovering a marker shows trade details (price, amount, time)
4. **AC4:** Markers scale appropriately when zooming

## Tasks / Subtasks

- [ ] Task 1: Fetch trade data for chart (AC: 1, 2)
  - [ ] Get trades for selected pair
  - [ ] Filter to chart timeframe

- [ ] Task 2: Add marker trace to Plotly (AC: 1, 2)
  - [ ] Scatter trace with triangle markers
  - [ ] Green for buys, red for sells

- [ ] Task 3: Configure hover tooltips (AC: 3)
  - [ ] Show price, amount, timestamp
  - [ ] Dark theme styling

- [ ] Task 4: Handle zoom behavior (AC: 4)
  - [ ] Fixed pixel size markers
  - [ ] Or scale with zoom level

## Dev Notes

### Trade Markers Implementation

```python
"""Add trade markers to price chart."""

import plotly.graph_objects as go

from dashboard.services.data_models import Trade


def add_trade_markers(fig: go.Figure, trades: list[Trade]) -> None:
    """Add trade execution markers to chart."""
    buys = [t for t in trades if t.side == "buy"]
    sells = [t for t in trades if t.side == "sell"]

    # Buy markers (green triangles up)
    if buys:
        fig.add_trace(go.Scatter(
            x=[t.timestamp for t in buys],
            y=[float(t.price) for t in buys],
            mode="markers",
            name="Buys",
            marker=dict(
                symbol="triangle-up",
                size=12,
                color="#00c853",
                line=dict(width=1, color="#008837"),
            ),
            hovertemplate=(
                "<b>BUY</b><br>"
                "Price: $%{y:,.2f}<br>"
                "Amount: %{customdata[0]}<br>"
                "Time: %{x|%H:%M:%S}<br>"
                "<extra></extra>"
            ),
            customdata=[[float(t.amount)] for t in buys],
        ))

    # Sell markers (red triangles down)
    if sells:
        fig.add_trace(go.Scatter(
            x=[t.timestamp for t in sells],
            y=[float(t.price) for t in sells],
            mode="markers",
            name="Sells",
            marker=dict(
                symbol="triangle-down",
                size=12,
                color="#ff5252",
                line=dict(width=1, color="#c41c00"),
            ),
            hovertemplate=(
                "<b>SELL</b><br>"
                "Price: $%{y:,.2f}<br>"
                "Amount: %{customdata[0]}<br>"
                "Time: %{x|%H:%M:%S}<br>"
                "<extra></extra>"
            ),
            customdata=[[float(t.amount)] for t in sells],
        ))
```

### Marker Styling

| Property | Buy | Sell |
|----------|-----|------|
| Symbol | `triangle-up` | `triangle-down` |
| Color | `#00c853` | `#ff5252` |
| Size | 12px | 12px |
| Border | `#008837` | `#c41c00` |

### Zoom Behavior

Plotly markers maintain pixel size during zoom by default.
For relative sizing:

```python
marker=dict(
    size=12,
    sizemode="diameter",  # Fixed pixel size
    # OR
    sizeref=2,  # Scale with data
)
```

### Integration with Chart Component

```python
def price_chart() -> None:
    fig = create_figure()

    # Add price line
    fig.add_trace(go.Scatter(...))

    # Add trade markers
    if state.trades:
        add_trade_markers(fig, state.trades)

    chart = ui.plotly(fig)
```

### Fetching Trades for Chart

```python
# Only fetch trades in chart timeframe
trades = await api_client.get_pair_trades(
    symbol=state.selected_pair,
    start_time=chart_start_time,
    end_time=chart_end_time,
)
```

### Project Structure Notes

- Modifies: `dashboard/components/price_chart.py`
- May need: `dashboard/services/api_client.py` (extend trades endpoint)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-82-add-trade-markers-to-chart)
- [Plotly Markers](https://plotly.com/python/marker-style/)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

