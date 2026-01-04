"""Risk management module.

Provides comprehensive risk management for trading:
- Position sizing (Fixed Fractional, Kelly, Grid)
- Stop-loss handling (Fixed, Percentage, Trailing, ATR)
- Circuit breaker (Daily loss, Consecutive losses, Max drawdown)
- Drawdown tracking and analysis
- Central risk manager orchestrating all components
"""

from crypto_bot.risk.position_sizer import (
    PositionSize,
    FixedFractionalSizer,
    KellySizer,
    GridPositionSizer,
    DynamicPositionSizer,
)
from crypto_bot.risk.stop_loss import (
    StopLossType,
    StopLossConfig,
    StopLossState,
    StopLossHandler,
    GridStopLoss,
    StopLossManager,
)
from crypto_bot.risk.circuit_breaker import (
    CircuitBreakerTrigger,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreaker,
    CircuitBreakerManager,
)
from crypto_bot.risk.drawdown import (
    DrawdownMetrics,
    DrawdownPeriod,
    DrawdownTracker,
    DrawdownAnalyzer,
    DrawdownAlert,
)
from crypto_bot.risk.risk_manager import (
    RiskConfig,
    TradeValidation,
    RiskManager,
    RiskManagerFactory,
)

__all__ = [
    # Position Sizing
    "PositionSize",
    "FixedFractionalSizer",
    "KellySizer",
    "GridPositionSizer",
    "DynamicPositionSizer",
    # Stop-Loss
    "StopLossType",
    "StopLossConfig",
    "StopLossState",
    "StopLossHandler",
    "GridStopLoss",
    "StopLossManager",
    # Circuit Breaker
    "CircuitBreakerTrigger",
    "CircuitBreakerConfig",
    "CircuitBreakerState",
    "CircuitBreaker",
    "CircuitBreakerManager",
    # Drawdown
    "DrawdownMetrics",
    "DrawdownPeriod",
    "DrawdownTracker",
    "DrawdownAnalyzer",
    "DrawdownAlert",
    # Risk Manager
    "RiskConfig",
    "TradeValidation",
    "RiskManager",
    "RiskManagerFactory",
]
