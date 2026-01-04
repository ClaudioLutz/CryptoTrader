"""Fee and slippage simulation for realistic backtesting.

Provides realistic modeling of:
- Trading fees (percentage, fixed, tiered)
- Slippage (fixed, volume-based, random)
- Latency effects

Best Practices (2025):
- Binance spot fee: ~0.1% maker/taker
- Realistic slippage: 0.05-0.1% for liquid pairs
- Volume-based slippage for large orders
- Latency spikes can cause significant price drift
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class FeeType(str, Enum):
    """Types of fee structures."""

    PERCENTAGE = "percentage"  # Percentage of trade value
    FIXED = "fixed"  # Fixed fee per trade
    TIERED = "tiered"  # Volume-based tiered rates


@dataclass
class FeeConfig:
    """Configuration for fee calculation.

    Attributes:
        type: Fee calculation type.
        maker_rate: Maker fee rate (limit orders adding liquidity).
        taker_rate: Taker fee rate (market orders taking liquidity).
        fixed_fee: Fixed fee amount (for FIXED type).
        volume_tiers: Volume-based tiers (for TIERED type).
                     Dict mapping 30d volume threshold -> rate.
    """

    type: FeeType = FeeType.PERCENTAGE
    maker_rate: Decimal = Decimal("0.001")  # 0.1%
    taker_rate: Decimal = Decimal("0.001")  # 0.1%
    fixed_fee: Decimal = Decimal(0)
    volume_tiers: Optional[dict[Decimal, Decimal]] = None

    def __post_init__(self) -> None:
        """Validate fee configuration."""
        if self.maker_rate < 0 or self.taker_rate < 0:
            raise ValueError("Fee rates cannot be negative")
        if self.type == FeeType.TIERED and not self.volume_tiers:
            raise ValueError("Volume tiers required for tiered fee type")


class FeeCalculator:
    """Calculate trading fees based on configuration.

    Example:
        >>> config = FeeConfig(maker_rate=Decimal("0.001"))
        >>> calc = FeeCalculator(config)
        >>> fee = calc.calculate(Decimal("1.0"), Decimal("50000"), is_maker=False)
        >>> print(f"Fee: ${fee}")
    """

    def __init__(self, config: FeeConfig) -> None:
        """Initialize fee calculator.

        Args:
            config: Fee configuration.
        """
        self._config = config
        self._30d_volume = Decimal(0)
        self._logger = logger.bind(component="fee_calculator")

    @property
    def config(self) -> FeeConfig:
        """Get fee configuration."""
        return self._config

    def calculate(
        self,
        amount: Decimal,
        price: Decimal,
        is_maker: bool = False,
    ) -> Decimal:
        """Calculate fee for a trade.

        Args:
            amount: Trade amount in base currency.
            price: Trade price.
            is_maker: Whether this is a maker order.

        Returns:
            Fee amount in quote currency.
        """
        notional = amount * price

        if self._config.type == FeeType.FIXED:
            return self._config.fixed_fee

        elif self._config.type == FeeType.PERCENTAGE:
            rate = self._config.maker_rate if is_maker else self._config.taker_rate
            return notional * rate

        elif self._config.type == FeeType.TIERED:
            rate = self._get_tiered_rate(is_maker)
            return notional * rate

        return Decimal(0)

    def _get_tiered_rate(self, is_maker: bool) -> Decimal:
        """Get fee rate based on 30-day volume.

        Args:
            is_maker: Whether this is a maker order.

        Returns:
            Applicable fee rate.
        """
        if not self._config.volume_tiers:
            return self._config.maker_rate if is_maker else self._config.taker_rate

        # Find applicable tier
        applicable_rate = self._config.taker_rate
        for volume_threshold, rate in sorted(self._config.volume_tiers.items()):
            if self._30d_volume >= volume_threshold:
                applicable_rate = rate
            else:
                break

        return applicable_rate

    def update_volume(self, trade_value: Decimal) -> None:
        """Update 30-day rolling volume.

        Args:
            trade_value: Value of completed trade.
        """
        self._30d_volume += trade_value

    def reset_volume(self) -> None:
        """Reset 30-day volume tracking."""
        self._30d_volume = Decimal(0)


class SlippageModel(ABC):
    """Base class for slippage models.

    Slippage represents the difference between expected execution
    price and actual execution price. It's typically adverse
    (worse than expected).
    """

    @abstractmethod
    def calculate(
        self,
        price: Decimal,
        amount: Decimal,
        side: str,
        volume: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate slippage-adjusted execution price.

        Args:
            price: Expected price.
            amount: Order amount.
            side: "buy" or "sell".
            volume: Market volume (for volume-based models).

        Returns:
            Adjusted execution price (worse than expected).
        """
        pass


class NoSlippage(SlippageModel):
    """No slippage model (unrealistic, for testing only)."""

    def calculate(
        self,
        price: Decimal,
        amount: Decimal,
        side: str,
        volume: Optional[Decimal] = None,
    ) -> Decimal:
        """Return price unchanged."""
        return price


