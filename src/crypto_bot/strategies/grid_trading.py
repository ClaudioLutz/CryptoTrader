"""Grid trading strategy implementation.

Grid trading profits from price oscillations by placing buy orders below
the current price and sell orders above. When a buy fills, a sell is placed
at the next level up. When a sell fills, profit is recorded and a new buy
is placed.

Supports two spacing modes:
- Arithmetic: Equal dollar intervals (best for stable pairs)
- Geometric: Equal percentage intervals (best for volatile assets like BTC)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import structlog
from pydantic import Field, field_validator

from crypto_bot.exchange.base_exchange import Order, OrderSide, OrderStatus, Ticker
from crypto_bot.strategies.base_strategy import (
    ExecutionContext,
    StrategyConfig,
    StrategyFactory,
)

logger = structlog.get_logger()


# =============================================================================
# Grid Configuration (Story 2.2)
# =============================================================================


class GridSpacing(str, Enum):
    """Grid spacing type."""

    ARITHMETIC = "arithmetic"  # Equal dollar intervals
    GEOMETRIC = "geometric"  # Equal percentage intervals


class GridConfig(StrategyConfig):
    """Configuration for grid trading strategy.

    Attributes:
        lower_price: Lower boundary of the grid range.
        upper_price: Upper boundary of the grid range.
        num_grids: Number of grid levels (3-100).
        total_investment: Total capital to allocate to the grid.
        spacing: Arithmetic or geometric spacing.
        stop_loss_pct: Percentage below lower_price to trigger stop-loss.
        take_profit_pct: Optional percentage above upper_price for take-profit.
        cancel_on_stop: Whether to cancel all orders on stop-loss.
    """

    name: str = Field(default="grid", description="Strategy type")
    lower_price: Decimal = Field(..., gt=0, description="Lower grid boundary")
    upper_price: Decimal = Field(..., gt=0, description="Upper grid boundary")
    num_grids: int = Field(default=20, ge=3, le=100, description="Number of grid levels")
    total_investment: Decimal = Field(..., gt=0, description="Total capital allocation")
    spacing: GridSpacing = Field(
        default=GridSpacing.GEOMETRIC,
        description="Grid spacing type",
    )
    stop_loss_pct: Decimal = Field(
        default=Decimal("0.10"),
        ge=0,
        le=1,
        description="Stop-loss percentage below lower_price",
    )
    take_profit_pct: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=1,
        description="Take-profit percentage above upper_price",
    )
    cancel_on_stop: bool = Field(
        default=True,
        description="Cancel all orders on stop-loss trigger",
    )

    @field_validator("upper_price")
    @classmethod
    def upper_must_exceed_lower(cls, v: Decimal, info: Any) -> Decimal:
        """Validate that upper_price exceeds lower_price."""
        if "lower_price" in info.data and v <= info.data["lower_price"]:
            raise ValueError("upper_price must be greater than lower_price")
        return v

    @property
    def grid_range_pct(self) -> Decimal:
        """Calculate percentage range of grid."""
        return (self.upper_price - self.lower_price) / self.lower_price

    @property
    def stop_loss_price(self) -> Decimal:
        """Calculate absolute stop-loss price."""
        return self.lower_price * (1 - self.stop_loss_pct)

    @property
    def take_profit_price(self) -> Optional[Decimal]:
        """Calculate absolute take-profit price if configured."""
        if self.take_profit_pct is None:
            return None
        return self.upper_price * (1 + self.take_profit_pct)


@dataclass
class GridLevel:
    """Represents a single grid level.

    Attributes:
        index: Grid level index (0 = lowest).
        price: Price at this grid level.
        buy_order_id: ID of active buy order at this level.
        sell_order_id: ID of active sell order at this level.
        filled_buy: Whether the buy at this level was filled.
        filled_sell: Whether the sell at this level was filled.
        quantity: Order quantity for this level.
    """

    index: int
    price: Decimal
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    filled_buy: bool = False
    filled_sell: bool = False
    quantity: Decimal = Decimal(0)


def calculate_grid_levels(config: GridConfig) -> list[GridLevel]:
    """Calculate grid price levels based on spacing type.

    Args:
        config: Grid configuration.

    Returns:
        List of GridLevel objects from lowest to highest price.
    """
    levels: list[GridLevel] = []

    if config.spacing == GridSpacing.ARITHMETIC:
        # Equal dollar intervals
        step = (config.upper_price - config.lower_price) / (config.num_grids - 1)
        for i in range(config.num_grids):
            price = config.lower_price + (step * i)
            # Round to reasonable precision (2 decimal places for most pairs)
            price = price.quantize(Decimal("0.01"))
            levels.append(GridLevel(index=i, price=price))
    else:
        # Equal percentage intervals (geometric)
        ratio = (config.upper_price / config.lower_price) ** (
            Decimal(1) / (config.num_grids - 1)
        )
        for i in range(config.num_grids):
            price = config.lower_price * (ratio**i)
            price = price.quantize(Decimal("0.01"))
            levels.append(GridLevel(index=i, price=price))

    return levels


def calculate_order_size(
    config: GridConfig,
    num_active_grids: int,
    reserve_pct: Decimal = Decimal("0.20"),
) -> Decimal:
    """Calculate order size per grid level.

    Allocates investment across active grid levels with a reserve buffer.

    Args:
        config: Grid configuration.
        num_active_grids: Number of grid levels that will have orders.
        reserve_pct: Percentage of capital to hold in reserve (default 20%).

    Returns:
        Order size in quote currency for each grid level.
    """
    if num_active_grids <= 0:
        return Decimal(0)

    # Reserve capital for volatility buffer
    active_capital = config.total_investment * (1 - reserve_pct)
    return (active_capital / num_active_grids).quantize(Decimal("0.00000001"))


def validate_grid_config(
    config: GridConfig, current_price: Decimal
) -> list[str]:
    """Validate grid config against current market conditions.

    Args:
        config: Grid configuration to validate.
        current_price: Current market price.

    Returns:
        List of warning messages (empty if no issues).
    """
    warnings: list[str] = []

    if current_price < config.lower_price:
        warnings.append(
            f"Current price {current_price} below grid range "
            f"(lower: {config.lower_price})"
        )
    if current_price > config.upper_price:
        warnings.append(
            f"Current price {current_price} above grid range "
            f"(upper: {config.upper_price})"
        )
    if config.grid_range_pct > Decimal("0.5"):
        warnings.append(
            f"Grid range {config.grid_range_pct:.0%} is very wide "
            "(consider narrowing for better fill rates)"
        )
    if config.num_grids < 10:
        warnings.append(
            "Less than 10 grids may miss trading opportunities"
        )
    if config.num_grids > 50:
        warnings.append(
            "More than 50 grids may have high fee costs relative to profits"
        )

    return warnings


# =============================================================================
# Grid Trading Strategy (Story 2.3)
# =============================================================================


@dataclass
class GridStatistics:
    """Trading statistics for the grid strategy."""

    total_profit: Decimal = Decimal(0)
    total_fees: Decimal = Decimal(0)
    completed_cycles: int = 0
    buy_fills: int = 0
    sell_fills: int = 0

    @property
    def net_profit(self) -> Decimal:
        """Calculate profit after fees."""
        return self.total_profit - self.total_fees


class GridTradingStrategy:
    """Grid trading strategy implementation.

    Places buy orders below the current price and manages the grid lifecycle:
    1. Buy fills -> place sell at next level up
    2. Sell fills -> record profit, place new buy at original level
    """

    # Fee rate assumption (0.1% per side, typical for major exchanges)
    DEFAULT_FEE_RATE = Decimal("0.001")
    # State version for migrations
    STATE_VERSION = 1

    def __init__(self, config: GridConfig, context: Optional[ExecutionContext] = None):
        """Initialize grid trading strategy.

        Args:
            config: Grid configuration.
            context: Optional execution context (can be set via initialize()).
        """
        self._config = config
        self._context = context
        self._grid_levels: list[GridLevel] = []
        self._active_orders: dict[str, GridLevel] = {}  # order_id -> level
        self._stats = GridStatistics()
        self._initialized = False
        self._stopped = False
        self._logger = logger.bind(
            strategy="grid",
            symbol=config.symbol,
        )

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return f"grid_{self._config.symbol.replace('/', '_')}"

    @property
    def symbol(self) -> str:
        """Trading pair symbol."""
        return self._config.symbol

    @property
    def config(self) -> GridConfig:
        """Get grid configuration."""
        return self._config

    @property
    def statistics(self) -> GridStatistics:
        """Get trading statistics."""
        return self._stats

    @property
    def active_order_count(self) -> int:
        """Number of active orders."""
        return len(self._active_orders)

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize strategy and place initial grid orders.

        Args:
            context: Execution context for order operations.
        """
        self._context = context
        self._grid_levels = calculate_grid_levels(self._config)

        current_price = await context.get_current_price(self.symbol)

        # Validate configuration
        warnings = validate_grid_config(self._config, current_price)
        for warning in warnings:
            self._logger.warning("config_warning", message=warning)

        self._logger.info(
            "grid_initializing",
            current_price=str(current_price),
            num_levels=len(self._grid_levels),
            lower_price=str(self._config.lower_price),
            upper_price=str(self._config.upper_price),
            spacing=self._config.spacing.value,
        )

        # Place buy orders below current price
        await self._place_initial_orders(current_price)
        self._initialized = True

    async def _place_initial_orders(self, current_price: Decimal) -> None:
        """Place buy orders for all grid levels below current price."""
        levels_below = [l for l in self._grid_levels if l.price < current_price]
        if not levels_below:
            self._logger.warning(
                "no_levels_below_price",
                current_price=str(current_price),
            )
            return

        # Calculate order size
        order_size = calculate_order_size(self._config, len(levels_below))

        for level in levels_below:
            # Calculate quantity in base currency
            quantity = order_size / level.price
            quantity = quantity.quantize(Decimal("0.00000001"))
            level.quantity = quantity

            try:
                order_id = await self._context.place_order(
                    symbol=self.symbol,
                    side="buy",
                    amount=quantity,
                    price=level.price,
                )
                level.buy_order_id = order_id
                self._active_orders[order_id] = level

                self._logger.info(
                    "grid_order_placed",
                    side="buy",
                    level=level.index,
                    price=str(level.price),
                    quantity=str(quantity),
                    order_id=order_id,
                )
            except Exception as e:
                self._logger.error(
                    "order_placement_failed",
                    level=level.index,
                    price=str(level.price),
                    error=str(e),
                )

    async def on_tick(self, ticker: Ticker) -> None:
        """Monitor price and check for stop-loss/take-profit.

        Args:
            ticker: Current ticker data.
        """
        if self._stopped or not self._initialized:
            return

        # Check stop-loss
        if ticker.last < self._config.stop_loss_price:
            self._logger.warning(
                "stop_loss_triggered",
                current_price=str(ticker.last),
                stop_loss=str(self._config.stop_loss_price),
            )
            await self._execute_stop_loss()
            return

        # Check take-profit
        take_profit = self._config.take_profit_price
        if take_profit and ticker.last > take_profit:
            self._logger.info(
                "take_profit_triggered",
                current_price=str(ticker.last),
                take_profit=str(take_profit),
            )
            await self._execute_take_profit()

    async def _execute_stop_loss(self) -> None:
        """Execute stop-loss: cancel orders and stop strategy."""
        self._stopped = True

        if self._config.cancel_on_stop:
            await self._cancel_all_orders()

        self._logger.warning(
            "strategy_stopped",
            reason="stop_loss",
            total_profit=str(self._stats.total_profit),
            completed_cycles=self._stats.completed_cycles,
        )

    async def _execute_take_profit(self) -> None:
        """Execute take-profit: cancel orders and stop strategy."""
        self._stopped = True
        await self._cancel_all_orders()

        self._logger.info(
            "strategy_stopped",
            reason="take_profit",
            total_profit=str(self._stats.total_profit),
            completed_cycles=self._stats.completed_cycles,
        )

    async def _cancel_all_orders(self) -> None:
        """Cancel all active orders."""
        for order_id, level in list(self._active_orders.items()):
            try:
                await self._context.cancel_order(order_id, self.symbol)
                self._logger.info("order_cancelled", order_id=order_id, level=level.index)
            except Exception as e:
                self._logger.error(
                    "cancel_failed",
                    order_id=order_id,
                    error=str(e),
                )
        self._active_orders.clear()

    async def on_order_filled(self, order: Order) -> None:
        """Handle order fill - place counter order.

        Args:
            order: The filled order.
        """
        if order.id not in self._active_orders:
            self._logger.debug("order_not_tracked", order_id=order.id)
            return

        level = self._active_orders.pop(order.id)

        if order.side == OrderSide.BUY:
            await self._handle_buy_fill(level, order)
        elif order.side == OrderSide.SELL:
            await self._handle_sell_fill(level, order)

    async def _handle_buy_fill(self, level: GridLevel, order: Order) -> None:
        """Handle buy order fill - place sell at next level up.

        Args:
            level: The grid level where buy was filled.
            order: The filled buy order.
        """
        level.filled_buy = True
        level.buy_order_id = None
        self._stats.buy_fills += 1

        self._logger.info(
            "buy_filled",
            level=level.index,
            price=str(order.price),
            quantity=str(order.filled),
        )

        # Find next level up for sell order
        next_level = self._get_next_level_up(level)
        if not next_level:
            self._logger.warning(
                "no_level_for_sell",
                level=level.index,
            )
            return

        try:
            sell_order_id = await self._context.place_order(
                symbol=self.symbol,
                side="sell",
                amount=order.filled,
                price=next_level.price,
            )
            level.sell_order_id = sell_order_id
            self._active_orders[sell_order_id] = level

            self._logger.info(
                "grid_counter_order",
                side="sell",
                buy_level=level.index,
                buy_price=str(level.price),
                sell_price=str(next_level.price),
                order_id=sell_order_id,
            )
        except Exception as e:
            self._logger.error(
                "sell_order_failed",
                level=level.index,
                error=str(e),
            )

    async def _handle_sell_fill(self, level: GridLevel, order: Order) -> None:
        """Handle sell order fill - record profit, place new buy.

        Args:
            level: The grid level (original buy level).
            order: The filled sell order.
        """
        level.filled_sell = True
        level.sell_order_id = None
        self._stats.sell_fills += 1
        self._stats.completed_cycles += 1

        # Calculate profit
        profit = self._calculate_profit(level, order)
        self._stats.total_profit += profit

        self._logger.info(
            "grid_cycle_complete",
            level=level.index,
            buy_price=str(level.price),
            sell_price=str(order.price),
            profit=str(profit),
            total_profit=str(self._stats.total_profit),
            completed_cycles=self._stats.completed_cycles,
        )

        # Reset level for new cycle
        level.filled_buy = False
        level.filled_sell = False

        # Place new buy order at this level
        await self._place_buy_at_level(level)

    def _get_next_level_up(self, level: GridLevel) -> Optional[GridLevel]:
        """Get the next grid level above the given level.

        Args:
            level: Current grid level.

        Returns:
            Next level up, or None if at top of grid.
        """
        next_index = level.index + 1
        if next_index >= len(self._grid_levels):
            return None
        return self._grid_levels[next_index]

    async def _place_buy_at_level(self, level: GridLevel) -> None:
        """Place a buy order at the specified grid level.

        Args:
            level: Grid level for the buy order.
        """
        try:
            order_id = await self._context.place_order(
                symbol=self.symbol,
                side="buy",
                amount=level.quantity,
                price=level.price,
            )
            level.buy_order_id = order_id
            self._active_orders[order_id] = level

            self._logger.info(
                "grid_order_placed",
                side="buy",
                level=level.index,
                price=str(level.price),
                quantity=str(level.quantity),
                order_id=order_id,
            )
        except Exception as e:
            self._logger.error(
                "buy_order_failed",
                level=level.index,
                error=str(e),
            )

    def _calculate_profit(self, level: GridLevel, sell_order: Order) -> Decimal:
        """Calculate profit from grid cycle (sell - buy - fees).

        Args:
            level: The buy level.
            sell_order: The filled sell order.

        Returns:
            Net profit after estimated fees.
        """
        buy_price = level.price
        sell_price = sell_order.price or level.price
        amount = sell_order.filled

        gross_profit = (sell_price - buy_price) * amount

        # Estimate fees (actual fees may differ)
        fee_rate = self.DEFAULT_FEE_RATE
        buy_fee = buy_price * amount * fee_rate
        sell_fee = sell_price * amount * fee_rate
        total_fees = buy_fee + sell_fee
        self._stats.total_fees += total_fees

        return gross_profit - total_fees

    async def on_order_cancelled(self, order: Order) -> None:
        """Handle order cancellation.

        Args:
            order: The cancelled order.
        """
        if order.id in self._active_orders:
            level = self._active_orders.pop(order.id)
            self._logger.info(
                "order_cancelled_external",
                order_id=order.id,
                level=level.index,
            )

    def remove_order_from_state(self, order_id: str) -> None:
        """Remove an order from tracked state.

        Used during reconciliation to clean up phantom orders.

        Args:
            order_id: Order ID to remove.
        """
        if order_id in self._active_orders:
            del self._active_orders[order_id]

    def get_state(self) -> dict[str, Any]:
        """Serialize strategy state for persistence.

        Returns:
            Dictionary containing all state needed for restoration.
        """
        return {
            "version": self.STATE_VERSION,
            "config": self._config.model_dump(mode="json"),
            "grid_levels": [
                {
                    "index": level.index,
                    "price": str(level.price),
                    "buy_order_id": level.buy_order_id,
                    "sell_order_id": level.sell_order_id,
                    "filled_buy": level.filled_buy,
                    "filled_sell": level.filled_sell,
                    "quantity": str(level.quantity),
                }
                for level in self._grid_levels
            ],
            "active_orders": list(self._active_orders.keys()),
            "statistics": {
                "total_profit": str(self._stats.total_profit),
                "total_fees": str(self._stats.total_fees),
                "completed_cycles": self._stats.completed_cycles,
                "buy_fills": self._stats.buy_fills,
                "sell_fills": self._stats.sell_fills,
            },
            "initialized": self._initialized,
            "stopped": self._stopped,
        }

    @classmethod
    def from_state(
        cls, state: dict[str, Any], context: ExecutionContext
    ) -> "GridTradingStrategy":
        """Restore strategy from persisted state.

        Args:
            state: Dictionary from get_state().
            context: Execution context for the restored strategy.

        Returns:
            Restored GridTradingStrategy instance.
        """
        # Handle version migrations if needed
        state = cls._migrate_state(state)

        # Restore config
        config = GridConfig(**state["config"])
        strategy = cls(config, context)

        # Restore grid levels
        strategy._grid_levels = [
            GridLevel(
                index=l["index"],
                price=Decimal(l["price"]),
                buy_order_id=l.get("buy_order_id"),
                sell_order_id=l.get("sell_order_id"),
                filled_buy=l.get("filled_buy", False),
                filled_sell=l.get("filled_sell", False),
                quantity=Decimal(l.get("quantity", "0")),
            )
            for l in state["grid_levels"]
        ]

        # Restore active orders mapping
        active_order_ids = set(state.get("active_orders", []))
        for level in strategy._grid_levels:
            if level.buy_order_id and level.buy_order_id in active_order_ids:
                strategy._active_orders[level.buy_order_id] = level
            if level.sell_order_id and level.sell_order_id in active_order_ids:
                strategy._active_orders[level.sell_order_id] = level

        # Restore statistics
        stats = state.get("statistics", {})
        strategy._stats = GridStatistics(
            total_profit=Decimal(stats.get("total_profit", "0")),
            total_fees=Decimal(stats.get("total_fees", "0")),
            completed_cycles=stats.get("completed_cycles", 0),
            buy_fills=stats.get("buy_fills", 0),
            sell_fills=stats.get("sell_fills", 0),
        )

        strategy._initialized = state.get("initialized", False)
        strategy._stopped = state.get("stopped", False)

        strategy._logger.info(
            "strategy_restored",
            levels=len(strategy._grid_levels),
            active_orders=len(strategy._active_orders),
            completed_cycles=strategy._stats.completed_cycles,
        )

        return strategy

    @classmethod
    def _migrate_state(cls, state: dict[str, Any]) -> dict[str, Any]:
        """Migrate state from older versions if needed.

        Args:
            state: State dictionary to migrate.

        Returns:
            Migrated state dictionary.
        """
        version = state.get("version", 0)

        if version < 1:
            # Migration from v0 to v1
            # Add any necessary field transformations here
            state["version"] = 1

        return state

    async def shutdown(self) -> None:
        """Clean up resources and optionally cancel open orders."""
        self._logger.info("strategy_shutting_down")

        if self._config.cancel_on_stop:
            await self._cancel_all_orders()

        self._stopped = True

        self._logger.info(
            "strategy_shutdown_complete",
            total_profit=str(self._stats.total_profit),
            net_profit=str(self._stats.net_profit),
            completed_cycles=self._stats.completed_cycles,
        )


# Register strategy with factory
StrategyFactory.register("grid", GridTradingStrategy)
