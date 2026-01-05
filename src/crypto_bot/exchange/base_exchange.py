"""Abstract exchange interface and data models."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """Order status enumeration."""

    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Ticker:
    """Immutable ticker data from exchange."""

    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Balance:
    """Immutable balance data for a currency."""

    currency: str
    free: Decimal
    used: Decimal
    total: Decimal


@dataclass
class Order:
    """Order data from exchange."""

    id: str
    client_order_id: str | None
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: Decimal | None
    amount: Decimal
    filled: Decimal
    remaining: Decimal
    cost: Decimal
    fee: Decimal | None
    timestamp: datetime


@dataclass(frozen=True)
class OHLCV:
    """Immutable OHLCV candle data."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class Trade:
    """Immutable trade data from exchange."""

    id: str
    order_id: str | None
    symbol: str
    side: OrderSide
    amount: Decimal
    price: Decimal
    cost: Decimal
    fee: Decimal | None
    timestamp: datetime


class ExchangeError(Exception):
    """Base exception for exchange errors."""

    pass


class AuthenticationError(ExchangeError):
    """API key or signature invalid."""

    pass


class InsufficientFundsError(ExchangeError):
    """Not enough balance for order."""

    pass


class OrderNotFoundError(ExchangeError):
    """Order ID does not exist."""

    pass


class RateLimitError(ExchangeError):
    """Rate limit exceeded."""

    pass


class InvalidOrderError(ExchangeError):
    """Invalid order parameters."""

    pass


class BaseExchange(ABC):
    """Abstract base class defining the exchange interface.

    All exchange implementations must inherit from this class and
    implement all abstract methods. This ensures strategies remain
    exchange-agnostic.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection and load markets.

        Should be called before any other operations. Implementations
        should load market data and validate API credentials.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connections and resources.

        Should be called when shutting down to properly close
        any open connections.
        """

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Get current ticker for symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").

        Returns:
            Ticker data with bid, ask, and last prices.

        Raises:
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def fetch_balance(self) -> dict[str, Balance]:
        """Get account balances for all currencies.

        Returns:
            Dictionary mapping currency codes to Balance objects.

        Raises:
            AuthenticationError: If API credentials are invalid.
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        """Place a new order.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            order_type: MARKET or LIMIT.
            side: BUY or SELL.
            amount: Order quantity in base currency.
            price: Limit price (required for LIMIT orders).

        Returns:
            The created Order object.

        Raises:
            InsufficientFundsError: If balance is insufficient.
            InvalidOrderError: If order parameters are invalid.
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> Order:
        """Cancel an existing order.

        Args:
            order_id: The exchange order ID.
            symbol: Trading pair symbol.

        Returns:
            The cancelled Order object.

        Raises:
            OrderNotFoundError: If order does not exist.
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def fetch_order(self, order_id: str, symbol: str) -> Order:
        """Get order status and details.

        Args:
            order_id: The exchange order ID.
            symbol: Trading pair symbol.

        Returns:
            The Order object with current status.

        Raises:
            OrderNotFoundError: If order does not exist.
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def fetch_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Get all open orders.

        Args:
            symbol: Optional symbol filter. If None, returns all open orders.

        Returns:
            List of open Order objects.

        Raises:
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[OHLCV]:
        """Get OHLCV candle data.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h", "1d").
            limit: Maximum number of candles to return.

        Returns:
            List of OHLCV candle data, oldest first.

        Raises:
            ExchangeError: If the request fails.
        """

    @abstractmethod
    async def fetch_my_trades(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[Trade]:
        """Get recent trades for a symbol.

        Args:
            symbol: Trading pair symbol.
            limit: Maximum number of trades to return.

        Returns:
            List of Trade objects, most recent first.

        Raises:
            ExchangeError: If the request fails.
        """
