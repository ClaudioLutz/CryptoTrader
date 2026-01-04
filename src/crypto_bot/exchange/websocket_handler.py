"""WebSocket handler for real-time market data."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from crypto_bot.exchange.base_exchange import Ticker

logger = structlog.get_logger()

# Type alias for ticker callback
TickerCallback = Callable[[Ticker], Awaitable[None]]


class WebSocketHandler:
    """WebSocket handler for real-time price feeds.

    Provides subscription-based real-time data feeds using CCXT Pro.
    Includes automatic reconnection and fallback to REST polling.
    """

    def __init__(
        self,
        exchange: Any,  # ccxt.Exchange
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        """Initialize WebSocket handler.

        Args:
            exchange: CCXT exchange instance (must support watch_* methods).
            reconnect_delay: Initial delay before reconnection attempt.
            max_reconnect_delay: Maximum delay between reconnection attempts.
        """
        self._exchange = exchange
        self._running = False
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._current_delay = reconnect_delay
        self._ticker_callbacks: dict[str, list[TickerCallback]] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._logger = logger.bind(component="websocket_handler")

    @property
    def is_running(self) -> bool:
        """Check if WebSocket handler is running."""
        return self._running

    @property
    def subscribed_symbols(self) -> list[str]:
        """Get list of subscribed symbols."""
        return list(self._ticker_callbacks.keys())

    async def subscribe_ticker(
        self,
        symbol: str,
        callback: TickerCallback,
    ) -> None:
        """Subscribe to real-time ticker updates for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            callback: Async function to call with ticker updates.
        """
        if symbol not in self._ticker_callbacks:
            self._ticker_callbacks[symbol] = []

        self._ticker_callbacks[symbol].append(callback)

        self._logger.info(
            "ticker_subscribed",
            symbol=symbol,
            callback_count=len(self._ticker_callbacks[symbol]),
        )

    async def unsubscribe_ticker(
        self,
        symbol: str,
        callback: TickerCallback | None = None,
    ) -> None:
        """Unsubscribe from ticker updates.

        Args:
            symbol: Trading pair symbol.
            callback: Specific callback to remove. If None, removes all callbacks.
        """
        if symbol not in self._ticker_callbacks:
            return

        if callback is None:
            del self._ticker_callbacks[symbol]
        else:
            self._ticker_callbacks[symbol] = [
                cb for cb in self._ticker_callbacks[symbol] if cb != callback
            ]
            if not self._ticker_callbacks[symbol]:
                del self._ticker_callbacks[symbol]

        self._logger.info("ticker_unsubscribed", symbol=symbol)

    async def start(self) -> None:
        """Start WebSocket listener for all subscribed symbols."""
        if self._running:
            self._logger.warning("websocket_already_running")
            return

        self._running = True
        self._current_delay = self._reconnect_delay

        self._logger.info(
            "websocket_starting",
            symbols=list(self._ticker_callbacks.keys()),
        )

        # Create a task for each subscribed symbol
        for symbol in self._ticker_callbacks:
            task = asyncio.create_task(self._watch_ticker(symbol))
            self._tasks.append(task)

    async def stop(self) -> None:
        """Stop WebSocket listener and clean up."""
        if not self._running:
            return

        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        self._logger.info("websocket_stopped")

    async def _watch_ticker(self, symbol: str) -> None:
        """Watch ticker updates for a specific symbol.

        Automatically reconnects on disconnect with exponential backoff.
        """
        while self._running and symbol in self._ticker_callbacks:
            try:
                # Use CCXT Pro's watch_ticker method
                raw_ticker = await self._exchange.watch_ticker(symbol)
                ticker = self._convert_ticker(raw_ticker)

                # Reset delay on successful connection
                self._current_delay = self._reconnect_delay

                # Notify all callbacks
                for callback in self._ticker_callbacks.get(symbol, []):
                    try:
                        await callback(ticker)
                    except Exception as e:
                        self._logger.error(
                            "callback_error",
                            symbol=symbol,
                            error=str(e),
                        )

            except asyncio.CancelledError:
                break
            except AttributeError:
                # Exchange doesn't support watch_ticker (no CCXT Pro)
                self._logger.warning(
                    "websocket_not_supported",
                    symbol=symbol,
                    fallback="rest_polling",
                )
                await self._fallback_polling(symbol)
                break
            except Exception as e:
                if not self._running:
                    break

                self._logger.error(
                    "websocket_error",
                    symbol=symbol,
                    error=str(e),
                    reconnect_delay=self._current_delay,
                )

                # Exponential backoff for reconnection
                await asyncio.sleep(self._current_delay)
                self._current_delay = min(
                    self._current_delay * 2,
                    self._max_reconnect_delay,
                )

    async def _fallback_polling(self, symbol: str) -> None:
        """Fallback to REST polling when WebSocket unavailable.

        Args:
            symbol: Trading pair symbol to poll.
        """
        self._logger.info("using_rest_fallback", symbol=symbol)

        while self._running and symbol in self._ticker_callbacks:
            try:
                raw_ticker = await self._exchange.fetch_ticker(symbol)
                ticker = self._convert_ticker(raw_ticker)

                for callback in self._ticker_callbacks.get(symbol, []):
                    try:
                        await callback(ticker)
                    except Exception as e:
                        self._logger.error(
                            "callback_error",
                            symbol=symbol,
                            error=str(e),
                        )

                # Poll interval for REST fallback (respect rate limits)
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(
                    "polling_error",
                    symbol=symbol,
                    error=str(e),
                )
                await asyncio.sleep(5.0)

    def _convert_ticker(self, raw: dict[str, Any]) -> Ticker:
        """Convert raw ticker data to Ticker dataclass."""
        return Ticker(
            symbol=raw["symbol"],
            bid=Decimal(str(raw["bid"])) if raw.get("bid") else Decimal("0"),
            ask=Decimal(str(raw["ask"])) if raw.get("ask") else Decimal("0"),
            last=Decimal(str(raw["last"])) if raw.get("last") else Decimal("0"),
            timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, tz=UTC),
        )


class WebSocketManager:
    """Manager for multiple WebSocket connections.

    Coordinates WebSocket handlers across multiple exchanges or
    provides a single point of control for all real-time data.
    """

    def __init__(self) -> None:
        """Initialize WebSocket manager."""
        self._handlers: dict[str, WebSocketHandler] = {}
        self._logger = logger.bind(component="websocket_manager")

    def add_handler(self, name: str, handler: WebSocketHandler) -> None:
        """Add a WebSocket handler.

        Args:
            name: Identifier for the handler.
            handler: WebSocketHandler instance.
        """
        self._handlers[name] = handler

    def get_handler(self, name: str) -> WebSocketHandler | None:
        """Get a WebSocket handler by name."""
        return self._handlers.get(name)

    async def start_all(self) -> None:
        """Start all registered WebSocket handlers."""
        for name, handler in self._handlers.items():
            self._logger.info("starting_handler", name=name)
            await handler.start()

    async def stop_all(self) -> None:
        """Stop all registered WebSocket handlers."""
        for name, handler in self._handlers.items():
            self._logger.info("stopping_handler", name=name)
            await handler.stop()
