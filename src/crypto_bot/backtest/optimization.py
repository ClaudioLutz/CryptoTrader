"""Parameter optimization framework for strategy tuning.

Provides systematic parameter optimization approaches:
- Grid search: Exhaustive search over parameter space
- Walk-forward analysis: Rolling window validation
- Multi-objective optimization: Balance multiple metrics

Best Practices:
- Always use out-of-sample validation
- Avoid overfitting with walk-forward analysis
- Consider transaction costs in optimization
- Focus on robust parameters, not optimal ones
"""

import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Type

import pandas as pd
import structlog

from crypto_bot.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult

logger = structlog.get_logger()


@dataclass
class ParameterRange:
    """Definition of a parameter range for optimization.

    Attributes:
        name: Parameter name in strategy config.
        values: List of values to test.
        param_type: Type for casting (Decimal, int, float, etc.).
    """

    name: str
    values: list[Any]
    param_type: type = float

    @classmethod
    def from_range(
        cls,
        name: str,
        start: float,
        end: float,
        step: float,
        param_type: type = float,
    ) -> "ParameterRange":
        """Create parameter range from start, end, step.

        Args:
            name: Parameter name.
            start: Starting value.
            end: Ending value (inclusive).
            step: Step size.
            param_type: Type for casting.

        Returns:
            ParameterRange with computed values.
        """
        values = []
        current = start
        while current <= end:
            if param_type == int:
                values.append(int(current))
            elif param_type == Decimal:
                values.append(Decimal(str(current)))
            else:
                values.append(param_type(current))
            current += step
        return cls(name=name, values=values, param_type=param_type)


@dataclass
class OptimizationResult:
    """Result from parameter optimization.

    Attributes:
        best_params: Best performing parameter combination.
        best_metric: Value of the optimization metric.
        all_results: All tested combinations with results.
        metric_name: Name of the optimization metric.
        run_time: Total optimization time in seconds.
    """

    best_params: dict[str, Any]
    best_metric: Decimal
    all_results: list[dict]
    metric_name: str
    run_time: float


@dataclass
class WalkForwardResult:
    """Result from walk-forward analysis.

    Attributes:
        fold_results: Results for each fold.
        aggregated_metrics: Combined metrics across all folds.
        robustness_score: Score indicating parameter stability.
        best_params_per_fold: Best parameters found in each fold.
        out_of_sample_performance: Combined OOS performance.
    """

    fold_results: list[BacktestResult]
    aggregated_metrics: dict[str, Decimal]
    robustness_score: Decimal
    best_params_per_fold: list[dict]
    out_of_sample_performance: Decimal


