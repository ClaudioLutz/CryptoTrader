# Story 8.3: Implement Candlestick Chart Toggle

Status: review

**Version:** v1.5

## Story

As a **trader (Claudio)**,
I want **to switch between line and candlestick chart**,
So that **I can see OHLC data when investigating**.

## Acceptance Criteria

1. **AC1:** Toggle control switches between line and candlestick mode
2. **AC2:** Candlestick colors: green for up candles, red for down
3. **AC3:** Toggle remembers preference during session
4. **AC4:** Chart data is preserved during toggle (no refetch)

## Tasks / Subtasks

- [x] Task 1: Add chart mode state (AC: 3)
  - [x] Add `chart_mode` to state ("line" | "candlestick")
  - [x] Default to "line"

- [x] Task 2: Create toggle control (AC: 1)
  - [x] Add toggle/switch UI element
  - [x] Connect to state.chart_mode

- [x] Task 3: Implement candlestick trace (AC: 2)
  - [x] Use go.Candlestick
  - [x] Green for up (close > open)
  - [x] Red for down (close < open)

- [x] Task 4: Toggle without refetch (AC: 4)
  - [x] Store OHLC data
  - [x] Switch trace type only

## Dev Notes

### Chart Mode State

```python
# In dashboard/state.py
from typing import Literal

ChartMode = Literal["line", "candlestick"]

class DashboardState:
    def __init__(self):
        # ... existing ...
        self.chart_mode: ChartMode = "line"
```

### Toggle Control

```python
"""Chart mode toggle control."""

from nicegui import ui

from dashboard.state import state


def chart_mode_toggle() -> None:
    """Toggle between line and candlestick chart."""
    with ui.row().classes("chart-toggle items-center gap-2"):
        ui.label("Chart:").classes("toggle-label")

        toggle = ui.toggle(
            ["Line", "Candles"],
            value="Line" if state.chart_mode == "line" else "Candles",
        ).classes("chart-mode-toggle")

        def on_toggle(e):
            state.chart_mode = "line" if e.value == "Line" else "candlestick"

        toggle.on("update:model-value", on_toggle)
```

### Candlestick Implementation

```python
"""Candlestick chart trace."""

import plotly.graph_objects as go


def create_candlestick_trace(ohlc_data: list[dict]) -> go.Candlestick:
    """Create candlestick trace from OHLC data."""
    return go.Candlestick(
        x=[d["timestamp"] for d in ohlc_data],
        open=[d["open"] for d in ohlc_data],
        high=[d["high"] for d in ohlc_data],
        low=[d["low"] for d in ohlc_data],
        close=[d["close"] for d in ohlc_data],
        name="Price",
        increasing=dict(
            line=dict(color="#00c853"),
            fillcolor="#00c853",
        ),
        decreasing=dict(
            line=dict(color="#ff5252"),
            fillcolor="#ff5252",
        ),
    )


def create_line_trace(ohlc_data: list[dict]) -> go.Scatter:
    """Create line trace from OHLC data (using close)."""
    return go.Scatter(
        x=[d["timestamp"] for d in ohlc_data],
        y=[d["close"] for d in ohlc_data],
        mode="lines",
        name="Price",
        line=dict(color="#4a9eff", width=2),
    )
```

### Dynamic Trace Switching

```python
def price_chart() -> None:
    """Price chart with mode toggle."""
    # Store OHLC data for both modes
    ohlc_data = state.price_data  # Fetched elsewhere

    def create_figure() -> go.Figure:
        fig = go.Figure()

        if state.chart_mode == "candlestick":
            fig.add_trace(create_candlestick_trace(ohlc_data))
        else:
            fig.add_trace(create_line_trace(ohlc_data))

        # Apply dark theme layout
        fig.update_layout(...)

        return fig

    # Chart with reactive mode binding
    chart = ui.plotly(create_figure())

    # Rebuild chart on mode change (preserves data)
    def update_chart_mode():
        chart.update_figure(create_figure())

    # Watch for state.chart_mode changes
```

### OHLC Data Model

```python
class OHLCData(BaseModel):
    """OHLC candle data."""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
```

### CSS for Toggle

```css
.chart-toggle {
  position: absolute;
  top: 8px;
  right: 16px;
  z-index: 10;
}

.toggle-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.chart-mode-toggle {
  background-color: var(--surface);
  border-radius: 4px;
}
```

### Project Structure Notes

- Modifies: `dashboard/components/price_chart.py`
- Modifies: `dashboard/state.py` (add chart_mode)
- May need: Extended OHLC data from API

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-83-implement-candlestick-chart-toggle)
- [Plotly Candlestick](https://plotly.com/python/candlestick-charts/)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Added ChartMode type and chart_mode field to state.py
- Created Line/Candles toggle in chart header
- Candlestick mode uses go.Candlestick with OHLC data
- Green for up candles (close > open), red for down
- Toggle updates chart via update_figure() without refetch
- Chart mode preference persists during session

### File List

- dashboard/state.py (modified)
- dashboard/components/price_chart.py (modified)
- dashboard/assets/css/theme.css (modified)

