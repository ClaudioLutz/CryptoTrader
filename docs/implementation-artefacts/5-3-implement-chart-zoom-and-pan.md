# Story 5.3: Implement Chart Zoom and Pan

Status: review

## Story

As a **trader (Claudio)**,
I want **to zoom and pan the price chart**,
So that **I can investigate specific time periods in detail**.

## Acceptance Criteria

1. **AC1:** Mouse scroll wheel zooms in/out centered on cursor position
2. **AC2:** Click and drag pans horizontally across time
3. **AC3:** Double-click resets to default view (24 hours)
4. **AC4:** Zoom/pan interactions feel responsive (<100ms)
5. **AC5:** Chart toolbar is hidden (interactions via mouse only)

## Tasks / Subtasks

- [x] Task 1: Configure zoom behavior (AC: 1)
  - [x] Enable scroll zoom via config scrollZoom: true
  - [x] Plotly centers zoom on cursor by default
  - [x] Set fixedrange=False on both axes

- [x] Task 2: Configure pan behavior (AC: 2)
  - [x] Enable drag to pan via dragmode="pan"
  - [x] Both axes allow pan (not just horizontal)
  - [x] Smooth animation is Plotly default

- [x] Task 3: Configure reset behavior (AC: 3)
  - [x] Enable double-click reset via config doubleClick: "reset"
  - [x] Default range restored on double-click

- [x] Task 4: Optimize performance (AC: 4)
  - [x] Using standard Scatter trace (WebGL not needed for MVP data size)
  - [x] Can upgrade to Scattergl if needed later

- [x] Task 5: Hide toolbar (AC: 5)
  - [x] Set displayModeBar: false in config
  - [x] Mouse-only interactions enabled

## Dev Notes

### Zoom and Pan Configuration

[Source: docs/planning-artefacts/epics.md - Story 5.3]

```python
def create_figure() -> go.Figure:
    fig = go.Figure()

    # ... add traces ...

    fig.update_layout(
        # Enable zoom and pan
        dragmode="pan",  # Default to pan mode

        # X-axis zoom/pan settings
        xaxis=dict(
            fixedrange=False,  # Allow zoom
            rangeslider=dict(visible=False),  # No range slider
        ),

        # Y-axis settings (auto-scale with x zoom)
        yaxis=dict(
            fixedrange=False,
            autorange=True,
        ),
    )

    return fig


# NiceGUI Plotly config
chart = ui.plotly(fig).classes("price-chart")
chart.update_config({
    "scrollZoom": True,  # Enable scroll zoom
    "doubleClick": "reset",  # Double-click resets view
    "displayModeBar": False,  # Hide toolbar
    "responsive": True,
})
```

### Interaction Modes

| Interaction | Action | Behavior |
|-------------|--------|----------|
| Scroll wheel | Zoom | Zoom in/out centered on cursor |
| Click + drag | Pan | Move horizontally across time |
| Double-click | Reset | Return to default 24h view |

### Plotly Config Options

```python
config = {
    "scrollZoom": True,
    "doubleClick": "reset",
    "displayModeBar": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d",
        "resetScale2d", "toImage"
    ],
    "displaylogo": False,
    "responsive": True,
}
```

### Performance Optimization

For smooth interactions:
```python
# Use WebGL for large datasets
fig.add_trace(go.Scattergl(  # Note: Scattergl, not Scatter
    x=timestamps,
    y=prices,
    mode="lines",
))

# Or limit data points
if len(data) > 1000:
    # Downsample to hourly
    data = data.resample("1H").mean()
```

### Default View Range

```python
from datetime import datetime, timedelta

# Store default range (24 hours)
now = datetime.now()
default_range = [now - timedelta(hours=24), now]

fig.update_xaxes(range=default_range)

# Reset handler (built into Plotly with doubleClick="reset")
```

### Project Structure Notes

- Modifies: `dashboard/components/price_chart.py`
- No new files required

### References

- [Plotly Interactions](https://plotly.com/python/configuration-options/)
- [Epics Document](docs/planning-artefacts/epics.md#story-53-implement-chart-zoom-and-pan)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Zoom/pan configured in create_price_chart() via chart._props["config"]
- scrollZoom: true enables mouse wheel zoom
- doubleClick: "reset" enables view reset
- displayModeBar: false hides toolbar
- dragmode="pan" in layout for default pan behavior

### File List

- dashboard/components/price_chart.py (modified)

