"""Page object model for the login page (Story 10.3).

This module provides a high-level API for testing authentication flows.
"""

from playwright.sync_api import Page, expect


class LoginPage:
    """Page object for dashboard login page.

    Tests authentication functionality from Story 10.3.

    Usage:
        login = LoginPage(page)
        login.goto()
        login.enter_password("secret")
        login.submit()
        assert login.is_error_visible() == False
    """

    def __init__(self, page: Page, base_url: str = "http://localhost:8083") -> None:
        """Initialize login page object.

        Args:
            page: Playwright page instance.
            base_url: Dashboard base URL (with auth enabled).
        """
        self.page = page
        self.base_url = base_url

        # Login form elements
        self.login_card = page.locator(".login-card")
        self.title = page.locator(".login-title")
        self.subtitle = page.locator(".login-subtitle")
        self.password_input = page.locator(".login-input input")
        self.submit_button = page.locator(".login-button")
        self.error_message = page.locator(".login-error")
        self.password_toggle = page.locator("[aria-label='Toggle password visibility']")

    def goto(self) -> None:
        """Navigate to login page."""
        self.page.goto(f"{self.base_url}/login")
        self.page.wait_for_load_state("networkidle")

    def goto_dashboard(self) -> None:
        """Navigate to dashboard (should redirect to login if auth required)."""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        """Check if login page is displayed.

        Returns:
            True if login card is visible.
        """
        try:
            self.login_card.wait_for(timeout=5000)
            return self.login_card.is_visible()
        except Exception:
            return False

    def enter_password(self, password: str) -> None:
        """Enter password into input field.

        Args:
            password: Password to enter.
        """
        self.password_input.fill(password)

    def submit(self) -> None:
        """Click the login button."""
        self.submit_button.click()

    def submit_with_enter(self) -> None:
        """Submit form by pressing Enter key."""
        self.password_input.press("Enter")

    def is_error_visible(self) -> bool:
        """Check if error message is visible.

        Returns:
            True if error is displayed.
        """
        # Check for 'visible' class on error element
        error_class = self.error_message.get_attribute("class") or ""
        return "visible" in error_class

    def get_error_text(self) -> str:
        """Get error message text.

        Returns:
            Error message string.
        """
        return self.error_message.inner_text()

    def toggle_password_visibility(self) -> None:
        """Toggle password visibility (show/hide)."""
        self.password_toggle.click()

    def is_password_visible(self) -> bool:
        """Check if password is shown in plain text.

        Returns:
            True if password input type is 'text'.
        """
        input_type = self.password_input.get_attribute("type")
        return input_type == "text"

    def login(self, password: str) -> None:
        """Perform complete login flow.

        Args:
            password: Password to use for login.
        """
        self.enter_password(password)
        self.submit()
        # Wait for navigation or error
        self.page.wait_for_load_state("networkidle")

    def is_redirected_to_dashboard(self) -> bool:
        """Check if successfully redirected to dashboard after login.

        Returns:
            True if current URL is dashboard (not login).
        """
        return "/login" not in self.page.url

    def assert_login_success(self) -> None:
        """Assert that login was successful.

        Raises:
            AssertionError: If still on login page or error visible.
        """
        expect(self.page).not_to_have_url(f"{self.base_url}/login")
        expect(self.error_message).not_to_have_class("visible")

    def assert_login_failure(self) -> None:
        """Assert that login failed.

        Raises:
            AssertionError: If error is not visible.
        """
        expect(self.error_message).to_have_class("login-error visible")
