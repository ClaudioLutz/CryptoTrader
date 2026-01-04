# Epic: Phase 2 - Charting & Visualization

**Epic Owner:** Development Team
**Priority:** High - Essential for trading dashboard UX
**Dependencies:** Epic 3 (API Client), Epic 4 (Dashboard Pages)

---

## Overview

This epic implements professional financial charting using Plotly for analytics and streamlit-lightweight-charts for TradingView-style candlesticks. Charts are optimized for real-time trading data visualization.

### Key Deliverables
- Equity curve with drawdown overlay
- Grid levels visualization
- TradingView-style candlestick chart
- Trade markers on price charts

### Technology Stack
- **Plotly**: Interactive charts for equity curves, analytics, grid visualization
- **streamlit-lightweight-charts**: TradingView-style OHLCV charts with lower overhead
- **pandas**: Data manipulation for chart preparation

---

## Story 5.1: Build Equity Curve with Drawdown Overlay

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** an equity curve showing account growth and drawdown
**So that** I can visualize overall performance and risk

### Acceptance Criteria

- [ ] Create equity curve component:
  ```python
  import plotly.graph_objects as go
  from plotly.subplots import make_subplots
  import streamlit as st
  import pandas as pd

  def render_equity_curve(equity_data: list):
      """Render equity curve with drawdown overlay."""
      if not equity_data:
          st.info("No equity data available")
          return

      df = pd.DataFrame(equity_data)
      df['timestamp'] = pd.to_datetime(df['timestamp'])
      df['peak'] = df['equity'].cummax()
      df['drawdown'] = (df['equity'] - df['peak']) / df['peak'] * 100

      fig = make_subplots(specs=[[{"secondary_y": True}]])

      # Equity line
      fig.add_trace(
          go.Scatter(
              x=df['timestamp'],
              y=df['equity'],
              name="Equity",
              line=dict(color='#2962FF', width=2),
              hovertemplate="$%{y:,.2f}<extra></extra>"
          ),
          secondary_y=False
      )

      # Drawdown area
      fig.add_trace(
          go.Scatter(
              x=df['timestamp'],
              y=df['drawdown'],
              name="Drawdown %",
              fill='tozeroy',
              fillcolor='rgba(239,83,80,0.3)',
              line=dict(color='#ef5350', width=1),
              hovertemplate="%{y:.2f}%<extra></extra>"
          ),
          secondary_y=True
      )

      fig.update_layout(
          title="Equity Curve with Drawdown",
          hovermode="x unified",
          height=450,
          template="plotly_dark",
          legend=dict(
              orientation="h",
              yanchor="bottom",
              y=1.02,
              xanchor="right",
              x=1
          )
      )
      fig.update_yaxes(title_text="Equity ($)", secondary_y=False)
      fig.update_yaxes(title_text="Drawdown (%)", secondary_y=True)

      st.plotly_chart(fig, use_container_width=True)
  ```
- [ ] Plot equity line on primary Y-axis
- [ ] Plot drawdown as filled area on secondary Y-axis
- [ ] Calculate peak equity and drawdown percentage
- [ ] Use dark theme matching Streamlit config
- [ ] Enable hover tooltips with formatted values
- [ ] Responsive width using `use_container_width=True`

### Technical Notes
- `make_subplots` with `secondary_y=True` enables dual Y-axis
- `plotly_dark` template matches dashboard theme
- `hovermode="x unified"` shows both values on hover
- Calculate drawdown as `(current - peak) / peak * 100`

### Definition of Done
- Equity curve renders with correct data
- Drawdown overlay visible and accurate
- Hover shows both values
- Chart responsive to container width
- Empty state handled gracefully

---

## Story 5.2: Implement Grid Levels Visualization

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** trader
**I want** a visual representation of grid levels relative to current price
**So that** I can understand order placement strategy

### Acceptance Criteria

