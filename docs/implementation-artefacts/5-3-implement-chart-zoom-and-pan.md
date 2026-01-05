# Story 5.3: Implement Chart Zoom and Pan

Status: ready-for-dev

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

- [ ] Task 1: Configure zoom behavior (AC: 1)
  - [ ] Enable scroll zoom
  - [ ] Center zoom on cursor position
  - [ ] Set zoom limits

- [ ] Task 2: Configure pan behavior (AC: 2)
  - [ ] Enable drag to pan
  - [ ] Limit to horizontal panning
  - [ ] Smooth pan animation

- [ ] Task 3: Configure reset behavior (AC: 3)
  - [ ] Enable double-click reset
  - [ ] Store default range

- [ ] Task 4: Optimize performance (AC: 4)
  - [ ] Enable WebGL if needed
  - [ ] Debounce interactions

- [ ] Task 5: Hide toolbar (AC: 5)
  - [ ] Remove modebar
  - [ ] Mouse-only interactions

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

{{agent_model_name_version}}

### Completion Notes List

### File List

