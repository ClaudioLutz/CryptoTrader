"""CCXT wrapper with error handling, rate limiting, and retry logic."""

import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt
import structlog

from crypto_bot.config.settings import ExchangeSettings

# Re-sync time with exchange every 5 minutes
TIME_SYNC_INTERVAL_SECONDS = 300
from crypto_bot.exchange.base_exchange import (
    OHLCV,
    AuthenticationError,
    Balance,
    BaseExchange,
    ExchangeError,
    InsufficientFundsError,
    InvalidOrderError,
    Order,
    OrderNotFoundError,
    OrderSide,
    OrderStatus,
    OrderType,
    Ticker,
)
from crypto_bot.utils.retry import retry_with_backoff

logger = structlog.get_logger()


class CCXTExchange(BaseExchange):
    """CCXT-based exchange implementation.

    Provides a unified interface to cryptocurrency exchanges via CCXT,
    with automatic retry logic, rate limiting, and error handling.
    """

    def __init__(self, settings: ExchangeSettings) -> None:
        """Initialize CCXT exchange wrapper.

        Args:
            settings: Exchange configuration settings.
        """
        self._settings = settings
        self._exchange: ccxt.Exchange | None = None
        self._markets: dict[str, Any] = {}
        self._last_time_sync: float = 0
        self._logger = logger.bind(
            component="ccxt_exchange",
            exchange=settings.name,
        )

    @property
    def exchange(self) -> ccxt.Exchange:
        """Get the underlying CCXT exchange instance."""
        if self._exchange is None:
            raise ExchangeError("Exchange not connected. Call connect() first.")
        return self._exchange

    @property
    def markets(self) -> dict[str, Any]:
        """Get loaded market data."""
        return self._markets

    async def connect(self) -> None:
        """Initialize connection and load markets."""
        try:
            # Get exchange class from ccxt
            exchange_class = getattr(ccxt, self._settings.name, None)
            if exchange_class is None:
                raise ExchangeError(f"Unknown exchange: {self._settings.name}")

            # Initialize exchange with settings
            self._exchange = exchange_class(
                {
                    "apiKey": self._settings.api_key.get_secret_value(),
                    "secret": self._settings.api_secret.get_secret_value(),
                    "enableRateLimit": True,
                    "rateLimit": self._settings.rate_limit_ms,
                    "timeout": self._settings.timeout_ms,
                    "options": {
                        "defaultType": "spot",
                        # Auto-sync with exchange server time to avoid timestamp errors
                        "adjustForTimeDifference": True,
                        # Increase receive window tolerance (max 60000ms)
                        "recvWindow": 60000,
                    },
                }
            )

            # Enable testnet/sandbox mode if configured
            if self._settings.testnet:
                self._exchange.set_sandbox_mode(True)

            # Sync time with Binance server using CCXT's built-in method
            # This is critical when system clock is ahead/behind server time
            await self._sync_time()

            # Pre-load markets to cache symbol info
            self._markets = await self._exchange.load_markets()

            self._logger.info(
                "exchange_connected",
                testnet=self._settings.testnet,
                markets_loaded=len(self._markets),
            )

        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """Clean up connections."""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None
            self._logger.info("exchange_disconnected")

    async def _sync_time(self) -> None:
        """Sync local time with exchange server time."""
        try:
            await self._exchange.load_time_difference()
            self._last_time_sync = time.time()
            time_diff = self._exchange.options.get("timeDifference", 0)
            self._logger.info(
                "time_sync",
                time_difference_ms=time_diff,
                message="Synchronized with exchange server time",
            )
        except Exception as e:
            self._logger.warning("time_sync_failed", error=str(e))

    async def ensure_time_sync(self) -> None:
        """Re-sync time if interval has passed. Call before sensitive operations."""
        if time.time() - self._last_time_sync > TIME_SYNC_INTERVAL_SECONDS:
            self._logger.debug("time_sync_interval_reached")
            await self._sync_time()

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Get current ticker for symbol."""
        try:
            raw = await self.exchange.fetch_ticker(symbol)
            return self._convert_ticker(raw)
        except ccxt.BadSymbol as e:
            raise InvalidOrderError(f"Invalid symbol: {symbol}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch ticker: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_balance(self) -> dict[str, Balance]:
        """Get account balances."""
        try:
            raw = await self.exchange.fetch_balance()
            return self._convert_balances(raw)
        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch balance: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def create_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        """Place a new order."""
        # Validate and adjust order parameters
        adjusted_amount, adjusted_price = self._prepare_order_params(
            symbol, amount, price
        )

        try:
            raw = await self.exchange.create_order(
                symbol=symbol,
                type=order_type.value,
                side=side.value,
                amount=float(adjusted_amount),
                price=float(adjusted_price) if adjusted_price else None,
            )

            order = self._convert_order(raw)

            self._logger.info(
                "order_created",
                order_id=order.id,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                amount=str(adjusted_amount),
                price=str(adjusted_price) if adjusted_price else "market",
            )

            return order

        except ccxt.InsufficientFunds as e:
            raise InsufficientFundsError(f"Insufficient funds: {e}") from e
        except ccxt.InvalidOrder as e:
            raise InvalidOrderError(f"Invalid order: {e}") from e
        except ccxt.AuthenticationError as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to create order: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def cancel_order(self, order_id: str, symbol: str) -> Order:
        """Cancel an existing order."""
        try:
            raw = await self.exchange.cancel_order(order_id, symbol)
            order = self._convert_order(raw)

            self._logger.info(
                "order_cancelled",
                order_id=order_id,
                symbol=symbol,
            )

            return order

        except ccxt.OrderNotFound as e:
            raise OrderNotFoundError(f"Order not found: {order_id}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to cancel order: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_order(self, order_id: str, symbol: str) -> Order:
        """Get order status."""
        try:
            raw = await self.exchange.fetch_order(order_id, symbol)
            return self._convert_order(raw)
        except ccxt.OrderNotFound as e:
            raise OrderNotFoundError(f"Order not found: {order_id}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch order: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get all open orders."""
        await self.ensure_time_sync()
        try:
            raw_orders = await self.exchange.fetch_open_orders(symbol)
            return [self._convert_order(o) for o in raw_orders]
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch open orders: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[OHLCV]:
        """Get OHLCV candle data."""
        try:
            raw_ohlcv = await self.exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, limit=limit
            )
            return [self._convert_ohlcv(candle) for candle in raw_ohlcv]
        except ccxt.BadSymbol as e:
            raise InvalidOrderError(f"Invalid symbol: {symbol}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch OHLCV: {e}") from e

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_my_trades(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list["Trade"]:
        """Get recent trades for a symbol from exchange."""
        from crypto_bot.exchange.base_exchange import Trade

        try:
            raw_trades = await self.exchange.fetch_my_trades(symbol, limit=limit)
            trades = []
            for t in raw_trades:
                trades.append(Trade(
                    id=str(t.get("id", "")),
                    order_id=str(t.get("order")) if t.get("order") else None,
                    symbol=t.get("symbol", symbol),
                    side=OrderSide(t.get("side", "buy")),
                    amount=Decimal(str(t.get("amount", 0))),
                    price=Decimal(str(t.get("price", 0))),
                    cost=Decimal(str(t.get("cost", 0))),
                    fee=Decimal(str(t.get("fee", {}).get("cost", 0))) if t.get("fee") else None,
                    timestamp=datetime.fromtimestamp(t.get("timestamp", 0) / 1000, tz=UTC),
                ))
            return trades
        except ccxt.BadSymbol as e:
            raise InvalidOrderError(f"Invalid symbol: {symbol}") from e
        except ccxt.BaseError as e:
            raise ExchangeError(f"Failed to fetch trades: {e}") from e

    def _prepare_order_params(
        self,
        symbol: str,
        amount: Decimal,
        price: Decimal | None,
    ) -> tuple[Decimal, Decimal | None]:
        """Validate and adjust order parameters for exchange precision.

        Args:
            symbol: Trading pair symbol.
            amount: Desired order amount.
            price: Desired order price (optional).

        Returns:
            Tuple of (adjusted_amount, adjusted_price).
        """
        market = self._markets.get(symbol)
        if not market:
            # If market not found, return original values
            return amount, price

        precision = market.get("precision", {})
        limits = market.get("limits", {})

        # Adjust amount precision
        amount_precision = precision.get("amount")
        if amount_precision is not None:
            adjusted_amount = self._round_to_precision(amount, amount_precision)
        else:
            adjusted_amount = amount

        # Check minimum amount
        min_amount = limits.get("amount", {}).get("min")
        if min_amount and adjusted_amount < Decimal(str(min_amount)):
            raise InvalidOrderError(
                f"Order amount {adjusted_amount} below minimum {min_amount}"
            )

        # Adjust price precision
        adjusted_price = price
        if price is not None:
            price_precision = precision.get("price")
            if price_precision is not None:
                adjusted_price = self._round_to_precision(price, price_precision)

        return adjusted_amount, adjusted_price

    @staticmethod
    def _round_to_precision(value: Decimal, precision: int | float) -> Decimal:
        """Round value to exchange's required precision.

        Args:
            value: The value to round.
            precision: Number of decimal places or step size.

        Returns:
            Rounded Decimal value.
        """
        if isinstance(precision, int):
            quantize_str = f"0.{'0' * precision}"
        else:
            # Handle step size (e.g., 0.001)
            quantize_str = str(precision)
        return value.quantize(Decimal(quantize_str))

    def _convert_ticker(self, raw: dict[str, Any]) -> Ticker:
        """Convert CCXT ticker response to Ticker dataclass."""
        return Ticker(
            symbol=raw["symbol"],
            bid=Decimal(str(raw["bid"])) if raw.get("bid") else Decimal("0"),
            ask=Decimal(str(raw["ask"])) if raw.get("ask") else Decimal("0"),
            last=Decimal(str(raw["last"])) if raw.get("last") else Decimal("0"),
            timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, tz=UTC),
        )

    def _convert_balances(self, raw: dict[str, Any]) -> dict[str, Balance]:
        """Convert CCXT balance response to Balance dataclasses."""
        balances: dict[str, Balance] = {}

        for currency, data in raw.items():
            # Skip non-currency keys (like 'info', 'timestamp', etc.)
            if not isinstance(data, dict) or "free" not in data:
                continue

            free = Decimal(str(data.get("free") or 0))
            used = Decimal(str(data.get("used") or 0))
            total = Decimal(str(data.get("total") or 0))

            # Only include currencies with non-zero balance
            if total > 0:
                balances[currency] = Balance(
                    currency=currency,
                    free=free,
                    used=used,
                    total=total,
                )

        return balances

    def _convert_order(self, raw: dict[str, Any]) -> Order:
        """Convert CCXT order response to Order dataclass."""
        return Order(
            id=raw["id"],
            client_order_id=raw.get("clientOrderId"),
            symbol=raw["symbol"],
            side=OrderSide(raw["side"]),
            order_type=OrderType(raw["type"]),
            status=self._convert_order_status(raw["status"]),
            price=Decimal(str(raw["price"])) if raw.get("price") else None,
            amount=Decimal(str(raw["amount"])),
            filled=Decimal(str(raw.get("filled") or 0)),
            remaining=Decimal(str(raw.get("remaining") or raw["amount"])),
            cost=Decimal(str(raw.get("cost") or 0)),
            fee=self._extract_fee(raw.get("fee")),
            timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, tz=UTC),
        )

    @staticmethod
    def _convert_order_status(status: str) -> OrderStatus:
        """Convert CCXT order status to OrderStatus enum."""
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.CLOSED,
            "canceled": OrderStatus.CANCELED,
            "cancelled": OrderStatus.CANCELED,
            "expired": OrderStatus.EXPIRED,
        }
        return status_map.get(status.lower(), OrderStatus.OPEN)

    @staticmethod
    def _extract_fee(fee_data: dict[str, Any] | None) -> Decimal | None:
        """Extract fee amount from CCXT fee structure."""
        if fee_data and "cost" in fee_data:
            return Decimal(str(fee_data["cost"]))
        return None

    def _convert_ohlcv(self, candle: list[Any]) -> OHLCV:
        """Convert CCXT OHLCV candle to OHLCV dataclass."""
        return OHLCV(
            timestamp=datetime.fromtimestamp(candle[0] / 1000, tz=UTC),
            open=Decimal(str(candle[1])),
            high=Decimal(str(candle[2])),
            low=Decimal(str(candle[3])),
            close=Decimal(str(candle[4])),
            volume=Decimal(str(candle[5])),
        )
