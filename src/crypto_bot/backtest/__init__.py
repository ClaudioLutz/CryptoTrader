"""Backtesting infrastructure module.

Provides comprehensive backtesting capabilities:
- Execution context abstraction for live/backtest switching
- Fee and slippage simulation
- Event-driven backtest engine
- Performance metrics calculation
- Parameter optimization (grid search, walk-forward)
"""

from crypto_bot.backtest.execution_context import (
    ExecutionContext,
    ExtendedExecutionContext,
)
from crypto_bot.backtest.simulation import (
    FeeType,
    FeeConfig,
    FeeCalculator,
    SlippageModel,
    NoSlippage,
    FixedSlippage,
    VolumeBasedSlippage,
    RandomSlippage,
    CombinedSlippage,
    LatencyConfig,
    LatencySimulator,
    SimulationConfig,
)
from crypto_bot.backtest.backtest_context import (
    SimulatedOrder,
    BacktestContext,
)
from crypto_bot.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    BacktestEngine,
    BacktestRunner,
)
from crypto_bot.backtest.metrics import (
    ReturnMetrics,
    RiskMetrics,
    RiskAdjustedMetrics,
    TradeMetrics,
    PerformanceReport,
    MetricsCalculator,
    format_report,
)
from crypto_bot.backtest.optimization import (
    ParameterRange,
    OptimizationResult,
    WalkForwardResult,
    GridSearchOptimizer,
    WalkForwardAnalyzer,
    OptimizationReport,
)

__all__ = [
    # Execution Context
    "ExecutionContext",
    "ExtendedExecutionContext",
    # Simulation
    "FeeType",
    "FeeConfig",
    "FeeCalculator",
    "SlippageModel",
    "NoSlippage",
    "FixedSlippage",
    "VolumeBasedSlippage",
    "RandomSlippage",
    "CombinedSlippage",
    "LatencyConfig",
    "LatencySimulator",
    "SimulationConfig",
    # Backtest Context
    "SimulatedOrder",
    "BacktestContext",
    # Engine
    "BacktestConfig",
    "BacktestResult",
    "BacktestEngine",
    "BacktestRunner",
    # Metrics
    "ReturnMetrics",
    "RiskMetrics",
    "RiskAdjustedMetrics",
    "TradeMetrics",
    "PerformanceReport",
    "MetricsCalculator",
    "format_report",
    # Optimization
    "ParameterRange",
    "OptimizationResult",
    "WalkForwardResult",
    "GridSearchOptimizer",
    "WalkForwardAnalyzer",
    "OptimizationReport",
]
