"""Application entry point with initialization and graceful shutdown."""

import asyncio
import signal
import sys
from typing import Any

from crypto_bot import __version__
from crypto_bot.config.logging_config import configure_logging, get_logger
from crypto_bot.config.settings import AppSettings, get_settings


class GracefulShutdown:
    """Handle graceful shutdown on SIGINT/SIGTERM."""

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._logger = get_logger("shutdown")

    @property
    def should_shutdown(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()

    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown is requested."""
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """Signal that shutdown has been requested."""
        self._logger.info("shutdown_requested")
        self._shutdown_event.set()


def _setup_signal_handlers(shutdown: GracefulShutdown) -> None:
    """Set up signal handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()

    def handle_signal(_sig: signal.Signals) -> None:
        shutdown.request_shutdown()

    # Windows doesn't support SIGTERM in the same way
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal, sig)


def _print_startup_banner(settings: AppSettings, logger: Any) -> None:
    """Log startup configuration (with secrets redacted)."""
    logger.info(
        "starting_bot",
        version=__version__,
        exchange=settings.exchange.name,
        testnet=settings.exchange.testnet,
        symbol=settings.trading.symbol,
        dry_run=settings.trading.dry_run,
        log_level=settings.log_level,
    )


async def main() -> int:
    """Main application entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Load settings first - this validates configuration
    try:
        settings = get_settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    # Initialize logging
    configure_logging(
        log_level=settings.log_level,
        json_output=settings.json_logs,
    )
    logger = get_logger("main")

    # Print startup banner
    _print_startup_banner(settings, logger)

    # Set up graceful shutdown
    shutdown = GracefulShutdown()

    try:
        # Set up signal handlers (Unix only, Windows uses different mechanism)
        if sys.platform != "win32":
            _setup_signal_handlers(shutdown)

        # TODO: Initialize components (exchange, strategy, etc.)
        logger.info("bot_initialized", status="ready")

        # Main loop placeholder - will be replaced with actual trading loop
        if sys.platform == "win32":
            # On Windows, we need to handle Ctrl+C differently
            try:
                while not shutdown.should_shutdown:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                shutdown.request_shutdown()
        else:
            await shutdown.wait_for_shutdown()

        logger.info("shutting_down")
        # TODO: Cleanup components
        return 0

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        return 0
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        return 1
    finally:
        logger.info("bot_stopped")


def cli() -> None:
    """CLI entry point."""
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
