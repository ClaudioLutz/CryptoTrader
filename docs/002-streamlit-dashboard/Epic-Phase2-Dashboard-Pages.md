# Epic: Phase 2 - Dashboard Pages Implementation

**Epic Owner:** Development Team
**Priority:** High - Core dashboard functionality
**Dependencies:** Epic 1 (Project Setup), Epic 2 (Auth & Navigation), Epic 3 (API Client)

---

## Overview

This epic implements all dashboard pages with real-time updates using `@st.fragment`. Each page focuses on specific trading data with appropriate refresh intervals.

### Key Deliverables
- Live dashboard overview with key metrics
- Positions & orders management page
- Trade history with advanced filtering (AgGrid)
- Risk management status page
- Grid strategy visualization
- Configuration page with safety controls

### Design Principles
- Use `@st.fragment(run_every=)` for partial page updates
- Limit to 3-4 auto-refreshing fragments per page
- Static elements outside fragments to prevent flicker
- Progressive enhancement: basic functionality first, then real-time

---

## Story 4.1: Build Live Dashboard Overview Page

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** a dashboard overview showing key metrics at a glance
**So that** I can quickly assess trading performance

### Acceptance Criteria

- [ ] Create `pages/dashboard.py`:
  ```python
  import streamlit as st
  from components.api_client import fetch_pnl, fetch_positions, fetch_status

  st.title("📊 Trading Dashboard")

  # Auto-refreshing metrics panel
  @st.fragment(run_every="2s")
  def live_metrics_panel():
      pnl = fetch_pnl()
      positions = fetch_positions()

      col1, col2, col3, col4 = st.columns(4)
      col1.metric(
          "Total P&L",
          f"${pnl.get('total', 0):,.2f}",
          f"{pnl.get('change_pct', 0):+.2f}%",
          border=True
      )
      col2.metric(
          "Unrealized",
          f"${pnl.get('unrealized', 0):,.2f}",
          border=True
      )
      col3.metric(
          "Open Positions",
          len(positions.get('positions', [])),
          border=True
      )
      col4.metric(
          "Grid Cycles",
          pnl.get('cycles', 0),
          border=True
      )

  live_metrics_panel()
  ```
- [ ] Display 4 key metrics: Total P&L, Unrealized P&L, Open Positions, Grid Cycles
- [ ] Use `@st.fragment(run_every="2s")` for auto-refresh
- [ ] Show delta values where appropriate
- [ ] Add equity curve chart (static, refreshes with page)
- [ ] Add recent trades table (last 10)

### Technical Notes
- Fragments with `run_every` refresh independently of page
- Keep fragment code minimal to reduce render time
- `border=True` on metrics provides visual separation
- Delta colors: green for positive, red for negative

### Definition of Done
- Dashboard shows all key metrics
- Metrics auto-refresh every 2 seconds
- No page flicker during fragment refresh
- Error states handled gracefully

---

## Story 4.2: Implement Positions & Orders Page

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** to view and manage open positions and orders
**So that** I can monitor my trading exposure

### Acceptance Criteria

- [ ] Create `pages/positions_orders.py`:
  ```python
  import streamlit as st
  import pandas as pd
  from components.api_client import fetch_positions

  st.title("📋 Positions & Orders")

  @st.fragment(run_every="3s")
  def positions_table():
      data = fetch_positions()
      positions = data.get('positions', [])

      if not positions:
          st.info("No open positions")
          return

      df = pd.DataFrame(positions)

      # Color-coded P&L column
      st.dataframe(
          df,
          column_config={
              "pnl": st.column_config.NumberColumn(
                  "P&L",
                  format="$%.2f",
              ),
              "entry_price": st.column_config.NumberColumn(
                  "Entry",
                  format="$%.2f",
              ),
              "current_price": st.column_config.NumberColumn(
                  "Current",
                  format="$%.2f",
              ),
          },
          hide_index=True,
      )

  positions_table()
  ```
- [ ] Display positions with entry price, current price, P&L
- [ ] Show pending orders with status
- [ ] Add order cancellation button (with confirmation)
- [ ] Filter by symbol
- [ ] Sort by P&L, entry time, or symbol

### Technical Notes
- `st.dataframe` with `column_config` for formatting
- Cancel order requires API POST with confirmation dialog
- Consider using AgGrid for more control (Story 4.3)

### Definition of Done
- All open positions displayed
- Pending orders visible
- Data refreshes automatically
- Order cancellation works with confirmation

---

## Story 4.3: Create Trade History Page with AgGrid

**Story Points:** 8
**Priority:** P1 - High

### Description
**As a** trader
**I want** to view and filter my trade history
**So that** I can analyze past performance

### Acceptance Criteria