class GridSearchOptimizer:
    """Exhaustive grid search parameter optimization.

    Tests all combinations of parameter values to find
    the best performing configuration.

    Example:
        >>> optimizer = GridSearchOptimizer(
        ...     strategy_class=MyStrategy,
        ...     data=ohlcv_data,
        ...     base_config=backtest_config,
        ...     base_strategy_config={"symbol": "BTC/USDT"},
        ... )
        >>> result = await optimizer.optimize(
        ...     parameter_ranges=[
        ...         ParameterRange.from_range("grid_spacing", 0.01, 0.05, 0.01),
        ...         ParameterRange.from_range("num_grids", 5, 20, 5, int),
        ...     ],
        ...     metric="sharpe_ratio",
        ... )
    """

    def __init__(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        base_config: BacktestConfig,
        base_strategy_config: dict[str, Any],
    ) -> None:
        """Initialize grid search optimizer.

        Args:
            strategy_class: Strategy class to optimize.
            data: Historical data for backtesting.
            base_config: Base backtest configuration.
            base_strategy_config: Base strategy configuration.
        """
        self._strategy_class = strategy_class
        self._data = data
        self._base_config = base_config
        self._base_strategy_config = base_strategy_config
        self._logger = logger.bind(component="grid_search_optimizer")

    async def optimize(
        self,
        parameter_ranges: list[ParameterRange],
        metric: str = "sharpe_ratio",
        maximize: bool = True,
        max_workers: int = 4,
    ) -> OptimizationResult:
        """Run grid search optimization.

        Args:
            parameter_ranges: Parameter ranges to search.
            metric: Metric to optimize (sharpe_ratio, total_return, etc.).
            maximize: Whether to maximize (True) or minimize (False).
            max_workers: Maximum parallel backtests.

        Returns:
            OptimizationResult with best parameters.
        """
        start_time = datetime.now()

        # Generate all parameter combinations
        param_names = [p.name for p in parameter_ranges]
        param_values = [p.values for p in parameter_ranges]
        combinations = list(itertools.product(*param_values))

        total_combinations = len(combinations)
        self._logger.info(
            "grid_search_starting",
            parameters=param_names,
            combinations=total_combinations,
        )

        all_results = []

        # Run backtests for each combination
        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            strategy_config = {**self._base_strategy_config, **params}

            engine = BacktestEngine(self._data, self._base_config)
            result = await engine.run(self._strategy_class, strategy_config)

            metric_value = self._get_metric(result, metric)
            all_results.append({
                "params": params,
                "metric": metric_value,
                "result": result,
            })

            if (i + 1) % 10 == 0:
                self._logger.info(
                    "optimization_progress",
                    completed=i + 1,
                    total=total_combinations,
                )

        # Find best result
        if maximize:
            best = max(all_results, key=lambda x: x["metric"])
        else:
            best = min(all_results, key=lambda x: x["metric"])

        run_time = (datetime.now() - start_time).total_seconds()

        self._logger.info(
            "grid_search_complete",
            best_params=best["params"],
            best_metric=str(best["metric"]),
            run_time=run_time,
        )

        return OptimizationResult(
            best_params=best["params"],
            best_metric=best["metric"],
            all_results=[{
                "params": r["params"],
                "metric": float(r["metric"]),
            } for r in all_results],
            metric_name=metric,
            run_time=run_time,
        )

    def _get_metric(self, result: BacktestResult, metric: str) -> Decimal:
        """Extract metric value from backtest result."""
        metric_map = {
            "sharpe_ratio": result.sharpe_ratio,
            "total_return": result.total_return,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
        }
        return metric_map.get(metric, Decimal(0))


