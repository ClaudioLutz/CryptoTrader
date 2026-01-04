"""Circuit breaker for trading risk management.

Provides automatic trading pause when risk limits are breached.
Prevents loss compounding during adverse market conditions.

Trigger Conditions:
- Daily loss exceeding threshold (default 5%)
- Consecutive losing trades
- Maximum drawdown reached
- High error rate
- Manual override

Best Practices (2025):
- 5% daily loss limit is recommended threshold
- Circuit breaker should pause trading, not exit positions
- Cooldown period prevents immediate re-entry
- Daily reset at midnight UTC
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Protocol

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class CircuitBreakerTrigger(str, Enum):
    """Reasons why circuit breaker can trip."""

    DAILY_LOSS = "daily_loss"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    MAX_DRAWDOWN = "max_drawdown"
    MANUAL = "manual"
    ERROR_RATE = "error_rate"


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker thresholds.

    Attributes:
        max_daily_loss_pct: Maximum daily loss before tripping.
        max_consecutive_losses: Max losing trades in a row.
        max_drawdown_pct: Maximum drawdown from peak.
        max_error_rate: Maximum error rate (errors/trades).
        cooldown_minutes: Minutes to wait after trip.
        auto_reset_daily: Whether to reset at midnight UTC.
    """

    max_daily_loss_pct: Decimal = Field(
        default=Decimal("0.05"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Maximum daily loss percentage (5%)",
    )
    max_consecutive_losses: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum consecutive losing trades",
    )
    max_drawdown_pct: Decimal = Field(
        default=Decimal("0.15"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Maximum drawdown from peak (15%)",
    )
    max_error_rate: Decimal = Field(
        default=Decimal("0.50"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Maximum error rate (50%)",
    )
    cooldown_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Cooldown period in minutes",
    )
    auto_reset_daily: bool = Field(
        default=True,
        description="Automatically reset daily counters at midnight UTC",
    )

    model_config = {"frozen": False}


@dataclass
class CircuitBreakerState:
    """Current state of the circuit breaker.

    Attributes:
        is_tripped: Whether trading is currently paused.
        trigger: The trigger that caused the trip.
        tripped_at: When the circuit breaker tripped.
        cooldown_until: When cooldown period ends.
        daily_pnl: Cumulative P&L for the day.
        daily_trades: Number of trades today.
        daily_errors: Number of errors today.
        day_start: Start of the current trading day.
        consecutive_losses: Current losing streak.
        consecutive_wins: Current winning streak.
        peak_equity: Highest equity value seen.
        current_equity: Current equity value.
        current_drawdown: Current drawdown from peak.
    """

    is_tripped: bool = False
    trigger: Optional[CircuitBreakerTrigger] = None
    tripped_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None

    # Daily tracking
    daily_pnl: Decimal = Decimal(0)
    daily_trades: int = 0
    daily_errors: int = 0
    day_start: datetime = field(
        default_factory=lambda: datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    )

    # Consecutive tracking
    consecutive_losses: int = 0
    consecutive_wins: int = 0

    # Drawdown tracking
    peak_equity: Decimal = Decimal(0)
    current_equity: Decimal = Decimal(0)
    current_drawdown: Decimal = Decimal(0)


class AlertManager(Protocol):
    """Protocol for sending alerts."""

    async def send_critical(self, message: str, details: dict) -> None:
        """Send a critical alert."""
        ...


class CircuitBreaker:
    """Multi-condition circuit breaker for trading protection.

    Monitors trading activity and automatically halts trading
    when risk thresholds are breached.

    Example:
        >>> config = CircuitBreakerConfig(max_daily_loss_pct=Decimal("0.05"))
        >>> breaker = CircuitBreaker(config)
        >>> breaker.set_initial_equity(Decimal("10000"))
        >>>
        >>> # Record trade results
        >>> if breaker.is_trading_allowed:
        ...     # Execute trade
        ...     trigger = breaker.record_trade(pnl, new_equity)
        ...     if trigger:
        ...         print(f"Circuit breaker tripped: {trigger}")
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        """Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration.
        """
        self._config = config
        self._state = CircuitBreakerState()
        self._alerter: Optional[AlertManager] = None
        self._logger = logger.bind(component="circuit_breaker")

    @property
    def config(self) -> CircuitBreakerConfig:
        """Get circuit breaker configuration."""
        return self._config

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state

    def set_alerter(self, alerter: AlertManager) -> None:
        """Set alerter for notifications.

        Args:
            alerter: Alert manager instance.
        """
        self._alerter = alerter

    def set_initial_equity(self, equity: Decimal) -> None:
        """Set initial equity for drawdown tracking.

        Args:
            equity: Starting equity value.
        """
        self._state.peak_equity = equity
        self._state.current_equity = equity
        self._logger.info("initial_equity_set", equity=str(equity))

    @property
    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed.

        Returns:
            True if trading is allowed, False if circuit breaker is tripped.
        """
        # Check for daily reset
        self._maybe_reset_daily()

        if self._state.is_tripped:
            # Check if cooldown has passed
            if (
                self._state.cooldown_until
                and datetime.utcnow() >= self._state.cooldown_until
            ):
                self._reset()
                return True
            return False
        return True

    @property
    def is_tripped(self) -> bool:
        """Check if circuit breaker is currently tripped."""
        return self._state.is_tripped

    @property
    def trigger(self) -> Optional[CircuitBreakerTrigger]:
        """Get the trigger that caused the trip."""
        return self._state.trigger

    def _maybe_reset_daily(self) -> None:
        """Reset daily counters if new day started."""
        if not self._config.auto_reset_daily:
            return

        now = datetime.utcnow()
        current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if current_day > self._state.day_start:
            self._logger.info(
                "daily_reset",
                previous_day=self._state.day_start.isoformat(),
                daily_pnl=str(self._state.daily_pnl),
                daily_trades=self._state.daily_trades,
            )
            self._state.day_start = current_day
            self._state.daily_pnl = Decimal(0)
            self._state.daily_trades = 0
            self._state.daily_errors = 0

    def record_trade(
        self,
        pnl: Decimal,
        equity: Decimal,
    ) -> Optional[CircuitBreakerTrigger]:
        """Record trade result and check limits.

        Args:
            pnl: Profit/loss from the trade.
            equity: New equity value after trade.

        Returns:
            CircuitBreakerTrigger if a limit was breached, None otherwise.
        """
        self._maybe_reset_daily()

        # Update daily tracking
        self._state.daily_trades += 1
        self._state.daily_pnl += pnl
        self._state.current_equity = equity

        # Update peak equity and drawdown
        if equity > self._state.peak_equity:
            self._state.peak_equity = equity

        if self._state.peak_equity > 0:
            self._state.current_drawdown = (
                self._state.peak_equity - equity
            ) / self._state.peak_equity
        else:
            self._state.current_drawdown = Decimal(0)

        # Track consecutive losses/wins
        if pnl < 0:
            self._state.consecutive_losses += 1
            self._state.consecutive_wins = 0
        else:
            self._state.consecutive_wins += 1
            self._state.consecutive_losses = 0

        self._logger.debug(
            "trade_recorded",
            pnl=str(pnl),
            equity=str(equity),
            daily_pnl=str(self._state.daily_pnl),
            consecutive_losses=self._state.consecutive_losses,
            drawdown=f"{self._state.current_drawdown:.2%}",
        )

        # Check all limits
        return self._check_limits()

    def _check_limits(self) -> Optional[CircuitBreakerTrigger]:
        """Check all circuit breaker conditions.

        Returns:
            Trigger type if limit breached, None otherwise.
        """
        trigger = None

        # Daily loss limit
        if self._state.peak_equity > 0:
            daily_loss_pct = abs(self._state.daily_pnl) / self._state.peak_equity
            if (
                self._state.daily_pnl < 0
                and daily_loss_pct >= self._config.max_daily_loss_pct
            ):
                trigger = CircuitBreakerTrigger.DAILY_LOSS
                self._logger.warning(
                    "circuit_breaker_daily_loss",
                    daily_loss_pct=f"{daily_loss_pct:.2%}",
                    limit=f"{self._config.max_daily_loss_pct:.2%}",
                )

        # Consecutive losses
        if (
            trigger is None
            and self._state.consecutive_losses >= self._config.max_consecutive_losses
        ):
            trigger = CircuitBreakerTrigger.CONSECUTIVE_LOSSES
            self._logger.warning(
                "circuit_breaker_consecutive_losses",
                count=self._state.consecutive_losses,
                limit=self._config.max_consecutive_losses,
            )

        # Max drawdown
        if (
            trigger is None
            and self._state.current_drawdown >= self._config.max_drawdown_pct
        ):
            trigger = CircuitBreakerTrigger.MAX_DRAWDOWN
            self._logger.warning(
                "circuit_breaker_max_drawdown",
                drawdown=f"{self._state.current_drawdown:.2%}",
                limit=f"{self._config.max_drawdown_pct:.2%}",
            )

        if trigger:
            self._trip(trigger)

        return trigger

    def record_error(self) -> Optional[CircuitBreakerTrigger]:
        """Record an error and check error rate limit.

        Returns:
            CircuitBreakerTrigger.ERROR_RATE if limit breached.
        """
        self._state.daily_errors += 1

        if self._state.daily_trades > 0:
            error_rate = Decimal(self._state.daily_errors) / self._state.daily_trades
            self._logger.debug(
                "error_recorded",
                errors=self._state.daily_errors,
                trades=self._state.daily_trades,
                rate=f"{error_rate:.2%}",
            )

            if error_rate >= self._config.max_error_rate:
                self._trip(CircuitBreakerTrigger.ERROR_RATE)
                return CircuitBreakerTrigger.ERROR_RATE

        return None

    def _trip(self, trigger: CircuitBreakerTrigger) -> None:
        """Trip the circuit breaker.

        Args:
            trigger: The trigger condition that caused the trip.
        """
        self._state.is_tripped = True
        self._state.trigger = trigger
        self._state.tripped_at = datetime.utcnow()
        self._state.cooldown_until = datetime.utcnow() + timedelta(
            minutes=self._config.cooldown_minutes
        )

        self._logger.error(
            "circuit_breaker_tripped",
            trigger=trigger.value,
            cooldown_until=self._state.cooldown_until.isoformat(),
            daily_pnl=str(self._state.daily_pnl),
            consecutive_losses=self._state.consecutive_losses,
            drawdown=f"{self._state.current_drawdown:.2%}",
        )

        # Send alert
        if self._alerter:
            asyncio.create_task(
                self._alerter.send_critical(
                    f"Circuit breaker tripped: {trigger.value}",
                    {
                        "daily_pnl": str(self._state.daily_pnl),
                        "consecutive_losses": self._state.consecutive_losses,
                        "drawdown": f"{self._state.current_drawdown:.2%}",
                        "cooldown_until": self._state.cooldown_until.isoformat(),
                    },
                )
            )

    def _reset(self) -> None:
        """Reset circuit breaker state (after cooldown)."""
        self._logger.info(
            "circuit_breaker_reset",
            was_triggered_by=self._state.trigger.value if self._state.trigger else None,
        )
        self._state.is_tripped = False
        self._state.trigger = None
        self._state.tripped_at = None
        self._state.cooldown_until = None
        self._state.consecutive_losses = 0

    def manual_reset(self) -> None:
        """Manually reset circuit breaker.

        Use with caution - bypasses cooldown period.
        """
        self._logger.warning("circuit_breaker_manual_reset")
        self._reset()

    def manual_trip(self, reason: str = "manual") -> None:
        """Manually trip circuit breaker.

        Args:
            reason: Reason for manual trip.
        """
        self._logger.warning("circuit_breaker_manual_trip", reason=reason)
        self._trip(CircuitBreakerTrigger.MANUAL)

    def get_status(self) -> dict:
        """Get current circuit breaker status.

        Returns:
            Dictionary with current status information.
        """
        return {
            "is_tripped": self._state.is_tripped,
            "trigger": self._state.trigger.value if self._state.trigger else None,
            "tripped_at": (
                self._state.tripped_at.isoformat() if self._state.tripped_at else None
            ),
            "cooldown_until": (
                self._state.cooldown_until.isoformat()
                if self._state.cooldown_until
                else None
            ),
            "daily_pnl": str(self._state.daily_pnl),
            "daily_trades": self._state.daily_trades,
            "daily_errors": self._state.daily_errors,
            "consecutive_losses": self._state.consecutive_losses,
            "consecutive_wins": self._state.consecutive_wins,
            "current_drawdown": f"{self._state.current_drawdown:.2%}",
            "peak_equity": str(self._state.peak_equity),
            "current_equity": str(self._state.current_equity),
        }

    def get_remaining_cooldown(self) -> Optional[timedelta]:
        """Get remaining cooldown time.

        Returns:
            Remaining cooldown duration, None if not in cooldown.
        """
        if self._state.cooldown_until:
            remaining = self._state.cooldown_until - datetime.utcnow()
            return remaining if remaining.total_seconds() > 0 else None
        return None


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different strategies/symbols.

    Allows independent circuit breaker tracking per trading strategy
    while also supporting a global circuit breaker.

    Example:
        >>> manager = CircuitBreakerManager()
        >>> manager.create("BTC_GRID", CircuitBreakerConfig(max_daily_loss_pct=Decimal("0.03")))
        >>> manager.create("ETH_GRID", CircuitBreakerConfig(max_daily_loss_pct=Decimal("0.05")))
        >>>
        >>> if manager.is_trading_allowed("BTC_GRID"):
        ...     # Execute BTC grid trade
        ...     manager.record_trade("BTC_GRID", pnl, equity)
    """

    def __init__(self, global_config: Optional[CircuitBreakerConfig] = None) -> None:
        """Initialize circuit breaker manager.

        Args:
            global_config: Configuration for global circuit breaker.
        """
        self._breakers: dict[str, CircuitBreaker] = {}
        self._global_breaker: Optional[CircuitBreaker] = None
        self._logger = logger.bind(component="circuit_breaker_manager")

        if global_config:
            self._global_breaker = CircuitBreaker(global_config)
            self._logger.info("global_circuit_breaker_enabled")

    def create(
        self,
        name: str,
        config: CircuitBreakerConfig,
        initial_equity: Optional[Decimal] = None,
    ) -> CircuitBreaker:
        """Create a new circuit breaker.

        Args:
            name: Unique identifier for the circuit breaker.
            config: Circuit breaker configuration.
            initial_equity: Initial equity value.

        Returns:
            The created CircuitBreaker.
        """
        breaker = CircuitBreaker(config)
        if initial_equity is not None:
            breaker.set_initial_equity(initial_equity)
        self._breakers[name] = breaker

        self._logger.info("circuit_breaker_created", name=name)
        return breaker

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name.

        Args:
            name: Circuit breaker identifier.

        Returns:
            CircuitBreaker if found, None otherwise.
        """
        return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove a circuit breaker.

        Args:
            name: Circuit breaker identifier.

        Returns:
            True if removed, False if not found.
        """
        if name in self._breakers:
            del self._breakers[name]
            self._logger.info("circuit_breaker_removed", name=name)
            return True
        return False

    def is_trading_allowed(self, name: Optional[str] = None) -> bool:
        """Check if trading is allowed.

        Args:
            name: Specific circuit breaker to check.
                  If None, checks global breaker only.

        Returns:
            True if trading is allowed.
        """
        # Check global breaker first
        if self._global_breaker and not self._global_breaker.is_trading_allowed:
            return False

        # Check specific breaker
        if name and name in self._breakers:
            return self._breakers[name].is_trading_allowed

        return True

    def record_trade(
        self,
        name: str,
        pnl: Decimal,
        equity: Decimal,
    ) -> Optional[CircuitBreakerTrigger]:
        """Record a trade for a specific circuit breaker.

        Args:
            name: Circuit breaker identifier.
            pnl: Trade profit/loss.
            equity: New equity value.

        Returns:
            Trigger if limit breached, None otherwise.
        """
        trigger = None

        # Record on specific breaker
        if name in self._breakers:
            trigger = self._breakers[name].record_trade(pnl, equity)

        # Also record on global breaker
        if self._global_breaker:
            global_trigger = self._global_breaker.record_trade(pnl, equity)
            trigger = trigger or global_trigger

        return trigger

    def record_error(self, name: str) -> Optional[CircuitBreakerTrigger]:
        """Record an error for a specific circuit breaker.

        Args:
            name: Circuit breaker identifier.

        Returns:
            Trigger if error rate limit breached.
        """
        trigger = None

        if name in self._breakers:
            trigger = self._breakers[name].record_error()

        if self._global_breaker:
            global_trigger = self._global_breaker.record_error()
            trigger = trigger or global_trigger

        return trigger

    def get_all_status(self) -> dict[str, dict]:
        """Get status of all circuit breakers.

        Returns:
            Dictionary mapping names to status dicts.
        """
        status = {}
        for name, breaker in self._breakers.items():
            status[name] = breaker.get_status()
        if self._global_breaker:
            status["_global"] = self._global_breaker.get_status()
        return status

    def reset_all(self) -> None:
        """Manually reset all circuit breakers."""
        for name, breaker in self._breakers.items():
            if breaker.is_tripped:
                breaker.manual_reset()
                self._logger.info("circuit_breaker_reset", name=name)
        if self._global_breaker and self._global_breaker.is_tripped:
            self._global_breaker.manual_reset()
            self._logger.info("global_circuit_breaker_reset")
