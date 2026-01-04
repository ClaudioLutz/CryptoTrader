"""Simulated execution context for backtesting.

Provides an ExecutionContext implementation that simulates order
execution against historical data. Uses fee and slippage models
for realistic simulation.

Features:
- Simulated order execution with fees and slippage
- Balance and position tracking
- Limit order processing on price updates
- Trade history for analysis
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog

from crypto_bot.backtest.simulation import (
    FeeCalculator,
    FeeConfig,
    SlippageModel,
    FixedSlippage,
)

logger = structlog.get_logger()


@dataclass
class SimulatedOrder:
    """Represents a simulated order in backtest.

    Attributes:
        id: Order identifier.
        symbol: Trading pair symbol.
        side: "buy" or "sell".
        order_type: "limit" or "market".
        amount: Order quantity.
        price: Limit price (None for market).
        filled: Amount filled.
        status: "open", "closed", "canceled".
        created_at: Order creation timestamp.
        filled_at: Fill timestamp (if filled).
        fill_price: Actual execution price.
        fee: Fee paid.
    """

    id: str
    symbol: str
    side: str
    order_type: str
    amount: Decimal
    price: Optional[Decimal]
    filled: Decimal = Decimal(0)
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    fill_price: Optional[Decimal] = None
    fee: Decimal = Decimal(0)


class BacktestContext:
    """Simulated execution context for backtesting.

    Implements the ExecutionContext protocol for use in backtesting.
    Tracks balances, positions, and orders while simulating realistic
    execution with fees and slippage.

    Example:
        >>> context = BacktestContext(
        ...     initial_balance={"USDT": Decimal("10000")},
        ...     fee_rate=Decimal("0.001"),
        ... )
        >>> # Simulate market state
        >>> context.set_market_state(timestamp, {"BTC/USDT": Decimal("50000")})
        >>> # Place order
        >>> order_id = await context.place_order("BTC/USDT", "buy", Decimal("0.1"))
    """

    def __init__(
        self,
        initial_balance: dict[str, Decimal],
        fee_rate: Decimal = Decimal("0.001"),
        slippage_rate: Decimal = Decimal("0.0005"),
        slippage_model: Optional[SlippageModel] = None,
        fee_calculator: Optional[FeeCalculator] = None,
    ) -> None:
        """Initialize backtest execution context.

        Args:
            initial_balance: Initial balances by currency.
            fee_rate: Fee rate (if not using fee_calculator).
            slippage_rate: Slippage rate (if not using slippage_model).
            slippage_model: Custom slippage model.
            fee_calculator: Custom fee calculator.
        """
        self._initial_balance = initial_balance.copy()
        self._balance = initial_balance.copy()
        self._positions: dict[str, Decimal] = {}

        # Fee and slippage models
        self._slippage_model = slippage_model or FixedSlippage(rate=slippage_rate)
        self._fee_calculator = fee_calculator or FeeCalculator(
            FeeConfig(taker_rate=fee_rate, maker_rate=fee_rate)
        )

        # Order tracking
        self._orders: dict[str, SimulatedOrder] = {}
        self._order_counter = 0

        # Trade history
        self._trades: list[dict] = []

        # Market state
        self._current_timestamp: datetime = datetime.utcnow()
        self._current_prices: dict[str, Decimal] = {}
        self._current_volumes: dict[str, Decimal] = {}

        self._logger = logger.bind(component="backtest_context")

    @property
    def timestamp(self) -> datetime:
        """Get current simulation timestamp."""
        return self._current_timestamp

    @property
    def is_live(self) -> bool:
        """This is not live trading."""
        return False

    def set_market_state(
        self,
        timestamp: datetime,
        prices: dict[str, Decimal],
        volumes: Optional[dict[str, Decimal]] = None,
    ) -> None:
        """Update market state for current bar.

        Should be called for each new candle/tick in the backtest.

        Args:
            timestamp: Current timestamp.
            prices: Current prices by symbol.
            volumes: Current volumes by symbol (optional).
        """
        self._current_timestamp = timestamp
        self._current_prices = prices
        self._current_volumes = volumes or {}

        # Process pending limit orders
        self._process_pending_orders()

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price for symbol.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Current price.

        Raises:
            ValueError: If no price data for symbol.
        """
        if symbol not in self._current_prices:
            raise ValueError(f"No price data for {symbol}")
        return self._current_prices[symbol]

    async def get_balance(self, currency: str) -> Decimal:
        """Get available balance for currency.

        Args:
            currency: Currency code.

        Returns:
            Available balance (0 if none).
        """
        return self._balance.get(currency, Decimal(0))

    async def get_position(self, symbol: str) -> Optional[Decimal]:
        """Get current position for symbol.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Position size, None if no position.
        """
        pos = self._positions.get(symbol, Decimal(0))
        return pos if pos != 0 else None

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "limit",
    ) -> str:
        """Place a simulated order.

        Market orders fill immediately with slippage.
        Limit orders are queued and processed on price updates.

        Args:
            symbol: Trading pair symbol.
            side: "buy" or "sell".
            amount: Order quantity.
            price: Limit price (None for market).
            order_type: "limit" or "market".

        Returns:
            Order ID.

        Raises:
            ValueError: If insufficient balance.
        """
        # Generate order ID
        self._order_counter += 1
        order_id = f"BT_{self._order_counter}"

        # Determine order type
        if price is None:
            order_type = "market"

        order = SimulatedOrder(
            id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            created_at=self._current_timestamp,
        )
        self._orders[order_id] = order

        self._logger.debug(
            "order_placed",
            order_id=order_id,
            symbol=symbol,
            side=side,
            amount=str(amount),
            price=str(price) if price else "market",
        )

        # Market orders fill immediately
        if order_type == "market":
            if symbol not in self._current_prices:
                raise ValueError(f"No price data for {symbol}")
            self._fill_order(order, self._current_prices[symbol])

        return order_id

    def _fill_order(self, order: SimulatedOrder, market_price: Decimal) -> None:
        """Simulate order fill with slippage and fees.

        Args:
            order: Order to fill.
            market_price: Current market price.
        """
        # Get volume for slippage calculation
        volume = self._current_volumes.get(order.symbol)

        # Apply slippage
        fill_price = self._slippage_model.calculate(
            price=market_price,
            amount=order.amount,
            side=order.side,
            volume=volume,
        )

        # For limit orders, use limit price if better
        if order.price is not None:
            if order.side == "buy" and order.price < fill_price:
                fill_price = order.price
            elif order.side == "sell" and order.price > fill_price:
                fill_price = order.price

        # Calculate fee
        is_maker = order.order_type == "limit"
        fee = self._fee_calculator.calculate(order.amount, fill_price, is_maker)

        # Update order
        order.filled = order.amount
        order.fill_price = fill_price
        order.fee = fee
        order.status = "closed"
        order.filled_at = self._current_timestamp

        # Update balance and position
        base, quote = order.symbol.split("/")

        if order.side == "buy":
            cost = fill_price * order.amount + fee
            if self._balance.get(quote, Decimal(0)) < cost:
                self._logger.warning(
                    "insufficient_balance",
                    required=str(cost),
                    available=str(self._balance.get(quote, 0)),
                )
                order.status = "canceled"
                return

            self._balance[quote] = self._balance.get(quote, Decimal(0)) - cost
            self._positions[order.symbol] = (
                self._positions.get(order.symbol, Decimal(0)) + order.amount
            )
        else:
            proceeds = fill_price * order.amount - fee
            self._balance[quote] = self._balance.get(quote, Decimal(0)) + proceeds
            self._positions[order.symbol] = (
                self._positions.get(order.symbol, Decimal(0)) - order.amount
            )

        # Record trade
        self._trades.append({
            "timestamp": self._current_timestamp,
            "symbol": order.symbol,
            "side": order.side,
            "amount": order.amount,
            "price": fill_price,
            "fee": fee,
            "order_id": order.id,
            "order_type": order.order_type,
        })

        self._logger.debug(
            "order_filled",
            order_id=order.id,
            fill_price=str(fill_price),
            fee=str(fee),
        )

    def _process_pending_orders(self) -> None:
        """Process pending limit orders against current prices."""
        for order in list(self._orders.values()):
            if order.status != "open" or order.order_type != "limit":
                continue

            symbol = order.symbol
            if symbol not in self._current_prices:
                continue

            current_price = self._current_prices[symbol]

            # Check if limit order can fill
            can_fill = False
            if order.side == "buy" and current_price <= order.price:
                can_fill = True
            elif order.side == "sell" and current_price >= order.price:
                can_fill = True

            if can_fill:
                self._fill_order(order, current_price)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Order ID to cancel.
            symbol: Trading pair symbol (unused but required by protocol).

        Returns:
            True if cancelled, False if not found or already filled.
        """
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status == "open":
                order.status = "canceled"
                self._logger.debug("order_canceled", order_id=order_id)
                return True
        return False

    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Get order status.

        Args:
            order_id: Order ID.
            symbol: Trading pair symbol (unused).

        Returns:
            Order status dictionary.

        Raises:
            ValueError: If order not found.
        """
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")

        order = self._orders[order_id]
        return {
            "id": order.id,
            "status": order.status,
            "filled": order.filled,
            "remaining": order.amount - order.filled,
            "price": order.fill_price,
            "fee": order.fee,
        }

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Get all open orders.

        Args:
            symbol: Optional symbol filter.

        Returns:
            List of open order dictionaries.
        """
        result = []
        for order in self._orders.values():
            if order.status == "open":
                if symbol is None or order.symbol == symbol:
                    result.append({
                        "id": order.id,
                        "symbol": order.symbol,
                        "side": order.side,
                        "amount": order.amount,
                        "price": order.price,
                        "type": order.order_type,
                    })
        return result

    def get_portfolio_value(self, quote_currency: str = "USDT") -> Decimal:
        """Calculate total portfolio value in quote currency.

        Args:
            quote_currency: Currency to value portfolio in.

        Returns:
            Total portfolio value.
        """
        total = self._balance.get(quote_currency, Decimal(0))

        for symbol, amount in self._positions.items():
            if amount != 0 and symbol in self._current_prices:
                total += amount * self._current_prices[symbol]

        return total

    def get_trade_history(self) -> list[dict]:
        """Get all executed trades.

        Returns:
            List of trade dictionaries.
        """
        return self._trades.copy()

    def get_metrics(self) -> dict:
        """Get backtest summary metrics.

        Returns:
            Dictionary with summary metrics.
        """
        initial_value = sum(self._initial_balance.values())
        final_value = self.get_portfolio_value()

        return {
            "initial_balance": initial_value,
            "final_balance": final_value,
            "total_return": (
                (final_value - initial_value) / initial_value
                if initial_value > 0 else Decimal(0)
            ),
            "total_trades": len(self._trades),
            "total_fees": sum(t["fee"] for t in self._trades),
        }

    def get_balances(self) -> dict[str, Decimal]:
        """Get all balances.

        Returns:
            Dictionary of currency -> balance.
        """
        return self._balance.copy()

    def get_positions(self) -> dict[str, Decimal]:
        """Get all positions.

        Returns:
            Dictionary of symbol -> position size.
        """
        return {k: v for k, v in self._positions.items() if v != 0}

    def reset(self) -> None:
        """Reset context to initial state."""
        self._balance = self._initial_balance.copy()
        self._positions.clear()
        self._orders.clear()
        self._trades.clear()
        self._order_counter = 0
        self._logger.info("backtest_context_reset")
