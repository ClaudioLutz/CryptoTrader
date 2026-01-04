# Streamlit Crypto Trading Dashboard: Complete Implementation Plan

A Python-native frontend for your grid trading bot requires careful architectural decisions balancing real-time updates, performance, and safety. This plan leverages **st.fragment** for partial page updates, **httpx** for async backend communication, and **streamlit-lightweight-charts** for professional TradingView-style visualizations—all patterns validated for 2024-2025 Streamlit development.

## Architecture overview and technology stack

The recommended architecture separates concerns into three layers: a navigation entrypoint handling authentication and routing, page-specific fragments enabling independent data refresh, and a shared state/API layer managing backend communication.

**Core dependencies (requirements.txt):**
```
streamlit>=1.37.0
httpx>=0.27.0
plotly>=5.24.0
streamlit-lightweight-charts>=0.7.20
streamlit-aggrid>=0.3.4
streamlit-authenticator>=0.3.2
pandas>=2.0.0
numpy>=1.24.0
orjson>=3.9.0
pyyaml>=6.0
```

The stack prioritizes **httpx** over requests because it supports both sync and async APIs with connection pooling, critical for efficiently polling your 8 REST endpoints. For charting, Plotly handles equity curves and P&L visualization while lightweight-charts delivers TradingView-style candlesticks with superior real-time performance.

## Project structure and multi-page navigation

Streamlit 1.36+ introduced `st.Page` and `st.navigation` as the preferred multi-page pattern, replacing the legacy `pages/` directory approach. This enables dynamic page access control based on authentication.

```
trading_dashboard/
├── .streamlit/
│   └── config.toml              # Theme configuration
├── app.py                       # Entrypoint with navigation
├── config.yaml                  # Auth credentials
├── pages/
│   ├── dashboard.py             # Live overview
│   ├── positions_orders.py      # Grid positions
│   ├── trade_history.py         # Historical trades
│   ├── risk_management.py       # Circuit breakers, drawdown
│   ├── grid_strategy.py         # Grid visualization
│   └── configuration.py         # Bot settings
└── components/
    ├── api_client.py            # Backend communication
    ├── auth.py                  # Authentication
    └── state.py                 # Shared state
```

**Entrypoint (app.py):**
```python
import streamlit as st
from components.auth import check_auth
from components.state import init_state

st.set_page_config(
    page_title="Grid Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize shared state
init_state()

# Authentication gate
if not check_auth():
    st.stop()

# Define pages with role-based access
dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True)
positions = st.Page("pages/positions_orders.py", title="Positions", icon="📋")
history = st.Page("pages/trade_history.py", title="Trade History", icon="📜")
risk = st.Page("pages/risk_management.py", title="Risk Management", icon="⚠️")
grid = st.Page("pages/grid_strategy.py", title="Grid Strategy", icon="📐")
config = st.Page("pages/configuration.py", title="Configuration", icon="⚙️")

# Navigation with sections
pg = st.navigation({
    "Trading": [dashboard, positions, history],
    "Strategy": [grid, risk],
    "System": [config],
})

# Shared sidebar elements across all pages
with st.sidebar:
    st.caption(f"User: {st.session_state.get('username', 'Unknown')}")
    if st.button("🔄 Refresh All Data"):
        st.cache_data.clear()
        st.rerun()

pg.run()
```

## Real-time data updates with st.fragment

The **`@st.fragment(run_every=)`** decorator, stable since Streamlit 1.37, enables partial page updates without full script reruns—essential for trading dashboards requiring **1-5 second refresh intervals** without disrupting user interactions.

**Key pattern for live data display:**
```python
import streamlit as st
from components.api_client import fetch_pnl, fetch_positions

# Static elements (don't rerun with fragment)
st.title("📊 Trading Dashboard")

# Auto-refreshing fragment for metrics
@st.fragment(run_every="2s")
def live_metrics_panel():
    pnl = fetch_pnl()  # Cached with 5s TTL
    positions = fetch_positions()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total P&L", f"${pnl.get('total', 0):,.2f}", 
                f"{pnl.get('change_pct', 0):+.2f}%", border=True)
    col2.metric("Unrealized", f"${pnl.get('unrealized', 0):,.2f}", border=True)
    col3.metric("Open Positions", len(positions), border=True)
    col4.metric("Grid Cycles", pnl.get('cycles', 0), border=True)

live_metrics_panel()
```

