"""Event-driven backtesting engine.

Runs strategies on historical data using the BacktestContext
to simulate order execution. Generates performance metrics
and equity curves for analysis.

Features:
- Event-driven simulation matching live trading behavior
- Multi-symbol support
- Strategy lifecycle management
- Equity curve and trade history tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, Type

import pandas as pd
import structlog

from crypto_bot.backtest.backtest_context import BacktestContext
from crypto_bot.backtest.simulation import FeeConfig, SimulationConfig
from crypto_bot.exchange.base_exchange import Ticker

logger = structlog.get_logger()


@dataclass
class BacktestConfig:
    """Configuration for backtest execution.

    Attributes:
        start_date: Backtest start date.
        end_date: Backtest end date.
        initial_balance: Initial balances by currency.
        symbols: List of symbols to trade.
        timeframe: Candle timeframe (e.g., "1h").
        fee_config: Fee configuration.
        slippage_rate: Slippage rate for simulation.
    """

    start_date: datetime
    end_date: datetime
    initial_balance: dict[str, Decimal]
    symbols: list[str]
    timeframe: str = "1h"
    fee_config: FeeConfig = field(default_factory=FeeConfig)
    slippage_rate: Decimal = Decimal("0.0005")

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if not self.symbols:
            raise ValueError("At least one symbol required")
        if not self.initial_balance:
            raise ValueError("Initial balance required")


@dataclass
class BacktestResult:
    """Results from a backtest run.

    Attributes:
        config: Backtest configuration used.
        strategy_name: Name of the strategy tested.
        start_date: Actual start date.
        end_date: Actual end date.
        initial_balance: Starting balance.
        final_balance: Ending balance.
        total_return: Total return percentage.
        total_trades: Number of trades executed.
        winning_trades: Number of winning trades.
        losing_trades: Number of losing trades.
        win_rate: Winning trade percentage.
        profit_factor: Gross profit / gross loss.
        max_drawdown: Maximum drawdown percentage.
        sharpe_ratio: Risk-adjusted return metric.
        equity_curve: DataFrame with equity over time.
        trades: List of all trades.
    """

    config: BacktestConfig
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    final_balance: Decimal
    total_return: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    equity_curve: pd.DataFrame
    trades: list[dict]


class BacktestEngine:
    """Event-driven backtesting engine.

    Runs strategies on historical OHLCV data, simulating order
    execution and tracking performance metrics.

    Example:
        >>> config = BacktestConfig(
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 12, 31),
        ...     initial_balance={"USDT": Decimal("10000")},
        ...     symbols=["BTC/USDT"],
        ... )
        >>> engine = BacktestEngine(data_provider, config)
        >>> result = await engine.run(MyStrategy, {"param": value})
    """

    def __init__(
        self,
        data: pd.DataFrame,
        config: BacktestConfig,
    ) -> None:
        """Initialize backtest engine.

        Args:
            data: OHLCV data with columns for each symbol.
                  Expected format: datetime index with {symbol}_close, etc.
            config: Backtest configuration.
        """
        self._data = data
        self._config = config
        self._context: Optional[BacktestContext] = None
        self._logger = logger.bind(component="backtest_engine")

    @property
    def config(self) -> BacktestConfig:
        """Get backtest configuration."""
        return self._config

    async def run(
        self,
        strategy_class: Type,
        strategy_config: dict[str, Any],
    ) -> BacktestResult:
        """Run backtest with the given strategy.

        Args:
            strategy_class: Strategy class to instantiate.
            strategy_config: Configuration for the strategy.

        Returns:
            BacktestResult with performance metrics.
        """
        strategy_name = getattr(strategy_class, "__name__", "Unknown")
        self._logger.info(
            "backtest_starting",
            strategy=strategy_name,
            start=self._config.start_date.isoformat(),
            end=self._config.end_date.isoformat(),
            symbols=self._config.symbols,
        )

        # Initialize context
        self._context = BacktestContext(
            initial_balance=self._config.initial_balance,
            fee_rate=self._config.fee_config.taker_rate,
            slippage_rate=self._config.slippage_rate,
        )

        # Instantiate strategy
        strategy = strategy_class(strategy_config)

        # Initialize strategy with context
        await strategy.initialize(self._context)

        # Track equity curve
        equity_curve: list[dict] = []

        # Filter data to date range
        data = self._data[
            (self._data.index >= self._config.start_date) &
            (self._data.index <= self._config.end_date)
        ]

        # Iterate through data
        for timestamp, row in data.iterrows():
            # Build prices dict for this bar
            prices = {}
            volumes = {}

            for symbol in self._config.symbols:
                close_col = f"{symbol.replace('/', '_')}_close"
                vol_col = f"{symbol.replace('/', '_')}_volume"

                if close_col in row:
                    prices[symbol] = Decimal(str(row[close_col]))
                if vol_col in row:
                    volumes[symbol] = Decimal(str(row[vol_col]))

            if not prices:
                continue

            # Update market state
            self._context.set_market_state(timestamp, prices, volumes)

            # Create ticker for each symbol and call strategy
            for symbol in self._config.symbols:
                if symbol not in prices:
                    continue

                price = prices[symbol]
                ticker = Ticker(
                    symbol=symbol,
                    bid=price * Decimal("0.9999"),
                    ask=price * Decimal("1.0001"),
                    last=price,
                    timestamp=timestamp,
                )

                try:
                    await strategy.on_tick(ticker)
                except Exception as e:
                    self._logger.error(
                        "strategy_error",
                        error=str(e),
                        timestamp=timestamp.isoformat(),
                    )

            # Record equity
            equity = self._context.get_portfolio_value()
            equity_curve.append({
                "timestamp": timestamp,
                "equity": float(equity),
            })

        # Shutdown strategy
        try:
            await strategy.shutdown()
        except Exception as e:
            self._logger.warning("strategy_shutdown_error", error=str(e))

        # Calculate results
        result = self._calculate_results(strategy_name, equity_curve)

        self._logger.info(
            "backtest_complete",
            total_return=f"{result.total_return:.2%}",
            total_trades=result.total_trades,
            max_drawdown=f"{result.max_drawdown:.2%}",
            sharpe_ratio=f"{result.sharpe_ratio:.2f}",
        )

        return result

    def _calculate_results(
        self,
        strategy_name: str,
        equity_curve: list[dict],
    ) -> BacktestResult:
        """Calculate backtest performance metrics.

        Args:
            strategy_name: Name of the strategy.
            equity_curve: List of equity data points.

        Returns:
            BacktestResult with all metrics.
        """
        trades = self._context.get_trade_history()
        equity_df = pd.DataFrame(equity_curve)

        # Basic metrics
        initial = sum(self._config.initial_balance.values())
        final = self._context.get_portfolio_value()
        total_return = (final - initial) / initial if initial > 0 else Decimal(0)

        # Trade analysis
        pnls = self._calculate_trade_pnls(trades)
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        win_rate = Decimal(len(winning)) / len(pnls) if pnls else Decimal(0)

        gross_profit = sum(winning) if winning else Decimal(0)
        gross_loss = abs(sum(losing)) if losing else Decimal(1)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal(0)

        # Drawdown
        max_drawdown = Decimal(0)
        if not equity_df.empty:
            equity_series = equity_df["equity"].astype(float)
            peak = equity_series.expanding().max()
            drawdown = (peak - equity_series) / peak
            max_drawdown = Decimal(str(drawdown.max()))

        # Sharpe ratio
        sharpe = Decimal(0)
        if not equity_df.empty:
            equity_series = equity_df["equity"].astype(float)
            returns = equity_series.pct_change().dropna()
            if len(returns) > 1 and returns.std() > 0:
                # Annualize based on timeframe
                periods_per_year = self._get_periods_per_year()
                sharpe = Decimal(str(
                    (returns.mean() / returns.std()) * (periods_per_year ** 0.5)
                ))

        return BacktestResult(
            config=self._config,
            strategy_name=strategy_name,
            start_date=self._config.start_date,
            end_date=self._config.end_date,
            initial_balance=initial,
            final_balance=final,
            total_return=total_return,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            equity_curve=equity_df,
            trades=trades,
        )

    def _calculate_trade_pnls(self, trades: list[dict]) -> list[Decimal]:
        """Calculate P&L for each completed trade cycle.

        Args:
            trades: List of trade dictionaries.

        Returns:
            List of P&L values for each round-trip trade.
        """
        pnls: list[Decimal] = []
        open_trades: dict[str, list[dict]] = {}

        for trade in trades:
            symbol = trade["symbol"]
            if trade["side"] == "buy":
                if symbol not in open_trades:
                    open_trades[symbol] = []
                open_trades[symbol].append(trade)
            elif symbol in open_trades and open_trades[symbol]:
                buy = open_trades[symbol].pop(0)
                pnl = (
                    (trade["price"] - buy["price"]) * trade["amount"]
                    - trade["fee"] - buy["fee"]
                )
                pnls.append(pnl)

        return pnls

    def _get_periods_per_year(self) -> float:
        """Get number of periods per year based on timeframe."""
        timeframe_periods = {
            "1m": 525600,
            "3m": 175200,
            "5m": 105120,
            "15m": 35040,
            "30m": 17520,
            "1h": 8760,
            "2h": 4380,
            "4h": 2190,
            "6h": 1460,
            "8h": 1095,
            "12h": 730,
            "1d": 365,
            "3d": 122,
            "1w": 52,
        }
        return timeframe_periods.get(self._config.timeframe, 8760)


class BacktestRunner:
    """Convenience class for running multiple backtests.

    Provides utilities for batch backtesting and comparison.

    Example:
        >>> runner = BacktestRunner()
        >>> results = await runner.run_multiple(
        ...     data=ohlcv_data,
        ...     config=base_config,
        ...     strategies=[Strategy1, Strategy2],
        ...     strategy_configs=[config1, config2],
        ... )
    """

    def __init__(self) -> None:
        """Initialize backtest runner."""
        self._logger = logger.bind(component="backtest_runner")

    async def run_multiple(
        self,
        data: pd.DataFrame,
        config: BacktestConfig,
        strategies: list[Type],
        strategy_configs: list[dict[str, Any]],
    ) -> list[BacktestResult]:
        """Run multiple strategies and compare results.

        Args:
            data: OHLCV data for backtesting.
            config: Base backtest configuration.
            strategies: List of strategy classes.
            strategy_configs: Configuration for each strategy.

        Returns:
            List of BacktestResults.
        """
        if len(strategies) != len(strategy_configs):
            raise ValueError("Number of strategies must match number of configs")

        results = []
        for strategy_class, strategy_config in zip(strategies, strategy_configs):
            engine = BacktestEngine(data, config)
            result = await engine.run(strategy_class, strategy_config)
            results.append(result)

        return results

    def compare_results(self, results: list[BacktestResult]) -> pd.DataFrame:
        """Create comparison table of backtest results.

        Args:
            results: List of backtest results.

        Returns:
            DataFrame comparing key metrics.
        """
        rows = []
        for result in results:
            rows.append({
                "Strategy": result.strategy_name,
                "Total Return": f"{result.total_return:.2%}",
                "Max Drawdown": f"{result.max_drawdown:.2%}",
                "Sharpe Ratio": f"{result.sharpe_ratio:.2f}",
                "Win Rate": f"{result.win_rate:.2%}",
                "Profit Factor": f"{result.profit_factor:.2f}",
                "Total Trades": result.total_trades,
            })

        return pd.DataFrame(rows)

    def print_summary(self, result: BacktestResult) -> None:
        """Print formatted backtest summary.

        Args:
            result: Backtest result to summarize.
        """
        print(f"\n{'=' * 50}")
        print(f"Backtest Results: {result.strategy_name}")
        print(f"{'=' * 50}")
        print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
        print(f"Initial Balance: ${result.initial_balance:,.2f}")
        print(f"Final Balance: ${result.final_balance:,.2f}")
        print(f"Total Return: {result.total_return:.2%}")
        print(f"{'=' * 50}")
        print("Risk Metrics:")
        print(f"  Max Drawdown: {result.max_drawdown:.2%}")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"{'=' * 50}")
        print("Trade Statistics:")
        print(f"  Total Trades: {result.total_trades}")
        print(f"  Winning Trades: {result.winning_trades}")
        print(f"  Losing Trades: {result.losing_trades}")
        print(f"  Win Rate: {result.win_rate:.2%}")
        print(f"  Profit Factor: {result.profit_factor:.2f}")
        print(f"{'=' * 50}\n")
