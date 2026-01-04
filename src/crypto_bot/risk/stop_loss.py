"""Stop-loss handler with multiple strategies.

Provides automated stop-loss execution with various strategies:
- Fixed: Static price level
- Percentage: Percentage from entry price
- Trailing: Follows price movement in favorable direction
- ATR-based: Adaptive stop based on Average True Range

Best Practices (2025):
- Static 5% stops don't work in crypto (BTC can move +/-8% daily)
- ATR-based stops adapt to market volatility
- Trailing stops only move in favorable direction (never backwards)
- Grid stop-loss typically 5-10% below lower grid boundary
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Protocol

import structlog

logger = structlog.get_logger()


class StopLossType(str, Enum):
    """Types of stop-loss strategies."""

    FIXED = "fixed"  # Fixed price level
    PERCENTAGE = "percentage"  # Percentage from entry
    TRAILING = "trailing"  # Trailing stop
    ATR = "atr"  # ATR-based adaptive


@dataclass
class StopLossConfig:
    """Configuration for stop-loss behavior.

    Attributes:
        type: The stop-loss strategy type.
        value: Strategy-specific value:
               - FIXED: The stop price
               - PERCENTAGE: Percentage (e.g., 0.05 for 5%)
               - TRAILING: Trail percentage
               - ATR: ATR multiplier (e.g., 2.0 for 2x ATR)
        trailing_activation: Optional profit % to activate trailing.
    """

    type: StopLossType
    value: Decimal
    trailing_activation: Optional[Decimal] = None

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.value <= 0:
            raise ValueError("Stop-loss value must be positive")
        if (
            self.type == StopLossType.PERCENTAGE
            and self.value > Decimal("0.50")
        ):
            raise ValueError("Percentage stop-loss cannot exceed 50%")


@dataclass
class StopLossState:
    """Current state of a stop-loss.

    Attributes:
        config: The stop-loss configuration.
        entry_price: Position entry price.
        current_stop: Current stop-loss price level.
        highest_price: Highest price seen (for long trailing).
        lowest_price: Lowest price seen (for short trailing).
        triggered: Whether stop-loss has triggered.
        triggered_at: Timestamp when triggered.
        trailing_active: Whether trailing is active.
    """

    config: StopLossConfig
    entry_price: Decimal
    current_stop: Decimal
    highest_price: Decimal
    lowest_price: Decimal
    triggered: bool = False
    triggered_at: Optional[datetime] = None
    trailing_active: bool = False


class ExecutionContext(Protocol):
    """Protocol for order execution (subset needed for stop-loss)."""

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
    ) -> str:
        """Place an order."""
        ...


class StopLossHandler:
    """Handles stop-loss calculation, monitoring, and execution.

    Supports multiple stop-loss strategies and tracks state across
    price updates.

    Example:
        >>> config = StopLossConfig(
        ...     type=StopLossType.TRAILING,
        ...     value=Decimal("0.05"),  # 5% trailing
        ... )
        >>> handler = StopLossHandler(config)
        >>> state = handler.initialize(Decimal("50000"), "buy")
        >>> handler.update(Decimal("52000"), "buy")  # Price up
        >>> if handler.check_stop(Decimal("49000"), "buy"):
        ...     await handler.execute_stop(context, "BTC/USDT", amount, "buy")
    """

    def __init__(self, config: StopLossConfig) -> None:
        """Initialize stop-loss handler.

        Args:
            config: Stop-loss configuration.
        """
        self._config = config
        self._state: Optional[StopLossState] = None
        self._logger = logger.bind(
            component="stop_loss_handler",
            type=config.type.value,
        )

    @property
    def config(self) -> StopLossConfig:
        """Get stop-loss configuration."""
        return self._config

    @property
    def state(self) -> Optional[StopLossState]:
        """Get current stop-loss state."""
        return self._state

    @property
    def current_stop(self) -> Optional[Decimal]:
        """Get current stop price."""
        return self._state.current_stop if self._state else None

    @property
    def is_triggered(self) -> bool:
        """Check if stop-loss has triggered."""
        return self._state.triggered if self._state else False

    def initialize(self, entry_price: Decimal, side: str) -> StopLossState:
        """Initialize stop-loss for a new position.

        Args:
            entry_price: Position entry price.
            side: Position side ("buy" for long, "sell" for short).

        Returns:
            Initialized StopLossState.
        """
        stop_price = self._calculate_initial_stop(entry_price, side)

        self._state = StopLossState(
            config=self._config,
            entry_price=entry_price,
            current_stop=stop_price,
            highest_price=entry_price,
            lowest_price=entry_price,
            trailing_active=self._config.trailing_activation is None,
        )

        self._logger.info(
            "stop_loss_initialized",
            entry_price=str(entry_price),
            stop_price=str(stop_price),
            side=side,
        )

        return self._state

    def _calculate_initial_stop(
        self,
        entry_price: Decimal,
        side: str,
    ) -> Decimal:
        """Calculate initial stop-loss price.

        Args:
            entry_price: Position entry price.
            side: Position side.

        Returns:
            Initial stop-loss price.
        """
        if self._config.type == StopLossType.FIXED:
            return self._config.value

        elif self._config.type == StopLossType.PERCENTAGE:
            if side == "buy":
                return entry_price * (1 - self._config.value)
            else:
                return entry_price * (1 + self._config.value)

        elif self._config.type == StopLossType.TRAILING:
            if side == "buy":
                return entry_price * (1 - self._config.value)
            else:
                return entry_price * (1 + self._config.value)

        elif self._config.type == StopLossType.ATR:
            # ATR-based requires ATR value, default to percentage as fallback
            # ATR will be set via update_atr_stop()
            if side == "buy":
                return entry_price * (1 - Decimal("0.05"))  # 5% default
            else:
                return entry_price * (1 + Decimal("0.05"))

        raise ValueError(f"Unknown stop-loss type: {self._config.type}")

    def update(self, current_price: Decimal, side: str) -> bool:
        """Update stop-loss based on price movement.

        For trailing stops, adjusts the stop price when price moves
        in the favorable direction.

        Args:
            current_price: Current market price.
            side: Position side.

        Returns:
            True if stop was updated, False otherwise.
        """
        if self._state is None:
            raise RuntimeError("Stop-loss not initialized")

        if self._state.triggered:
            return False

        # Update high/low tracking
        if current_price > self._state.highest_price:
            self._state.highest_price = current_price
        if current_price < self._state.lowest_price:
            self._state.lowest_price = current_price

        # Check trailing activation
        if not self._state.trailing_active and self._config.trailing_activation:
            profit_pct = self._calculate_profit_pct(current_price, side)
            if profit_pct >= self._config.trailing_activation:
                self._state.trailing_active = True
                self._logger.info(
                    "trailing_stop_activated",
                    profit_pct=f"{profit_pct:.2%}",
                )

        # Update trailing stop
        if (
            self._config.type == StopLossType.TRAILING
            and self._state.trailing_active
        ):
            return self._update_trailing(current_price, side)

        return False

    def _calculate_profit_pct(
        self,
        current_price: Decimal,
        side: str,
    ) -> Decimal:
        """Calculate current profit percentage.

        Args:
            current_price: Current market price.
            side: Position side.

        Returns:
            Profit percentage (negative if loss).
        """
        if self._state is None:
            return Decimal(0)

        if side == "buy":
            return (current_price - self._state.entry_price) / self._state.entry_price
        else:
            return (self._state.entry_price - current_price) / self._state.entry_price

    def _update_trailing(self, current_price: Decimal, side: str) -> bool:
        """Update trailing stop based on price movement.

        Args:
            current_price: Current market price.
            side: Position side.

        Returns:
            True if stop was updated.
        """
        if self._state is None:
            return False

        updated = False

        if side == "buy":
            # Long position - trail below highest price
            if current_price > self._state.highest_price:
                self._state.highest_price = current_price
                new_stop = current_price * (1 - self._config.value)

                # Only move stop up (never down)
                if new_stop > self._state.current_stop:
                    old_stop = self._state.current_stop
                    self._state.current_stop = new_stop
                    updated = True
                    self._logger.info(
                        "trailing_stop_updated",
                        old_stop=str(old_stop),
                        new_stop=str(new_stop),
                        highest=str(current_price),
                    )
        else:
            # Short position - trail above lowest price
            if current_price < self._state.lowest_price:
                self._state.lowest_price = current_price
                new_stop = current_price * (1 + self._config.value)

                # Only move stop down (never up)
                if new_stop < self._state.current_stop:
                    old_stop = self._state.current_stop
                    self._state.current_stop = new_stop
                    updated = True
                    self._logger.info(
                        "trailing_stop_updated",
                        old_stop=str(old_stop),
                        new_stop=str(new_stop),
                        lowest=str(current_price),
                    )

        return updated

    def calculate_atr_stop(
        self,
        reference_price: Decimal,
        atr: Decimal,
        side: str,
        multiplier: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate stop-loss based on Average True Range.

        Args:
            reference_price: Reference price (entry or highest/lowest).
            atr: Current ATR value.
            side: Position side.
            multiplier: ATR multiplier (defaults to config value).

        Returns:
            ATR-based stop-loss price.
        """
        mult = multiplier or self._config.value
        atr_distance = atr * mult

        if side == "buy":
            return reference_price - atr_distance
        else:
            return reference_price + atr_distance

    def update_atr_stop(
        self,
        current_price: Decimal,
        atr: Decimal,
        side: str,
    ) -> bool:
        """Update ATR-based stop with new volatility data.

        Args:
            current_price: Current market price.
            atr: Current ATR value.
            side: Position side.

        Returns:
            True if stop was updated.
        """
        if self._state is None:
            raise RuntimeError("Stop-loss not initialized")

        if self._config.type != StopLossType.ATR:
            return False

        if self._state.triggered:
            return False

        # Update high/low tracking
        if current_price > self._state.highest_price:
            self._state.highest_price = current_price
        if current_price < self._state.lowest_price:
            self._state.lowest_price = current_price

        # Calculate new ATR-based stop
        reference_price = (
            self._state.highest_price if side == "buy" else self._state.lowest_price
        )
        new_stop = self.calculate_atr_stop(reference_price, atr, side)

        # Only move stop in favorable direction
        updated = False
        if side == "buy" and new_stop > self._state.current_stop:
            old_stop = self._state.current_stop
            self._state.current_stop = new_stop
            updated = True
            self._logger.info(
                "atr_stop_updated",
                old_stop=str(old_stop),
                new_stop=str(new_stop),
                atr=str(atr),
            )
        elif side == "sell" and new_stop < self._state.current_stop:
            old_stop = self._state.current_stop
            self._state.current_stop = new_stop
            updated = True
            self._logger.info(
                "atr_stop_updated",
                old_stop=str(old_stop),
                new_stop=str(new_stop),
                atr=str(atr),
            )

        return updated

    def check_stop(self, current_price: Decimal, side: str) -> bool:
        """Check if stop-loss should trigger.

        Args:
            current_price: Current market price.
            side: Position side.

        Returns:
            True if stop-loss triggered.
        """
        if self._state is None:
            raise RuntimeError("Stop-loss not initialized")

        if self._state.triggered:
            return False

        triggered = False
        if side == "buy":
            triggered = current_price <= self._state.current_stop
        else:
            triggered = current_price >= self._state.current_stop

        if triggered:
            self._state.triggered = True
            self._state.triggered_at = datetime.utcnow()
            self._logger.warning(
                "stop_loss_triggered",
                current_price=str(current_price),
                stop_price=str(self._state.current_stop),
                side=side,
                entry_price=str(self._state.entry_price),
            )

        return triggered

    async def execute_stop(
        self,
        context: ExecutionContext,
        symbol: str,
        amount: Decimal,
        side: str,
    ) -> str:
        """Execute stop-loss market order.

        Args:
            context: Execution context for placing orders.
            symbol: Trading pair symbol.
            amount: Position amount to close.
            side: Original position side.

        Returns:
            Order ID of the stop-loss order.
        """
        # Close position with opposite side market order
        close_side = "sell" if side == "buy" else "buy"

        order_id = await context.place_order(
            symbol=symbol,
            side=close_side,
            amount=amount,
            price=None,  # Market order
        )

        self._logger.info(
            "stop_loss_executed",
            order_id=order_id,
            symbol=symbol,
            amount=str(amount),
            close_side=close_side,
        )

        return order_id

    def reset(self) -> None:
        """Reset stop-loss state for new position."""
        self._state = None
        self._logger.debug("stop_loss_reset")


