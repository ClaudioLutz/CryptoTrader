"""Position sizing algorithms for risk-controlled trading.

Provides multiple position sizing strategies:
- FixedFractionalSizer: Risk a fixed percentage of capital per trade
- KellySizer: Optimal position sizing using Kelly Criterion
- GridPositionSizer: Position sizing optimized for grid trading

Best Practices (2025):
- Risk 1-2% of capital per trade maximum
- Use half-Kelly or quarter-Kelly to reduce volatility
- Reserve 20% capital for grid trading volatility spikes
- Maximum 20% of portfolio in any single position
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class PositionSize:
    """Result of position size calculation.

    Attributes:
        amount: Position size in base currency units.
        risk_amount: Absolute amount at risk in quote currency.
        position_value: Total position value in quote currency.
        risk_pct_actual: Actual risk percentage of portfolio.
    """

    amount: Decimal
    risk_amount: Decimal
    position_value: Decimal
    risk_pct_actual: Decimal


class FixedFractionalSizer:
    """Position sizing using fixed percentage of capital at risk.

    The fixed fractional method ensures consistent risk exposure by
    risking the same percentage of capital on every trade, regardless
    of account size or win/loss streaks.

    Example:
        >>> sizer = FixedFractionalSizer(risk_pct=Decimal("0.02"))  # 2% risk
        >>> position = sizer.calculate(
        ...     balance=Decimal("10000"),
        ...     entry_price=Decimal("50000"),
        ...     stop_loss_price=Decimal("49000"),
        ... )
        >>> print(f"Position size: {position.amount} BTC")
    """

    def __init__(self, risk_pct: Decimal = Decimal("0.02")) -> None:
        """Initialize fixed fractional position sizer.

        Args:
            risk_pct: Percentage of capital to risk per trade.
                     Default 2% (0.02). Must be between 0.1% and 10%.

        Raises:
            ValueError: If risk_pct is outside valid range.
        """
        if not Decimal("0.001") <= risk_pct <= Decimal("0.10"):
            raise ValueError(
                f"risk_pct must be between 0.1% and 10%, got {risk_pct:.2%}"
            )
        self._risk_pct = risk_pct
        self._logger = logger.bind(component="fixed_fractional_sizer")

    @property
    def risk_pct(self) -> Decimal:
        """Get configured risk percentage."""
        return self._risk_pct

    def calculate(
        self,
        balance: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
    ) -> PositionSize:
        """Calculate position size based on risk parameters.

        Position size is calculated such that if stop-loss is hit,
        the loss equals risk_pct of balance.

        Args:
            balance: Available capital in quote currency.
            entry_price: Intended entry price.
            stop_loss_price: Stop-loss price level.

        Returns:
            PositionSize with calculated values.

        Raises:
            ValueError: If stop loss equals entry price.
        """
        risk_amount = balance * self._risk_pct
        price_risk = abs(entry_price - stop_loss_price)

        if price_risk == 0:
            raise ValueError("Stop loss cannot equal entry price")

        amount = risk_amount / price_risk
        position_value = amount * entry_price

        self._logger.debug(
            "position_calculated",
            balance=str(balance),
            risk_pct=f"{self._risk_pct:.2%}",
            risk_amount=str(risk_amount),
            amount=str(amount),
            position_value=str(position_value),
        )

        return PositionSize(
            amount=amount,
            risk_amount=risk_amount,
            position_value=position_value,
            risk_pct_actual=self._risk_pct,
        )

    def validate_position(
        self,
        position_size: PositionSize,
        balance: Decimal,
        max_position_pct: Decimal = Decimal("0.20"),
    ) -> list[str]:
        """Validate position size against risk limits.

        Args:
            position_size: Calculated position size.
            balance: Available capital.
            max_position_pct: Maximum position as % of balance.

        Returns:
            List of warning messages (empty if valid).
        """
        warnings: list[str] = []

        if position_size.position_value > balance * max_position_pct:
            warnings.append(
                f"Position value {position_size.position_value:.2f} exceeds "
                f"{max_position_pct:.0%} of balance ({balance * max_position_pct:.2f})"
            )

        if position_size.risk_pct_actual > Decimal("0.05"):
            warnings.append(
                f"Risk {position_size.risk_pct_actual:.1%} exceeds 5% threshold"
            )

        return warnings


class KellySizer:
    """Position sizing using Kelly Criterion.

    The Kelly Criterion calculates the optimal bet size to maximize
    long-term growth rate. In practice, fractional Kelly (half or quarter)
    is used to reduce volatility.

    Formula: Kelly% = W - (1-W)/R
    Where: W = Win rate, R = Win/Loss ratio

    Example:
        >>> sizer = KellySizer(fraction=Decimal("0.5"))  # Half-Kelly
        >>> kelly_pct = sizer.calculate_kelly(
        ...     win_rate=Decimal("0.55"),
        ...     avg_win=Decimal("200"),
        ...     avg_loss=Decimal("100"),
        ... )
        >>> print(f"Kelly fraction: {kelly_pct:.2%}")
    """

    def __init__(self, fraction: Decimal = Decimal("0.5")) -> None:
        """Initialize Kelly position sizer.

        Args:
            fraction: Kelly fraction to use.
                     0.5 = half-Kelly (recommended)
                     0.25 = quarter-Kelly (conservative)
                     1.0 = full Kelly (aggressive, not recommended)
        """
        if not Decimal("0") < fraction <= Decimal("1"):
            raise ValueError(f"fraction must be between 0 and 1, got {fraction}")
        self._fraction = fraction
        self._logger = logger.bind(component="kelly_sizer")

    @property
    def fraction(self) -> Decimal:
        """Get configured Kelly fraction."""
        return self._fraction

    def calculate_kelly(
        self,
        win_rate: Decimal,
        avg_win: Decimal,
        avg_loss: Decimal,
    ) -> Decimal:
        """Calculate Kelly fraction for position sizing.

        Args:
            win_rate: Historical win rate (0-1).
            avg_win: Average winning trade amount.
            avg_loss: Average losing trade amount (positive value).

        Returns:
            Recommended position size as fraction of capital.
            Capped at 25% to prevent over-leverage.
        """
        if avg_loss == 0:
            self._logger.warning("kelly_zero_avg_loss", returning=Decimal(0))
            return Decimal(0)

        if not Decimal(0) <= win_rate <= Decimal(1):
            self._logger.warning("kelly_invalid_win_rate", win_rate=str(win_rate))
            return Decimal(0)

        win_loss_ratio = avg_win / avg_loss
        kelly = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Apply fractional Kelly and clamp to reasonable range
        adjusted = max(Decimal(0), kelly * self._fraction)
        capped = min(adjusted, Decimal("0.25"))  # Cap at 25%

        self._logger.debug(
            "kelly_calculated",
            win_rate=f"{win_rate:.2%}",
            win_loss_ratio=str(win_loss_ratio),
            raw_kelly=str(kelly),
            adjusted=str(adjusted),
            capped=str(capped),
        )

        return capped

    def calculate(
        self,
        balance: Decimal,
        entry_price: Decimal,
        win_rate: Decimal,
        avg_win: Decimal,
        avg_loss: Decimal,
    ) -> PositionSize:
        """Calculate position size using Kelly Criterion.

        Args:
            balance: Available capital in quote currency.
            entry_price: Intended entry price.
            win_rate: Historical win rate.
            avg_win: Average winning trade amount.
            avg_loss: Average losing trade amount.

        Returns:
            PositionSize with Kelly-based values.
        """
        kelly_pct = self.calculate_kelly(win_rate, avg_win, avg_loss)
        risk_amount = balance * kelly_pct
        amount = risk_amount / entry_price

        return PositionSize(
            amount=amount,
            risk_amount=risk_amount,
            position_value=amount * entry_price,
            risk_pct_actual=kelly_pct,
        )


class GridPositionSizer:
    """Position sizing optimized for grid trading.

    Grid trading requires distributing capital across multiple price
    levels while maintaining reserve capital for volatility spikes.

    Example:
        >>> sizer = GridPositionSizer(
        ...     allocation_pct=Decimal("0.80"),  # 80% to grid
        ...     reserve_pct=Decimal("0.20"),      # 20% reserve
        ... )
        >>> per_grid = sizer.calculate_per_grid(
        ...     balance=Decimal("10000"),
        ...     num_grids=20,
        ...     active_grids=15,
        ... )
    """

    def __init__(
        self,
        allocation_pct: Decimal = Decimal("0.80"),
        reserve_pct: Decimal = Decimal("0.20"),
    ) -> None:
        """Initialize grid position sizer.

        Args:
            allocation_pct: Percentage of capital allocated to grid.
            reserve_pct: Percentage kept in reserve.

        Raises:
            ValueError: If percentages don't sum to valid range.
        """
        if allocation_pct + reserve_pct > Decimal("1.0"):
            raise ValueError(
                f"allocation_pct ({allocation_pct}) + reserve_pct ({reserve_pct}) "
                "cannot exceed 100%"
            )
        if allocation_pct <= Decimal(0) or reserve_pct < Decimal(0):
            raise ValueError("Percentages must be positive")

        self._allocation_pct = allocation_pct
        self._reserve_pct = reserve_pct
        self._logger = logger.bind(component="grid_position_sizer")

    @property
    def allocation_pct(self) -> Decimal:
        """Get grid allocation percentage."""
        return self._allocation_pct

    @property
    def reserve_pct(self) -> Decimal:
        """Get reserve percentage."""
        return self._reserve_pct

    def calculate_per_grid(
        self,
        balance: Decimal,
        num_grids: int,
        active_grids: Optional[int] = None,
    ) -> Decimal:
        """Calculate amount per grid level.

        Args:
            balance: Total available capital.
            num_grids: Total number of grid levels.
            active_grids: Number of active grids (defaults to num_grids).

        Returns:
            Amount to allocate per grid level.
        """
        if num_grids <= 0:
            raise ValueError("num_grids must be positive")

        active = active_grids if active_grids is not None else num_grids
        if active <= 0:
            raise ValueError("active_grids must be positive")

        allocated_capital = balance * self._allocation_pct
        per_grid = allocated_capital / active

        self._logger.debug(
            "grid_position_calculated",
            balance=str(balance),
            allocated=str(allocated_capital),
            num_grids=num_grids,
            active_grids=active,
            per_grid=str(per_grid),
        )

        return per_grid

    def calculate_grid_allocation(
        self,
        balance: Decimal,
        num_grids: int,
        prices: list[Decimal],
    ) -> dict[Decimal, Decimal]:
        """Calculate allocation for each grid price level.

        Args:
            balance: Total available capital.
            num_grids: Number of grid levels.
            prices: List of grid price levels.

        Returns:
            Dictionary mapping price level to allocation amount.
        """
        if len(prices) != num_grids:
            raise ValueError(
                f"Number of prices ({len(prices)}) must match num_grids ({num_grids})"
            )

        per_grid = self.calculate_per_grid(balance, num_grids)

        # Equal allocation per grid
        return {price: per_grid for price in prices}

    def get_reserve_amount(self, balance: Decimal) -> Decimal:
        """Get the reserve amount not allocated to grid.

        Args:
            balance: Total available capital.

        Returns:
            Amount held in reserve.
        """
        return balance * self._reserve_pct


class DynamicPositionSizer:
    """Dynamic position sizing based on market conditions.

    Adjusts position size based on:
    - Current volatility (ATR-based)
    - Recent drawdown
    - Consecutive win/loss streaks
    """

    def __init__(
        self,
        base_sizer: FixedFractionalSizer,
        volatility_adjustment: bool = True,
        drawdown_adjustment: bool = True,
    ) -> None:
        """Initialize dynamic position sizer.

        Args:
            base_sizer: Base fixed fractional sizer.
            volatility_adjustment: Reduce size in high volatility.
            drawdown_adjustment: Reduce size during drawdowns.
        """
        self._base_sizer = base_sizer
        self._volatility_adjustment = volatility_adjustment
        self._drawdown_adjustment = drawdown_adjustment
        self._logger = logger.bind(component="dynamic_position_sizer")

    def calculate(
        self,
        balance: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        current_atr: Optional[Decimal] = None,
        average_atr: Optional[Decimal] = None,
        current_drawdown_pct: Decimal = Decimal(0),
    ) -> PositionSize:
        """Calculate dynamically adjusted position size.

        Args:
            balance: Available capital.
            entry_price: Intended entry price.
            stop_loss_price: Stop-loss price.
            current_atr: Current ATR value.
            average_atr: Historical average ATR.
            current_drawdown_pct: Current drawdown percentage.

        Returns:
            Adjusted PositionSize.
        """
        # Get base position size
        base_position = self._base_sizer.calculate(
            balance, entry_price, stop_loss_price
        )

        adjustment_factor = Decimal(1)

        # Volatility adjustment: reduce size when volatility is high
        if (
            self._volatility_adjustment
            and current_atr is not None
            and average_atr is not None
            and average_atr > 0
        ):
            volatility_ratio = current_atr / average_atr
            if volatility_ratio > Decimal("1.5"):
                # High volatility: reduce position
                vol_adjustment = Decimal(1) / volatility_ratio
                adjustment_factor *= max(vol_adjustment, Decimal("0.5"))
                self._logger.debug(
                    "volatility_adjustment",
                    ratio=str(volatility_ratio),
                    adjustment=str(vol_adjustment),
                )

        # Drawdown adjustment: reduce size during drawdowns
        if self._drawdown_adjustment and current_drawdown_pct > Decimal("0.05"):
            # Progressively reduce: -50% size at 10% drawdown, -75% at 15%
            dd_factor = Decimal(1) - (current_drawdown_pct * Decimal(5))
            dd_factor = max(dd_factor, Decimal("0.25"))
            adjustment_factor *= dd_factor
            self._logger.debug(
                "drawdown_adjustment",
                drawdown=f"{current_drawdown_pct:.2%}",
                factor=str(dd_factor),
            )

        # Apply adjustments
        adjusted_amount = base_position.amount * adjustment_factor
        adjusted_value = adjusted_amount * entry_price
        adjusted_risk = base_position.risk_amount * adjustment_factor

        self._logger.info(
            "dynamic_position_calculated",
            base_amount=str(base_position.amount),
            adjustment_factor=str(adjustment_factor),
            adjusted_amount=str(adjusted_amount),
        )

        return PositionSize(
            amount=adjusted_amount,
            risk_amount=adjusted_risk,
            position_value=adjusted_value,
            risk_pct_actual=base_position.risk_pct_actual * adjustment_factor,
        )