- [ ] Create grid levels chart:
  ```python
  import plotly.graph_objects as go
  import streamlit as st
  import numpy as np

  def render_grid_levels(current_price: float, grid_config: dict):
      """Render grid strategy price levels."""
      grid_start = grid_config.get('lower_price', 0)
      grid_end = grid_config.get('upper_price', 0)
      grid_step = grid_config.get('grid_step', 0)

      if not all([grid_start, grid_end, grid_step]):
          st.warning("Grid configuration incomplete")
          return

      levels = np.arange(grid_start, grid_end + grid_step, grid_step)
      buy_levels = levels[levels < current_price]
      sell_levels = levels[levels > current_price]

      fig = go.Figure()

      # Current price line
      fig.add_hline(
          y=current_price,
          line=dict(color='yellow', width=3, dash='dash'),
          annotation_text=f"Current: ${current_price:,.2f}",
          annotation_position="right"
      )

      # Buy levels (green)
      for level in buy_levels:
          fig.add_hline(
              y=level,
              line=dict(color='rgba(38,166,154,0.6)', width=1)
          )
          fig.add_shape(
              type="rect",
              x0=0, x1=1,
              y0=level - grid_step * 0.1,
              y1=level + grid_step * 0.1,
              xref="paper",
              fillcolor="rgba(38,166,154,0.2)",
              line_width=0
          )

      # Sell levels (red)
      for level in sell_levels:
          fig.add_hline(
              y=level,
              line=dict(color='rgba(239,83,80,0.6)', width=1)
          )
          fig.add_shape(
              type="rect",
              x0=0, x1=1,
              y0=level - grid_step * 0.1,
              y1=level + grid_step * 0.1,
              xref="paper",
              fillcolor="rgba(239,83,80,0.2)",
              line_width=0
          )

      fig.update_layout(
          title="Grid Strategy Levels",
          yaxis_title="Price ($)",
          height=600,
          showlegend=False,
          template="plotly_dark",
          xaxis=dict(showticklabels=False, showgrid=False),
      )

      st.plotly_chart(fig, use_container_width=True)
  ```
- [ ] Show current price as prominent yellow dashed line
- [ ] Display buy levels (below price) in green
- [ ] Display sell levels (above price) in red
- [ ] Add shaded zones around each level
- [ ] Calculate levels from grid configuration
- [ ] Handle edge cases (price at grid boundary)

