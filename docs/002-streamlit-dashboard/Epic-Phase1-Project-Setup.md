# Epic: Phase 1 - Project Setup & Core Architecture

**Epic Owner:** Development Team
**Priority:** Critical - Must be completed before other dashboard work
**Dependencies:** Backend API endpoints from Phase 4 of core bot

---

## Overview

Phase 1 establishes the dashboard project structure, dependencies, and foundational components. This phase delivers a runnable Streamlit application with proper configuration and shared state management.

### Key Deliverables
- Dashboard directory structure within the existing project
- Complete `requirements.txt` with pinned dependencies
- Streamlit configuration file for theming
- Shared state management module

### Technology Stack
Based on 2024-2025 Streamlit best practices:
- **Streamlit 1.37+**: Required for stable `@st.fragment(run_every=)` decorator
- **httpx 0.27+**: Async HTTP client with connection pooling
- **Plotly 5.24+**: Interactive charting
- **streamlit-lightweight-charts 0.7.20+**: TradingView-style candlesticks
- **streamlit-aggrid 0.3.4+**: Professional data tables
- **streamlit-authenticator 0.3.2+**: Authentication

---

## Story 1.1: Initialize Dashboard Project Structure

**Story Points:** 2
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a well-organized dashboard directory structure
**So that** code is maintainable and follows Streamlit multi-page patterns

### Acceptance Criteria

- [ ] Create dashboard directory structure:
  ```
  trading_dashboard/
  ├── .streamlit/
  │   └── config.toml
  ├── app.py
  ├── config.yaml
  ├── pages/
  │   ├── dashboard.py
  │   ├── positions_orders.py
  │   ├── trade_history.py
  │   ├── risk_management.py
  │   ├── grid_strategy.py
  │   └── configuration.py
  └── components/
      ├── __init__.py
      ├── api_client.py
      ├── auth.py
      └── state.py
  ```
- [ ] Create `__init__.py` files where needed
- [ ] Add dashboard directory to `.gitignore` exclusions for local config
- [ ] Verify structure allows `streamlit run app.py`

### Technical Notes
- Use Streamlit 1.36+ `st.Page` pattern instead of legacy `pages/` auto-discovery
- Keep page files focused on UI, delegate business logic to components
- `config.yaml` stores authentication credentials (not in git)

### Definition of Done
- Directory structure created and committed
- `streamlit run app.py` launches without errors
- All `__init__.py` files present in component directories

---

## Story 1.2: Configure Dependencies and Requirements

**Story Points:** 2
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** all dashboard dependencies defined with pinned versions
**So that** builds are reproducible and compatible

### Acceptance Criteria

- [ ] Create `trading_dashboard/requirements.txt`:
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
- [ ] Verify all dependencies install cleanly
- [ ] Test import of each library
- [ ] Document any system-level dependencies (if any)
- [ ] Add to main project's optional dependencies group

### Technical Notes
- `httpx` chosen over `requests` for async support and connection pooling
- `orjson` provides faster JSON parsing for API responses
- `streamlit-lightweight-charts` has lower overhead than Plotly for OHLCV data

### Definition of Done
- `requirements.txt` created with all dependencies
- `pip install -r requirements.txt` succeeds in clean virtualenv
- All imports work without errors

---

## Story 1.3: Create Streamlit Configuration

**Story Points:** 1
**Priority:** P1 - High

### Description
**As a** developer
**I want** Streamlit theming and behavior configured
**So that** the dashboard has a professional trading appearance

### Acceptance Criteria

- [ ] Create `.streamlit/config.toml`:
  ```toml
  [theme]
  primaryColor = "#2962FF"
  backgroundColor = "#0E1117"
  secondaryBackgroundColor = "#1E2130"
  textColor = "#FAFAFA"
  font = "sans serif"

  [server]
  headless = true
  port = 8501
  enableCORS = false

  [browser]
  gatherUsageStats = false
  ```
- [ ] Configure dark theme matching TradingView style
- [ ] Set appropriate server defaults
- [ ] Disable usage stats collection

### Technical Notes
- Dark theme reduces eye strain for trading interfaces
- Color scheme matches lightweight-charts defaults for consistency
- `headless = true` for production deployment

### Definition of Done
- Config file created with all settings
- Dashboard launches with correct theme
- No Streamlit telemetry sent

---

## Story 1.4: Implement Shared State Management

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** centralized state management for the dashboard
**So that** state is consistent across pages and fragments

### Acceptance Criteria

- [ ] Create `components/state.py`:
  ```python
  import streamlit as st
  from dataclasses import dataclass, field
  from typing import Dict, Any, Optional

  @dataclass
  class DashboardState:
      config: Dict[str, Any] = field(default_factory=dict)
      read_only_mode: bool = True
      last_refresh: Optional[str] = None
      selected_symbol: str = "BTC/USDT"

  def init_state() -> None:
      """Initialize session state on app startup."""
      if "dashboard_state" not in st.session_state:
          st.session_state.dashboard_state = DashboardState()
      if "authenticated" not in st.session_state:
          st.session_state.authenticated = False

  def get_state() -> DashboardState:
      """Get the current dashboard state."""
      return st.session_state.dashboard_state
  ```
- [ ] Initialize state in `app.py` before navigation
- [ ] State survives page navigation
- [ ] State cleared on logout
- [ ] Document state variables and their purposes

### Technical Notes
- Use `st.session_state` for cross-page persistence
- Dataclass provides type hints and default values
- Read-only mode defaults to `True` for safety
- Avoid storing large datasets in session state (use caching instead)

### Definition of Done
- State module implemented with type hints
- State persists across page navigation
- State initializes correctly on fresh session
- Unit tests for state initialization

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 1.1 Initialize Dashboard Project Structure | 2 | P0 | None |
| 1.2 Configure Dependencies and Requirements | 2 | P0 | 1.1 |
| 1.3 Create Streamlit Configuration | 1 | P1 | 1.1 |
| 1.4 Implement Shared State Management | 3 | P0 | 1.1 |
| **Total** | **8** | | |

---

## Sources & References

- [Streamlit Configuration Documentation](https://docs.streamlit.io/library/advanced-features/configuration)
- [Streamlit Session State](https://docs.streamlit.io/library/api-reference/session-state)
- [httpx Documentation](https://www.python-httpx.org/)
