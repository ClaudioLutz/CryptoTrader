"""Page object model for the main dashboard page.

This module provides a high-level API for interacting with dashboard elements.
Using page objects improves test maintainability and readability.
"""

from playwright.sync_api import Page, expect


class DashboardPage:
    """Page object for CryptoTrader Dashboard.

    Encapsulates dashboard interactions for E2E tests.

    Usage:
        dashboard = DashboardPage(page)
        dashboard.goto()
        assert dashboard.is_loaded()
        dashboard.select_tab("Trade History")
    """

    def __init__(self, page: Page, base_url: str = "http://localhost:8081") -> None:
        """Initialize dashboard page object.

        Args:
            page: Playwright page instance.
            base_url: Dashboard base URL.
        """
        self.page = page
        self.base_url = base_url

        # Header elements (Epic 3) - NiceGUI creates <header> element
        self.header = page.locator("header")
        self.status_indicator = page.locator(".status-indicator")
        self.total_pnl = page.locator(".pnl-display")
        self.last_updated = page.locator(".timestamp-display, .timestamp-stale")

        # Tab navigation (Story 9.1, 10.2) - Use .q-tab__label for specific labels
        self.tabs = page.locator(".dashboard-tabs")
        self.dashboard_tab = page.locator(".q-tab__label").filter(has_text="Dashboard")
        self.history_tab = page.locator(".q-tab__label").filter(has_text="Trade History")
        self.config_tab = page.locator(".q-tab__label").filter(has_text="Configuration")

        # Pairs table (Epic 4) - use specific container with .first
        self.pairs_table = page.locator(".pairs-table-container").first

        # Price chart (Epic 5)
        self.chart_container = page.locator(".chart-container")
        self.chart_title = page.locator(".chart-title")
        self.grid_toggle = page.locator(".grid-toggle")
        self.chart_mode_toggle = page.locator(".chart-mode-toggle")

        # Trade history (Epic 9) - Use specific selector with .first for strict mode
        self.trade_history = page.locator(".trade-history-view").first
        self.filter_controls = page.locator(".history-filters")

        # Configuration (Story 10.2) - use .first to avoid strict mode
        self.config_view = page.locator(".config-view").first
        self.config_sections = page.locator(".section-header")

    def goto(self) -> None:
        """Navigate to dashboard."""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")

    def is_loaded(self) -> bool:
        """Check if dashboard is fully loaded.

        Returns:
            True if main dashboard elements are visible.
        """
        try:
            self.header.wait_for(timeout=10000)
            return self.header.is_visible()
        except Exception:
            return False

    def wait_for_data(self, timeout: int = 15000) -> None:
        """Wait for dashboard data to load.

        Waits for the pairs table to show data rows.

        Args:
            timeout: Maximum wait time in milliseconds.
        """
        self.page.wait_for_selector(".pair-row", timeout=timeout)

    def get_status(self) -> str:
        """Get current dashboard status (GREEN/AMBER/RED).

        Returns:
            Status text from RAG indicator.
        """
        return self.status_indicator.inner_text()

    def get_total_pnl(self) -> str:
        """Get total P&L value from header.

        Returns:
            P&L value text (e.g., "+$1,234.56").
        """
        return self.total_pnl.inner_text()

    def select_tab(self, tab_name: str) -> None:
        """Select a dashboard tab.

        Args:
            tab_name: Tab name ("Dashboard", "Trade History", "Configuration").
        """
        # Use the tab label div with filter to avoid matching icon text
        self.page.locator(".q-tab__label").filter(has_text=tab_name).click()
        self.page.wait_for_load_state("networkidle")

    def is_tab_active(self, tab_name: str) -> bool:
        """Check if a tab is currently active.

        Args:
            tab_name: Tab name to check.

        Returns:
            True if tab is active.
        """
        tab = self.page.locator(f"text={tab_name}")
        return "q-tab--active" in (tab.get_attribute("class") or "")

    # Pairs Table Methods (Epic 4)

    def get_pair_count(self) -> int:
        """Get number of trading pairs in table.

        Returns:
            Count of pair rows.
        """
        return self.page.locator(".pair-row").count()

    def get_pair_symbols(self) -> list[str]:
        """Get list of trading pair symbols.

        Returns:
            List of symbol strings (e.g., ["BTC/USDT", "ETH/USDT"]).
        """
        symbols = self.page.locator(".pair-symbol").all_inner_texts()
        return symbols

    def expand_pair_row(self, symbol: str) -> None:
        """Expand a pair row to show details (Story 7.1).

        Args:
            symbol: Trading pair symbol.
        """
        row = self.page.locator(f".pair-row:has-text('{symbol}')")
        expand_btn = row.locator(".expand-btn")
        if expand_btn.is_visible():
            expand_btn.click()

    # Chart Methods (Epic 5, 8, 10.1)

    def toggle_grid_overlay(self) -> None:
        """Toggle grid visualization overlay (Story 10.1)."""
        self.grid_toggle.click()

    def switch_chart_mode(self, mode: str) -> None:
        """Switch chart between line and candlestick (Story 8.3).

        Args:
            mode: "Line" or "Candles".
        """
        self.chart_mode_toggle.locator(f"text={mode}").click()

    def is_chart_visible(self) -> bool:
        """Check if price chart is visible.

        Returns:
            True if chart container is visible.
        """
        return self.chart_container.is_visible()

    # Trade History Methods (Epic 9)

    def filter_trades_by_pair(self, symbol: str) -> None:
        """Filter trade history by pair (Story 9.3).

        Args:
            symbol: Trading pair symbol to filter by.
        """
        self.select_tab("Trade History")
        pair_filter = self.page.locator(".pair-filter")
        pair_filter.select_option(label=symbol)

    def get_trade_history_count(self) -> int:
        """Get number of trades in history table.

        Returns:
            Count of trade rows.
        """
        return self.page.locator(".trade-row").count()

    # Configuration Methods (Story 10.2)

    def is_config_readonly(self) -> bool:
        """Check if configuration view is read-only.

        Returns:
            True if read-only badge is visible.
        """
        self.select_tab("Configuration")
        return self.page.locator(".read-only-badge").is_visible()

    def get_config_sections(self) -> list[str]:
        """Get configuration section headers.

        Returns:
            List of section header texts.
        """
        self.select_tab("Configuration")
        return self.page.locator(".section-header").all_inner_texts()