### Technical Notes
- `add_hline` creates horizontal price levels
- `add_shape` with `type="rect"` creates shaded zones
- `xref="paper"` makes shapes span full width
- Green (#26a69a) and red (#ef5350) match trading conventions

### Definition of Done
- Grid levels display correctly
- Current price clearly visible
- Buy/sell levels color-coded
- Shaded zones around levels
- Works with various grid configurations

---

## Story 5.3: Create TradingView-Style Candlestick Chart

**Story Points:** 8
**Priority:** P1 - High

### Description
**As a** trader
**I want** TradingView-style candlestick charts
**So that** I can analyze price action professionally

### Acceptance Criteria

- [ ] Create candlestick chart with lightweight-charts:
  ```python
  from streamlit_lightweight_charts import renderLightweightCharts
  import streamlit as st
  import pandas as pd
  import json

  def render_candlestick_chart(ohlc_df: pd.DataFrame, chart_id: str = "price_chart"):
      """Render TradingView-style candlestick chart."""
      if ohlc_df.empty:
          st.info("No price data available")
          return

      # Format data for lightweight-charts
      # Expects: time, open, high, low, close
      ohlc_df = ohlc_df.copy()
      ohlc_df['time'] = pd.to_datetime(ohlc_df['time']).dt.strftime('%Y-%m-%d')

      candles = json.loads(
          ohlc_df[['time', 'open', 'high', 'low', 'close']].to_json(orient='records')
      )

      chart_options = {
          "height": 400,
          "layout": {
              "background": {"type": "solid", "color": "#131722"},
              "textColor": "#d1d4dc"
          },
          "grid": {
              "vertLines": {"color": "rgba(42,46,57,0)"},
              "horzLines": {"color": "rgba(42,46,57,0.6)"}
          },
          "crosshair": {
              "mode": 0  # Normal crosshair
          },
          "rightPriceScale": {
              "borderColor": "rgba(197,203,206,0.8)"
          },
          "timeScale": {
              "borderColor": "rgba(197,203,206,0.8)",
              "timeVisible": True
          }
      }

      series = [{
          "type": "Candlestick",
          "data": candles,
          "options": {
              "upColor": "#26a69a",
              "downColor": "#ef5350",
              "borderVisible": False,
              "wickUpColor": "#26a69a",
              "wickDownColor": "#ef5350"
          }
      }]

      renderLightweightCharts(
          [{"chart": chart_options, "series": series}],
          chart_id
      )
  ```
- [ ] Display OHLC candlesticks with proper colors
- [ ] Green candles for up, red for down
- [ ] Include wick colors matching body
- [ ] Dark background matching TradingView
- [ ] Crosshair for price inspection
- [ ] Time scale with proper formatting
- [ ] Zoom and pan functionality (built-in)

### Technical Notes
- `streamlit-lightweight-charts` wraps TradingView's lightweight-charts library
- Lower overhead than Plotly for OHLCV data
- Time must be in 'YYYY-MM-DD' or Unix timestamp format
- Chart ID must be unique if multiple charts on page

### Definition of Done
- Candlesticks render correctly
- Colors match trading conventions
- Crosshair works on hover
- Zoom/pan functional
- Responsive to container width

---

## Story 5.4: Add Trade Markers to Price Charts

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** trader
**I want** trade markers on price charts
**So that** I can see where trades were executed

### Acceptance Criteria

- [ ] Extend candlestick chart with trade markers:
  ```python
  def render_candlestick_with_trades(
      ohlc_df: pd.DataFrame,
      trades_df: pd.DataFrame,
      chart_id: str = "price_chart"
  ):
      """Render candlestick chart with trade markers."""
      if ohlc_df.empty:
          st.info("No price data available")
          return

      # Format OHLC data
      ohlc_df = ohlc_df.copy()
      ohlc_df['time'] = pd.to_datetime(ohlc_df['time']).dt.strftime('%Y-%m-%d')
      candles = json.loads(
          ohlc_df[['time', 'open', 'high', 'low', 'close']].to_json(orient='records')
      )

      # Format trade markers
      markers = []
      if not trades_df.empty:
          for _, trade in trades_df.iterrows():
              markers.append({
                  "time": pd.to_datetime(trade['timestamp']).strftime('%Y-%m-%d'),
                  "position": "belowBar" if trade['side'] == 'buy' else "aboveBar",
                  "color": "#26a69a" if trade['side'] == 'buy' else "#ef5350",
                  "shape": "arrowUp" if trade['side'] == 'buy' else "arrowDown",
                  "text": f"{trade['side'].upper()} @ ${trade['price']:,.2f}"
              })

      chart_options = {
          "height": 400,
          "layout": {
              "background": {"type": "solid", "color": "#131722"},
              "textColor": "#d1d4dc"
          },
          "grid": {
              "vertLines": {"color": "rgba(42,46,57,0)"},
              "horzLines": {"color": "rgba(42,46,57,0.6)"}
          }
      }

      series = [{
          "type": "Candlestick",
          "data": candles,
          "options": {
              "upColor": "#26a69a",
              "downColor": "#ef5350",
              "borderVisible": False
          },
          "markers": markers
      }]

      renderLightweightCharts(
          [{"chart": chart_options, "series": series}],
          chart_id
      )
  ```
- [ ] Buy markers: green arrow up, below candle
- [ ] Sell markers: red arrow down, above candle
- [ ] Marker text shows side and price
- [ ] Markers positioned on correct date/time
- [ ] Handle many trades (pagination/filtering)

### Technical Notes
- Markers are part of the series configuration
- `position`: "belowBar" or "aboveBar"
- `shape`: "arrowUp", "arrowDown", "circle", "square"
- Too many markers can clutter chart - consider filtering

### Definition of Done
- Trade markers display on chart
- Buy/sell markers correctly positioned
- Colors match trading conventions
- Marker text readable on hover
- Performance acceptable with many trades

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 5.1 Build Equity Curve with Drawdown | 5 | P0 | Epic 3 |
| 5.2 Implement Grid Levels Visualization | 5 | P1 | Epic 3 |
| 5.3 Create TradingView Candlestick Chart | 8 | P1 | Epic 3 |
| 5.4 Add Trade Markers to Charts | 5 | P1 | 5.3 |
| **Total** | **23** | | |

---

## Sources & References

- [Plotly Python Documentation](https://plotly.com/python/)
- [streamlit-lightweight-charts](https://github.com/nickmccullum/streamlit-lightweight-charts)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Plotly Subplots](https://plotly.com/python/subplots/)
