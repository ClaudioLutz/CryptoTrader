# Story 10.3: Implement Simple Authentication (Optional)

Status: review

**Version:** v2.0

## Story

As a **trader (Claudio)**,
I want **to add password protection if accessing remotely**,
So that **the dashboard isn't openly accessible on the network**.

## Acceptance Criteria

1. **AC1:** Simple password prompt appears on page load (when enabled)
2. **AC2:** Successful authentication grants access to dashboard
3. **AC3:** Session persists across page refreshes (cookie/token)
4. **AC4:** Failed attempts show error message
5. **AC5:** Authentication can be disabled for localhost-only use

## Tasks / Subtasks

- [x] Task 1: Add authentication config (AC: 5)
  - [x] Add `auth_enabled` to config
  - [x] Add `auth_password` to config (SecretStr)

- [x] Task 2: Create login page (AC: 1, 4)
  - [x] Password input field
  - [x] Submit button
  - [x] Error message display

- [x] Task 3: Implement session management (AC: 2, 3)
  - [x] Generate session token on success
  - [x] Store in cookie
  - [x] Validate on page load

- [x] Task 4: Protect dashboard routes (AC: 2)
  - [x] Check authentication before rendering
  - [x] Redirect to login if not authenticated

## Dev Notes

### Configuration Extension

```python
# In dashboard/config.py
from pydantic import SecretStr


class DashboardConfig(BaseSettings):
    # ... existing ...

    # Authentication (optional)
    auth_enabled: bool = Field(
        default=False,
        description="Enable password authentication"
    )
    auth_password: SecretStr = Field(
        default=SecretStr(""),
        description="Dashboard access password"
    )
    auth_session_hours: int = Field(
        default=24,
        description="Session duration in hours"
    )
```

### Authentication Middleware

```python
"""Simple authentication for dashboard."""

import hashlib
import secrets
from datetime import datetime, timedelta

from nicegui import app, ui

from dashboard.config import config


# Session storage (in-memory for simplicity)
_sessions: dict[str, datetime] = {}


def check_auth() -> bool:
    """Check if current request is authenticated."""
    if not config.auth_enabled:
        return True

    session_token = app.storage.user.get("session_token")
    if not session_token:
        return False

    expiry = _sessions.get(session_token)
    if not expiry or datetime.now() > expiry:
        return False

    return True


def create_session() -> str:
    """Create new session token."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=config.auth_session_hours)
    _sessions[token] = expiry
    return token


def verify_password(password: str) -> bool:
    """Verify password against configured value."""
    return password == config.auth_password.get_secret_value()


def login_page() -> None:
    """Render login page."""
    with ui.card().classes("login-card"):
        ui.label("CryptoTrader Dashboard").classes("login-title")
        ui.label("Enter password to continue").classes("login-subtitle")

        password_input = ui.input(
            "Password",
            password=True,
            password_toggle_button=True,
        ).classes("login-input")

        error_label = ui.label("").classes("login-error")

        async def handle_login():
            if verify_password(password_input.value):
                token = create_session()
                app.storage.user["session_token"] = token
                ui.navigate.to("/")
            else:
                error_label.text = "Invalid password"
                error_label.classes(add="visible")

        ui.button("Login", on_click=handle_login).classes("login-button")
```

### Route Protection

```python
"""Protected dashboard routes."""

from nicegui import ui

from dashboard.auth import check_auth, login_page


@ui.page("/")
def dashboard_page():
    """Main dashboard page with auth check."""
    if not check_auth():
        ui.navigate.to("/login")
        return

    # Render dashboard
    create_ui()


@ui.page("/login")
def login_route():
    """Login page route."""
    if check_auth():
        ui.navigate.to("/")
        return

    login_page()
```

### CSS Styling

```css
.login-card {
  max-width: 400px;
  margin: 100px auto;
  padding: 32px;
  background-color: var(--bg-secondary);
}

.login-title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.login-subtitle {
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.login-input {
  width: 100%;
  margin-bottom: 16px;
}

.login-button {
  width: 100%;
  background-color: var(--accent);
}

.login-error {
  color: var(--status-error);
  font-size: 13px;
  margin-bottom: 16px;
  visibility: hidden;
}

.login-error.visible {
  visibility: visible;
}
```

### Environment Variables

```bash
# Enable authentication
export DASHBOARD_AUTH_ENABLED=true
export DASHBOARD_AUTH_PASSWORD=your_secure_password

# Or in .env file
DASHBOARD_AUTH_ENABLED=true
DASHBOARD_AUTH_PASSWORD=your_secure_password
```

### Security Notes

This is **simple** authentication for localhost/LAN use:
- Password stored in config (use SecretStr)
- Session token in memory
- HTTPS recommended for remote access (not implemented here)

For production use, consider:
- Proper password hashing
- Database-backed sessions
- HTTPS/TLS termination
- Rate limiting on login attempts

### Project Structure Notes

- Creates: `dashboard/auth.py`
- Modifies: `dashboard/config.py`
- Modifies: `dashboard/main.py`

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-103-implement-simple-authentication)
- [NiceGUI Storage](https://nicegui.io/documentation#storage)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Added auth_enabled, auth_password (SecretStr), auth_session_hours to config.py
- Created auth.py module with:
  - check_auth() - validates session token
  - create_session() - generates secure token with expiry
  - verify_password() - compares against config
  - create_login_page() - NiceGUI login UI
  - logout() - clears session
  - cleanup_expired_sessions() - memory cleanup
- In-memory session storage with configurable expiry (default 24h)
- Login page: centered card with password input, toggle visibility, error message
- Route protection: /login redirects to / if already authenticated
- Dashboard redirect to /login if not authenticated when auth enabled
- Auth disabled by default (config.auth_enabled=False)
- storage_secret added to ui.run() for user storage support
- Enter key submits login form
- CSS styling for login page with dark theme

### File List

- dashboard/config.py (modified)
- dashboard/auth.py (created)
- dashboard/main.py (modified)
- dashboard/assets/css/theme.css (modified)

