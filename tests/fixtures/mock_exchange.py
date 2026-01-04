"""Mock exchange for testing."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

from crypto_bot.exchange.base_exchange import (
    Balance,
    BaseExchange,
    InsufficientFundsError,
    InvalidOrderError,
    OHLCV,
    Order,
    OrderNotFoundError,
    OrderSide,
    OrderStatus,
    OrderType,
    Ticker,
)


class MockExchange(BaseExchange):
    """Mock exchange for unit testing.

    Simulates exchange behavior without making real API calls.
    Supports configurable responses and failure injection.
    """

    def __init__(
        self,
        initial_balances: Optional[dict[str, Decimal]] = None,
        ticker_data: Optional[dict[str, Ticker]] = None,
    ) -> None:
        """Initialize mock exchange.

        Args:
            initial_balances: Starting balances by currency.
            ticker_data: Ticker data by symbol.
        """
        self._connected = False
        self._balances: dict[str, Decimal] = initial_balances or {
            "USDT": Decimal("10000"),
            "BTC": Decimal("0.5"),
        }
        self._tickers = ticker_data or {}
        self._orders: dict[str, Order] = {}
        self._order_counter = 0
        self._fail_next_call: Optional[Exception] = None

    def inject_failure(self, exception: Exception) -> None:
        """Inject a failure for the next API call.

        Args:
            exception: Exception to raise on next call.
        """
        self._fail_next_call = exception

    def _check_failure(self) -> None:
        """Check and raise any injected failure."""
        if self._fail_next_call:
            exc = self._fail_next_call
            self._fail_next_call = None
            raise exc

    async def connect(self) -> None:
        """Simulate connection."""
        self._check_failure()
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Return mock ticker data."""
        self._check_failure()

        if symbol in self._tickers:
            return self._tickers[symbol]

        # Default mock ticker
        return Ticker(
            symbol=symbol,
            bid=Decimal("50000"),
            ask=Decimal("50001"),
            last=Decimal("50000.5"),
            timestamp=datetime.now(UTC),
        )

    async def fetch_balance(self) -> dict[str, Balance]:
        """Return mock balances."""
        self._check_failure()

        return {
            currency: Balance(
                currency=currency,
                free=amount,
                used=Decimal("0"),
                total=amount,
            )
            for currency, amount in self._balances.items()
        }

    async def create_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: Decimal,
        price: Optional[Decimal] = None,
    ) -> Order:
        """Create mock order."""
        self._check_failure()

        # Validate order
        base, quote = symbol.split("/")

        if side == OrderSide.BUY:
            required = amount * (price or Decimal("50000"))
            if self._balances.get(quote, Decimal("0")) < required:
                raise InsufficientFundsError(f"Insufficient {quote}")
        else:
            if self._balances.get(base, Decimal("0")) < amount:
                raise InsufficientFundsError(f"Insufficient {base}")

        # Create order
        self._order_counter += 1
        order_id = f"mock_order_{self._order_counter}"

        order = Order(
            id=order_id,
            client_order_id=None,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=OrderStatus.OPEN,
            price=price,
            amount=amount,
            filled=Decimal("0"),
            remaining=amount,
            cost=Decimal("0"),
            fee=None,
            timestamp=datetime.now(UTC),
        )

        self._orders[order_id] = order
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> Order:
        """Cancel mock order."""
        self._check_failure()

        if order_id not in self._orders:
            raise OrderNotFoundError(f"Order {order_id} not found")

        order = self._orders[order_id]
        order.status = OrderStatus.CANCELED
        return order

    async def fetch_order(self, order_id: str, symbol: str) -> Order:
        """Fetch mock order."""
        self._check_failure()

        if order_id not in self._orders:
            raise OrderNotFoundError(f"Order {order_id} not found")

        return self._orders[order_id]

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Fetch mock open orders."""
        self._check_failure()

        orders = [o for o in self._orders.values() if o.status == OrderStatus.OPEN]

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return orders

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[OHLCV]:
        """Return mock OHLCV data."""
        self._check_failure()

        candles = []
        base_price = Decimal("50000")
        now = datetime.now(UTC)

        for i in range(limit):
            price = base_price + Decimal(str(i * 10))
            candles.append(
                OHLCV(
                    timestamp=now,
                    open=price,
                    high=price + Decimal("100"),
                    low=price - Decimal("100"),
                    close=price + Decimal("50"),
                    volume=Decimal("100"),
                )
            )

        return candles

    def fill_order(self, order_id: str, fill_amount: Optional[Decimal] = None) -> None:
        """Simulate order fill (for testing).

        Args:
            order_id: Order to fill.
            fill_amount: Amount to fill. If None, fills entire order.
        """
        if order_id not in self._orders:
            return

        order = self._orders[order_id]
        fill = fill_amount or order.remaining

        order.filled += fill
        order.remaining -= fill

        if order.remaining <= 0:
            order.status = OrderStatus.CLOSED

        # Update balances
        base, quote = order.symbol.split("/")
        price = order.price or Decimal("50000")

        if order.side == OrderSide.BUY:
            self._balances[base] = self._balances.get(base, Decimal("0")) + fill
            self._balances[quote] = self._balances.get(quote, Decimal("0")) - (fill * price)
        else:
            self._balances[base] = self._balances.get(base, Decimal("0")) - fill
            self._balances[quote] = self._balances.get(quote, Decimal("0")) + (fill * price)

    # Additional test helper methods
    def set_price(self, symbol: str, price: Decimal) -> None:
        """Set price for a symbol.

        Args:
            symbol: Trading pair symbol.
            price: New price.
        """
        self._tickers[symbol] = Ticker(
            symbol=symbol,
            bid=price - Decimal("0.5"),
            ask=price + Decimal("0.5"),
            last=price,
            timestamp=datetime.now(UTC),
        )

    def set_balance(self, currency: str, amount: Decimal) -> None:
        """Set balance for a currency.

        Args:
            currency: Currency code.
            amount: New balance.
        """
        self._balances[currency] = amount

    def get_balance(self, currency: str) -> Decimal:
        """Get balance for a currency.

        Args:
            currency: Currency code.

        Returns:
            Balance amount.
        """
        return self._balances.get(currency, Decimal("0"))

    def reset(self) -> None:
        """Reset mock state."""
        self._orders.clear()
        self._order_counter = 0
        self._fail_next_call = None

    @property
    def order_count(self) -> int:
        """Get total number of orders created."""
        return self._order_counter

    @property
    def open_orders(self) -> list[Order]:
        """Get all open orders."""
        return [o for o in self._orders.values() if o.status == OrderStatus.OPEN]

    @property
    def closed_orders(self) -> list[Order]:
        """Get all closed orders."""
        return [o for o in self._orders.values() if o.status == OrderStatus.CLOSED]
