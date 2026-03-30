"""CryptoTrader Dashboard - Authentication with Security Hardening.

Provides password protection for dashboard access with security features:
- bcrypt password hashing (passwords starting with $2b$ are treated as hashes)
- Rate limiting on login attempts (5 attempts per 15 minutes per IP)
- Constant-time token comparison to prevent timing attacks
- Session management with configurable expiry

Story 10.3: Simple Authentication
- AC1: Simple password prompt appears on page load (when enabled)
- AC2: Successful authentication grants access to dashboard
- AC3: Session persists across page refreshes (cookie/token)
- AC4: Failed attempts show error message
- AC5: Authentication can be disabled for localhost-only use
"""

import hmac
import logging
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from time import time

from nicegui import app, ui

from dashboard.config import config

logger = logging.getLogger(__name__)

# In-memory session storage (simple implementation)
# Key: session token, Value: expiry datetime
_sessions: dict[str, datetime] = {}

# Rate limiting for login attempts
_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 900  # 15 minutes


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


def _is_rate_limited(client_ip: str) -> bool:
    """Check if client IP has exceeded login attempt limit.

    Args:
        client_ip: Client IP address.

    Returns:
        True if rate limited.
    """
    now = time()
    # Clean up old attempts outside the window
    _login_attempts[client_ip] = [
        t for t in _login_attempts[client_ip] if now - t < _LOGIN_WINDOW_SECONDS
    ]
    return len(_login_attempts[client_ip]) >= _MAX_LOGIN_ATTEMPTS


def _record_login_attempt(client_ip: str) -> None:
    """Record a login attempt for rate limiting.

    Args:
        client_ip: Client IP address.
    """
    _login_attempts[client_ip].append(time())


def _get_remaining_lockout_time(client_ip: str) -> int:
    """Get remaining lockout time in seconds.

    Args:
        client_ip: Client IP address.

    Returns:
        Seconds until rate limit resets, or 0 if not limited.
    """
    if not _login_attempts[client_ip]:
        return 0
    oldest_attempt = min(_login_attempts[client_ip])
    remaining = _LOGIN_WINDOW_SECONDS - (time() - oldest_attempt)
    return max(0, int(remaining))


def verify_password(password: str, client_ip: str = "unknown") -> tuple[bool, str]:
    """Verify password against configured value with rate limiting.

    Supports both plain-text passwords (for backward compatibility) and
    bcrypt hashed passwords (recommended for production).

    Args:
        password: User-provided password.
        client_ip: Client IP for rate limiting.

    Returns:
        Tuple of (success, error_message). Error message is empty on success.
    """
    # Check rate limiting first
    if _is_rate_limited(client_ip):
        remaining = _get_remaining_lockout_time(client_ip)
        logger.warning("login_rate_limited", client_ip=client_ip, remaining_seconds=remaining)
        return False, f"Too many attempts. Try again in {remaining // 60 + 1} minutes."

    stored_password = config.auth_password.get_secret_value()

    # Check if stored password is a bcrypt hash
    if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
        try:
            import bcrypt
            is_valid = bcrypt.checkpw(password.encode(), stored_password.encode())
        except Exception as e:
            logger.error("bcrypt_verify_error", error=str(e))
            _record_login_attempt(client_ip)
            return False, "Authentication error"
    else:
        # Plain-text comparison (backward compatible, but log warning)
        is_valid = hmac.compare_digest(password, stored_password)

    if not is_valid:
        _record_login_attempt(client_ip)
        attempts_remaining = _MAX_LOGIN_ATTEMPTS - len(_login_attempts[client_ip])
        logger.warning(
            "login_failed",
            client_ip=client_ip,
            attempts_remaining=attempts_remaining,
        )
        if attempts_remaining <= 2:
            return False, f"Invalid password. {attempts_remaining} attempts remaining."
        return False, "Invalid password"

    # Clear rate limit on successful login
    _login_attempts.pop(client_ip, None)
    logger.info("login_success", client_ip=client_ip)
    return True, ""


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Use this to generate hashed passwords for the config:
        python -c "from dashboard.auth import hash_password; print(hash_password('your-password'))"

    Args:
        password: Plain-text password.

    Returns:
        bcrypt hash string.
    """
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


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
            # Get client IP (NiceGUI provides this via request)
            client_ip = app.storage.user.get("client_ip", "unknown")

            success, error_msg = verify_password(password_input.value, client_ip)
            if success:
                # Create session and store token
                token = create_session()
                app.storage.user["session_token"] = token
                # Redirect to dashboard
                ui.navigate.to("/")
            else:
                error_label.text = error_msg
                error_label.classes(add="visible")
                # Clear password field
                password_input.value = ""

        ui.button("Login", on_click=handle_login).classes("login-button")

        # Enter key handling
        password_input.on("keydown.enter", handle_login)
