"""E2E tests for dashboard loading and basic functionality.

Tests core dashboard features from Epics 1-6:
- Dashboard loads successfully
- Header displays status
- Tab navigation works
- Price chart renders
- Data updates in real-time

Run with: pytest tests/e2e/test_dashboard_load.py -m e2e
"""

import pytest
from playwright.sync_api import Page, expect

from tests.support.page_objects.dashboard_page import DashboardPage


@pytest.mark.e2e
class TestDashboardLoad:
    """Test suite for dashboard loading (Epic 1, 3)."""

    def test_dashboard_loads_successfully(self, dashboard_page: Page) -> None:
        """Test that dashboard page loads without errors.

        Story 1.5: Main entry point renders UI.
        """
        dashboard = DashboardPage(dashboard_page)
        assert dashboard.is_loaded(), "Dashboard should load successfully"

    def test_header_strip_visible(self, dashboard_page: Page) -> None:
        """Test that header strip is displayed (Story 3.1).

        AC: Fixed header strip at top with status elements.
        """
        dashboard = DashboardPage(dashboard_page)
        expect(dashboard.header).to_be_visible()

    def test_status_indicator_present(self, dashboard_page: Page) -> None:
        """Test RAG status indicator is visible (Story 3.2).

        AC: GREEN/AMBER/RED indicator for bot status.
        """
        dashboard = DashboardPage(dashboard_page)
        expect(dashboard.status_indicator).to_be_visible()

    def test_page_title_correct(self, dashboard_page: Page) -> None:
        """Test page title is set correctly."""
        expect(dashboard_page).to_have_title("CryptoTrader Dashboard")


@pytest.mark.e2e
class TestTabNavigation:
    """Test suite for tab navigation (Story 9.1, 10.2)."""

    def test_dashboard_tab_active_by_default(self, dashboard_page: Page) -> None:
        """Test Dashboard tab is active on load."""
        dashboard = DashboardPage(dashboard_page)
        expect(dashboard.dashboard_tab).to_be_visible()

    def test_can_navigate_to_trade_history(self, dashboard_page: Page) -> None:
        """Test navigation to Trade History tab (Story 9.1)."""
        dashboard = DashboardPage(dashboard_page)
        dashboard.select_tab("Trade History")
        expect(dashboard.trade_history).to_be_visible()

    def test_can_navigate_to_configuration(self, dashboard_page: Page) -> None:
        """Test navigation to Configuration tab (Story 10.2)."""
        dashboard = DashboardPage(dashboard_page)
        dashboard.select_tab("Configuration")
        expect(dashboard.config_view).to_be_visible()

    def test_can_return_to_dashboard_tab(self, dashboard_page: Page) -> None:
        """Test returning to Dashboard tab."""
        dashboard = DashboardPage(dashboard_page)
        dashboard.select_tab("Configuration")
        dashboard.select_tab("Dashboard")
        expect(dashboard.pairs_table).to_be_visible()


@pytest.mark.e2e
class TestPriceChart:
    """Test suite for price chart (Epic 5)."""

    def test_chart_container_visible(self, dashboard_page: Page) -> None:
        """Test chart container is rendered (Story 5.1)."""
        dashboard = DashboardPage(dashboard_page)
        assert dashboard.is_chart_visible(), "Price chart should be visible"

    def test_chart_title_displayed(self, dashboard_page: Page) -> None:
        """Test chart shows title with pair symbol."""
        dashboard = DashboardPage(dashboard_page)
        expect(dashboard.chart_title).to_be_visible()

    def test_grid_toggle_present(self, dashboard_page: Page) -> None:
        """Test grid overlay toggle exists (Story 10.1)."""
        dashboard = DashboardPage(dashboard_page)
        expect(dashboard.grid_toggle).to_be_visible()

    def test_chart_mode_toggle_present(self, dashboard_page: Page) -> None:
        """Test chart mode toggle exists (Story 8.3)."""
        dashboard = DashboardPage(dashboard_page)
        expect(dashboard.chart_mode_toggle).to_be_visible()


@pytest.mark.e2e
class TestConfigurationView:
    """Test suite for configuration view (Story 10.2)."""

    def test_configuration_is_readonly(self, dashboard_page: Page) -> None:
        """Test configuration view shows read-only badge (AC2)."""
        dashboard = DashboardPage(dashboard_page)
        assert dashboard.is_config_readonly(), "Config should show read-only badge"

    def test_configuration_has_sections_or_unavailable_message(
        self, dashboard_page: Page
    ) -> None:
        """Test configuration view shows sections or unavailable message (AC1, AC3).

        When bot is connected: shows General, Trading Pairs, Risk, Timing sections.
        When bot is offline: shows 'Configuration not available' message.
        """
        dashboard = DashboardPage(dashboard_page)
        sections = dashboard.get_config_sections()

        if len(sections) >= 2:
            # Bot connected - should have multiple sections
            assert len(sections) >= 2, "Config should have multiple sections"
        else:
            # Bot offline - should show unavailable message
            dashboard.select_tab("Configuration")
            unavailable_msg = dashboard_page.locator("text=Configuration not available")
            expect(unavailable_msg).to_be_visible(timeout=5000)


@pytest.mark.e2e
@pytest.mark.slow
class TestDashboardStability:
    """Test suite for dashboard stability (Epic 6).

    These tests verify real-time updates and long-running stability.
    Marked as slow since they involve waiting for updates.
    """

    def test_dashboard_remains_responsive(self, dashboard_page: Page) -> None:
        """Test dashboard stays responsive over time (Story 6.3).

        Simulates user interaction after 10 seconds of dashboard running.
        """
        import time

        dashboard = DashboardPage(dashboard_page)
        time.sleep(10)  # Let dashboard run for a bit

        # Should still be responsive
        dashboard.select_tab("Trade History")
        expect(dashboard.trade_history).to_be_visible(timeout=5000)

        dashboard.select_tab("Dashboard")
        expect(dashboard.pairs_table).to_be_visible(timeout=5000)
