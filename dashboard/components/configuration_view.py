"""CryptoTrader Dashboard - Configuration View Component.

Displays bot configuration settings in a read-only view.

Story 10.2: Configuration View
- AC1: Display key settings: trading pairs, grid spacing, order sizes, risk parameters
- AC2: All settings are read-only (no edit capability)
- AC3: Values are formatted for readability
- AC4: View is accessed via a tab
"""

from nicegui import ui

from dashboard.services.data_models import BotConfig, PairConfig
from dashboard.state import state


def create_configuration_view() -> None:
    """Create the configuration view tab content.

    Displays bot configuration in a read-only format with clear sections
    for general settings, trading pairs, and risk management.
    """
    with ui.column().classes("config-view gap-4 w-full"):
        # Header with read-only indicator
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.icon("settings", size="24px").classes("text-secondary")
            ui.label("Bot Configuration").classes("text-h6 text-primary")
            ui.badge("Read-only").classes("read-only-badge")

        config = state.bot_config

        if config is None:
            _create_no_config_message()
            return

        # General section
        _create_general_section(config)

        # Trading pairs section
        _create_pairs_section(config)

        # Risk management section
        _create_risk_section(config)

        # Timing section
        _create_timing_section(config)


def _create_no_config_message() -> None:
    """Display message when configuration is not available."""
    with ui.card().classes("config-section"):
        with ui.column().classes("items-center gap-2 p-8"):
            ui.icon("warning", size="48px").classes("text-warning")
            ui.label("Configuration not available").classes("text-h6 text-primary")
            ui.label(
                "Connect to the trading bot to view configuration."
            ).classes("text-secondary")


def _create_general_section(config: BotConfig) -> None:
    """Create general configuration section.

    Args:
        config: Bot configuration data.
    """
    with ui.card().classes("config-section"):
        ui.label("General").classes("section-header")
        with ui.column().classes("config-items"):
            _config_item("Bot Name", config.bot_name)
            _config_item("Version", config.version)
            _config_item("Exchange", config.exchange)


def _create_pairs_section(config: BotConfig) -> None:
    """Create trading pairs configuration section.

    Args:
        config: Bot configuration data.
    """
    with ui.card().classes("config-section"):
        ui.label("Trading Pairs").classes("section-header")

        if not config.pairs:
            ui.label("No trading pairs configured").classes("text-tertiary")
            return

        for pair in config.pairs:
            _create_pair_card(pair)


def _create_pair_card(pair: PairConfig) -> None:
    """Create configuration card for a trading pair.

    Args:
        pair: Pair configuration data.
    """
    with ui.card().classes("pair-config-card"):
        # Header with symbol and status
        with ui.row().classes("justify-between items-center w-full"):
            ui.label(pair.symbol).classes("pair-symbol text-primary")
            status = "Enabled" if pair.enabled else "Disabled"
            status_class = "status-enabled" if pair.enabled else "status-disabled"
            ui.badge(status).classes(status_class)

        # Grid of settings
        with ui.row().classes("pair-settings gap-8 mt-2"):
            with ui.column().classes("gap-1"):
                _config_item("Grid Levels", str(pair.grid_levels))
                _config_item("Grid Spacing", f"{pair.grid_spacing_pct}%")

            with ui.column().classes("gap-1"):
                _config_item("Order Size", str(pair.order_size))
                _config_item("Max Position", str(pair.max_position))


def _create_risk_section(config: BotConfig) -> None:
    """Create risk management configuration section.

    Args:
        config: Bot configuration data.
    """
    with ui.card().classes("config-section"):
        ui.label("Risk Management").classes("section-header")
        with ui.column().classes("config-items"):
            _config_item("Max Open Orders", str(config.risk.max_open_orders))
            _config_item(
                "Max Daily Loss",
                f"${config.risk.max_daily_loss:,.2f}",
            )
            _config_item(
                "Stop Loss",
                f"{config.risk.stop_loss_pct}%" if config.risk.stop_loss_pct else "Disabled",
            )
            _config_item(
                "Take Profit",
                f"{config.risk.take_profit_pct}%" if config.risk.take_profit_pct else "Disabled",
            )


def _create_timing_section(config: BotConfig) -> None:
    """Create timing configuration section.

    Args:
        config: Bot configuration data.
    """
    with ui.card().classes("config-section"):
        ui.label("Timing").classes("section-header")
        with ui.column().classes("config-items"):
            _config_item("API Timeout", f"{config.api_timeout_ms} ms")
            _config_item("Poll Interval", f"{config.poll_interval_ms} ms")


def _config_item(label: str, value: str) -> None:
    """Create a single configuration item row.

    Args:
        label: Setting name/label.
        value: Setting value (formatted string).
    """
    with ui.row().classes("config-item"):
        ui.label(label).classes("config-label")
        ui.label(value).classes("config-value")