class WalkForwardAnalyzer:
    """Walk-forward analysis for robust parameter optimization.

    Splits data into rolling windows, optimizes on in-sample data,
    and validates on out-of-sample data to prevent overfitting.

    Example:
        >>> analyzer = WalkForwardAnalyzer(
        ...     strategy_class=MyStrategy,
        ...     data=ohlcv_data,
        ...     base_config=backtest_config,
        ...     base_strategy_config={"symbol": "BTC/USDT"},
        ... )
        >>> result = await analyzer.analyze(
        ...     parameter_ranges=[...],
        ...     num_folds=5,
        ...     in_sample_pct=0.7,
        ... )
    """

    def __init__(
        self,
        strategy_class: Type,
        data: pd.DataFrame,
        base_config: BacktestConfig,
        base_strategy_config: dict[str, Any],
    ) -> None:
        """Initialize walk-forward analyzer.

        Args:
            strategy_class: Strategy class to analyze.
            data: Historical data for backtesting.
            base_config: Base backtest configuration.
            base_strategy_config: Base strategy configuration.
        """
        self._strategy_class = strategy_class
        self._data = data
        self._base_config = base_config
        self._base_strategy_config = base_strategy_config
        self._logger = logger.bind(component="walk_forward_analyzer")

    async def analyze(
        self,
        parameter_ranges: list[ParameterRange],
        num_folds: int = 5,
        in_sample_pct: float = 0.7,
        metric: str = "sharpe_ratio",
    ) -> WalkForwardResult:
        """Run walk-forward analysis.

        Args:
            parameter_ranges: Parameter ranges to test.
            num_folds: Number of rolling windows.
            in_sample_pct: Percentage of each fold for in-sample.
            metric: Metric to optimize.

        Returns:
            WalkForwardResult with analysis results.
        """
        self._logger.info(
            "walk_forward_starting",
            num_folds=num_folds,
            in_sample_pct=in_sample_pct,
        )

        # Split data into folds
        folds = self._create_folds(num_folds, in_sample_pct)

        fold_results = []
        best_params_per_fold = []
        oos_returns = []

        for i, (in_sample, out_of_sample) in enumerate(folds):
            self._logger.info(f"Processing fold {i + 1}/{num_folds}")

            # Optimize on in-sample data
            is_config = self._create_config(in_sample)
            optimizer = GridSearchOptimizer(
                strategy_class=self._strategy_class,
                data=in_sample,
                base_config=is_config,
                base_strategy_config=self._base_strategy_config,
            )

            opt_result = await optimizer.optimize(
                parameter_ranges=parameter_ranges,
                metric=metric,
            )
            best_params = opt_result.best_params
            best_params_per_fold.append(best_params)

            # Validate on out-of-sample data
            oos_config = self._create_config(out_of_sample)
            strategy_config = {**self._base_strategy_config, **best_params}

            engine = BacktestEngine(out_of_sample, oos_config)
            oos_result = await engine.run(self._strategy_class, strategy_config)
            fold_results.append(oos_result)
            oos_returns.append(float(oos_result.total_return))

            self._logger.info(
                f"Fold {i + 1} complete",
                best_params=best_params,
                oos_return=f"{oos_result.total_return:.2%}",
            )

        # Aggregate metrics
        aggregated = self._aggregate_results(fold_results)
        oos_performance = Decimal(str(sum(oos_returns) / len(oos_returns)))

        # Calculate robustness score
        robustness = self._calculate_robustness(best_params_per_fold)

        self._logger.info(
            "walk_forward_complete",
            oos_performance=f"{oos_performance:.2%}",
            robustness_score=f"{robustness:.2f}",
        )

        return WalkForwardResult(
            fold_results=fold_results,
            aggregated_metrics=aggregated,
            robustness_score=robustness,
            best_params_per_fold=best_params_per_fold,
            out_of_sample_performance=oos_performance,
        )

    def _create_folds(
        self,
        num_folds: int,
        in_sample_pct: float,
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """Create rolling window folds.

        Args:
            num_folds: Number of folds.
            in_sample_pct: In-sample percentage.

        Returns:
            List of (in_sample, out_of_sample) DataFrame tuples.
        """
        folds = []
        total_len = len(self._data)
        fold_size = total_len // num_folds
        in_sample_size = int(fold_size * in_sample_pct)

        for i in range(num_folds):
            start = i * fold_size
            is_end = start + in_sample_size
            oos_end = min(start + fold_size, total_len)

            in_sample = self._data.iloc[start:is_end]
            out_of_sample = self._data.iloc[is_end:oos_end]

            folds.append((in_sample, out_of_sample))

        return folds

    def _create_config(self, data: pd.DataFrame) -> BacktestConfig:
        """Create BacktestConfig for a data subset."""
        start_date = data.index[0] if hasattr(data.index[0], "date") else datetime.now()
        end_date = data.index[-1] if hasattr(data.index[-1], "date") else datetime.now()

        return BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_balance=self._base_config.initial_balance,
            symbols=self._base_config.symbols,
            timeframe=self._base_config.timeframe,
            fee_config=self._base_config.fee_config,
            slippage_rate=self._base_config.slippage_rate,
        )

    def _aggregate_results(
        self,
        results: list[BacktestResult],
    ) -> dict[str, Decimal]:
        """Aggregate metrics across folds."""
        if not results:
            return {}

        return {
            "avg_total_return": Decimal(str(
                sum(float(r.total_return) for r in results) / len(results)
            )),
            "avg_sharpe_ratio": Decimal(str(
                sum(float(r.sharpe_ratio) for r in results) / len(results)
            )),
            "avg_max_drawdown": Decimal(str(
                sum(float(r.max_drawdown) for r in results) / len(results)
            )),
            "avg_win_rate": Decimal(str(
                sum(float(r.win_rate) for r in results) / len(results)
            )),
        }

    def _calculate_robustness(
        self,
        params_per_fold: list[dict],
    ) -> Decimal:
        """Calculate parameter robustness score.

        Measures how stable the optimal parameters are across folds.
        Higher score means more robust parameters.
        """
        if len(params_per_fold) < 2:
            return Decimal("1.0")

        # Calculate coefficient of variation for each parameter
        cvs = []
        param_names = params_per_fold[0].keys()

        for name in param_names:
            values = [float(p[name]) for p in params_per_fold if name in p]
            if len(values) > 1 and sum(values) > 0:
                mean = sum(values) / len(values)
                std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
                cv = std / mean if mean > 0 else 0
                cvs.append(cv)

        # Robustness = 1 - average CV (higher = more robust)
        avg_cv = sum(cvs) / len(cvs) if cvs else 0
        robustness = max(0, min(1, 1 - avg_cv))

        return Decimal(str(robustness))