**Fragment limitations to consider:**
- Cannot render widgets to externally created containers
- Return values ignored during fragment reruns (use session_state)
- Elements in external containers accumulate until full-app rerun

For sub-second tick data, combine WebSocket with queue pattern:

```python
import streamlit as st
import websocket
import threading
import queue
from streamlit.runtime.scriptrunner import add_script_run_ctx

if "price_queue" not in st.session_state:
    st.session_state.price_queue = queue.Queue(maxsize=1000)

def start_websocket():
    def on_message(ws, message):
        st.session_state.price_queue.put(json.loads(message))
    
    ws = websocket.WebSocketApp(
        "wss://your-exchange/ws",
        on_message=on_message
    )
    ws.run_forever()

if "ws_thread" not in st.session_state:
    thread = threading.Thread(target=start_websocket, daemon=True)
    add_script_run_ctx(thread)  # Required for Streamlit context
    thread.start()
    st.session_state.ws_thread = thread

@st.fragment(run_every="1s")
def display_live_prices():
    while not st.session_state.price_queue.empty():
        data = st.session_state.price_queue.get_nowait()
        st.session_state.last_price = data.get("price")
    st.metric("Price", f"${st.session_state.get('last_price', 0):,.2f}")
```

## Backend integration with httpx and caching

**httpx** is the recommended HTTP client for connecting to your aiohttp backend—it supports both sync and async modes with connection pooling, unlike requests.

**API client implementation (components/api_client.py):**
```python
import httpx
import streamlit as st
import asyncio
from typing import Dict, Any

API_BASE_URL = "http://localhost:8080"

@st.cache_resource
def get_http_client():
    """Cached client with connection pooling"""
    return httpx.Client(
        base_url=API_BASE_URL,
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )

# Endpoint-specific functions with appropriate TTLs
@st.cache_data(ttl=5)
def fetch_trades() -> Dict[str, Any]:
    return get_http_client().get("/api/trades").json()

@st.cache_data(ttl=5)
def fetch_positions() -> Dict[str, Any]:
    return get_http_client().get("/api/positions").json()

@st.cache_data(ttl=10)
def fetch_pnl() -> Dict[str, Any]:
    return get_http_client().get("/api/pnl").json()

@st.cache_data(ttl=10)
def fetch_equity() -> Dict[str, Any]:
    return get_http_client().get("/api/equity").json()

@st.cache_data(ttl=30)
def fetch_status() -> Dict[str, Any]:
    return get_http_client().get("/api/status").json()

@st.cache_data(ttl=60)
def fetch_health() -> Dict[str, Any]:
    return get_http_client().get("/health").json()

# Concurrent fetch for dashboard initialization
async def fetch_all_dashboard_data():
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        tasks = [
            client.get("/api/trades"),
            client.get("/api/positions"),
            client.get("/api/pnl"),
            client.get("/api/equity"),
            client.get("/api/status"),
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            "trades": responses[0].json() if not isinstance(responses[0], Exception) else {},
            "positions": responses[1].json() if not isinstance(responses[1], Exception) else {},
            "pnl": responses[2].json() if not isinstance(responses[2], Exception) else {},
            "equity": responses[3].json() if not isinstance(responses[3], Exception) else {},
            "status": responses[4].json() if not isinstance(responses[4], Exception) else {},
        }

@st.cache_data(ttl=5)
def get_all_data():
    return asyncio.run(fetch_all_dashboard_data())
```

**Caching strategy by data type:**

| Endpoint | TTL | Rationale |
|----------|-----|-----------|
| `/api/trades`, `/api/positions` | 5s | Real-time trading data |
| `/api/pnl`, `/api/equity` | 10s | Computed values, slightly stale OK |
| `/api/status` | 30s | Slow-changing operational state |
| `/health`, `/ready` | 60s | Infrastructure status |