- [ ] Create `pages/trade_history.py` with AgGrid:
  ```python
  import streamlit as st
  import pandas as pd
  from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
  from components.api_client import fetch_trades

  st.title("📜 Trade History")

  # Filters
  col1, col2, col3 = st.columns(3)
  with col1:
      symbol_filter = st.selectbox("Symbol", ["All", "BTC/USDT", "ETH/USDT"])
  with col2:
      side_filter = st.selectbox("Side", ["All", "BUY", "SELL"])
  with col3:
      date_range = st.date_input("Date Range", [])

  # Load and filter data
  data = fetch_trades()
  trades = data.get('trades', [])
  df = pd.DataFrame(trades)

  # Apply filters...

  # Configure AgGrid
  gb = GridOptionsBuilder.from_dataframe(df)
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
      df,
      gridOptions=gb.build(),
      allow_unsafe_jscode=True,
      theme="balham",
      height=500
  )
  ```
- [ ] Implement filtering by symbol, side, date range
- [ ] Color-code P&L (green positive, red negative)
- [ ] Color-code BUY/SELL sides
- [ ] Enable pagination (25 rows per page)
- [ ] Enable column sorting and filtering
- [ ] Support row selection for bulk actions
- [ ] Export selected rows to CSV

### Technical Notes
- AgGrid requires `allow_unsafe_jscode=True` for styling
- "balham" theme works well with dark Streamlit themes
- JsCode styling executes in browser, not Python
- Consider server-side pagination for large datasets

### Definition of Done
- Trade history displays with all columns
- Filtering works correctly
- P&L and side columns color-coded
- Pagination functional
- CSV export works

---

## Story 4.4: Build Risk Management Page

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** trader
**I want** to view risk metrics and circuit breaker status
**So that** I can monitor risk exposure

### Acceptance Criteria

- [ ] Create `pages/risk_management.py`:
  ```python
  import streamlit as st
  from components.api_client import fetch_status, fetch_health

  st.title("⚠️ Risk Management")

  @st.fragment(run_every="5s")
  def risk_status_panel():
      status = fetch_status()
      health = fetch_health()

      # Status indicators
      def status_icon(healthy: bool) -> str:
          return "🟢" if healthy else "🔴"

      st.subheader("System Status")
      cols = st.columns(5)
      cols[0].markdown(f"{status_icon(health.get('healthy'))} **API Health**")
      cols[1].markdown(f"{status_icon(status.get('ws_connected'))} **WebSocket**")
      cols[2].markdown(f"{status_icon(not status.get('circuit_breaker_active'))} **Circuit Breaker**")
      cols[3].markdown(f"{status_icon(status.get('trading_enabled'))} **Trading**")
      cols[4].markdown(f"{status_icon(status.get('db_connected'))} **Database**")

      # Risk metrics
      st.subheader("Risk Metrics")
      col1, col2, col3 = st.columns(3)

      drawdown = status.get('current_drawdown', 0)
      max_drawdown = status.get('max_drawdown_limit', 10)
      drawdown_pct = (drawdown / max_drawdown) * 100 if max_drawdown else 0

      with col1:
          st.metric(
              "Current Drawdown",
              f"{drawdown:.2f}%",
              delta=f"Limit: {max_drawdown}%",
              delta_color="off",
              border=True
          )
          st.progress(min(drawdown_pct / 100, 1.0))

      with col2:
          st.metric(
              "Daily Loss",
              f"${status.get('daily_loss', 0):,.2f}",
              delta=f"Limit: ${status.get('daily_loss_limit', 0):,.2f}",
              delta_color="off",
              border=True
          )

      with col3:
          circuit_breaker = status.get('circuit_breaker_active', False)
          st.metric(
              "Circuit Breaker",
              "ACTIVE" if circuit_breaker else "Inactive",
              delta="Trading halted" if circuit_breaker else "Normal",
              delta_color="inverse" if circuit_breaker else "off",
              border=True
          )

  risk_status_panel()
  ```
- [ ] Display 5 system status indicators (API, WebSocket, Circuit Breaker, Trading, Database)
- [ ] Show current drawdown with progress bar
- [ ] Display daily loss vs limit
- [ ] Show circuit breaker status prominently
- [ ] Auto-refresh every 5 seconds
- [ ] Alert styling for critical states

### Technical Notes
- Traffic light indicators (🟢/🔴) provide quick visual status
- Progress bar shows drawdown as percentage of limit
- "inverse" delta_color highlights bad states
- Consider audio/visual alert on circuit breaker trigger

### Definition of Done
- All status indicators display correctly
- Risk metrics show current vs limit
- Circuit breaker status prominent
- Auto-refresh working
- Visual alerts for critical states

---

## Story 4.5: Implement Grid Strategy Visualization Page

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** trader
**I want** to visualize my grid strategy levels
**So that** I can understand order placement

### Acceptance Criteria