class GridStopLoss:
    """Stop-loss handler specifically for grid trading.

    Sets stop-loss below the lower grid boundary to protect
    against trend breakdown scenarios.

    Example:
        >>> grid_stop = GridStopLoss(
        ...     lower_grid_price=Decimal("45000"),
        ...     buffer_pct=Decimal("0.10"),  # 10% below
        ... )
        >>> if grid_stop.check(Decimal("40000")):
        ...     print("Grid stop triggered!")
    """

    def __init__(
        self,
        lower_grid_price: Decimal,
        buffer_pct: Decimal = Decimal("0.10"),
    ) -> None:
        """Initialize grid stop-loss.

        Args:
            lower_grid_price: Lowest grid price level.
            buffer_pct: Buffer percentage below lower grid.
        """
        if lower_grid_price <= 0:
            raise ValueError("lower_grid_price must be positive")
        if not Decimal("0") < buffer_pct < Decimal("1"):
            raise ValueError("buffer_pct must be between 0 and 1")

        self._lower_grid_price = lower_grid_price
        self._buffer_pct = buffer_pct
        self._stop_price = lower_grid_price * (1 - buffer_pct)
        self._triggered = False
        self._triggered_at: Optional[datetime] = None
        self._logger = logger.bind(component="grid_stop_loss")

        self._logger.info(
            "grid_stop_initialized",
            lower_grid=str(lower_grid_price),
            buffer_pct=f"{buffer_pct:.1%}",
            stop_price=str(self._stop_price),
        )

    @property
    def stop_price(self) -> Decimal:
        """Get the grid stop-loss price."""
        return self._stop_price

    @property
    def is_triggered(self) -> bool:
        """Check if grid stop has triggered."""
        return self._triggered

    def check(self, current_price: Decimal) -> bool:
        """Check if price breached grid stop-loss.

        Args:
            current_price: Current market price.

        Returns:
            True if stop-loss triggered.
        """
        if self._triggered:
            return False

        if current_price <= self._stop_price:
            self._triggered = True
            self._triggered_at = datetime.utcnow()
            self._logger.warning(
                "grid_stop_triggered",
                current_price=str(current_price),
                stop_price=str(self._stop_price),
            )
            return True

        return False

    def update_grid(
        self,
        new_lower_price: Decimal,
        buffer_pct: Optional[Decimal] = None,
    ) -> None:
        """Update grid stop for new grid configuration.

        Args:
            new_lower_price: New lowest grid price.
            buffer_pct: Optional new buffer percentage.
        """
        self._lower_grid_price = new_lower_price
        if buffer_pct is not None:
            self._buffer_pct = buffer_pct
        self._stop_price = new_lower_price * (1 - self._buffer_pct)
        self._triggered = False

        self._logger.info(
            "grid_stop_updated",
            lower_grid=str(new_lower_price),
            stop_price=str(self._stop_price),
        )


