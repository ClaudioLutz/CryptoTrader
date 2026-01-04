"""Application entry point with CLI interface and graceful shutdown.

Provides command-line interface for:
- Starting the trading bot
- Configuring dry-run mode
- Setting log verbosity
- Displaying configuration summary
"""

import argparse
import asyncio
import signal
import sys
from decimal import Decimal
from typing import Any, Optional

from crypto_bot import __version__
from crypto_bot.bot import BotBuilder, TradingBot
from crypto_bot.config.logging_config import configure_logging, get_logger
from crypto_bot.config.settings import AppSettings, get_settings
from crypto_bot.data.persistence import Database
from crypto_bot.exchange.binance_adapter import BinanceAdapter
from crypto_bot.strategies.grid_trading import GridConfig, GridTradingStrategy


# =============================================================================
# CLI Argument Parsing
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Crypto Trading Bot - Grid strategy automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  crypto-bot                      # Start with default config
  crypto-bot --dry-run            # Simulate trading without real orders
  crypto-bot --log-level DEBUG    # Enable verbose logging
  crypto-bot -c config.yaml       # Use custom config file

Configuration:
  Settings are loaded from environment variables and .env file.
  See documentation for available configuration options.
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to configuration file (YAML)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in simulation mode without real trades",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging verbosity level",
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Trading pair symbol (e.g., BTC/USDT)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


# =============================================================================
# Startup Banner
# =============================================================================


BANNER = """
================================================================================
   ____                  _          ____        _
  / ___|_ __ _   _ _ __ | |_ ___   | __ )  ___ | |_
 | |   | '__| | | | '_ \\| __/ _ \\  |  _ \\ / _ \\| __|
 | |___| |  | |_| | |_) | || (_) | | |_) | (_) | |_
  \\____|_|   \\__, | .__/ \\__\\___/  |____/ \\___/ \\__|
             |___/|_|
================================================================================
"""


def display_banner(settings: AppSettings, dry_run: bool) -> None:
    """Display startup banner with configuration summary.

    Args:
        settings: Application settings.
        dry_run: Whether dry-run mode is enabled.
    """
    print(BANNER)
    print(f"  Version:   {__version__}")
    print(f"  Exchange:  {settings.exchange.name}")
    print(f"  Testnet:   {settings.exchange.testnet}")
    print(f"  Dry Run:   {dry_run}")
    print(f"  Symbol:    {settings.trading.symbol}")
    print(f"  Log Level: {settings.log_level}")
    print()
    print("=" * 80)
    print()


# =============================================================================
# Graceful Shutdown Handler
# =============================================================================


class GracefulShutdown:
    """Handle graceful shutdown on SIGINT/SIGTERM."""

    def __init__(self) -> None:
        """Initialize shutdown handler."""
        self._shutdown_event = asyncio.Event()
        self._bot: Optional[TradingBot] = None
        self._logger = get_logger("shutdown")

    @property
    def should_shutdown(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()

    def set_bot(self, bot: TradingBot) -> None:
        """Set the bot instance for shutdown."""
        self._bot = bot

    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown is requested."""
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """Signal that shutdown has been requested."""
        self._logger.info("shutdown_requested")
        self._shutdown_event.set()

    async def handle_shutdown(self) -> None:
        """Handle shutdown by stopping the bot."""
        if self._bot:
            await self._bot.stop()


def setup_signal_handlers(shutdown: GracefulShutdown) -> None:
    """Set up signal handlers for graceful shutdown.

    Args:
        shutdown: Shutdown handler instance.
    """
    loop = asyncio.get_running_loop()

    def handle_signal(sig: signal.Signals) -> None:
        shutdown.request_shutdown()
        asyncio.create_task(shutdown.handle_shutdown())

    # Windows doesn't support SIGTERM in the same way
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal, sig)


# =============================================================================
# Strategy Factory
# =============================================================================


def create_grid_strategy(settings: AppSettings) -> GridTradingStrategy:
    """Create a grid trading strategy from settings.

    Creates a default grid configuration based on settings.
    In production, this would load from a config file.

    Args:
        settings: Application settings.

    Returns:
        Configured GridTradingStrategy.
    """
    # Default grid configuration
    # These would typically come from a config file
    config = GridConfig(
        name="grid",
        symbol=settings.trading.symbol,
        lower_price=Decimal("40000"),  # Example: $40,000
        upper_price=Decimal("50000"),  # Example: $50,000
        num_grids=20,
        total_investment=Decimal("1000"),  # Example: $1,000
        dry_run=settings.trading.dry_run,
    )

    return GridTradingStrategy(config)


# =============================================================================
# Main Entry Point
# =============================================================================


async def main() -> int:
    """Main application entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Parse CLI arguments
    args = parse_args()

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    # Override settings from CLI args
    if args.dry_run:
        settings.trading.dry_run = True
    if args.log_level:
        settings.log_level = args.log_level
    if args.symbol:
        settings.trading.symbol = args.symbol

    # Initialize logging
    configure_logging(
        log_level=settings.log_level,
        json_output=settings.json_logs,
    )
    logger = get_logger("main")

    # Display startup banner
    display_banner(settings, settings.trading.dry_run)

    # Set up graceful shutdown
    shutdown = GracefulShutdown()

    try:
        # Set up signal handlers (Unix only)
        if sys.platform != "win32":
            setup_signal_handlers(shutdown)

        # Create components
        exchange = BinanceAdapter(settings.exchange)
        database = Database(settings.database)
        strategy = create_grid_strategy(settings)

        # Build and start bot
        bot = (
            BotBuilder()
            .with_settings(settings)
            .with_exchange(exchange)
            .with_database(database)
            .with_strategy(strategy)
            .build()
        )

        shutdown.set_bot(bot)

        logger.info(
            "bot_initialized",
            strategy=strategy.name,
            symbol=strategy.symbol,
            dry_run=settings.trading.dry_run,
        )

        # Start the bot (runs until shutdown)
        if sys.platform == "win32":
            # On Windows, handle Ctrl+C differently
            try:
                await bot.start()
            except KeyboardInterrupt:
                logger.info("keyboard_interrupt")
                await bot.stop()
        else:
            await bot.start()

        return 0

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        return 0
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        return 1
    finally:
        logger.info("bot_exiting")


def cli() -> None:
    """CLI entry point."""
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