- [ ] Create `pages/grid_strategy.py`:
  ```python
  import streamlit as st
  from components.api_client import fetch_status

  st.title("📐 Grid Strategy")

  # Fetch grid configuration
  status = fetch_status()
  grid_config = status.get('grid_config', {})

  # Display grid parameters
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Lower Price", f"${grid_config.get('lower_price', 0):,.2f}")
  col2.metric("Upper Price", f"${grid_config.get('upper_price', 0):,.2f}")
  col3.metric("Grid Count", grid_config.get('num_grids', 0))
  col4.metric("Grid Step", f"${grid_config.get('grid_step', 0):,.2f}")

  # Grid visualization chart (see Epic 5)
  # render_grid_levels(current_price, grid_config)

  # Grid level table
  st.subheader("Grid Levels")
  # Show each level with order status (filled/pending)
  ```
- [ ] Display grid parameters (lower, upper, count, step)
- [ ] Show current price relative to grid
- [ ] Display all grid levels in table
- [ ] Indicate which levels have filled orders
- [ ] Visual chart of grid levels (Epic 5)

### Technical Notes
- Grid levels can be computed from config
- Color-code levels: green (buy), red (sell), yellow (current price)
- Consider interactive chart allowing level inspection

### Definition of Done
- Grid parameters displayed
- All grid levels visible
- Filled vs pending levels distinguishable
- Visual chart renders correctly

---

## Story 4.6: Create Configuration Page with Safety Controls

**Story Points:** 8
**Priority:** P1 - High

### Description
**As a** trader
**I want** to modify bot configuration with safety controls
**So that** I can adjust strategy without accidental changes

### Acceptance Criteria

- [ ] Create `pages/configuration.py`:
  ```python
  import streamlit as st
  from components.state import get_state
  from components.api_client import get_http_client

  st.title("⚙️ Configuration")
  state = get_state()

  # Safety toggle in sidebar
  with st.sidebar:
      state.read_only_mode = st.toggle("🔒 Read-Only Mode", value=True)

  if state.read_only_mode:
      st.info("Configuration is read-only. Disable lock to make changes.")

  # Configuration form
  with st.form("config_form"):
      st.subheader("Grid Parameters")

      col1, col2 = st.columns(2)
      with col1:
          grid_size = st.number_input(
              "Grid Size ($)",
              value=state.config.get('grid_size', 100),
              disabled=state.read_only_mode
          )
          num_grids = st.number_input(
              "Number of Grids",
              value=state.config.get('num_grids', 10),
              disabled=state.read_only_mode
          )
      with col2:
          stop_loss = st.number_input(
              "Stop Loss (%)",
              value=state.config.get('stop_loss_pct', 5.0),
              disabled=state.read_only_mode
          )
          take_profit = st.number_input(
              "Take Profit (%)",
              value=state.config.get('take_profit_pct', 10.0),
              disabled=state.read_only_mode
          )

      submitted = st.form_submit_button(
          "Save Configuration",
          disabled=state.read_only_mode
      )

      if submitted:
          st.session_state.pending_config = {
              'grid_size': grid_size,
              'num_grids': num_grids,
              'stop_loss_pct': stop_loss,
              'take_profit_pct': take_profit
          }

  # Confirmation dialog
  @st.dialog("⚠️ Confirm Configuration Change")
  def confirm_save():
      st.write("Apply these changes?")
      st.json(st.session_state.pending_config)
      if st.button("Confirm", type="primary"):
          response = get_http_client().post(
              "/api/config",
              json=st.session_state.pending_config
          )
          if response.status_code == 200:
              st.success("Configuration saved!")
              state.config.update(st.session_state.pending_config)
          else:
              st.error(f"Failed to save: {response.text}")
          st.rerun()

  if st.session_state.get('pending_config'):
      confirm_save()
  ```
- [ ] Read-only mode toggle (defaults to ON)
- [ ] All inputs disabled in read-only mode
- [ ] Confirmation dialog before saving
- [ ] Display pending changes before confirmation
- [ ] API call to save configuration
- [ ] Success/error feedback
- [ ] Load current config on page load

### Technical Notes
- Read-only mode is critical safety feature
- `@st.dialog` creates modal confirmation
- Form submission triggers confirmation, not immediate save
- Consider validation before API call

### Definition of Done
- Read-only mode prevents all changes
- Confirmation dialog shows pending changes
- Configuration saves to backend
- Success/error feedback displayed
- Current values loaded on page init

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 4.1 Build Live Dashboard Overview | 5 | P0 | Epic 3 |
| 4.2 Implement Positions & Orders | 5 | P0 | Epic 3 |
| 4.3 Create Trade History with AgGrid | 8 | P1 | Epic 3 |
| 4.4 Build Risk Management Page | 5 | P1 | Epic 3 |
| 4.5 Implement Grid Strategy Visualization | 5 | P1 | Epic 3 |
| 4.6 Create Configuration Page | 8 | P1 | Epic 3 |
| **Total** | **36** | | |

---

## Sources & References

- [Streamlit Fragments](https://docs.streamlit.io/library/api-reference/execution-flow/st.fragment)
- [streamlit-aggrid Documentation](https://github.com/PablocFonseca/streamlit-aggrid)
- [Streamlit Dialogs](https://docs.streamlit.io/library/api-reference/execution-flow/st.dialog)
