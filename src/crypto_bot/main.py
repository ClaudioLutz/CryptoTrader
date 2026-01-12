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
from crypto_bot.utils.health import HealthCheckServer


# =============================================================================
# Multi-Bot Tracker for Health Server
# =============================================================================


class MultiBotTracker:
    """Tracks multiple bot instances for health server status reporting.

    The HealthCheckServer expects a single bot reference with a `_running`
    attribute. This class wraps multiple bots and reports aggregate status.
    """

    def __init__(self) -> None:
        """Initialize empty bot tracker."""
        self._bots: list[TradingBot] = []

    def add_bot(self, bot: "TradingBot") -> None:
        """Add a bot to be tracked.

        Args:
            bot: TradingBot instance to track.
        """
        self._bots.append(bot)

    @property
    def _running(self) -> bool:
        """Check if any tracked bot is running."""
        return any(getattr(b, "_running", False) for b in self._bots)

    @property
    def _strategy(self) -> Optional[Any]:
        """Return first bot's strategy for status display."""
        for bot in self._bots:
            if hasattr(bot, "_strategy") and bot._strategy:
                return bot._strategy
        return None

    @property
    def _exchange(self) -> Optional[Any]:
        """Return first bot's exchange for status display."""
        for bot in self._bots:
            if hasattr(bot, "_exchange") and bot._exchange:
                return bot._exchange
        return None

    @property
    def _dry_run(self) -> bool:
        """Check if bots are in dry run mode."""
        for bot in self._bots:
            if hasattr(bot, "_settings"):
                return bot._settings.trading.dry_run
        return True

    def get_all_strategies(self) -> list[Any]:
        """Get all strategies from tracked bots."""
        return [b._strategy for b in self._bots if hasattr(b, "_strategy")]


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

    parser.add_argument(
        "--api-port",
        type=int,
        default=8080,
        help="Port for the dashboard API server (default: 8080)",
    )

    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Disable the dashboard API server",
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


def display_banner(settings: AppSettings, dry_run: bool, api_port: int | None = None) -> None:
    """Display startup banner with configuration summary.

    Args:
        settings: Application settings.
        dry_run: Whether dry-run mode is enabled.
        api_port: API server port (None if disabled).
    """
    print(BANNER)
    print(f"  Version:   {__version__}")
    print(f"  Exchange:  {settings.exchange.name}")
    print(f"  Testnet:   {settings.exchange.testnet}")
    print(f"  Dry Run:   {dry_run}")
    print(f"  Symbol:    {settings.trading.symbol}")
    print(f"  Log Level: {settings.log_level}")
    if api_port:
        print(f"  API:       http://localhost:{api_port}")
    else:
        print(f"  API:       Disabled")
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

# Multi-pair grid configurations
# Adjusted for $50 balance - trading only SOL/USDT with $45 investment
GRID_CONFIGS = [
    {
        "symbol": "SOL/USDT",
        "lower_price": Decimal("120"),
        "upper_price": Decimal("150"),
        "num_grids": 6,
        "total_investment": Decimal("45"),
    },
]


def create_grid_strategies(settings: AppSettings) -> list[GridTradingStrategy]:
    """Create grid trading strategies for multiple pairs.

    Args:
        settings: Application settings.

    Returns:
        List of configured GridTradingStrategy instances.
    """
    strategies = []
    for cfg in GRID_CONFIGS:
        config = GridConfig(
            name=f"grid_{cfg['symbol'].replace('/', '_')}",
            symbol=cfg["symbol"],
            lower_price=cfg["lower_price"],
            upper_price=cfg["upper_price"],
            num_grids=cfg["num_grids"],
            total_investment=cfg["total_investment"],
            dry_run=settings.trading.dry_run,
        )
        strategies.append(GridTradingStrategy(config))
    return strategies


