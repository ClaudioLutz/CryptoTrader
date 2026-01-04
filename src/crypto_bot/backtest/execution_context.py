"""Execution context protocol for backtest/live trading abstraction.

The ExecutionContext protocol defines the interface that strategies use
to interact with the execution environment. By using this abstraction,
the same strategy code can run unchanged in:
- Live trading
- Paper trading (dry-run)
- Backtesting

This is the adapter pattern - strategies depend only on this protocol,
not on specific exchange implementations or backtest engines.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ExecutionContext(Protocol):
    """Abstract interface for order execution.

    All execution environments (live, paper, backtest) must implement
    this protocol. Strategies interact only through this interface.

    Example:
        >>> class MyStrategy:
        ...     async def on_signal(self, context: ExecutionContext):
        ...         price = await context.get_current_price("BTC/USDT")
        ...         if price < threshold:
        ...             await context.place_order("BTC/USDT", "buy", amount)
    """

    @property
    def timestamp(self) -> datetime:
        """Current simulation/market timestamp.

        For live trading, this is current time.
        For backtesting, this is the simulated timestamp.

        Returns:
            Current timestamp in the execution context.
        """
        ...

    @property
    def is_live(self) -> bool:
        """Whether this is live trading.

        Returns:
            True for live/paper trading, False for backtesting.
        """
        ...

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price for symbol.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").

        Returns:
            Current last traded price.

        Raises:
            ValueError: If symbol is not supported.
        """
        ...

    async def get_balance(self, currency: str) -> Decimal:
        """Get available balance for currency.

        Args:
            currency: Currency code (e.g., "BTC", "USDT").

        Returns:
            Available (free) balance for the currency.
        """
        ...

    async def get_position(self, symbol: str) -> Optional[Decimal]:
        """Get current position size for symbol.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Position size in base currency, None if no position.
        """
        ...

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "limit",
    ) -> str:
        """Place an order.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").
            side: "buy" or "sell".
            amount: Order quantity in base currency.
            price: Limit price (None for market order).
            order_type: "limit" or "market".

        Returns:
            Order ID assigned by the execution context.

        Raises:
            InsufficientFundsError: If balance is insufficient.
            InvalidOrderError: If order parameters are invalid.
        """
        ...

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: The order ID to cancel.
            symbol: Trading pair symbol.

        Returns:
            True if cancelled, False if not found or already filled.
        """
        ...

    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Get order status and fill information.

        Args:
            order_id: The order ID to check.
            symbol: Trading pair symbol.

        Returns:
            Dictionary with order status:
            - id: Order ID
            - status: "open", "closed", "canceled"
            - filled: Amount filled
            - remaining: Amount remaining
            - price: Execution price (if filled)
            - fee: Trading fee paid

        Raises:
            OrderNotFoundError: If order does not exist.
        """
        ...

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Get all open orders.

        Args:
            symbol: Optional symbol filter. If None, returns all open orders.

        Returns:
            List of order dictionaries with:
            - id: Order ID
            - symbol: Trading pair
            - side: "buy" or "sell"
            - amount: Order quantity
            - price: Limit price
            - type: Order type
        """
        ...


@runtime_checkable
class ExtendedExecutionContext(ExecutionContext, Protocol):
    """Extended execution context with additional capabilities.

    Provides additional methods useful for advanced strategies
    and backtesting analysis.
    """

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[dict]:
        """Get OHLCV candle data.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h", "1d").
            limit: Maximum number of candles.

        Returns:
            List of OHLCV dictionaries with:
            - timestamp: Candle timestamp
            - open, high, low, close: Price data
            - volume: Trading volume
        """
        ...

    async def get_ticker(self, symbol: str) -> dict:
        """Get current ticker data.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Dictionary with:
            - symbol: Trading pair
            - bid: Best bid price
            - ask: Best ask price
            - last: Last traded price
            - volume_24h: 24-hour volume
            - timestamp: Ticker timestamp
        """
        ...

    async def get_portfolio_value(self, quote_currency: str = "USDT") -> Decimal:
        """Get total portfolio value in quote currency.

        Args:
            quote_currency: Currency to value portfolio in.

        Returns:
            Total portfolio value.
        """
        ...

    async def get_all_balances(self) -> dict[str, Decimal]:
        """Get all non-zero balances.

        Returns:
            Dictionary mapping currency -> balance.
        """
        ...
