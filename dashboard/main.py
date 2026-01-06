"""CryptoTrader Dashboard - Main Entry Point.

This module serves as the main entry point for the NiceGUI dashboard.
Run with: python dashboard/main.py or python -m dashboard.main

Epic 6: Implements timer-based polling for real-time updates.
Epic 10: Adds Configuration tab and optional authentication.
"""

import logging
from pathlib import Path

from nicegui import app, ui

from dashboard.auth import check_auth, create_login_page, is_auth_enabled
from dashboard.components.configuration_view import create_configuration_view
from dashboard.components.header import create_header
from dashboard.components.pairs_table import create_pairs_table
from dashboard.components.timeframe_row import create_timeframe_row
from dashboard.components.trade_history import create_trade_history_view
from dashboard.config import config
from dashboard.services.api_client import exchange_breaker
from dashboard.services.websocket_service import BinanceWebSocketService
from dashboard.state import state

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_theme() -> None:
    """Load custom dark theme CSS from assets/css/theme.css."""
    theme_path = Path(__file__).parent / "assets" / "css" / "theme.css"
    if theme_path.exists():
        ui.add_css(theme_path.read_text())
        logger.debug("Theme CSS loaded from %s", theme_path)


async def setup_polling() -> None:
    """Set up timer-based polling for data refresh with WebSocket integration (Phase 1).

    Implements hybrid data flow:
    - WebSocket: Real-time order/balance/ticker updates (primary)
    - REST polling: Health checks + fallback when WebSocket unavailable
    - Trade cache: Initialized BEFORE WebSocket to avoid race condition
    """
    # Initialize state and API client
    await state.initialize()
    logger.info("State initialized, starting polling timers")

    # Initialize trade cache from REST before starting WebSocket
    await state._calculate_pnl_from_trades()
    logger.info(
        "Trade cache initialized with %d trades", len(state._trade_cache)
    )

    # Start WebSocket service (Phase 1 hardening)
    ws_service = BinanceWebSocketService(state)
    try:
        await ws_service.start()
        state._websocket_service = ws_service
        state.set_websocket_connected(True)
        logger.info("WebSocket streams started successfully")
    except Exception as e:
        logger.warning("WebSocket failed, using REST fallback: %s", str(e))
        state.set_websocket_connected(False)

    # REST polling as fallback (existing timers)
    # Tier 1: Health (always REST) + P&L (from cache)
    ui.timer(
        config.poll_interval_tier1,
        state.refresh_tier1,
    )
    logger.debug("Tier 1 polling started (interval: %.1fs)", config.poll_interval_tier1)

    # Tier 2: Pairs table, Chart (skipped when WebSocket connected)
    ui.timer(
        config.poll_interval_tier2,
        state.refresh_tier2,
    )
    logger.debug("Tier 2 polling started (interval: %.1fs)", config.poll_interval_tier2)


async def shutdown_polling() -> None:
    """Clean up resources on dashboard shutdown (Phase 1: WebSocket cleanup)."""
    # Stop WebSocket service if running
    if state._websocket_service:
        await state._websocket_service.stop()
        logger.info("WebSocket service stopped")

    # Shutdown state and API client
    await state.shutdown()
    logger.info("Dashboard state shutdown complete")


def create_ui() -> None:
    """Create the dashboard UI components.

    This function sets up the main dashboard page structure:
    1. Header strip (fixed at top)
    2. Tab navigation (Story 9.1, 10.2)
    3. Dashboard tab: pairs table, chart
    4. Trade History tab: history table with filters
    5. Configuration tab: read-only bot settings (Story 10.2)
    """
    # Enable dark mode
    ui.dark_mode(True)

    # Load custom theme CSS
    load_theme()

    # Create fixed header strip (Epic 3) and store container for UI refresh
    header_container = create_header()

    # Register UI refresh callback for WebSocket updates (Phase 1, Issue #7 fix)
    def refresh_ui() -> None:
        """Refresh UI components when WebSocket pushes updates."""
        # NiceGUI automatically handles refreshes via its internal WebSocket
        # This callback can be used for forced refreshes if needed
        pass

    state.register_ui_refresh(refresh_ui)

    # Tab navigation (Story 9.1, 10.2)
    with ui.tabs().classes("dashboard-tabs w-full") as tabs:
        dashboard_tab = ui.tab("Dashboard", icon="dashboard")
        history_tab = ui.tab("Trade History", icon="history")
        config_tab = ui.tab("Configuration", icon="settings")

    with ui.tab_panels(tabs, value=dashboard_tab).classes("tab-panels w-full"):
        # Dashboard tab content
        with ui.tab_panel(dashboard_tab).classes("dashboard-panel"):
            # Timeframe performance row (Story 8.1)
            create_timeframe_row()

            # Main content area
            with ui.column().classes("w-full p-4"):
                # Pairs table with embedded mini charts (Epic 4, 7)
                # Charts are now inside each pair card for better UX
                create_pairs_table()

        # Trade History tab content (Epic 9)
        with ui.tab_panel(history_tab).classes("history-panel"):
            create_trade_history_view()

        # Configuration tab content (Story 10.2)
        with ui.tab_panel(config_tab).classes("config-panel"):
            create_configuration_view()

    # Set up polling timers after UI is created (Epic 6)
    ui.timer(0.1, setup_polling, once=True)  # Delayed start to ensure UI is ready


@ui.page("/")
def index_page() -> None:
    """Main dashboard page route with authentication check (Story 10.3)."""
    # Check authentication if enabled
    if not check_auth():
        ui.navigate.to("/login")
        return

    create_ui()


@ui.page("/login")
def login_page() -> None:
    """Login page route (Story 10.3)."""
    # If already authenticated, redirect to dashboard
    if check_auth():
        ui.navigate.to("/")
        return

    # If auth not enabled, redirect to dashboard
    if not is_auth_enabled():
        ui.navigate.to("/")
        return

    # Enable dark mode and load theme for login page
    ui.dark_mode(True)
    load_theme()

    # Create login UI
    create_login_page()


def main() -> None:
    """Main entry point for the dashboard.

    Initializes logging, creates UI, and starts the NiceGUI server.
    """
    logger.info("Starting CryptoTrader Dashboard on port %d", config.dashboard_port)

    if is_auth_enabled():
        logger.info("Authentication enabled")

    # Run NiceGUI server with storage secret for sessions
    ui.run(
        port=config.dashboard_port,
        title="CryptoTrader Dashboard",
        dark=True,
        reload=False,  # Disable for production stability
        storage_secret="cryptotrader_dashboard_secret",  # Required for user storage
    )


if __name__ == "__main__":
    main()
