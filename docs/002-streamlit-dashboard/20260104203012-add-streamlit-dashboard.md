# Add Streamlit Trading Dashboard

## Summary

Implemented a complete Streamlit-based trading dashboard for the grid trading bot, featuring real-time metrics, charting, trade history, risk management, and configuration controls with safety patterns.

## Context / Problem

The trading bot lacked a visual frontend for monitoring and configuration. Operators needed a way to:
- View real-time trading metrics and P&L
- Monitor open positions and pending orders
- Analyze trade history with filtering
- Track risk metrics and circuit breaker status
- Visualize grid strategy levels
- Safely modify bot configuration

## What Changed

### New Directory: `trading_dashboard/`

**Core Files:**
- `app.py` - Main application entry point with auth and navigation
- `requirements.txt` - Dashboard dependencies (Streamlit 1.37+, httpx, Plotly, etc.)
- `.streamlit/config.toml` - Dark theme configuration
- `config.yaml.example` - Authentication configuration template

**Components (`components/`):**
- `__init__.py` - Package exports
- `state.py` - Shared state management using `st.session_state`
- `auth.py` - streamlit-authenticator integration
- `api_client.py` - httpx client with caching for backend API

**Pages (`pages/`):**
- `dashboard.py` - Live metrics, equity curve, recent trades
- `positions_orders.py` - Open positions and pending order management
- `trade_history.py` - Historical trades with AgGrid filtering
- `risk_management.py` - Risk metrics and circuit breaker status
- `grid_strategy.py` - Grid level visualization with Plotly
- `configuration.py` - Bot settings with read-only safety mode

### Updated Files:
- `.gitignore` - Added exclusions for `trading_dashboard/config.yaml`

### Documentation:
- Created epics and stories in `docs/002-streamlit-dashboard/`

## How to Test

1. Install dependencies:
   ```bash
   cd trading_dashboard
   pip install -r requirements.txt
   ```

2. Create authentication config:
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml with your credentials
   # Generate password hash: python -c "import streamlit_authenticator as stauth; print(stauth.Hasher(['password']).generate())"
   # Generate cookie key: python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Run the dashboard:
   ```bash
   streamlit run app.py
   ```

4. Verify:
   - Login page appears
   - After login, navigation works
   - All pages load without errors
   - Auto-refresh fragments update every 2-5 seconds

## Risk / Rollback Notes

**Risks:**
- Dashboard requires backend API to be running for data
- Authentication config must be properly configured
- Read-only mode must be enabled by default for safety

**Rollback:**
- Delete `trading_dashboard/` directory
- Remove `.gitignore` additions
- No changes to core trading bot functionality

**Dependencies:**
- Requires Streamlit 1.37+ for stable `@st.fragment(run_every=)`
- Backend API must expose endpoints: `/api/trades`, `/api/positions`, `/api/pnl`, `/api/equity`, `/api/status`, `/health`