## Financial charting implementation

Use **Plotly** for equity curves and analytics, **streamlit-lightweight-charts** for TradingView-style candlesticks and grid visualization.

**Equity curve with drawdown overlay:**
```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

def render_equity_curve(equity_data: list):
    df = pd.DataFrame(equity_data)
    df['peak'] = df['equity'].cummax()
    df['drawdown'] = (df['equity'] - df['peak']) / df['peak'] * 100
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['equity'], name="Equity",
                   line=dict(color='#2962FF', width=2)),
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(x=df['timestamp'], y=df['drawdown'], name="Drawdown %",
                   fill='tozeroy', fillcolor='rgba(239,83,80,0.3)',
                   line=dict(color='#ef5350', width=1)),
        secondary_y=True
    )
    
    fig.update_layout(
        title="Equity Curve with Drawdown",
        hovermode="x unified",
        height=450
    )
    fig.update_yaxes(title_text="Equity ($)", secondary_y=False)
    fig.update_yaxes(title_text="Drawdown (%)", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)
```

**Grid strategy visualization with price levels:**
```python
import plotly.graph_objects as go
import streamlit as st

def render_grid_levels(current_price: float, grid_config: dict):
    grid_start = grid_config['lower_price']
    grid_end = grid_config['upper_price']
    grid_step = grid_config['grid_step']
    
    levels = np.arange(grid_start, grid_end + grid_step, grid_step)
    buy_levels = levels[levels < current_price]
    sell_levels = levels[levels > current_price]
    
    fig = go.Figure()
    
    # Current price
    fig.add_hline(y=current_price, line=dict(color='yellow', width=3, dash='dash'),
                  annotation_text=f"Current: ${current_price:,.2f}")
    
    # Buy levels (green)
    for level in buy_levels:
        fig.add_hline(y=level, line=dict(color='rgba(38,166,154,0.6)', width=1))
        fig.add_shape(type="rect", x0=0, x1=1, y0=level-grid_step*0.1, 
                      y1=level+grid_step*0.1, xref="paper",
                      fillcolor="rgba(38,166,154,0.2)", line_width=0)
    
    # Sell levels (red)
    for level in sell_levels:
        fig.add_hline(y=level, line=dict(color='rgba(239,83,80,0.6)', width=1))
        fig.add_shape(type="rect", x0=0, x1=1, y0=level-grid_step*0.1,
                      y1=level+grid_step*0.1, xref="paper",
                      fillcolor="rgba(239,83,80,0.2)", line_width=0)
    
    fig.update_layout(
        title="Grid Strategy Levels",
        yaxis_title="Price ($)",
        height=600,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
```

**TradingView-style candlestick with trade markers:**
```python
from streamlit_lightweight_charts import renderLightweightCharts
import json

def render_tradingview_chart(ohlc_df: pd.DataFrame, trades_df: pd.DataFrame):
    # Format OHLC data
    candles = json.loads(ohlc_df[['time', 'open', 'high', 'low', 'close']].to_json(orient='records'))
    
    # Format trade markers
    markers = []
    for _, trade in trades_df.iterrows():
        markers.append({
            "time": trade['timestamp'].strftime('%Y-%m-%d'),
            "position": "belowBar" if trade['side'] == 'buy' else "aboveBar",
            "color": "#26a69a" if trade['side'] == 'buy' else "#ef5350",
            "shape": "arrowUp" if trade['side'] == 'buy' else "arrowDown",
            "text": f"{trade['side'].upper()}"
        })
    
    chart_options = {
        "height": 400,
        "layout": {"background": {"type": "solid", "color": "#131722"}, "textColor": "#d1d4dc"},
        "grid": {"vertLines": {"color": "rgba(42,46,57,0)"}, "horzLines": {"color": "rgba(42,46,57,0.6)"}}
    }
    
    series = [{
        "type": "Candlestick",
        "data": candles,
        "options": {"upColor": "#26a69a", "downColor": "#ef5350", "borderVisible": False},
        "markers": markers
    }]
    
    renderLightweightCharts([{"chart": chart_options, "series": series}], 'price_chart')
```