def create_grid_strategy(settings: AppSettings) -> GridTradingStrategy:
    """Create a single grid trading strategy (for backward compatibility).

    Args:
        settings: Application settings.

    Returns:
        Configured GridTradingStrategy.
    """
    # Use the first config that matches the symbol, or default to BTC
    for cfg in GRID_CONFIGS:
        if cfg["symbol"] == settings.trading.symbol:
            config = GridConfig(
                name="grid",
                symbol=cfg["symbol"],
                lower_price=cfg["lower_price"],
                upper_price=cfg["upper_price"],
                num_grids=cfg["num_grids"],
                total_investment=cfg["total_investment"],
                dry_run=settings.trading.dry_run,
            )
            return GridTradingStrategy(config)

    # Default fallback
    config = GridConfig(
        name="grid",
        symbol=settings.trading.symbol,
        lower_price=Decimal("88000"),
        upper_price=Decimal("94000"),
        num_grids=10,
        total_investment=Decimal("500"),
        dry_run=settings.trading.dry_run,
    )
    return GridTradingStrategy(config)


# =============================================================================
# Main Entry Point
# =============================================================================


def create_bot(
    settings: AppSettings,
    strategy: GridTradingStrategy,
    exchange: BinanceAdapter,
    database: Database,
) -> TradingBot:
    """Create a single trading bot for one strategy.

    Args:
        settings: Application settings.
        strategy: Trading strategy.
        exchange: Exchange adapter.
        database: Database connection.

    Returns:
        Configured TradingBot instance (not started).
    """
    return (
        BotBuilder()
        .with_settings(settings)
        .with_exchange(exchange)
        .with_database(database)
        .with_strategy(strategy)
        .build()
    )


async def run_bot(bot: TradingBot, logger: Any) -> None:
    """Run a trading bot.

    Args:
        bot: Bot instance to run.
        logger: Logger for status messages.
    """
    logger.info(
        "bot_starting",
        strategy=bot._strategy.name,
        symbol=bot._strategy.symbol,
    )
    await bot.start()


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

    # Initialize logging with file rotation
    configure_logging(
        log_level=settings.log_level,
        json_output=settings.json_logs,
        log_file="logs/crypto_bot.log",
    )
    logger = get_logger("main")

    # Determine API port
    api_port = None if args.no_api else args.api_port

    # Display startup banner
    display_banner(settings, settings.trading.dry_run, api_port)

    health_server: Optional[HealthCheckServer] = None

    try:
        # Create shared components
        exchange = BinanceAdapter(settings.exchange)
        database = Database(settings.database)

        # Check if running single or multi-pair mode
        if args.symbol:
            # Single pair mode (backward compatible)
            settings.trading.symbol = args.symbol
            strategy = create_grid_strategy(settings)
            strategies = [strategy]
        else:
            # Multi-pair mode
            strategies = create_grid_strategies(settings)

        logger.info(
            "starting_multi_pair_bot",
            pairs=[s.symbol for s in strategies],
            dry_run=settings.trading.dry_run,
        )

        # Connect exchange once (shared across all strategies)
        await exchange.connect()
        await database.connect()

        # Create all bots first (before starting them)
        bot_tracker = MultiBotTracker()
        bots: list[TradingBot] = []
        for strategy in strategies:
            bot = create_bot(settings, strategy, exchange, database)
            bots.append(bot)
            bot_tracker.add_bot(bot)
            logger.info(
                "bot_created",
                strategy=strategy.name,
                symbol=strategy.symbol,
                dry_run=settings.trading.dry_run,
            )

        # Start API server for dashboard
        if api_port:
            health_server = HealthCheckServer(host="0.0.0.0", port=api_port)
            health_server.set_database(database)
            health_server.set_bot(bot_tracker)  # Pass tracker for status reporting
            await health_server.start()
            logger.info("api_server_started", port=api_port)

        # Run all bots concurrently
        tasks = []
        for bot in bots:
            task = asyncio.create_task(run_bot(bot, logger))
            tasks.append(task)

        # Wait for all bots (they run forever until interrupted)
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("keyboard_interrupt")
            for task in tasks:
                task.cancel()

        return 0

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        return 0
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        return 1
    finally:
        # Stop API server
        if health_server:
            await health_server.stop()
            logger.info("api_server_stopped")
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
