"""CryptoTrader Dashboard - Main Entry Point.

BTC 1h Prediction-Strategie Dashboard.
Tabs: BTC Prediction | Trade History | Performance

Run with: python -m dashboard.main
"""

import logging
from pathlib import Path

from nicegui import ui

from dashboard.auth import check_auth, create_login_page, is_auth_enabled
from dashboard.components.header import create_header
from dashboard.components.performance_view import create_performance_view
from dashboard.components.predictions_view import create_predictions_view
from dashboard.components.trade_history import create_trade_history_view
from dashboard.config import config
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
    """Set up timer-based polling for data refresh with WebSocket integration.

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

    # Initial prediction data load
    await state.refresh_prediction_data()
    logger.info("Prediction data initialized")

    # Start WebSocket service
    ws_service = BinanceWebSocketService(state)
    try:
        await ws_service.start()
        state._websocket_service = ws_service
        state.set_websocket_connected(True)
        logger.info("WebSocket streams started successfully")
    except Exception as e:
        logger.warning("WebSocket failed, using REST fallback: %s", str(e))
        state.set_websocket_connected(False)

    # REST polling as fallback
    # Tier 1: Health (always REST) + P&L (from cache)
    ui.timer(
        config.poll_interval_tier1,
        state.refresh_tier1,
    )

    # Tier 2: Pairs table, Chart
    ui.timer(
        config.poll_interval_tier2,
        state.refresh_tier2,
    )

    # Tier 3: Prediction data (every 30s)
    ui.timer(30.0, state.refresh_prediction_data)


async def shutdown_polling() -> None:
    """Clean up resources on dashboard shutdown."""
    if state._websocket_service:
        await state._websocket_service.stop()
        logger.info("WebSocket service stopped")

    await state.shutdown()
    logger.info("Dashboard state shutdown complete")


def create_ui() -> None:
    """Create the dashboard UI components.

    Structure:
    1. Header strip (fixed at top)
    2. Tab navigation: BTC Prediction | Trade History | Performance
    """
    # Enable dark mode
    ui.dark_mode(True)

    # Load custom theme CSS
    load_theme()

    # Create fixed header strip
    create_header()

    # Tab navigation
    with ui.tabs().classes("dashboard-tabs w-full") as tabs:
        predictions_tab = ui.tab("BTC Prediction", icon="psychology")
        history_tab = ui.tab("Trade History", icon="history")
        performance_tab = ui.tab("Performance", icon="trending_up")

    with ui.tab_panels(tabs, value=predictions_tab).classes("tab-panels w-full"):
        # BTC Prediction tab (main view)
        with ui.tab_panel(predictions_tab).classes("predictions-panel"):
            create_predictions_view()

        # Trade History tab
        with ui.tab_panel(history_tab).classes("history-panel"):
            create_trade_history_view()

        # Performance tab
        with ui.tab_panel(performance_tab).classes("performance-panel"):
            create_performance_view()

    # Set up polling timers after UI is created
    ui.timer(0.1, setup_polling, once=True)


@ui.page("/")
def index_page() -> None:
    """Main dashboard page route with authentication check."""
    if not check_auth():
        ui.navigate.to("/login")
        return

    create_ui()


@ui.page("/login")
def login_page() -> None:
    """Login page route."""
    if check_auth():
        ui.navigate.to("/")
        return

    if not is_auth_enabled():
        ui.navigate.to("/")
        return

    ui.dark_mode(True)
    load_theme()
    create_login_page()


def main() -> None:
    """Main entry point for the dashboard."""
    logger.info("Starting CryptoTrader Dashboard on port %d", config.dashboard_port)

    if is_auth_enabled():
        logger.info("Authentication enabled")

    ui.run(
        port=config.dashboard_port,
        title="CryptoTrader - BTC Prediction",
        dark=True,
        reload=False,
        storage_secret="cryptotrader_dashboard_secret",
    )


if __name__ == "__main__":
    main()
