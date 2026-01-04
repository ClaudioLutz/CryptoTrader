"""Trading strategies module.

Provides:
- Strategy protocol interface for pluggable strategies
- Grid trading strategy implementation
- State persistence and reconciliation
"""

from crypto_bot.strategies.base_strategy import (
    ExecutionContext,
    Strategy,
    StrategyConfig,
    StrategyFactory,
)
from crypto_bot.strategies.grid_trading import (
    GridConfig,
    GridLevel,
    GridSpacing,
    GridStatistics,
    GridTradingStrategy,
    calculate_grid_levels,
    calculate_order_size,
    validate_grid_config,
)
from crypto_bot.strategies.strategy_state import (
    DatabaseStateStore,
    InMemoryStateStore,
    ReconciliationError,
    ReconciliationPolicy,
    ReconciliationResult,
    StateManager,
    StateReconciler,
    StateStore,
)

__all__ = [
    # Base strategy
    "ExecutionContext",
    "Strategy",
    "StrategyConfig",
    "StrategyFactory",
    # Grid trading
    "GridConfig",
    "GridLevel",
    "GridSpacing",
    "GridStatistics",
    "GridTradingStrategy",
    "calculate_grid_levels",
    "calculate_order_size",
    "validate_grid_config",
    # State management
    "DatabaseStateStore",
    "InMemoryStateStore",
    "ReconciliationError",
    "ReconciliationPolicy",
    "ReconciliationResult",
    "StateManager",
    "StateReconciler",
    "StateStore",
]
