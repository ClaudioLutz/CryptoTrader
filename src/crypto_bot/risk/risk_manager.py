"""Central risk manager orchestrating all risk components.

The RiskManager is the single entry point for all risk operations:
- Pre-trade validation (position sizing, risk limits)
- Stop-loss management
- Circuit breaker monitoring
- Drawdown tracking
- Post-trade recording

This module coordinates the position sizer, stop-loss handler,
circuit breaker, and drawdown tracker to provide comprehensive
risk management.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field
import structlog

from crypto_bot.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerTrigger,
)
from crypto_bot.risk.drawdown import DrawdownMetrics, DrawdownTracker
from crypto_bot.risk.position_sizer import (
    FixedFractionalSizer,
    PositionSize,
)
from crypto_bot.risk.stop_loss import (
    StopLossConfig,
    StopLossHandler,
    StopLossState,
    StopLossType,
)

logger = structlog.get_logger()


class RiskConfig(BaseModel):
    """Configuration for the risk manager.

    Attributes:
        risk_pct_per_trade: Percentage of capital to risk per trade.
        default_stop_loss_pct: Default stop-loss percentage.
        max_position_pct: Maximum position as percentage of balance.
        max_drawdown_warning: Drawdown level for warning.
        max_drawdown_limit: Maximum allowed drawdown.
        max_daily_loss_pct: Maximum daily loss percentage.
        max_consecutive_losses: Max losing trades before pause.
        cooldown_minutes: Trading pause duration after limit breach.
    """

    risk_pct_per_trade: Decimal = Field(
        default=Decimal("0.02"),
        ge=Decimal("0.001"),
        le=Decimal("0.10"),
        description="Risk percentage per trade (2%)",
    )
    default_stop_loss_pct: Decimal = Field(
        default=Decimal("0.05"),
        ge=Decimal("0.01"),
        le=Decimal("0.50"),
        description="Default stop-loss percentage (5%)",
    )
    max_position_pct: Decimal = Field(
        default=Decimal("0.20"),
        ge=Decimal("0.05"),
        le=Decimal("1.0"),
        description="Maximum position as % of balance (20%)",
    )
    max_drawdown_warning: Decimal = Field(
        default=Decimal("0.10"),
        ge=Decimal("0.01"),
        le=Decimal("0.50"),
        description="Drawdown warning threshold (10%)",
    )
    max_drawdown_limit: Decimal = Field(
        default=Decimal("0.15"),
        ge=Decimal("0.05"),
        le=Decimal("0.50"),
        description="Maximum drawdown limit (15%)",
    )
    max_daily_loss_pct: Decimal = Field(
        default=Decimal("0.05"),
        ge=Decimal("0.01"),
        le=Decimal("0.20"),
        description="Maximum daily loss (5%)",
    )
    max_consecutive_losses: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Max consecutive losses before pause",
    )
    cooldown_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Trading pause duration in minutes",
    )

    model_config = {"frozen": False}


@dataclass
class TradeValidation:
    """Result of pre-trade validation.

    Attributes:
        allowed: Whether the trade is allowed.
        position_size: Calculated position size (if allowed).
        stop_loss_price: Calculated stop-loss price (if allowed).
        warnings: List of warning messages.
        rejection_reason: Reason for rejection (if not allowed).
    """

    allowed: bool
    position_size: Optional[PositionSize]
    stop_loss_price: Optional[Decimal]
    warnings: list[str]
    rejection_reason: Optional[str]


class RiskManager:
    """Central risk management orchestrator.

    Coordinates all risk components to provide unified risk
    management for trading operations.

    Example:
        >>> config = RiskConfig()
        >>> risk_mgr = RiskManager.create_default(
        ...     config, initial_equity=Decimal("10000")
        ... )
        >>>
        >>> # Pre-trade validation
        >>> validation = await risk_mgr.validate_trade(
        ...     symbol="BTC/USDT",
        ...     side="buy",
        ...     entry_price=Decimal("50000"),
        ...     balance=Decimal("10000"),
        ... )
        >>>
        >>> if validation.allowed:
        ...     # Execute trade with validated position size
        ...     position = validation.position_size
        ...     stop = validation.stop_loss_price
        ...     # ... place order ...
        ...     # Register stop-loss
        ...     risk_mgr.register_stop_loss(position_id, side, entry_price)
    """

    def __init__(
        self,
        position_sizer: FixedFractionalSizer,
        circuit_breaker: CircuitBreaker,
        drawdown_tracker: DrawdownTracker,
        config: RiskConfig,
    ) -> None:
        """Initialize risk manager.

        Args:
            position_sizer: Position sizing calculator.
            circuit_breaker: Circuit breaker instance.
            drawdown_tracker: Drawdown tracker instance.
            config: Risk configuration.
        """
        self._position_sizer = position_sizer
        self._circuit_breaker = circuit_breaker
        self._drawdown_tracker = drawdown_tracker
        self._config = config
        self._stop_handlers: dict[str, tuple[StopLossHandler, str]] = {}
        self._logger = logger.bind(component="risk_manager")

    @classmethod
    def create_default(
        cls,
        config: RiskConfig,
        initial_equity: Decimal,
    ) -> "RiskManager":
        """Create a RiskManager with default components.

        Args:
            config: Risk configuration.
            initial_equity: Starting equity value.

        Returns:
            Configured RiskManager instance.
        """
        position_sizer = FixedFractionalSizer(risk_pct=config.risk_pct_per_trade)

        cb_config = CircuitBreakerConfig(
            max_daily_loss_pct=config.max_daily_loss_pct,
            max_consecutive_losses=config.max_consecutive_losses,
            max_drawdown_pct=config.max_drawdown_limit,
            cooldown_minutes=config.cooldown_minutes,
        )
        circuit_breaker = CircuitBreaker(cb_config)
        circuit_breaker.set_initial_equity(initial_equity)

        drawdown_tracker = DrawdownTracker(initial_equity=initial_equity)

        return cls(
            position_sizer=position_sizer,
            circuit_breaker=circuit_breaker,
            drawdown_tracker=drawdown_tracker,
            config=config,
        )

    @property
    def config(self) -> RiskConfig:
        """Get risk configuration."""
        return self._config

    @property
    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed."""
        return self._circuit_breaker.is_trading_allowed

    async def validate_trade(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        balance: Decimal,
        stop_loss_pct: Optional[Decimal] = None,
    ) -> TradeValidation:
        """Validate a trade before execution.

        Performs comprehensive pre-trade checks:
        - Circuit breaker status
        - Drawdown limits
        - Position sizing
        - Position limits

        Args:
            symbol: Trading pair symbol.
            side: Trade side ("buy" or "sell").
            entry_price: Intended entry price.
            balance: Available capital.
            stop_loss_pct: Optional stop-loss percentage override.

        Returns:
            TradeValidation with results.
        """
        warnings: list[str] = []

        # Check circuit breaker
        if not self._circuit_breaker.is_trading_allowed:
            trigger = self._circuit_breaker.trigger
            return TradeValidation(
                allowed=False,
                position_size=None,
                stop_loss_price=None,
                warnings=[],
                rejection_reason=(
                    f"Circuit breaker is tripped: {trigger.value if trigger else 'unknown'}"
                ),
            )

        # Check drawdown limit
        metrics = self._drawdown_tracker.get_current_metrics()
        if metrics.current_drawdown_pct >= self._config.max_drawdown_limit:
            return TradeValidation(
                allowed=False,
                position_size=None,
                stop_loss_price=None,
                warnings=[],
                rejection_reason=(
                    f"Drawdown at {metrics.current_drawdown_pct:.2%} "
                    f"exceeds limit of {self._config.max_drawdown_limit:.2%}"
                ),
            )

        # Warn if approaching drawdown limit
        if metrics.current_drawdown_pct >= self._config.max_drawdown_warning:
            warnings.append(
                f"Drawdown at {metrics.current_drawdown_pct:.1%}, "
                f"approaching limit of {self._config.max_drawdown_limit:.1%}"
            )

        # Calculate stop-loss price
        sl_pct = stop_loss_pct or self._config.default_stop_loss_pct
        if side == "buy":
            stop_loss_price = entry_price * (1 - sl_pct)
        else:
            stop_loss_price = entry_price * (1 + sl_pct)

        # Calculate position size
        try:
            position_size = self._position_sizer.calculate(
                balance=balance,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
            )
        except ValueError as e:
            return TradeValidation(
                allowed=False,
                position_size=None,
                stop_loss_price=None,
                warnings=[],
                rejection_reason=str(e),
            )

        # Validate position limits
        position_warnings = self._position_sizer.validate_position(
            position_size, balance, self._config.max_position_pct
        )
        warnings.extend(position_warnings)

        # Check if position value exceeds balance
        if position_size.position_value > balance:
            # Adjust position to fit balance
            adjusted_amount = (balance * Decimal("0.95")) / entry_price
            position_size = PositionSize(
                amount=adjusted_amount,
                risk_amount=position_size.risk_amount,
                position_value=adjusted_amount * entry_price,
                risk_pct_actual=position_size.risk_pct_actual,
            )
            warnings.append("Position adjusted to fit available balance")

        self._logger.info(
            "trade_validated",
            symbol=symbol,
            side=side,
            amount=str(position_size.amount),
            stop_loss=str(stop_loss_price),
            warnings=warnings,
        )

        return TradeValidation(
            allowed=True,
            position_size=position_size,
            stop_loss_price=stop_loss_price,
            warnings=warnings,
            rejection_reason=None,
        )

    async def record_trade_result(
        self,
        symbol: str,
        pnl: Decimal,
        equity: Decimal,
    ) -> Optional[CircuitBreakerTrigger]:
        """Record trade result and update risk metrics.

        Should be called after every trade (win or loss).

        Args:
            symbol: Trading pair symbol.
            pnl: Profit/loss from the trade.
            equity: New equity value after trade.

        Returns:
            CircuitBreakerTrigger if a limit was breached.
        """
        # Update drawdown tracker
        self._drawdown_tracker.update(equity)

        # Update circuit breaker
        trigger = self._circuit_breaker.record_trade(pnl, equity)

        if trigger:
            self._logger.warning(
                "risk_limit_triggered",
                trigger=trigger.value,
                pnl=str(pnl),
                equity=str(equity),
            )

        return trigger

    async def record_error(self) -> Optional[CircuitBreakerTrigger]:
        """Record an error occurrence.

        Should be called when a trade error occurs (order failure, etc.).

        Returns:
            CircuitBreakerTrigger if error rate limit breached.
        """
        return self._circuit_breaker.record_error()

    def register_stop_loss(
        self,
        position_id: str,
        side: str,
        entry_price: Decimal,
        stop_loss_pct: Optional[Decimal] = None,
        stop_type: StopLossType = StopLossType.PERCENTAGE,
    ) -> StopLossState:
        """Register a stop-loss for a position.

        Args:
            position_id: Unique position identifier.
            side: Position side ("buy" or "sell").
            entry_price: Position entry price.
            stop_loss_pct: Stop-loss percentage (optional).
            stop_type: Type of stop-loss.

        Returns:
            Initialized StopLossState.
        """
        sl_value = stop_loss_pct or self._config.default_stop_loss_pct

        config = StopLossConfig(
            type=stop_type,
            value=sl_value,
        )
        handler = StopLossHandler(config)
        state = handler.initialize(entry_price, side)
        self._stop_handlers[position_id] = (handler, side)

        self._logger.info(
            "stop_loss_registered",
            position_id=position_id,
            stop_price=str(state.current_stop),
            type=stop_type.value,
        )

        return state

    def update_stop_loss(
        self,
        position_id: str,
        current_price: Decimal,
    ) -> bool:
        """Update stop-loss for a position (for trailing stops).

        Args:
            position_id: Position identifier.
            current_price: Current market price.

        Returns:
            True if stop was updated.
        """
        if position_id not in self._stop_handlers:
            return False

        handler, side = self._stop_handlers[position_id]
        return handler.update(current_price, side)

    def check_stop_loss(
        self,
        position_id: str,
        current_price: Decimal,
    ) -> bool:
        """Check if stop-loss triggered for a position.

        Args:
            position_id: Position identifier.
            current_price: Current market price.

        Returns:
            True if stop-loss triggered.
        """
        if position_id not in self._stop_handlers:
            return False

        handler, side = self._stop_handlers[position_id]
        return handler.check_stop(current_price, side)

    async def check_stop_losses(
        self,
        current_prices: dict[str, Decimal],
        positions: dict[str, tuple[str, Decimal]],
    ) -> list[str]:
        """Check all stop-losses against current prices.

        Args:
            current_prices: Dict of symbol -> current price.
            positions: Dict of position_id -> (symbol, amount).

        Returns:
            List of triggered position IDs.
        """
        triggered: list[str] = []

        for position_id, (handler, side) in self._stop_handlers.items():
            if position_id not in positions:
                continue

            symbol, _ = positions[position_id]
            price = current_prices.get(symbol)

            if price is not None:
                # Update trailing stops
                handler.update(price, side)

                # Check if triggered
                if handler.check_stop(price, side):
                    triggered.append(position_id)
                    self._logger.warning(
                        "stop_loss_triggered",
                        position_id=position_id,
                        price=str(price),
                    )

        return triggered

    def remove_stop_loss(self, position_id: str) -> bool:
        """Remove stop-loss for a closed position.

        Args:
            position_id: Position identifier.

        Returns:
            True if removed, False if not found.
        """
        if position_id in self._stop_handlers:
            del self._stop_handlers[position_id]
            self._logger.debug("stop_loss_removed", position_id=position_id)
            return True
        return False

    def get_stop_loss_price(self, position_id: str) -> Optional[Decimal]:
        """Get current stop-loss price for a position.

        Args:
            position_id: Position identifier.

        Returns:
            Stop price if found, None otherwise.
        """
        if position_id in self._stop_handlers:
            handler, _ = self._stop_handlers[position_id]
            return handler.current_stop
        return None

    def get_risk_metrics(self) -> dict:
        """Get current risk metrics for monitoring.

        Returns:
            Dictionary with comprehensive risk metrics.
        """
        dd_metrics = self._drawdown_tracker.get_current_metrics()
        cb_state = self._circuit_breaker.state

        return {
            # Circuit breaker
            "circuit_breaker_tripped": cb_state.is_tripped,
            "circuit_breaker_trigger": (
                cb_state.trigger.value if cb_state.trigger else None
            ),
            "daily_pnl": str(cb_state.daily_pnl),
            "daily_trades": cb_state.daily_trades,
            "consecutive_losses": cb_state.consecutive_losses,
            "consecutive_wins": cb_state.consecutive_wins,

            # Drawdown
            "current_drawdown_pct": f"{dd_metrics.current_drawdown_pct:.2%}",
            "max_drawdown_pct": f"{dd_metrics.max_drawdown_pct:.2%}",
            "recovery_needed_pct": f"{dd_metrics.recovery_needed_pct:.2%}",
            "peak_equity": str(dd_metrics.peak_equity),
            "current_equity": str(dd_metrics.current_equity),

            # Stop-losses
            "active_stop_losses": len(self._stop_handlers),
        }

    def get_drawdown_metrics(self) -> DrawdownMetrics:
        """Get current drawdown metrics.

        Returns:
            DrawdownMetrics instance.
        """
        return self._drawdown_tracker.get_current_metrics()

    def get_circuit_breaker_status(self) -> dict:
        """Get circuit breaker status.

        Returns:
            Dictionary with circuit breaker status.
        """
        return self._circuit_breaker.get_status()

    def manual_trip_circuit_breaker(self, reason: str) -> None:
        """Manually trip the circuit breaker.

        Args:
            reason: Reason for manual trip.
        """
        self._circuit_breaker.manual_trip(reason)

    def manual_reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._circuit_breaker.manual_reset()

    def update_equity(self, equity: Decimal) -> DrawdownMetrics:
        """Update current equity (without recording trade).

        Useful for periodic equity snapshots.

        Args:
            equity: Current equity value.

        Returns:
            Updated DrawdownMetrics.
        """
        return self._drawdown_tracker.update(equity)