## Trade history with advanced filtering

**streamlit-aggrid** provides professional table capabilities essential for trading—conditional formatting, filtering, sorting, and pagination.

```python
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import streamlit as st

def render_trade_history(trades_df: pd.DataFrame):
    gb = GridOptionsBuilder.from_dataframe(trades_df)
    
    # Enable core features
    gb.configure_default_column(filterable=True, sortable=True, resizable=True)
    gb.configure_pagination(enabled=True, paginationPageSize=25)
    gb.configure_selection(selection_mode="multiple", use_checkbox=True)
    
    # P&L conditional formatting
    pnl_style = JsCode("""
    function(params) {
        if (params.value > 0) return {'color': '#26a69a', 'fontWeight': 'bold'};
        if (params.value < 0) return {'color': '#ef5350', 'fontWeight': 'bold'};
        return {};
    }
    """)
    gb.configure_column("pnl", cellStyle=pnl_style, type=["numericColumn"])
    
    # Side column styling
    side_style = JsCode("""
    function(params) {
        if (params.value === 'BUY') return {'backgroundColor': '#d4edda', 'color': '#155724'};
        if (params.value === 'SELL') return {'backgroundColor': '#f8d7da', 'color': '#721c24'};
        return {};
    }
    """)
    gb.configure_column("side", cellStyle=side_style)
    
    grid_response = AgGrid(
        trades_df,
        gridOptions=gb.build(),
        allow_unsafe_jscode=True,
        theme="balham",
        height=500
    )
    
    return grid_response['selected_rows']
```

## Risk metrics and status indicators

Display circuit breaker status, drawdown tracking, and health monitoring with clear visual hierarchy:

```python
import streamlit as st

def render_status_indicators(status_data: dict, health_data: dict):
    def status_icon(healthy: bool) -> str:
        return "🟢" if healthy else "🔴"
    
    st.subheader("System Status")
    cols = st.columns(5)
    
    cols[0].markdown(f"{status_icon(health_data.get('healthy'))} **API Health**")
    cols[1].markdown(f"{status_icon(status_data.get('ws_connected'))} **WebSocket**")
    cols[2].markdown(f"{status_icon(not status_data.get('circuit_breaker_active'))} **Circuit Breaker**")
    cols[3].markdown(f"{status_icon(status_data.get('trading_enabled'))} **Trading**")
    cols[4].markdown(f"{status_icon(status_data.get('db_connected'))} **Database**")

def render_risk_metrics(status_data: dict):
    st.subheader("Risk Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    drawdown = status_data.get('current_drawdown', 0)
    max_drawdown = status_data.get('max_drawdown_limit', 10)
    drawdown_pct = (drawdown / max_drawdown) * 100
    
    with col1:
        st.metric("Current Drawdown", f"{drawdown:.2f}%", 
                  delta=f"Limit: {max_drawdown}%", delta_color="off", border=True)
        st.progress(min(drawdown_pct / 100, 1.0))
    
    with col2:
        st.metric("Daily Loss", f"${status_data.get('daily_loss', 0):,.2f}",
                  delta=f"Limit: ${status_data.get('daily_loss_limit', 0):,.2f}", 
                  delta_color="off", border=True)
    
    with col3:
        circuit_breaker = status_data.get('circuit_breaker_active', False)
        st.metric("Circuit Breaker", "ACTIVE" if circuit_breaker else "Inactive",
                  delta="Trading halted" if circuit_breaker else "Normal", 
                  delta_color="inverse" if circuit_breaker else "off", border=True)
```

## Authentication for local deployment

**streamlit-authenticator** provides appropriate security for local trading dashboards with YAML-based credentials:

