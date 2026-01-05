# Story 5.2: Implement Chart Hover Tooltips

Status: review

## Story

As a **trader (Claudio)**,
I want **to see price details when hovering over the chart**,
So that **I can investigate specific price points**.

## Acceptance Criteria

1. **AC1:** Tooltip appears showing exact price with precision
2. **AC2:** Tooltip shows exact timestamp in local time
3. **AC3:** Crosshair cursor appears at hover position
4. **AC4:** Tooltip follows the mouse smoothly
5. **AC5:** Tooltip uses dark theme styling

## Tasks / Subtasks

- [x] Task 1: Configure Plotly hover mode (AC: 1, 2)
  - [x] Set hovermode to 'x unified'
  - [x] Configure hovertemplate: Price: $%{y:,.2f}, Time: %{x|%H:%M:%S}
  - [x] Hide trace name with <extra></extra>

- [x] Task 2: Add crosshair cursor (AC: 3)
  - [x] Enable spike lines for x-axis and y-axis
  - [x] Style spike lines: #4a9eff accent color, dot dash

- [x] Task 3: Style tooltip (AC: 4, 5)
  - [x] Dark theme background (#16213e)
  - [x] Text color #e8e8e8
  - [x] Roboto Mono font for numerical values

## Dev Notes

### Hover Configuration

[Source: docs/planning-artefacts/ux-design-specification.md - Interaction Patterns]

```python
def create_figure() -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=prices,
        mode="lines",
        name="Price",
        line=dict(color="#4a9eff", width=2),
        hovertemplate=(
            "<b>Price:</b> $%{y:,.2f}<br>"
            "<b>Time:</b> %{x|%H:%M:%S}<br>"
            "<extra></extra>"  # Hide trace name
        ),
    ))

    fig.update_layout(
        # Hover settings
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#16213e",
            bordercolor="#0f3460",
            font=dict(
                family="Roboto Mono, monospace",
                size=12,
                color="#e8e8e8",
            ),
        ),

        # Crosshair (spike lines)
        xaxis=dict(
            showspikes=True,
            spikecolor="#4a9eff",
            spikethickness=1,
            spikedash="dot",
            spikemode="across",
        ),
        yaxis=dict(
            showspikes=True,
            spikecolor="#4a9eff",
            spikethickness=1,
            spikedash="dot",
            spikemode="across",
        ),
    )

    return fig
```

### Hover Template Format

| Field | Format | Example |
|-------|--------|---------|
| Price | `$%{y:,.2f}` | $97,234.12 |
| Time | `%{x\|%H:%M:%S}` | 14:32:05 |
| Full timestamp | `%{x\|%Y-%m-%d %H:%M}` | 2026-01-05 14:32 |

### Tooltip Styling

```css
/* Plotly hover label - controlled via hoverlabel config */
.hoverlayer .hovertext {
  font-family: 'Roboto Mono', monospace !important;
}
```

### Crosshair Behavior

Plotly spike lines create the crosshair effect:
- `showspikes=True` - Enable spike lines
- `spikemode="across"` - Full width/height lines
- `spikedash="dot"` - Dotted line style
- `spikecolor="#4a9eff"` - Accent color

### Performance Note

For smooth hover on large datasets:
```python
fig.update_traces(hoverinfo="x+y", hoverdistance=50)
```

### Project Structure Notes

- Modifies: `dashboard/components/price_chart.py`
- No new files required

### References

- [Plotly Hover Documentation](https://plotly.com/python/hover-text-and-formatting/)
- [UX Design](docs/planning-artefacts/ux-design-specification.md#interaction-patterns)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Hover tooltips configured in create_figure() with hovertemplate
- Crosshair implemented via showspikes on both axes
- Hoverlabel styled with dark theme colors and Roboto Mono font
- Spikemode set to "across" for full crosshair effect

### File List

- dashboard/components/price_chart.py (modified)

