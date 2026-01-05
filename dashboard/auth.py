"""CryptoTrader Dashboard - Simple Authentication.

Provides optional password protection for dashboard access.
This is simple authentication for localhost/LAN use.

Story 10.3: Simple Authentication
- AC1: Simple password prompt appears on page load (when enabled)
- AC2: Successful authentication grants access to dashboard
- AC3: Session persists across page refreshes (cookie/token)
- AC4: Failed attempts show error message
- AC5: Authentication can be disabled for localhost-only use

Security Note:
This is SIMPLE authentication for local/LAN use only.
For production remote access, consider:
- HTTPS/TLS termination
- Proper password hashing
- Rate limiting on login attempts
- Database-backed sessions
"""

import secrets
from datetime import datetime, timedelta, timezone

from nicegui import app, ui

from dashboard.config import config

# In-memory session storage (simple implementation)
# Key: session token, Value: expiry datetime
_sessions: dict[str, datetime] = {}


def is_auth_enabled() -> bool:
    """Check if authentication is enabled.

    Returns:
        True if auth is enabled and password is configured.
    """
    return config.auth_enabled and bool(config.auth_password.get_secret_value())


def check_auth() -> bool:
    """Check if current request is authenticated.

    Returns:
        True if authentication not required or user is authenticated.
    """
    if not is_auth_enabled():
        return True

    # Check for session token in user storage
    session_token = app.storage.user.get("session_token")
    if not session_token:
        return False

    # Validate session token
    expiry = _sessions.get(session_token)
    if not expiry:
        return False

    if datetime.now(timezone.utc) > expiry:
        # Session expired, clean up
        _sessions.pop(session_token, None)
        app.storage.user.pop("session_token", None)
        return False

    return True


def create_session() -> str:
    """Create new session token after successful authentication.

    Returns:
        Session token string stored in browser.
    """
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(hours=config.auth_session_hours)
    _sessions[token] = expiry
    return token


def verify_password(password: str) -> bool:
    """Verify password against configured value.

    Args:
        password: User-provided password.

    Returns:
        True if password matches.
    """
    return password == config.auth_password.get_secret_value()


def logout() -> None:
    """Clear current session."""
    session_token = app.storage.user.get("session_token")
    if session_token:
        _sessions.pop(session_token, None)
        app.storage.user.pop("session_token", None)


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from memory."""
    now = datetime.now(timezone.utc)
    expired = [token for token, expiry in _sessions.items() if now > expiry]
    for token in expired:
        _sessions.pop(token, None)


def create_login_page() -> None:
    """Create the login page UI.

    Displays a centered login card with password input and submit button.
    Shows error message on failed login attempts.
    """
    with ui.card().classes("login-card"):
        # Header
        ui.label("CryptoTrader Dashboard").classes("login-title")
        ui.label("Enter password to continue").classes("login-subtitle")

        # Password input
        password_input = ui.input(
            label="Password",
            password=True,
            password_toggle_button=True,
        ).classes("login-input")

        # Error message (hidden by default)
        error_label = ui.label("").classes("login-error")

        # Login button
        async def handle_login() -> None:
            if verify_password(password_input.value):
                # Create session and store token
                token = create_session()
                app.storage.user["session_token"] = token
                # Redirect to dashboard
                ui.navigate.to("/")
            else:
                error_label.text = "Invalid password"
                error_label.classes(add="visible")
                # Clear password field
                password_input.value = ""

        ui.button("Login", on_click=handle_login).classes("login-button")

        # Enter key handling
        password_input.on("keydown.enter", handle_login)