class StopLossManager:
    """Manages multiple stop-losses for different positions.

    Provides centralized management of stop-losses across
    multiple trading positions.

    Example:
        >>> manager = StopLossManager()
        >>> manager.register(
        ...     "BTC_LONG_001",
        ...     StopLossConfig(type=StopLossType.TRAILING, value=Decimal("0.05")),
        ...     entry_price=Decimal("50000"),
        ...     side="buy",
        ... )
        >>> triggered = manager.check_all({"BTC/USDT": Decimal("48000")}, positions)
    """

    def __init__(self) -> None:
        """Initialize stop-loss manager."""
        self._handlers: dict[str, tuple[StopLossHandler, str]] = {}
        self._logger = logger.bind(component="stop_loss_manager")

    def register(
        self,
        position_id: str,
        config: StopLossConfig,
        entry_price: Decimal,
        side: str,
    ) -> StopLossState:
        """Register stop-loss for a position.

        Args:
            position_id: Unique position identifier.
            config: Stop-loss configuration.
            entry_price: Position entry price.
            side: Position side.

        Returns:
            Initialized StopLossState.
        """
        handler = StopLossHandler(config)
        state = handler.initialize(entry_price, side)
        self._handlers[position_id] = (handler, side)

        self._logger.info(
            "stop_loss_registered",
            position_id=position_id,
            stop_price=str(state.current_stop),
        )

        return state

    def unregister(self, position_id: str) -> bool:
        """Remove stop-loss for a position.

        Args:
            position_id: Position identifier.

        Returns:
            True if removed, False if not found.
        """
        if position_id in self._handlers:
            del self._handlers[position_id]
            self._logger.info("stop_loss_unregistered", position_id=position_id)
            return True
        return False

    def update(
        self,
        position_id: str,
        current_price: Decimal,
    ) -> bool:
        """Update stop-loss for a position.

        Args:
            position_id: Position identifier.
            current_price: Current market price.

        Returns:
            True if stop was updated.
        """
        if position_id not in self._handlers:
            return False

        handler, side = self._handlers[position_id]
        return handler.update(current_price, side)

    def check(
        self,
        position_id: str,
        current_price: Decimal,
    ) -> bool:
        """Check if stop-loss triggered for a position.

        Args:
            position_id: Position identifier.
            current_price: Current market price.

        Returns:
            True if triggered.
        """
        if position_id not in self._handlers:
            return False

        handler, side = self._handlers[position_id]
        return handler.check_stop(current_price, side)

    def check_all(
        self,
        current_prices: dict[str, Decimal],
        positions: dict[str, tuple[str, Decimal]],
    ) -> list[str]:
        """Check all stop-losses and return triggered position IDs.

        Args:
            current_prices: Dict of symbol -> current price.
            positions: Dict of position_id -> (symbol, amount).

        Returns:
            List of triggered position IDs.
        """
        triggered: list[str] = []

        for position_id, (handler, side) in self._handlers.items():
            if position_id not in positions:
                continue

            symbol, _ = positions[position_id]
            price = current_prices.get(symbol)

            if price is not None:
                # Update trailing stop
                handler.update(price, side)

                # Check trigger
                if handler.check_stop(price, side):
                    triggered.append(position_id)

        return triggered

    def get_handler(self, position_id: str) -> Optional[StopLossHandler]:
        """Get stop-loss handler for a position.

        Args:
            position_id: Position identifier.

        Returns:
            StopLossHandler if found, None otherwise.
        """
        if position_id in self._handlers:
            return self._handlers[position_id][0]
        return None

    def get_all_stops(self) -> dict[str, Decimal]:
        """Get all current stop prices.

        Returns:
            Dict of position_id -> stop price.
        """
        return {
            pos_id: handler.current_stop
            for pos_id, (handler, _) in self._handlers.items()
            if handler.current_stop is not None
        }