class FixedSlippage(SlippageModel):
    """Fixed percentage slippage.

    Applies a constant slippage rate regardless of order size.
    Simple but may underestimate slippage on large orders.

    Example:
        >>> slippage = FixedSlippage(rate=Decimal("0.0005"))  # 0.05%
        >>> exec_price = slippage.calculate(Decimal("50000"), Decimal("1"), "buy")
        >>> # Buy order executes at 50025 (slightly higher)
    """

    def __init__(self, rate: Decimal = Decimal("0.0005")) -> None:
        """Initialize fixed slippage model.

        Args:
            rate: Slippage rate (e.g., 0.0005 for 0.05%).
        """
        if rate < 0:
            raise ValueError("Slippage rate cannot be negative")
        self._rate = rate

    @property
    def rate(self) -> Decimal:
        """Get slippage rate."""
        return self._rate

    def calculate(
        self,
        price: Decimal,
        amount: Decimal,
        side: str,
        volume: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate fixed slippage-adjusted price.

        Buy orders pay slightly more, sell orders receive slightly less.

        Args:
            price: Expected price.
            amount: Order amount (unused).
            side: "buy" or "sell".
            volume: Market volume (unused).

        Returns:
            Slippage-adjusted price.
        """
        if side == "buy":
            return price * (1 + self._rate)
        else:
            return price * (1 - self._rate)


class VolumeBasedSlippage(SlippageModel):
    """Slippage based on order size relative to market volume.

    Larger orders relative to market volume experience more slippage
    due to market impact. More realistic for large orders.

    Example:
        >>> slippage = VolumeBasedSlippage(
        ...     base_rate=Decimal("0.0001"),
        ...     volume_impact=Decimal("0.1"),
        ... )
        >>> # Large order (10% of volume) has higher slippage
        >>> exec_price = slippage.calculate(
        ...     Decimal("50000"), Decimal("100"), "buy",
        ...     volume=Decimal("1000")
        ... )
    """

    def __init__(
        self,
        base_rate: Decimal = Decimal("0.0001"),  # 0.01%
        volume_impact: Decimal = Decimal("0.1"),  # 10% of order%
    ) -> None:
        """Initialize volume-based slippage model.

        Args:
            base_rate: Base slippage rate.
            volume_impact: Multiplier for order-to-volume ratio.
        """
        self._base_rate = base_rate
        self._volume_impact = volume_impact

    def calculate(
        self,
        price: Decimal,
        amount: Decimal,
        side: str,
        volume: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate volume-adjusted slippage.

        Args:
            price: Expected price.
            amount: Order amount.
            side: "buy" or "sell".
            volume: Market volume (notional).

        Returns:
            Slippage-adjusted price.
        """
        # Base slippage
        slippage = self._base_rate

        # Add volume impact
        if volume and volume > 0:
            order_value = amount * price
            order_pct = order_value / volume
            slippage += order_pct * self._volume_impact

        if side == "buy":
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)