class RiskManagerFactory:
    """Factory for creating configured RiskManager instances."""

    @staticmethod
    def create_conservative(initial_equity: Decimal) -> RiskManager:
        """Create a conservative risk manager.

        Uses lower risk per trade (1%), tighter stop-losses (3%),
        and lower drawdown limits.

        Args:
            initial_equity: Starting equity.

        Returns:
            Conservative RiskManager.
        """
        config = RiskConfig(
            risk_pct_per_trade=Decimal("0.01"),
            default_stop_loss_pct=Decimal("0.03"),
            max_position_pct=Decimal("0.15"),
            max_drawdown_warning=Decimal("0.07"),
            max_drawdown_limit=Decimal("0.10"),
            max_daily_loss_pct=Decimal("0.03"),
            max_consecutive_losses=3,
        )
        return RiskManager.create_default(config, initial_equity)

    @staticmethod
    def create_moderate(initial_equity: Decimal) -> RiskManager:
        """Create a moderate risk manager.

        Uses standard risk settings (2% risk, 5% stops).

        Args:
            initial_equity: Starting equity.

        Returns:
            Moderate RiskManager.
        """
        config = RiskConfig()  # Use defaults
        return RiskManager.create_default(config, initial_equity)

    @staticmethod
    def create_aggressive(initial_equity: Decimal) -> RiskManager:
        """Create an aggressive risk manager.

        Uses higher risk per trade (3%), wider stop-losses (8%),
        and more lenient limits.

        Args:
            initial_equity: Starting equity.

        Returns:
            Aggressive RiskManager.
        """
        config = RiskConfig(
            risk_pct_per_trade=Decimal("0.03"),
            default_stop_loss_pct=Decimal("0.08"),
            max_position_pct=Decimal("0.30"),
            max_drawdown_warning=Decimal("0.15"),
            max_drawdown_limit=Decimal("0.25"),
            max_daily_loss_pct=Decimal("0.08"),
            max_consecutive_losses=7,
        )
        return RiskManager.create_default(config, initial_equity)
