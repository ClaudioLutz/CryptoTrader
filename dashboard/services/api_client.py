"""CryptoTrader Dashboard - API Client.

Async HTTP client for fetching data from the trading bot API.
Uses httpx for async HTTP requests with configurable timeout and error handling.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
import pybreaker

from dashboard.config import config
from dashboard.services.data_models import (
    BotConfig,
    DashboardData,
    GridConfig,
    GridLevel,
    HealthResponse,
    OrderData,
    PairConfig,
    PairData,
    RiskConfig,
    TradeData,
)

logger = logging.getLogger(__name__)

# Circuit breaker for API fault tolerance
exchange_breaker = pybreaker.CircuitBreaker(
    fail_max=5,  # Open after 5 consecutive failures
    reset_timeout=60,  # Try half-open after 60 seconds
    name="BotAPICircuitBreaker",
)


class APIClient:
    """Async client for the trading bot REST API.

    This client provides methods to fetch health status, trading pairs,
    positions, orders, trades, and aggregated dashboard data.

    Usage:
        async with APIClient() as client:
            health = await client.get_health()
            pairs = await client.get_pairs()

    All methods handle errors gracefully and return None/empty values
    rather than raising exceptions, allowing the dashboard to display
    stale data indicators when the API is unavailable.
    """

    def __init__(self) -> None:
        """Initialize API client with configured timeout."""
        self._client: httpx.AsyncClient | None = None
        self._base_url = config.api_base_url
        self._timeout = config.api_timeout

    async def __aenter__(self) -> "APIClient":
        """Enter async context and create HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context and close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @exchange_breaker
    async def get_health(self) -> HealthResponse | None:
        """Fetch bot health status from /health endpoint.

        Returns:
            HealthResponse with status, uptime, and optional message,
            or None if request fails.
        """
        try:
            if not self._client:
                logger.error("API client not initialized")
                return None

            response = await self._client.get("/health")
            response.raise_for_status()
            data = response.json()

            return HealthResponse(
                status=data.get("status", "error"),
                uptime_seconds=int(data.get("uptime_seconds", 0)),
                message=data.get("message"),
            )
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return None
        except httpx.RequestError as e:
            logger.error("Health request failed: connection error: %s", e)
            raise  # Let circuit breaker count this failure
        except httpx.HTTPStatusError as e:
            logger.error(
                "Health request returned error status: %s", e.response.status_code
            )
            raise  # Let circuit breaker count this failure
        except Exception as e:
            logger.error("Health request failed: unexpected error: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_status(self) -> dict[str, Any] | None:
        """Fetch comprehensive bot status from /api/status endpoint.

        Returns:
            Dict with full bot status including strategies, risk metrics,
            grid config, etc. or None if request fails.
        """
        try:
            if not self._client:
                return None

            response = await self._client.get("/api/status")
            response.raise_for_status()
            return response.json()
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Status request failed: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_pairs(self) -> list[PairData]:
        """Fetch all trading pair data from /api/strategies endpoint.

        Returns:
            List of PairData for each trading pair, or empty list if request fails.
        """
        try:
            if not self._client:
                return []

            response = await self._client.get("/api/strategies")
            response.raise_for_status()
            data = response.json()

            pairs = []
            for strategy in data.get("strategies", []):
                symbol = strategy.get("symbol", "UNKNOWN")
                stats = strategy.get("statistics", {})

                # Fetch current price from OHLCV (1m candle for latest price)
                current_price = await self._get_current_price(symbol)

                pairs.append(
                    PairData(
                        symbol=symbol,
                        current_price=current_price,
                        pnl_today=Decimal(str(stats.get("total_profit", "0"))),
                        pnl_percent=Decimal("0"),
                        position_size=Decimal("0"),
                        order_count=stats.get("active_buy_orders", 0)
                        + stats.get("active_sell_orders", 0),
                    )
                )

            return pairs
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return []
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Pairs request failed: %s", e)
            raise  # Let circuit breaker count this failure

    async def _get_current_price(self, symbol: str) -> Decimal:
        """Fetch current price for a symbol from OHLCV endpoint.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Current price as Decimal, or 0 if request fails.
        """
        try:
            if not self._client:
                return Decimal("0")

            response = await self._client.get(
                "/api/ohlcv",
                params={"symbol": symbol, "timeframe": "1m", "limit": 1},
            )
            response.raise_for_status()
            data = response.json()
            ohlcv = data.get("ohlcv", [])
            if ohlcv:
                return Decimal(str(ohlcv[-1].get("close", 0)))
            return Decimal("0")
        except Exception as e:
            logger.debug("Failed to get current price for %s: %s", symbol, e)
            return Decimal("0")

    @exchange_breaker
    async def get_orders(self, symbol: str | None = None) -> list[OrderData]:
        """Fetch open orders from /api/orders endpoint.

        Args:
            symbol: Optional symbol to filter orders.

        Returns:
            List of OrderData for open orders, or empty list if request fails.
        """
        try:
            if not self._client:
                return []

            params = {"symbol": symbol} if symbol else {}
            response = await self._client.get("/api/orders", params=params)
            response.raise_for_status()
            data = response.json()

            orders = []
            for order in data.get("orders", []):
                orders.append(
                    OrderData(
                        order_id=order.get("id", ""),
                        symbol=order.get("symbol", ""),
                        side=order.get("side", "buy"),
                        price=Decimal(str(order.get("price", "0") or "0")),
                        amount=Decimal(str(order.get("amount", "0"))),
                        filled=Decimal(str(order.get("filled", "0"))),
                        status=order.get("status", "unknown"),
                    )
                )

            return orders
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return []
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Orders request failed: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_trades(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[TradeData]:
        """Fetch recent trades from /api/trades endpoint.

        Args:
            symbol: Optional symbol to filter trades.
            limit: Maximum number of trades to return.

        Returns:
            List of TradeData for recent trades, or empty list if request fails.
        """
        try:
            if not self._client:
                return []

            params: dict[str, Any] = {"limit": limit}
            if symbol:
                params["symbol"] = symbol

            response = await self._client.get("/api/trades", params=params)
            response.raise_for_status()
            data = response.json()

            trades = []
            for trade in data.get("trades", []):
                timestamp_str = trade.get("timestamp")
                timestamp = (
                    datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if timestamp_str
                    else datetime.now()
                )

                trades.append(
                    TradeData(
                        trade_id=trade.get("id", ""),
                        symbol=trade.get("symbol", ""),
                        side=trade.get("side", "buy"),
                        price=Decimal(str(trade.get("price", "0"))),
                        amount=Decimal(str(trade.get("amount", "0"))),
                        cost=Decimal(str(trade.get("cost", "0") or "0")),
                        fee=Decimal(str(trade.get("fee", "0") or "0")),
                        timestamp=timestamp,
                    )
                )

            return trades
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return []
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Trades HTTP request failed (%s): %r", type(e).__name__, e)
            raise  # Let circuit breaker count this failure
        except Exception as e:
            logger.error("Trades request failed with %s: %r", type(e).__name__, e)
            import traceback
            logger.error("Traceback: %s", traceback.format_exc())
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_pnl(self, period: str = "daily") -> dict[str, Any]:
        """Fetch P&L summary from /api/pnl endpoint.

        Args:
            period: Time period for P&L (daily, weekly, monthly).

        Returns:
            Dict with P&L metrics, or empty dict with defaults if request fails.
        """
        try:
            if not self._client:
                return {"total_pnl": "0", "total_trades": 0}

            response = await self._client.get("/api/pnl", params={"period": period})
            response.raise_for_status()
            return response.json()
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return {"total_pnl": "0", "total_trades": 0}
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("PnL request failed: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_total_pnl(self) -> Decimal:
        """Fetch total P&L for today.

        Returns:
            Total P&L as Decimal, or 0 if request fails.
        """
        try:
            pnl_data = await self.get_pnl(period="daily")
            return Decimal(str(pnl_data.get("total_pnl", "0")))
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return Decimal("0")

    @exchange_breaker
    async def get_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candlestick data from /api/ohlcv endpoint.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candlestick timeframe (1m, 5m, 1h, 4h, 1d).
            limit: Number of candles to return.

        Returns:
            List of OHLCV dictionaries, or empty list if request fails.
        """
        try:
            if not self._client:
                return []

            response = await self._client.get(
                "/api/ohlcv",
                params={"symbol": symbol, "timeframe": timeframe, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("ohlcv", [])
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return []
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("OHLCV request failed: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_grid_config(self, symbol: str) -> GridConfig | None:
        """Fetch grid configuration for a trading pair (Story 10.1).

        Args:
            symbol: Trading pair symbol.

        Returns:
            GridConfig with levels and current price, or None if request fails.
        """
        try:
            if not self._client:
                return None

            response = await self._client.get(
                "/api/grid", params={"symbol": symbol}
            )
            response.raise_for_status()
            data = response.json()

            levels = []
            for level_data in data.get("levels", []):
                levels.append(
                    GridLevel(
                        price=Decimal(str(level_data.get("price", "0"))),
                        side=level_data.get("side", "buy"),
                        status=level_data.get("status", "open"),
                        order_id=level_data.get("order_id"),
                    )
                )

            return GridConfig(
                symbol=data.get("symbol", symbol),
                levels=levels,
                current_price=Decimal(str(data.get("current_price", "0"))),
                grid_spacing=Decimal(str(data.get("grid_spacing", "0"))),
                total_levels=data.get("total_levels", len(levels)),
            )
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Grid config request failed: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_bot_config(self) -> BotConfig | None:
        """Fetch bot configuration (Story 10.2).

        Returns:
            BotConfig with all settings, or None if request fails.
        """
        try:
            if not self._client:
                return None

            response = await self._client.get("/api/config")
            response.raise_for_status()
            data = response.json()

            # Parse pair configurations
            pairs = []
            for pair_data in data.get("pairs", []):
                pairs.append(
                    PairConfig(
                        symbol=pair_data.get("symbol", ""),
                        enabled=pair_data.get("enabled", True),
                        grid_levels=pair_data.get("grid_levels", 10),
                        grid_spacing_pct=Decimal(
                            str(pair_data.get("grid_spacing_pct", "1.0"))
                        ),
                        order_size=Decimal(str(pair_data.get("order_size", "0.001"))),
                        max_position=Decimal(str(pair_data.get("max_position", "1.0"))),
                    )
                )

            # Parse risk configuration
            risk_data = data.get("risk", {})
            risk = RiskConfig(
                max_open_orders=risk_data.get("max_open_orders", 50),
                max_daily_loss=Decimal(str(risk_data.get("max_daily_loss", "1000"))),
                stop_loss_pct=(
                    Decimal(str(risk_data["stop_loss_pct"]))
                    if risk_data.get("stop_loss_pct")
                    else None
                ),
                take_profit_pct=(
                    Decimal(str(risk_data["take_profit_pct"]))
                    if risk_data.get("take_profit_pct")
                    else None
                ),
            )

            return BotConfig(
                bot_name=data.get("bot_name", "CryptoTrader"),
                version=data.get("version", "1.0.0"),
                exchange=data.get("exchange", "Binance"),
                pairs=pairs,
                risk=risk,
                api_timeout_ms=data.get("api_timeout_ms", 5000),
                poll_interval_ms=data.get("poll_interval_ms", 1000),
            )
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error("Bot config request failed: %s", e)
            raise  # Let circuit breaker count this failure

    @exchange_breaker
    async def get_dashboard_data(self) -> DashboardData:
        """Fetch aggregated dashboard data from multiple endpoints.

        Makes concurrent API calls to gather health, pairs, and P&L data,
        then aggregates into a single DashboardData object.

        Returns:
            DashboardData with all available data. Fields will be None/empty
            if their respective API calls failed.
        """
        try:
            health = await self.get_health()
            pairs = await self.get_pairs()
            total_pnl = await self.get_total_pnl()

            # Calculate total P&L percent (simplified - would need more data for accurate calc)
            total_pnl_percent = Decimal("0")

            return DashboardData(
                health=health,
                pairs=pairs,
                total_pnl=total_pnl,
                total_pnl_percent=total_pnl_percent,
                last_update=datetime.now() if health else None,
                is_stale=health is None,
            )
        except pybreaker.CircuitBreakerError:
            logger.warning("Circuit breaker is OPEN - API calls blocked")
            return DashboardData(
                health=None,
                pairs=[],
                total_pnl=Decimal("0"),
                total_pnl_percent=Decimal("0"),
                last_update=None,
                is_stale=True,
            )


# Module-level singleton for convenience
_api_client: APIClient | None = None


def get_api_client() -> APIClient:
    """Get the global API client instance.

    Returns:
        APIClient singleton instance.
    """
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client