class OptimizationReport:
    """Generate reports from optimization results."""

    @staticmethod
    def parameter_sensitivity(result: OptimizationResult) -> pd.DataFrame:
        """Analyze parameter sensitivity.

        Shows how performance varies with each parameter.

        Args:
            result: Grid search optimization result.

        Returns:
            DataFrame with sensitivity analysis.
        """
        all_results = result.all_results

        sensitivity_data = []
        params_tested = set()
        for r in all_results:
            params_tested.update(r["params"].keys())

        for param_name in params_tested:
            param_values = {}
            for r in all_results:
                val = r["params"].get(param_name)
                if val is not None:
                    if val not in param_values:
                        param_values[val] = []
                    param_values[val].append(r["metric"])

            for val, metrics in param_values.items():
                avg_metric = sum(metrics) / len(metrics)
                sensitivity_data.append({
                    "parameter": param_name,
                    "value": val,
                    "avg_metric": avg_metric,
                    "num_tests": len(metrics),
                })

        return pd.DataFrame(sensitivity_data)

    @staticmethod
    def heatmap_data(
        result: OptimizationResult,
        x_param: str,
        y_param: str,
    ) -> pd.DataFrame:
        """Generate heatmap data for 2D parameter visualization.

        Args:
            result: Grid search result.
            x_param: Parameter for x-axis.
            y_param: Parameter for y-axis.

        Returns:
            Pivot table suitable for heatmap plotting.
        """
        data = []
        for r in result.all_results:
            if x_param in r["params"] and y_param in r["params"]:
                data.append({
                    x_param: r["params"][x_param],
                    y_param: r["params"][y_param],
                    "metric": r["metric"],
                })

        df = pd.DataFrame(data)
        if not df.empty:
            return df.pivot_table(
                index=y_param,
                columns=x_param,
                values="metric",
                aggfunc="mean",
            )
        return df

    @staticmethod
    def summary(result: OptimizationResult) -> str:
        """Generate text summary of optimization results.

        Args:
            result: Optimization result.

        Returns:
            Formatted summary string.
        """
        lines = []
        lines.append("=" * 50)
        lines.append("OPTIMIZATION SUMMARY")
        lines.append("=" * 50)
        lines.append(f"Metric Optimized: {result.metric_name}")
        lines.append(f"Best Value: {result.best_metric:.4f}")
        lines.append(f"Total Combinations Tested: {len(result.all_results)}")
        lines.append(f"Run Time: {result.run_time:.1f} seconds")
        lines.append("-" * 50)
        lines.append("Best Parameters:")
        for name, value in result.best_params.items():
            lines.append(f"  {name}: {value}")
        lines.append("=" * 50)
        return "\n".join(lines)
