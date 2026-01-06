"""CryptoTrader Dashboard - WebSocket Service.

Manages Binance WebSocket connections for real-time data updates.
Uses python-binance library for User Data Stream and Market Data streams.

Phase 1 Dashboard Hardening: WebSocket-first data flow with REST fallback.
"""

import asyncio
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from binance import AsyncClient, BinanceSocketManager
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class BinanceWebSocketService:
    """Manages Binance WebSocket streams for real-time dashboard updates.

    Provides User Data Stream for order/balance updates and Market Data streams
    for ticker price updates. Follows callback pattern from existing WebSocketHandler.

    Attributes:
        is_connected: Whether WebSocket streams are currently active.
    """

    def __init__(self, state: Any) -> None:
        """Initialize WebSocket service.

        Args:
            state: DashboardState instance for cache updates and callbacks.
        """
        self._state = state
        self._client: AsyncClient | None = None
        self._bm: BinanceSocketManager | None = None
        self._running: bool = False
        self._user_stream_task: asyncio.Task[Any] | None = None
        self._market_stream_task: asyncio.Task[Any] | None = None
        self._reconnect_count: int = 0
        self._max_reconnect_delay: int = 60  # seconds

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket streams are active."""
        return self._running

    async def start(self) -> None:
        """Start User Data Stream and Market Data streams.

        Raises:
            Exception: If credentials missing or connection fails.
        """
        try:
            # Load .env file to get exchange credentials
            # (Dashboard config only loads DASHBOARD_* variables)
            env_path = Path(__file__).parent.parent.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)

            # Read bot's Binance credentials from environment
            api_key = os.getenv("EXCHANGE__API_KEY", "")
            api_secret = os.getenv("EXCHANGE__API_SECRET", "")
            testnet = os.getenv("EXCHANGE__TESTNET", "false").lower() == "true"

            if not api_key or not api_secret:
                raise ValueError(
                    "Missing EXCHANGE__API_KEY or EXCHANGE__API_SECRET environment variables"
                )

            # Create Binance AsyncClient
            self._client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
            logger.info("Connecting to Binance %s", "Testnet" if testnet else "Production")
            self._bm = BinanceSocketManager(self._client, user_timeout=60)
            self._running = True

            # Start User Data Stream (order/balance updates)
            self._user_stream_task = asyncio.create_task(self._start_user_stream())

            # Start Market Data Stream (ticker updates for all symbols)
            # Get symbols from state.pairs
            if self._state.pairs:
                symbols = [pair.symbol for pair in self._state.pairs]
                self._market_stream_task = asyncio.create_task(
                    self._start_market_stream(symbols)
                )

            logger.info(
                "WebSocket service started: user_stream=active market_stream=active"
            )

        except Exception as e:
            logger.error("Failed to start WebSocket service: %s", str(e))
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop all WebSocket streams and cleanup resources."""
        self._running = False

        # Cancel stream tasks
        if self._user_stream_task:
            self._user_stream_task.cancel()
            try:
                await self._user_stream_task
            except asyncio.CancelledError:
                pass
            self._user_stream_task = None

        if self._market_stream_task:
            self._market_stream_task.cancel()
            try:
                await self._market_stream_task
            except asyncio.CancelledError:
                pass
            self._market_stream_task = None

        # Close Binance client
        if self._client:
            await self._client.close_connection()
            self._client = None

        self._bm = None
        logger.info("WebSocket service stopped")

    async def _start_user_stream(self) -> None:
        """Start User Data Stream for order/balance updates.

        Note: BinanceSocketManager handles listenKey creation and keepalive automatically.
        The library sends keepalive pings every 30 minutes internally.
        """
        retry_delay = 1  # Start with 1 second

        while self._running:
            try:
                if not self._bm:
                    logger.warning("BinanceSocketManager not initialized")
                    await asyncio.sleep(retry_delay)
                    continue

                async with self._bm.user_socket() as stream:
                    logger.info("User Data Stream connected")
                    self._reconnect_count = 0  # Reset on success
                    retry_delay = 1

                    # Notify state of connection
                    if hasattr(self._state, "set_websocket_connected"):
                        self._state.set_websocket_connected(True)

                    while self._running:
                        msg = await stream.recv()
                        await self._handle_user_event(msg)

            except asyncio.CancelledError:
                logger.info("User Data Stream cancelled")
                break
            except Exception as e:
                logger.error("User Data Stream error: %s", str(e))
                self._reconnect_count += 1

                # Notify state of disconnection
                if hasattr(self._state, "set_websocket_connected"):
                    self._state.set_websocket_connected(False)

                if self._running:
                    # Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 60s
                    retry_delay = min(
                        2**self._reconnect_count, self._max_reconnect_delay
                    )
                    logger.info(
                        "Reconnecting User Data Stream in %ds (attempt %d)",
                        retry_delay,
                        self._reconnect_count,
                    )
                    await asyncio.sleep(retry_delay)

    async def _start_market_stream(self, symbols: list[str]) -> None:
        """Start combined ticker stream for all symbols.

        Args:
            symbols: List of trading pair symbols (e.g., ["BTC/USDT", "ETH/USDT"]).
        """
        retry_delay = 1

        while self._running:
            try:
                if not self._bm:
                    logger.warning("BinanceSocketManager not initialized")
                    await asyncio.sleep(retry_delay)
                    continue

                # Convert symbols to Binance format (BTCUSDT, ETHUSDT)
                binance_symbols = [
                    s.replace("/", "").upper() for s in symbols if "/" in s
                ]
                if not binance_symbols:
                    logger.warning("No valid symbols for market stream")
                    await asyncio.sleep(10)
                    continue

                # Create ticker streams
                streams = [f"{s.lower()}@ticker" for s in binance_symbols]

                async with self._bm.multiplex_socket(streams) as stream:
                    logger.info(
                        "Market Data Stream connected (%d symbols)", len(binance_symbols)
                    )
                    retry_delay = 1

                    while self._running:
                        msg = await stream.recv()
                        await self._handle_ticker_event(msg)

            except asyncio.CancelledError:
                logger.info("Market Data Stream cancelled")
                break
            except Exception as e:
                logger.error("Market Data Stream error: %s", str(e))

                if self._running:
                    # Exponential backoff
                    retry_delay = min(retry_delay * 2, self._max_reconnect_delay)
                    logger.info("Reconnecting Market Data Stream in %ds", retry_delay)
                    await asyncio.sleep(retry_delay)

    async def _handle_user_event(self, msg: dict[str, Any]) -> None:
        """Route User Data Stream events to appropriate handlers.

        Args:
            msg: Event message from Binance User Data Stream.
        """
        try:
            event_type = msg.get("e")

            if event_type == "executionReport":
                # Trade executed - update cache and recalculate P&L
                logger.debug(
                    "Trade execution: %s %s %s @ %s",
                    msg.get("S"),  # Side
                    msg.get("q"),  # Quantity
                    msg.get("s"),  # Symbol
                    msg.get("p"),  # Price
                )
                await self._state._update_trade_cache_from_websocket(msg)

            elif event_type == "outboundAccountPosition":
                # Balance changed - trigger tier1 refresh
                logger.debug("Account position update received")
                await self._state.refresh_tier1()

            else:
                logger.debug("Unhandled User Data Stream event: %s", event_type)

        except Exception as e:
            logger.error("Failed to handle user event: %s", str(e))

    async def _handle_ticker_event(self, msg: dict[str, Any]) -> None:
        """Update prices from ticker stream and trigger UI refresh.

        Args:
            msg: Ticker event message from Binance.
        """
        try:
            # Extract data from multiplex stream format
            data = msg.get("data", {})
            symbol_raw = data.get("s", "")  # e.g., "BTCUSDT"
            price_str = data.get("c", "0")  # Close price (current price)

            if not symbol_raw or not price_str:
                return

            # Convert BTCUSDT -> BTC/USDT
            if len(symbol_raw) >= 6:
                # Assume quote is last 4 chars (USDT, BUSD, etc.)
                base = symbol_raw[:-4]
                quote = symbol_raw[-4:]
                symbol = f"{base}/{quote}"
            else:
                symbol = symbol_raw

            price = Decimal(price_str)

            # Update pair price in state
            await self._state.on_websocket_ticker(symbol, price)

        except Exception as e:
            logger.error("Failed to handle ticker event: %s", str(e))
