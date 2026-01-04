# Epic: Phase 1 - Authentication & Navigation

**Epic Owner:** Development Team
**Priority:** Critical - Required for secure dashboard access
**Dependencies:** Epic 1 (Project Setup)

---

## Overview

This epic implements secure authentication and multi-page navigation using Streamlit 1.36+ patterns. The dashboard uses YAML-based credentials for local deployment with `streamlit-authenticator`.

### Key Deliverables
- Authentication gate blocking unauthenticated access
- Multi-page navigation with `st.Page` and `st.navigation`
- Role-based page access control
- Persistent sidebar with user context

### Security Considerations
- Password hashing with bcrypt
- Cookie-based session persistence
- No hardcoded credentials in code
- Config file excluded from git

---

## Story 2.1: Implement streamlit-authenticator Integration

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** secure login before accessing the dashboard
**So that** unauthorized users cannot view or modify trading data

### Acceptance Criteria

- [ ] Create `config.yaml` for credentials:
  ```yaml
  cookie:
    expiry_days: 30
    key: "your_64_char_hex_key_here"
    name: "trading_dashboard_auth"

  credentials:
    usernames:
      admin:
        email: admin@localhost
        first_name: Admin
        last_name: User
        password: "$2b$12$..."  # bcrypt hash
        roles: [admin]
  ```
- [ ] Create `components/auth.py`:
  ```python
  import streamlit as st
  import streamlit_authenticator as stauth
  import yaml
  from pathlib import Path

  def check_auth() -> bool:
      """Check authentication status, show login if needed."""
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
          st.error("Invalid username or password")
      return False
  ```
- [ ] Add `config.yaml` to `.gitignore`
- [ ] Create `config.yaml.example` template without secrets
- [ ] Document password hash generation:
  ```python
  # Generate hash:
  # python -c "import streamlit_authenticator as stauth; print(stauth.Hasher(['your_password']).generate())"
  ```
- [ ] Generate secure cookie key:
  ```python
  # python -c "import secrets; print(secrets.token_hex(32))"
  ```

### Technical Notes
- `streamlit-authenticator` handles session cookies automatically
- Bcrypt hashing is CPU-intensive but secure
- Cookie key must be exactly 64 hex characters
- Consider implementing password reset flow for production

### Definition of Done
- Authentication blocks access without login
- Valid credentials grant access
- Invalid credentials show error
- Session persists across browser refresh (cookie)
- No credentials in git repository

---

## Story 2.2: Build Multi-Page Navigation with st.Page

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** multi-page navigation using Streamlit 1.36+ patterns
**So that** pages can be dynamically loaded with access control

### Background
Streamlit 1.36+ introduced `st.Page` and `st.navigation` as the preferred multi-page pattern, replacing the legacy `pages/` directory auto-discovery.

### Acceptance Criteria

- [ ] Define pages in `app.py`:
  ```python
  # Define pages with role-based access
  dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True)
  positions = st.Page("pages/positions_orders.py", title="Positions", icon="📋")
  history = st.Page("pages/trade_history.py", title="Trade History", icon="📜")
  risk = st.Page("pages/risk_management.py", title="Risk Management", icon="⚠️")
  grid = st.Page("pages/grid_strategy.py", title="Grid Strategy", icon="📐")
  config = st.Page("pages/configuration.py", title="Configuration", icon="⚙️")
  ```
- [ ] Group pages by section:
  ```python
  pg = st.navigation({
      "Trading": [dashboard, positions, history],
      "Strategy": [grid, risk],
      "System": [config],
  })
  ```
- [ ] Call `pg.run()` after authentication check
- [ ] Create placeholder files for each page
- [ ] Verify navigation renders correctly

### Technical Notes
- `st.Page` accepts URL path, title, icon, and default flag
- Navigation sections group related pages in sidebar
- `default=True` sets landing page after login
- Page files are executed when navigated to

### Definition of Done
- All pages accessible from sidebar navigation
- Pages grouped into logical sections
- Default page loads after authentication
- Navigation state persists correctly

---

## Story 2.3: Create Application Entry Point

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a clean `app.py` entry point coordinating auth and navigation
**So that** the application starts correctly with proper initialization

### Acceptance Criteria

- [ ] Create `app.py`:
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

  # Define and configure pages
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

  # Shared sidebar elements
  with st.sidebar:
      st.caption(f"User: {st.session_state.get('username', 'Unknown')}")
      if st.button("🔄 Refresh All Data"):
          st.cache_data.clear()
          st.rerun()

  pg.run()
  ```
- [ ] `st.set_page_config` called first (required by Streamlit)
- [ ] State initialized before authentication
- [ ] Authentication checked before navigation rendered
- [ ] `st.stop()` prevents page content from loading without auth

### Technical Notes
- `layout="wide"` maximizes screen real estate for trading dashboards
- `initial_sidebar_state="expanded"` shows navigation immediately
- Order matters: `set_page_config` must be first Streamlit call
- `st.stop()` halts script execution without error

### Definition of Done
- `streamlit run app.py` launches successfully
- Unauthenticated users see login only
- Authenticated users see navigation and default page
- Page title and favicon set correctly

---

## Story 2.4: Add Sidebar Components and User Context

**Story Points:** 2
**Priority:** P1 - High

### Description
**As a** trader
**I want** persistent sidebar elements showing user context and quick actions
**So that** common actions are accessible from any page

### Acceptance Criteria

- [ ] Display current username in sidebar
- [ ] Add "Refresh All Data" button clearing cache:
  ```python
  if st.button("🔄 Refresh All Data"):
      st.cache_data.clear()
      st.rerun()
  ```
- [ ] Add logout button:
  ```python
  if st.button("🚪 Logout"):
      st.session_state.authenticator.logout()
      st.rerun()
  ```
- [ ] Display backend connection status indicator
- [ ] Show last data refresh timestamp
- [ ] Add read-only mode indicator

### Technical Notes
- Sidebar elements in `app.py` persist across all pages
- `st.cache_data.clear()` invalidates all cached API responses
- `st.rerun()` forces page refresh with cleared cache
- Connection status can use health endpoint

### Definition of Done
- Username visible on all pages
- Refresh button clears cache and reloads
- Logout button ends session
- Connection status updates correctly

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 2.1 Implement streamlit-authenticator | 5 | P0 | Epic 1 |
| 2.2 Build Multi-Page Navigation | 3 | P0 | 2.1 |
| 2.3 Create Application Entry Point | 3 | P0 | 2.1, 2.2 |
| 2.4 Add Sidebar Components | 2 | P1 | 2.3 |
| **Total** | **13** | | |

---

## Sources & References

- [streamlit-authenticator Documentation](https://github.com/mkhorasani/Streamlit-Authenticator)
- [Streamlit Multi-page Apps](https://docs.streamlit.io/library/get-started/multipage-apps)
- [st.navigation API Reference](https://docs.streamlit.io/library/api-reference/navigation)