**config.yaml:**
```yaml
cookie:
  expiry_days: 30
  key: "your_64_char_hex_key_here"  # Generate: python -c "import secrets; print(secrets.token_hex(32))"
  name: "trading_dashboard_auth"

credentials:
  usernames:
    admin:
      email: admin@localhost
      first_name: Admin
      last_name: User
      password: "$2b$12$..."  # Generate: streamlit_authenticator.Hasher(['password']).generate()
      roles: [admin]
```

**Authentication component (components/auth.py):**
```python
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from pathlib import Path

def check_auth() -> bool:
    if "authenticator" not in st.session_state:
        config_path = Path(__file__).parent.parent / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        st.session_state.authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days']
        )
    
    st.session_state.authenticator.login()
    
    if st.session_state.get("authentication_status"):
        return True
    elif st.session_state.get("authentication_status") is False:
        st.error("Invalid credentials")
    return False
```

## Configuration controls with safety patterns

Implement read-only mode by default with confirmation dialogs for dangerous actions:

```python
import streamlit as st
from components.state import get_state

st.title("⚙️ Configuration")
state = get_state()

# Safety toggle in sidebar
with st.sidebar:
    state.read_only_mode = st.toggle("🔒 Read-Only Mode", value=True)

if state.read_only_mode:
    st.info("Configuration is read-only. Disable lock to make changes.")

# Configuration form with validation
with st.form("config_form"):
    st.subheader("Grid Parameters")
    
    col1, col2 = st.columns(2)
    with col1:
        grid_size = st.number_input("Grid Size ($)", value=state.config.get('grid_size', 100),
                                     disabled=state.read_only_mode)
        num_grids = st.number_input("Number of Grids", value=state.config.get('num_grids', 10),
                                     disabled=state.read_only_mode)
    with col2:
        stop_loss = st.number_input("Stop Loss (%)", value=state.config.get('stop_loss_pct', 5.0),
                                     disabled=state.read_only_mode)
        take_profit = st.number_input("Take Profit (%)", value=state.config.get('take_profit_pct', 10.0),
                                       disabled=state.read_only_mode)
    
    submitted = st.form_submit_button("Save Configuration", disabled=state.read_only_mode)
    
    if submitted:
        st.session_state.pending_config = {
            'grid_size': grid_size, 'num_grids': num_grids,
            'stop_loss_pct': stop_loss, 'take_profit_pct': take_profit
        }

# Confirmation dialog
@st.dialog("⚠️ Confirm Configuration Change")
def confirm_save():
    st.write("Apply these changes?")
    st.json(st.session_state.pending_config)
    if st.button("Confirm", type="primary"):
        # Send to backend API
        response = get_http_client().post("/api/config", json=st.session_state.pending_config)
        if response.status_code == 200:
            st.success("Configuration saved!")
            state.config.update(st.session_state.pending_config)
        st.rerun()

if st.session_state.get('pending_config'):
    confirm_save()
```

## Performance optimization guidelines

For dashboards with **1-5 second updates** across multiple components:

- Use `@st.fragment(run_every=)` for independent sections rather than full-page refreshes
- Cache HTTP client with `@st.cache_resource` for connection pooling
- Batch API calls using `asyncio.gather()` during page initialization
- Set appropriate TTLs: 5s for real-time data, 30s for status, 60s+ for static config
- Use `lightweight-charts` for price data (lower overhead than Plotly for OHLC)
- Limit to **3-4 auto-refreshing fragments** per page to avoid server overload
- Use `st.empty()` placeholders for charts that update frequently

## Conclusion

This implementation provides a production-ready Streamlit trading dashboard architecture. Key decisions—**st.fragment for partial updates**, **httpx with async batching**, and **lightweight-charts for TradingView-style visualization**—optimize for the real-time requirements of crypto trading while maintaining code simplicity. The read-only-by-default configuration pattern and streamlit-authenticator integration ensure appropriate safety for a system that controls live trading.

Start by implementing the API client layer and dashboard overview page, then incrementally add specialized views (trade history, grid visualization, risk management). The fragment-based architecture allows each component to evolve independently while maintaining consistent refresh behavior across the dashboard.