class RandomSlippage(SlippageModel):
    """Random slippage within a range.

    Adds randomness to simulate real-world variability in execution.
    Useful for Monte Carlo simulations.

    Example:
        >>> slippage = RandomSlippage(
        ...     min_rate=Decimal("0.0001"),
        ...     max_rate=Decimal("0.001"),
        ... )
    """

    def __init__(
        self,
        min_rate: Decimal = Decimal("0.0001"),  # 0.01%
        max_rate: Decimal = Decimal("0.001"),  # 0.1%
    ) -> None:
        """Initialize random slippage model.

        Args:
            min_rate: Minimum slippage rate.
            max_rate: Maximum slippage rate.
        """
        if min_rate > max_rate:
            raise ValueError("min_rate cannot exceed max_rate")
        self._min_rate = float(min_rate)
        self._max_rate = float(max_rate)

    def calculate(
        self,
        price: Decimal,
        amount: Decimal,
        side: str,
        volume: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate random slippage-adjusted price.

        Args:
            price: Expected price.
            amount: Order amount (unused).
            side: "buy" or "sell".
            volume: Market volume (unused).

        Returns:
            Randomly slippage-adjusted price.
        """
        rate = Decimal(str(random.uniform(self._min_rate, self._max_rate)))

        if side == "buy":
            return price * (1 + rate)
        else:
            return price * (1 - rate)


class CombinedSlippage(SlippageModel):
    """Combines multiple slippage models.

    Useful for modeling both base slippage and volume impact.
    """

    def __init__(self, models: list[SlippageModel]) -> None:
        """Initialize combined slippage model.

        Args:
            models: List of slippage models to combine.
        """
        self._models = models

    def calculate(
        self,
        price: Decimal,
        amount: Decimal,
        side: str,
        volume: Optional[Decimal] = None,
    ) -> Decimal:
        """Apply all slippage models sequentially.

        Args:
            price: Expected price.
            amount: Order amount.
            side: "buy" or "sell".
            volume: Market volume.

        Returns:
            Combined slippage-adjusted price.
        """
        result = price
        for model in self._models:
            result = model.calculate(result, amount, side, volume)
        return result


@dataclass
class LatencyConfig:
    """Configuration for latency simulation.

    Attributes:
        min_ms: Minimum latency in milliseconds.
        max_ms: Maximum normal latency.
        spike_probability: Probability of latency spike.
        spike_max_ms: Maximum latency during spike.
    """

    min_ms: int = 50
    max_ms: int = 200
    spike_probability: float = 0.01  # 1% chance of spike
    spike_max_ms: int = 2000


class LatencySimulator:
    """Simulate network latency for order execution.

    Models realistic network delays including occasional spikes
    that can cause price drift between order and execution.

    Example:
        >>> lat = LatencySimulator(LatencyConfig())
        >>> latency = lat.get_latency_ms()
        >>> # Simulate price movement during latency
        >>> exec_price = lat.get_execution_price(
        ...     Decimal("50000"), Decimal("50050"), "market", "buy"
        ... )
    """

    def __init__(self, config: Optional[LatencyConfig] = None) -> None:
        """Initialize latency simulator.

        Args:
            config: Latency configuration.
        """
        self._config = config or LatencyConfig()
        self._logger = logger.bind(component="latency_simulator")

    def get_latency_ms(self) -> int:
        """Get simulated latency in milliseconds.

        Returns:
            Simulated latency value.
        """
        if random.random() < self._config.spike_probability:
            latency = random.randint(self._config.max_ms, self._config.spike_max_ms)
            self._logger.debug("latency_spike", latency_ms=latency)
            return latency
        return random.randint(self._config.min_ms, self._config.max_ms)

    def get_execution_price(
        self,
        order_price: Decimal,
        price_at_execution: Decimal,
        order_type: str,
        side: str,
    ) -> Optional[Decimal]:
        """Get execution price accounting for latency-induced price drift.

        For market orders, uses price at execution time.
        For limit orders, uses limit price if still valid.

        Args:
            order_price: Price when order was placed.
            price_at_execution: Price when order reaches exchange.
            order_type: "market" or "limit".
            side: "buy" or "sell".

        Returns:
            Execution price, or None if limit order can't fill.
        """
        if order_type == "market":
            return price_at_execution

        # Limit order - check if still valid
        if side == "buy":
            if price_at_execution <= order_price:
                return order_price  # Fill at limit
            else:
                return None  # Price moved up, order not filled
        else:
            if price_at_execution >= order_price:
                return order_price  # Fill at limit
            else:
                return None  # Price moved down, order not filled


@dataclass
class SimulationConfig:
    """Combined configuration for all simulation components.

    Attributes:
        fee_config: Fee calculation configuration.
        slippage_model: Slippage model to use.
        latency_config: Latency simulation configuration.
        enable_latency: Whether to simulate latency.
    """

    fee_config: FeeConfig
    slippage_model: SlippageModel
    latency_config: LatencyConfig
    enable_latency: bool = True

    @classmethod
    def realistic(cls) -> "SimulationConfig":
        """Create realistic simulation configuration.

        Returns:
            Configuration matching typical exchange conditions.
        """
        return cls(
            fee_config=FeeConfig(
                type=FeeType.PERCENTAGE,
                maker_rate=Decimal("0.001"),  # 0.1%
                taker_rate=Decimal("0.001"),  # 0.1%
            ),
            slippage_model=VolumeBasedSlippage(
                base_rate=Decimal("0.0002"),  # 0.02%
                volume_impact=Decimal("0.05"),  # 5% of order%
            ),
            latency_config=LatencyConfig(
                min_ms=50,
                max_ms=200,
                spike_probability=0.01,
                spike_max_ms=2000,
            ),
            enable_latency=True,
        )

    @classmethod
    def conservative(cls) -> "SimulationConfig":
        """Create conservative simulation with higher costs.

        Returns:
            Configuration that overestimates costs for safety.
        """
        return cls(
            fee_config=FeeConfig(
                type=FeeType.PERCENTAGE,
                maker_rate=Decimal("0.0015"),  # 0.15%
                taker_rate=Decimal("0.0015"),  # 0.15%
            ),
            slippage_model=FixedSlippage(rate=Decimal("0.001")),  # 0.1%
            latency_config=LatencyConfig(
                min_ms=100,
                max_ms=500,
                spike_probability=0.05,
                spike_max_ms=5000,
            ),
            enable_latency=True,
        )

    @classmethod
    def optimistic(cls) -> "SimulationConfig":
        """Create optimistic simulation with lower costs.

        Returns:
            Configuration with minimal friction (use cautiously).
        """
        return cls(
            fee_config=FeeConfig(
                type=FeeType.PERCENTAGE,
                maker_rate=Decimal("0.0005"),  # 0.05%
                taker_rate=Decimal("0.0005"),  # 0.05%
            ),
            slippage_model=FixedSlippage(rate=Decimal("0.0002")),  # 0.02%
            latency_config=LatencyConfig(
                min_ms=20,
                max_ms=100,
                spike_probability=0.001,
                spike_max_ms=500,
            ),
            enable_latency=False,
        )
