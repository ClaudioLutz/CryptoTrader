# Story 5.1: Implement Basic Price Chart

Status: review

## Story

As a **trader (Claudio)**,
I want **to see a price chart for my primary trading pair**,
So that **I can understand recent price movements**.

## Acceptance Criteria

1. **AC1:** Plotly line chart displays price over time
2. **AC2:** Chart height is approximately 300-400px
3. **AC3:** Chart uses dark theme colors (background: `#1a1a2e`, grid: `#0f3460`, line: `#4a9eff`)
4. **AC4:** X-axis shows time, Y-axis shows price
5. **AC5:** Chart renders within 3 seconds of page load
6. **AC6:** Default timeframe shows the last 24 hours

## Tasks / Subtasks

- [x] Task 1: Create chart component (AC: 1, 4)
  - [x] Created `dashboard/components/price_chart.py`
  - [x] Initialize Plotly figure with go.Scatter line trace
  - [x] Configure X (Time) and Y (Price) axes

- [x] Task 2: Apply dark theme styling (AC: 3)
  - [x] Set background color (#1a1a2e)
  - [x] Set grid line color (#0f3460)
  - [x] Set line color (accent #4a9eff)
  - [x] Configure axis labels with theme colors

- [x] Task 3: Set chart dimensions (AC: 2)
  - [x] Set height to 350px
  - [x] Width responsive via CSS

- [x] Task 4: Configure timeframe (AC: 5, 6)
  - [x] Default to 24 hours of sample data
  - [x] Uses state.ohlcv when available

## Dev Notes

### Price Chart Implementation

[Source: docs/planning-artefacts/architecture.md - Frontend Architecture]

```python
"""CryptoTrader Dashboard - Price Chart Component.

Interactive Plotly chart for price visualization.
"""

import plotly.graph_objects as go
from nicegui import ui

from dashboard.state import state


def price_chart() -> None:
    """Create price chart with dark theme styling."""

    def create_figure() -> go.Figure:
        """Create Plotly figure with dark theme."""
        # Sample data - replace with actual price data
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=[],  # timestamps
            y=[],  # prices
            mode="lines",
            name="Price",
            line=dict(color="#4a9eff", width=2),
        ))

        # Dark theme layout
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
            height=350,
            margin=dict(l=50, r=20, t=30, b=40),
            xaxis=dict(
                title="Time",
                gridcolor="#0f3460",
                showgrid=True,
            ),
            yaxis=dict(
                title="Price ($)",
                gridcolor="#0f3460",
                showgrid=True,
            ),
            showlegend=False,
        )

        return fig

    with ui.element("div").classes("chart-container"):
        chart = ui.plotly(create_figure()).classes("price-chart")
```

### CSS Styling

```css
.chart-container {
  margin-top: 16px;
  padding: 0 16px;
}

.price-chart {
  width: 100%;
  min-height: 300px;
  max-height: 400px;
}
```

### Plotly Dark Theme Colors

| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark navy | `#1a1a2e` |
| Grid lines | Surface | `#0f3460` |
| Price line | Accent | `#4a9eff` |
| Axis labels | Secondary text | `#a0a0a0` |
| Axis titles | Primary text | `#e8e8e8` |

### Data Source

Price data options:
1. **Bot API endpoint:** `/ohlcv` or `/prices/{symbol}`
2. **State accumulation:** Collect prices during polling
3. **On-demand fetch:** Request chart data separately

For MVP, fetch chart data via APIClient (add method in future iteration).

### Performance Considerations

[Source: docs/planning-artefacts/prd.md - NFR2]

- Chart render <3 seconds
- Use WebGL renderer for large datasets (`config={'scrollZoom': True}`)
- Limit data points (e.g., hourly aggregation for 24h view)

### NiceGUI Plotly Integration

```python
# NiceGUI provides ui.plotly() for Plotly integration
chart = ui.plotly(fig)

# Update chart data
def update_chart(new_data):
    fig.data[0].x = new_data['timestamps']
    fig.data[0].y = new_data['prices']
    chart.update()
```

### Project Structure Notes

- File location: `dashboard/components/price_chart.py`
- Integrates with: `dashboard/main.py`
- Depends on: `dashboard/state.py` (for data)

### References

- [Architecture](docs/planning-artefacts/architecture.md#built-in-components)
- [Plotly Documentation](https://plotly.com/python/)
- [NiceGUI Plotly](https://nicegui.io/documentation#plotly)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created dashboard/components/price_chart.py with create_price_chart()
- Uses Plotly go.Figure with go.Scatter trace
- Dark theme: plotly_dark template with custom colors
- Chart height 350px, responsive width
- Includes sample data generation for demo mode
- Integrated into main.py below pairs table

### File List

- dashboard/components/price_chart.py (created)
- dashboard/assets/css/theme.css (modified)
- dashboard/main.py (modified)

