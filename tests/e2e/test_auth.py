"""E2E tests for authentication (Story 10.3).

Tests authentication flows:
- Password prompt appears when auth enabled
- Successful login grants access
- Session persists across refreshes
- Failed attempts show error
- Auth can be disabled

Run with: pytest tests/e2e/test_auth.py -m e2e
"""

import pytest
from playwright.sync_api import Page, expect

from tests.support.page_objects.login_page import LoginPage


@pytest.mark.e2e
class TestAuthenticationEnabled:
    """Test suite for authentication when enabled (Story 10.3).

    These tests use a separate dashboard instance with auth enabled.
    """

    @pytest.fixture(autouse=True)
    def setup(self, dashboard_with_auth, auth_dashboard_url: str) -> None:
        """Ensure auth-enabled dashboard is running."""
        self.auth_url = auth_dashboard_url

    def test_redirects_to_login_when_not_authenticated(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test AC1: Password prompt appears on page load (when enabled).

        When accessing dashboard without authentication,
        user should be redirected to login page.
        """
        login = LoginPage(page, auth_dashboard_url)
        login.goto_dashboard()  # Try to access dashboard

        # Should be redirected to login
        assert login.is_loaded(), "Should redirect to login page"
        expect(page).to_have_url(f"{auth_dashboard_url}/login")

    def test_login_page_displays_correctly(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test login page UI elements are present (AC1)."""
        login = LoginPage(page, auth_dashboard_url)
        login.goto()

        expect(login.login_card).to_be_visible()
        expect(login.title).to_be_visible()
        expect(login.title).to_have_text("CryptoTrader Dashboard")
        expect(login.password_input).to_be_visible()
        expect(login.submit_button).to_be_visible()

    def test_successful_login_grants_access(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test AC2: Successful authentication grants access to dashboard.

        Using correct password should redirect to dashboard.
        """
        login = LoginPage(page, auth_dashboard_url)
        login.goto()
        login.login("test_password_123")  # Password from conftest fixture

        # Should be redirected to dashboard
        assert login.is_redirected_to_dashboard(), "Should redirect to dashboard after login"
        # Verify dashboard content is visible (not login)
        expect(page.locator("header")).to_be_visible(timeout=10000)

    def test_failed_login_shows_error(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test AC4: Failed attempts show error message.

        Using wrong password should display error and stay on login page.
        """
        login = LoginPage(page, auth_dashboard_url)
        login.goto()
        login.login("wrong_password")

        # Should show error
        assert login.is_error_visible(), "Should display error message"
        # Should still be on login page
        expect(page).to_have_url(f"{auth_dashboard_url}/login")

    def test_session_persists_across_refresh(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test AC3: Session persists across page refreshes.

        After successful login, refreshing should keep user authenticated.
        """
        login = LoginPage(page, auth_dashboard_url)
        login.goto()
        login.login("test_password_123")

        # Verify logged in
        expect(page.locator("header")).to_be_visible(timeout=10000)

        # Refresh page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Should still be on dashboard (not redirected to login)
        assert "/login" not in page.url, "Should remain authenticated after refresh"
        expect(page.locator("header")).to_be_visible(timeout=10000)

    def test_enter_key_submits_login(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test Enter key submits login form."""
        login = LoginPage(page, auth_dashboard_url)
        login.goto()
        login.enter_password("test_password_123")
        login.submit_with_enter()

        # Should login successfully
        assert login.is_redirected_to_dashboard(), "Enter key should submit form"

    def test_password_visibility_toggle(
        self, page: Page, auth_dashboard_url: str
    ) -> None:
        """Test password visibility can be toggled."""
        login = LoginPage(page, auth_dashboard_url)
        login.goto()
        login.enter_password("test_password")

        # Initially hidden
        assert not login.is_password_visible(), "Password should be hidden initially"

        # Toggle visibility
        login.toggle_password_visibility()
        assert login.is_password_visible(), "Password should be visible after toggle"


@pytest.mark.e2e
class TestAuthenticationDisabled:
    """Test suite for authentication when disabled (Story 10.3 AC5).

    These tests use the default dashboard instance with auth disabled.
    """

    def test_direct_access_to_dashboard(self, dashboard_page: Page) -> None:
        """Test AC5: Auth can be disabled for localhost-only use.

        When auth is disabled, dashboard should be directly accessible.
        """
        # dashboard_page fixture already navigated to dashboard
        # Should not be on login page
        assert "/login" not in dashboard_page.url, "Should not redirect to login"
        expect(dashboard_page.locator("header")).to_be_visible()

    def test_login_route_redirects_to_dashboard(
        self, page: Page, dashboard_url: str
    ) -> None:
        """Test login page redirects to dashboard when auth disabled."""
        page.goto(f"{dashboard_url}/login")
        page.wait_for_load_state("networkidle")

        # Should redirect to main dashboard
        assert "/login" not in page.url, "Should redirect away from login"


@pytest.mark.e2e
class TestSecurityBehavior:
    """Security-related authentication tests."""

    def test_multiple_failed_attempts(
        self, page: Page, auth_dashboard_url: str, dashboard_with_auth
    ) -> None:
        """Test behavior after multiple failed login attempts.

        Note: Current implementation doesn't rate limit, but test documents behavior.
        """
        login = LoginPage(page, auth_dashboard_url)
        login.goto()

        # Try multiple wrong passwords
        for _ in range(3):
            login.login("wrong")
            page.wait_for_timeout(500)

        # Should still show error (not lock out in current simple implementation)
        assert login.is_error_visible()

        # Should still allow correct password
        login.enter_password("test_password_123")
        login.submit()
        assert login.is_redirected_to_dashboard()
