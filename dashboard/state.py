"""CryptoTrader Dashboard - State Manager.

Centralized state management for dashboard data. Holds all dashboard data
and provides async refresh mechanism to fetch from the trading bot API.
All UI components access this single state instance.

Epic 6: Includes latency logging, retry logic, and cleanup for stability.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Literal

from dashboard.services.api_client import APIClient
from dashboard.services.data_models import (
    BotConfig,
    DashboardData,
    GridConfig,
    HealthResponse,
    OrderData,
    PairData,
    TradeData,
)

logger = logging.getLogger(__name__)

# Extended to include "reconnecting" for recovery state (Story 6-4)
ConnectionStatus = Literal["connected", "reconnecting", "stale", "offline"]

# Chart mode type (Story 8.3)
ChartMode = Literal["line", "candlestick"]


class DashboardState:
    """Centralized dashboard state container.

    Holds all dashboard data and provides refresh mechanism.
    NiceGUI automatically pushes changes to browser via WebSocket
    when state properties are updated.

    Attributes:
        health: Bot health status.
        pairs: List of trading pair data.
        total_pnl: Total P&L across all pairs.
        total_pnl_percent: Total P&L percentage.
        last_update: Timestamp of last successful update (local timezone).
        connection_status: Current API connection status.
        selected_pair: Currently selected pair for chart display.
        orders: Open orders for expanded row details.
        trades: Recent trades for expanded row details.
    """

    def __init__(self) -> None:
        """Initialize state with default values."""
        # Core data state
        self.health: HealthResponse | None = None
        self.pairs: list[PairData] = []
        self.realized_pnl: Decimal = Decimal("0")  # Phase 1: Separated P&L
        self.unrealized_pnl: Decimal = Decimal("0")  # Phase 1: Separated P&L
        self.total_pnl: Decimal = Decimal("0")
        self.total_pnl_percent: Decimal = Decimal("0")
        self.last_update: datetime | None = None

        # Connection state
        self.connection_status: ConnectionStatus = "offline"
        self._last_successful_update: datetime | None = None
        self._stale_threshold_seconds: int = 60

        # Retry/recovery state (Story 6-4)
        self._retry_count: int = 0
        self._max_retries: int = 5
        self._base_backoff: float = 1.0  # seconds
        self._is_retrying: bool = False

        # UI state
        self.selected_pair: str | None = None
        self.expanded_rows: set[str] = set()  # Symbol set for expanded rows
        self.chart_mode: ChartMode = "line"  # Story 8.3

        # Timeframe performance data (Story 8.1)
        self.pnl_1h: Decimal = Decimal("0")
        self.pnl_1h_pct: Decimal = Decimal("0")
        self.pnl_24h: Decimal = Decimal("0")
        self.pnl_24h_pct: Decimal = Decimal("0")
        self.pnl_7d: Decimal = Decimal("0")
        self.pnl_7d_pct: Decimal = Decimal("0")
        self.pnl_30d: Decimal = Decimal("0")
        self.pnl_30d_pct: Decimal = Decimal("0")

        # Trade history filters (Story 9.3)
        self.history_filter_symbol: str | None = None
        self.history_filter_side: str | None = None  # "buy", "sell", or None
        self.history_filter_start: datetime | None = None
        self.history_filter_end: datetime | None = None

        # Cached detail data (Tier 3 - on-demand)
        self.orders: list[OrderData] = []
        self.trades: list[TradeData] = []
        self.ohlcv: list[dict[str, Any]] = []
        # Per-symbol caches
        self.ohlcv_by_symbol: dict[str, list[dict[str, Any]]] = {}
        self.orders_by_symbol: dict[str, list[OrderData]] = {}
        self.trades_by_symbol: dict[str, list[TradeData]] = {}
        # Chart timeframe per symbol (default 1h)
        self.chart_timeframe_by_symbol: dict[str, str] = {}

        # Grid and configuration data (Story 10.1, 10.2)
        self.grid_config: GridConfig | None = None
        self.bot_config: BotConfig | None = None
        self.show_grid_overlay: bool = True  # Toggle for grid lines

        # Full API response for advanced components
        self._raw_status: dict[str, Any] | None = None

        # API client
        self._api_client: APIClient | None = None

        # Trade cache for P&L calculation (Phase 1 hardening)
        self._trade_cache: list[TradeData] = []
        self._trade_cache_initialized: bool = False
        self._cache_last_sync: datetime | None = None

        # WebSocket integration (Phase 1 hardening)
        self._websocket_service: Any | None = None
        self._websocket_connected: bool = False
        self._ui_refresh_callback: Callable[[], None] | None = None

    async def initialize(self) -> None:
        """Initialize API client. Call once on startup."""
        self._api_client = APIClient()
        await self._api_client.__aenter__()
        logger.info("Dashboard state initialized")

    async def shutdown(self) -> None:
        """Shutdown API client. Call on application exit."""
        if self._api_client:
            await self._api_client.__aexit__(None, None, None)
            self._api_client = None
            logger.info("Dashboard state shutdown")

    def register_ui_refresh(self, callback: Callable[[], None]) -> None:
        """Register UI refresh callback for WebSocket updates (Issue #7 fix).

        Args:
            callback: Function to call when UI needs to refresh after WebSocket updates.
        """
        self._ui_refresh_callback = callback
        logger.debug("UI refresh callback registered")

    def set_websocket_connected(self, connected: bool) -> None:
        """Update WebSocket connection state (called by WebSocketService).

        Args:
            connected: Whether WebSocket is connected.
        """
        self._websocket_connected = connected
        if not connected:
            logger.warning("WebSocket disconnected - falling back to REST polling")
        else:
            logger.info("WebSocket connected - reducing REST polling")

    async def on_websocket_ticker(self, symbol: str, price: Decimal) -> None:
        """Callback for WebSocket ticker updates - triggers UI refresh.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            price: Current price from ticker stream.
        """
        try:
            # Update pair price in state
            for pair in self.pairs:
                if pair.symbol == symbol:
                    pair.current_price = price
                    break

            # Trigger NiceGUI UI refresh if registered
            if self._ui_refresh_callback:
                self._ui_refresh_callback()

        except Exception as e:
            logger.error("Failed to handle WebSocket ticker for %s: %s", symbol, str(e))

    async def refresh(self) -> None:
        """Refresh all dashboard data from API with latency measurement.

        Updates connection_status based on API availability:
        - "connected": Successful API response
        - "reconnecting": Attempting to reconnect after failure
        - "stale": No successful response for >60 seconds
        - "offline": API unreachable

        Includes latency logging for Story 6-2.
        Now calculates P&L from actual trades like the old dashboard.
        """
        if not self._api_client:
            logger.warning("API client not initialized")
            self.connection_status = "offline"
            return

        start_time = time.perf_counter()

        try:
            # Fetch aggregated dashboard data
            dashboard_data = await self._api_client.get_dashboard_data()
            api_time = time.perf_counter()

            if dashboard_data.health is not None:
                # Successful update
                self.health = dashboard_data.health
                self.pairs = dashboard_data.pairs
                self.last_update = self._to_local_time(datetime.now(timezone.utc))
                self._last_successful_update = datetime.now(timezone.utc)
                self.connection_status = "connected"

                # Fetch trades and calculate P&L from actual trade history
                await self._calculate_pnl_from_trades()

                # Reset retry count on success
                self._retry_count = 0
                self._is_retrying = False

                # Log latency (Story 6-2)
                total_latency = (time.perf_counter() - start_time) * 1000
                api_latency = (api_time - start_time) * 1000
                logger.debug(
                    "State refreshed: api=%.1fms total=%.1fms pnl=%.2f",
                    api_latency,
                    total_latency,
                    float(self.total_pnl),
                )
            else:
                # API returned but health is None (partial failure)
                self._update_connection_status()

        except Exception as e:
            logger.error("State refresh failed: %s", str(e))
            self._update_connection_status()

    async def _calculate_pnl_from_trades(self) -> None:
        """Calculate P&L from actual trade history like the old dashboard.

        Uses cached trades (initialized on startup, updated by WebSocket).
        Only fetches from API if cache not initialized.
        """
        from dashboard.services.pnl_calculator import (
            calculate_pnl_from_trades,
            calculate_portfolio_pnl,
        )

        if not self._api_client:
            return

        try:
            # Use trade cache (initialized on startup, updated by WebSocket)
            if not self._trade_cache_initialized:
                # First time: fetch from API
                all_trades = await self._api_client.get_trades(limit=200)
                self._trade_cache = all_trades
                self._trade_cache_initialized = True
                if all_trades:
                    self._cache_last_sync = max(t.timestamp for t in all_trades)
            else:
                # Use cached trades (updated by WebSocket or periodic sync)
                all_trades = self._trade_cache

            self.trades = all_trades

            if not all_trades:
                self.total_pnl = Decimal("0")
                self.total_pnl_percent = Decimal("0")
                return

            # Group trades by symbol
            trades_by_symbol: dict[str, list] = {}
            for trade in all_trades:
                symbol = trade.symbol
                if symbol not in trades_by_symbol:
                    trades_by_symbol[symbol] = []
                trades_by_symbol[symbol].append(trade)

            # Get current prices from pairs data
            current_prices = {p.symbol: p.current_price for p in self.pairs}

            # Calculate portfolio P&L
            total_realized, total_unrealized, total_pnl, total_cycles = (
                calculate_portfolio_pnl(trades_by_symbol, current_prices)
            )

            # Phase 1: Store separated P&L values
            self.realized_pnl = total_realized
            self.unrealized_pnl = total_unrealized
            self.total_pnl = total_pnl
            # Calculate percentage (rough estimate based on buy cost)
            total_buy_cost = sum(
                t.cost if t.cost else t.price * t.amount
                for t in all_trades
                if t.side.lower() == "buy"
            )
            if total_buy_cost > 0:
                self.total_pnl_percent = (total_pnl / total_buy_cost) * 100
            else:
                self.total_pnl_percent = Decimal("0")

            # Update individual pair P&L
            for pair in self.pairs:
                if pair.symbol in trades_by_symbol:
                    pair_pnl = calculate_pnl_from_trades(
                        trades_by_symbol[pair.symbol],
                        current_prices.get(pair.symbol, Decimal("0")),
                    )
                    pair.pnl_today = pair_pnl.total_pnl
                    pair.position_size = pair_pnl.holdings

            # Calculate timeframe P&L (1H, 24H, 7D, 30D)
            self._calculate_timeframe_pnl(all_trades, current_prices)

            logger.info(
                "P&L calculated from %d trades: realized=%.2f unrealized=%.2f total=%.2f",
                len(all_trades),
                float(total_realized),
                float(total_unrealized),
                float(total_pnl),
            )

        except Exception as e:
            logger.error("Failed to calculate P&L from trades: %s", str(e))

    async def _update_trade_cache_from_websocket(self, trade_event: dict[str, Any]) -> None:
        """Append WebSocket trade event to cache and recalculate P&L.

        Args:
            trade_event: executionReport event from Binance User Data Stream.
        """
        try:
            # Parse trade event (Binance executionReport format)
            trade = TradeData(
                trade_id=str(trade_event.get("t", "")),  # Trade ID
                symbol=trade_event.get("s", ""),  # Symbol
                side="buy" if trade_event.get("S") == "BUY" else "sell",  # Side
                price=Decimal(str(trade_event.get("p", "0"))),  # Price
                amount=Decimal(str(trade_event.get("q", "0"))),  # Quantity
                cost=Decimal(str(trade_event.get("p", "0")))
                * Decimal(str(trade_event.get("q", "0"))),
                fee=Decimal(str(trade_event.get("n", "0"))),  # Commission
                timestamp=datetime.fromtimestamp(
                    trade_event.get("T", 0) / 1000, tz=timezone.utc
                ),  # Transaction time
            )

            # Append to cache
            self._trade_cache.append(trade)
            self._cache_last_sync = trade.timestamp

            # Keep cache size manageable (last 500 trades)
            if len(self._trade_cache) > 500:
                self._trade_cache = self._trade_cache[-500:]

            logger.debug(
                "Trade cache updated: %s %s %.8f @ %.2f (cache size: %d)",
                trade.side,
                trade.symbol,
                float(trade.amount),
                float(trade.price),
                len(self._trade_cache),
            )

            # Recalculate P&L from cache (zero API calls)
            await self._calculate_pnl_from_trades()

        except Exception as e:
            logger.error("Failed to update trade cache from WebSocket: %s", str(e))

    def _calculate_timeframe_pnl(
        self,
        all_trades: list[TradeData],
        current_prices: dict[str, Decimal],
    ) -> None:
        """Calculate P&L for different timeframes (1H, 24H, 7D, 30D).

        Filters trades by timestamp and calculates P&L for each period.

        Args:
            all_trades: All trades from API.
            current_prices: Current prices for each symbol.
        """
        from dashboard.services.pnl_calculator import calculate_portfolio_pnl

        now = datetime.now(timezone.utc)

        # Define timeframes
        timeframes = [
            ("1h", timedelta(hours=1)),
            ("24h", timedelta(hours=24)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
        ]

        for tf_name, tf_delta in timeframes:
            cutoff = now - tf_delta

            # Filter trades within the timeframe
            # Handle both timezone-aware and naive timestamps
            tf_trades = []
            for t in all_trades:
                if not t.timestamp:
                    continue
                # Make timestamp timezone-aware if naive
                ts = t.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    tf_trades.append(t)

            if tf_trades:
                # Group by symbol
                trades_by_symbol: dict[str, list] = {}
                for trade in tf_trades:
                    if trade.symbol not in trades_by_symbol:
                        trades_by_symbol[trade.symbol] = []
                    trades_by_symbol[trade.symbol].append(trade)

                # Calculate P&L for this timeframe
                _, _, tf_pnl, _ = calculate_portfolio_pnl(
                    trades_by_symbol, current_prices
                )

                # Calculate total buy cost for percentage
                tf_buy_cost = sum(
                    t.cost if t.cost else t.price * t.amount
                    for t in tf_trades
                    if t.side.lower() == "buy"
                )
                tf_pct = (tf_pnl / tf_buy_cost * 100) if tf_buy_cost > 0 else Decimal("0")
            else:
                tf_pnl = Decimal("0")
                tf_pct = Decimal("0")

            # Update state attributes
            if tf_name == "1h":
                self.pnl_1h = tf_pnl
                self.pnl_1h_pct = tf_pct
            elif tf_name == "24h":
                self.pnl_24h = tf_pnl
                self.pnl_24h_pct = tf_pct
            elif tf_name == "7d":
                self.pnl_7d = tf_pnl
                self.pnl_7d_pct = tf_pct
            elif tf_name == "30d":
                self.pnl_30d = tf_pnl
                self.pnl_30d_pct = tf_pct

    async def refresh_tier1(self) -> None:
        """Refresh Tier 1 data only (health, P&L) with REST fallback logic.

        Called frequently (every 2 seconds) for critical real-time data.
        Behavior:
        - Always check health via REST (no WebSocket equivalent)
        - Always calculate P&L (uses cached trades, not API call)
        - Skip fetching current prices if WebSocket connected (ticker stream provides)
        """
        if not self._websocket_connected:
            # WebSocket offline - full refresh via REST
            await self._refresh_with_retry()
        else:
            # WebSocket connected - only refresh health via REST
            if self._api_client:
                self.health = await self._api_client.get_health()
                self.connection_status = (
                    "connected" if self.health else self.connection_status
                )
            # P&L always calculated from cache (no API call)
            await self._calculate_pnl_from_trades()

    async def refresh_tier2(self) -> None:
        """Refresh Tier 2 data only (chart, table) with WebSocket fallback.

        Called less frequently (every 5 seconds) for non-critical data.
        Behavior:
        - Always fetch pairs/strategies data (WebSocket doesn't provide this)
        - Skip price updates if WebSocket connected (ticker stream provides real-time prices)
        """
        # Always need to fetch pairs data - WebSocket only provides price updates
        if self._api_client and not self._is_retrying:
            try:
                # Fetch pairs data from /api/strategies
                self.pairs = await self._api_client.get_pairs()

                # Update last_update timestamp
                if self.pairs:
                    self.last_update = self._to_local_time(datetime.now(timezone.utc))
            except Exception as e:
                logger.error("Tier 2 refresh failed: %s", str(e))

    async def _refresh_with_retry(self) -> None:
        """Refresh with automatic retry on failure (Story 6-4).

        Implements exponential backoff: 1s, 2s, 4s, 8s, 16s.
        After max retries, marks status as offline.
        """
        # Skip if already in retry loop
        if self._is_retrying:
            return

        try:
            await self.refresh()

            # If still not connected after refresh, start retry
            if self.connection_status != "connected" and self._retry_count < self._max_retries:
                await self._handle_retry()

        except Exception as e:
            logger.warning("Refresh failed, will retry: %s", str(e))
            await self._handle_retry()

    async def _handle_retry(self) -> None:
        """Handle failed refresh with exponential backoff."""
        self._retry_count += 1
        self._is_retrying = True

        if self._retry_count <= self._max_retries:
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s
            backoff = self._base_backoff * (2 ** (self._retry_count - 1))
            self.connection_status = "reconnecting"

            logger.info(
                "Reconnection attempt %d/%d, waiting %.1fs",
                self._retry_count,
                self._max_retries,
                backoff,
            )

            await asyncio.sleep(backoff)

            # Try again
            self._is_retrying = False
            await self._refresh_with_retry()
        else:
            # Max retries exceeded
            self.connection_status = "offline"
            self._is_retrying = False
            logger.error("Max retries exceeded, marking offline")

    async def refresh_orders(self, symbol: str | None = None) -> list[OrderData]:
        """Refresh open orders (Tier 3 - on-demand).

        Args:
            symbol: Optional symbol filter.

        Returns:
            List of orders.
        """
        if not self._api_client:
            return []

        orders = await self._api_client.get_orders(symbol)
        self.orders = orders
        if symbol:
            self.orders_by_symbol[symbol] = orders
        logger.debug("Orders refreshed: %d orders for %s", len(orders), symbol or "all")
        return orders

    async def refresh_trades(self, symbol: str | None = None, limit: int = 100) -> list[TradeData]:
        """Refresh recent trades (Tier 3 - on-demand).

        Args:
            symbol: Optional symbol filter (filtered client-side).
            limit: Maximum number of trades to fetch from API.

        Returns:
            List of trades (filtered by symbol if provided).
        """
        if not self._api_client:
            return []

        # Fetch all trades without symbol filter (API may not support it)
        all_trades = await self._api_client.get_trades(None, limit)
        self.trades = all_trades

        # Filter by symbol client-side if requested
        if symbol:
            symbol_trades = [t for t in all_trades if t.symbol == symbol]
            self.trades_by_symbol[symbol] = symbol_trades
            logger.info("Trades for card: %d trades for %s (from %d total)",
                        len(symbol_trades), symbol, len(all_trades))
            return symbol_trades

        logger.debug("Trades refreshed: %d trades", len(all_trades))
        return all_trades

    async def refresh_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Refresh OHLCV chart data.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candlestick timeframe.
            limit: Number of candles.

        Returns:
            List of OHLCV candles.
        """
        if not self._api_client:
            return []

        ohlcv_data = await self._api_client.get_ohlcv(symbol, timeframe, limit)
        self.ohlcv = ohlcv_data
        self.ohlcv_by_symbol[symbol] = ohlcv_data  # Store per symbol
        logger.debug("OHLCV refreshed: %d candles for %s", len(ohlcv_data), symbol)
        return ohlcv_data

    async def refresh_full_status(self) -> None:
        """Refresh full API status response for advanced components."""
        if not self._api_client:
            return

        self._raw_status = await self._api_client.get_status()

    async def refresh_grid_config(self, symbol: str | None = None) -> None:
        """Refresh grid configuration for a trading pair (Story 10.1).

        Args:
            symbol: Trading pair symbol. Uses selected_pair or first pair if None.
        """
        if not self._api_client:
            return

        target_symbol = symbol or self.selected_pair
        if not target_symbol and self.pairs:
            target_symbol = self.pairs[0].symbol

        if target_symbol:
            self.grid_config = await self._api_client.get_grid_config(target_symbol)
            logger.debug("Grid config refreshed for %s", target_symbol)

    async def refresh_bot_config(self) -> None:
        """Refresh bot configuration (Story 10.2)."""
        if not self._api_client:
            return

        self.bot_config = await self._api_client.get_bot_config()
        logger.debug("Bot config refreshed")

    def _update_connection_status(self) -> None:
        """Update connection status based on last successful update."""
        if self._last_successful_update is None:
            self.connection_status = "offline"
            return

        elapsed = (
            datetime.now(timezone.utc) - self._last_successful_update
        ).total_seconds()
        if elapsed > self._stale_threshold_seconds:
            self.connection_status = "stale"
        # Keep current status if recently successful

    @staticmethod
    def _to_local_time(dt: datetime) -> datetime:
        """Convert UTC datetime to local timezone.

        Args:
            dt: UTC datetime.

        Returns:
            Datetime in local timezone.
        """
        return dt.astimezone()

    # Computed properties for UI convenience
    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to API."""
        return self.connection_status == "connected"

    @property
    def is_stale(self) -> bool:
        """Return True if data is stale."""
        return self.connection_status == "stale"

    @property
    def is_offline(self) -> bool:
        """Return True if API is offline."""
        return self.connection_status == "offline"

    @property
    def is_reconnecting(self) -> bool:
        """Return True if attempting to reconnect (Story 6-4)."""
        return self.connection_status == "reconnecting"

    @property
    def pair_count(self) -> int:
        """Return number of trading pairs."""
        return len(self.pairs)

    @property
    def is_healthy(self) -> bool:
        """Return True if bot health status is healthy."""
        return self.health is not None and self.health.status == "healthy"

    @property
    def uptime_formatted(self) -> str:
        """Return formatted uptime string (e.g., '2h 30m')."""
        if self.health is None:
            return "N/A"

        seconds = self.health.uptime_seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return f"{seconds}s"

    @property
    def last_update_formatted(self) -> str:
        """Return formatted last update time."""
        if self.last_update is None:
            return "Never"
        return self.last_update.strftime("%H:%M:%S")

    def toggle_row_expansion(self, symbol: str) -> bool:
        """Toggle row expansion state for a symbol.

        Args:
            symbol: Trading pair symbol.

        Returns:
            True if row is now expanded, False if collapsed.
        """
        if symbol in self.expanded_rows:
            self.expanded_rows.discard(symbol)
            return False
        else:
            self.expanded_rows.add(symbol)
            return True

    def is_row_expanded(self, symbol: str) -> bool:
        """Check if a row is expanded.

        Args:
            symbol: Trading pair symbol.

        Returns:
            True if row is expanded.
        """
        return symbol in self.expanded_rows


# Singleton instance - import this in UI components
state = DashboardState()
