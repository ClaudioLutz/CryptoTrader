"""Performance metrics calculator for trading strategy analysis.

Provides comprehensive performance metrics:
- Return metrics (total return, CAGR, monthly returns)
- Risk metrics (volatility, max drawdown, VaR)
- Risk-adjusted metrics (Sharpe, Sortino, Calmar)
- Trade statistics (win rate, profit factor, expectancy)
"""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()


@dataclass
class ReturnMetrics:
    """Return-related performance metrics.

    Attributes:
        total_return: Total return percentage.
        cagr: Compound Annual Growth Rate.
        monthly_returns: List of monthly return percentages.
        best_month: Best monthly return.
        worst_month: Worst monthly return.
        positive_months: Number of positive months.
        negative_months: Number of negative months.
    """

    total_return: Decimal
    cagr: Decimal
    monthly_returns: list[Decimal]
    best_month: Decimal
    worst_month: Decimal
    positive_months: int
    negative_months: int


@dataclass
class RiskMetrics:
    """Risk-related performance metrics.

    Attributes:
        volatility: Annualized volatility (std of returns).
        max_drawdown: Maximum drawdown percentage.
        avg_drawdown: Average drawdown during drawdown periods.
        max_drawdown_duration: Longest drawdown period (days).
        var_95: Value at Risk at 95% confidence.
        var_99: Value at Risk at 99% confidence.
        cvar_95: Conditional VaR (Expected Shortfall) at 95%.
    """

    volatility: Decimal
    max_drawdown: Decimal
    avg_drawdown: Decimal
    max_drawdown_duration: int
    var_95: Decimal
    var_99: Decimal
    cvar_95: Decimal


@dataclass
class RiskAdjustedMetrics:
    """Risk-adjusted performance metrics.

    Attributes:
        sharpe_ratio: Return / volatility (risk-free rate assumed 0).
        sortino_ratio: Return / downside volatility.
        calmar_ratio: CAGR / max drawdown.
        information_ratio: Excess return / tracking error.
        omega_ratio: Probability-weighted profit/loss ratio.
    """

    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    information_ratio: Decimal
    omega_ratio: Decimal


@dataclass
class TradeMetrics:
    """Trade-related performance metrics.

    Attributes:
        total_trades: Total number of trades.
        winning_trades: Number of profitable trades.
        losing_trades: Number of unprofitable trades.
        win_rate: Winning trade percentage.
        avg_win: Average winning trade amount.
        avg_loss: Average losing trade amount.
        largest_win: Largest single winning trade.
        largest_loss: Largest single losing trade.
        profit_factor: Gross profit / gross loss.
        expectancy: Expected value per trade.
        avg_trade_duration: Average time holding a position.
        trades_per_month: Average trades per month.
    """

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    profit_factor: Decimal
    expectancy: Decimal
    avg_trade_duration: float
    trades_per_month: float


@dataclass
class PerformanceReport:
    """Complete performance report.

    Combines all metric categories into a comprehensive report.
    """

    return_metrics: ReturnMetrics
    risk_metrics: RiskMetrics
    risk_adjusted_metrics: RiskAdjustedMetrics
    trade_metrics: TradeMetrics


class MetricsCalculator:
    """Calculate comprehensive trading performance metrics.

    Example:
        >>> calc = MetricsCalculator()
        >>> report = calc.calculate_all(equity_curve, trades)
        >>> print(f"Sharpe Ratio: {report.risk_adjusted_metrics.sharpe_ratio:.2f}")
    """

    def __init__(
        self,
        risk_free_rate: Decimal = Decimal(0),
        periods_per_year: int = 365,
    ) -> None:
        """Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 0).
            periods_per_year: Number of data points per year.
        """
        self._risk_free_rate = risk_free_rate
        self._periods_per_year = periods_per_year
        self._logger = logger.bind(component="metrics_calculator")

    def calculate_all(
        self,
        equity_curve: pd.DataFrame,
        trades: list[dict],
        benchmark: Optional[pd.DataFrame] = None,
    ) -> PerformanceReport:
        """Calculate all performance metrics.

        Args:
            equity_curve: DataFrame with timestamp and equity columns.
            trades: List of trade dictionaries.
            benchmark: Optional benchmark for comparison.

        Returns:
            Complete PerformanceReport.
        """
        return_metrics = self.calculate_return_metrics(equity_curve)
        risk_metrics = self.calculate_risk_metrics(equity_curve)
        risk_adjusted = self.calculate_risk_adjusted_metrics(
            equity_curve, benchmark
        )
        trade_metrics = self.calculate_trade_metrics(trades)

        return PerformanceReport(
            return_metrics=return_metrics,
            risk_metrics=risk_metrics,
            risk_adjusted_metrics=risk_adjusted,
            trade_metrics=trade_metrics,
        )

    def calculate_return_metrics(
        self,
        equity_curve: pd.DataFrame,
    ) -> ReturnMetrics:
        """Calculate return-related metrics.

        Args:
            equity_curve: DataFrame with equity values.

        Returns:
            ReturnMetrics instance.
        """
        if equity_curve.empty:
            return self._empty_return_metrics()

        equity = equity_curve["equity"].values
        initial = equity[0]
        final = equity[-1]

        # Total return
        total_return = Decimal(str((final - initial) / initial if initial > 0 else 0))

        # CAGR
        if "timestamp" in equity_curve.columns:
            dates = pd.to_datetime(equity_curve["timestamp"])
            years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
        else:
            years = len(equity) / self._periods_per_year

        if years > 0 and initial > 0:
            cagr = Decimal(str((final / initial) ** (1 / years) - 1))
        else:
            cagr = Decimal(0)

        # Monthly returns
        if "timestamp" in equity_curve.columns and len(equity) > 30:
            equity_series = pd.Series(
                equity,
                index=pd.to_datetime(equity_curve["timestamp"])
            )
            monthly = equity_series.resample("ME").last()
            monthly_returns = monthly.pct_change().dropna().tolist()
        else:
            # Fallback: use simple chunking for monthly-ish returns
            monthly_returns = []
            chunk_size = max(len(equity) // 12, 1)
            for i in range(0, len(equity) - chunk_size, chunk_size):
                start_val = equity[i]
                end_val = equity[i + chunk_size]
                if start_val > 0:
                    monthly_returns.append((end_val - start_val) / start_val)
        monthly_returns = [Decimal(str(r)) for r in monthly_returns]

        best_month = max(monthly_returns) if monthly_returns else Decimal(0)
        worst_month = min(monthly_returns) if monthly_returns else Decimal(0)
        positive_months = sum(1 for r in monthly_returns if r > 0)
        negative_months = sum(1 for r in monthly_returns if r < 0)

        return ReturnMetrics(
            total_return=total_return,
            cagr=cagr,
            monthly_returns=monthly_returns,
            best_month=best_month,
            worst_month=worst_month,
            positive_months=positive_months,
            negative_months=negative_months,
        )

    def calculate_risk_metrics(
        self,
        equity_curve: pd.DataFrame,
    ) -> RiskMetrics:
        """Calculate risk-related metrics.

        Args:
            equity_curve: DataFrame with equity values.

        Returns:
            RiskMetrics instance.
        """
        if equity_curve.empty:
            return self._empty_risk_metrics()

        equity = equity_curve["equity"].values
        returns = np.diff(equity) / equity[:-1]
        returns = returns[~np.isnan(returns)]

        # Volatility (annualized)
        daily_vol = np.std(returns) if len(returns) > 1 else 0
        annualized_vol = daily_vol * np.sqrt(self._periods_per_year)
        volatility = Decimal(str(annualized_vol))

        # Drawdown analysis
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max

        max_drawdown = Decimal(str(np.max(drawdowns)))
        avg_drawdown = Decimal(str(np.mean(drawdowns[drawdowns > 0]))) if np.any(drawdowns > 0) else Decimal(0)

        # Max drawdown duration
        in_drawdown = drawdowns > 0
        dd_durations = []
        current_duration = 0
        for in_dd in in_drawdown:
            if in_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    dd_durations.append(current_duration)
                current_duration = 0
        if current_duration > 0:
            dd_durations.append(current_duration)
        max_dd_duration = max(dd_durations) if dd_durations else 0

        # Value at Risk
        if len(returns) > 0:
            var_95 = Decimal(str(-np.percentile(returns, 5)))
            var_99 = Decimal(str(-np.percentile(returns, 1)))
            # Conditional VaR (Expected Shortfall)
            cvar_95 = Decimal(str(-np.mean(returns[returns <= np.percentile(returns, 5)])))
        else:
            var_95 = var_99 = cvar_95 = Decimal(0)

        return RiskMetrics(
            volatility=volatility,
            max_drawdown=max_drawdown,
            avg_drawdown=avg_drawdown,
            max_drawdown_duration=max_dd_duration,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
        )

    def calculate_risk_adjusted_metrics(
        self,
        equity_curve: pd.DataFrame,
        benchmark: Optional[pd.DataFrame] = None,
    ) -> RiskAdjustedMetrics:
        """Calculate risk-adjusted performance metrics.

        Args:
            equity_curve: DataFrame with equity values.
            benchmark: Optional benchmark for comparison.

        Returns:
            RiskAdjustedMetrics instance.
        """
        if equity_curve.empty:
            return self._empty_risk_adjusted_metrics()

        equity = equity_curve["equity"].values
        returns = np.diff(equity) / equity[:-1]
        returns = returns[~np.isnan(returns)]

        # Sharpe Ratio
        if len(returns) > 1 and np.std(returns) > 0:
            excess_return = np.mean(returns) - float(self._risk_free_rate) / self._periods_per_year
            sharpe = excess_return / np.std(returns) * np.sqrt(self._periods_per_year)
        else:
            sharpe = 0

        # Sortino Ratio (using downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 1 and np.std(downside_returns) > 0:
            sortino = np.mean(returns) / np.std(downside_returns) * np.sqrt(self._periods_per_year)
        else:
            sortino = 0

        # Calmar Ratio
        max_dd = self.calculate_risk_metrics(equity_curve).max_drawdown
        cagr = self.calculate_return_metrics(equity_curve).cagr
        calmar = cagr / max_dd if max_dd > 0 else Decimal(0)

        # Information Ratio (relative to benchmark)
        info_ratio = Decimal(0)
        if benchmark is not None and "equity" in benchmark.columns:
            bench_returns = np.diff(benchmark["equity"].values) / benchmark["equity"].values[:-1]
            if len(returns) == len(bench_returns):
                excess = returns - bench_returns
                if np.std(excess) > 0:
                    info_ratio = Decimal(str(np.mean(excess) / np.std(excess) * np.sqrt(self._periods_per_year)))

        # Omega Ratio
        threshold = 0
        gains = returns[returns > threshold]
        losses = returns[returns <= threshold]
        if len(losses) > 0 and np.abs(np.sum(losses)) > 0:
            omega = Decimal(str(np.sum(gains) / np.abs(np.sum(losses))))
        else:
            omega = Decimal(0)

        return RiskAdjustedMetrics(
            sharpe_ratio=Decimal(str(sharpe)),
            sortino_ratio=Decimal(str(sortino)),
            calmar_ratio=calmar,
            information_ratio=info_ratio,
            omega_ratio=omega,
        )

    def calculate_trade_metrics(
        self,
        trades: list[dict],
    ) -> TradeMetrics:
        """Calculate trade-related metrics.

        Args:
            trades: List of trade dictionaries.

        Returns:
            TradeMetrics instance.
        """
        if not trades:
            return self._empty_trade_metrics()

        # Calculate P&L per round trip
        pnls = self._calculate_trade_pnls(trades)

        if not pnls:
            return self._empty_trade_metrics()

        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p <= 0]

        total_trades = len(pnls)
        winning_trades = len(winning)
        losing_trades = len(losing)

        win_rate = Decimal(winning_trades) / total_trades if total_trades > 0 else Decimal(0)

        avg_win = Decimal(str(np.mean(winning))) if winning else Decimal(0)
        avg_loss = Decimal(str(abs(np.mean(losing)))) if losing else Decimal(0)

        largest_win = Decimal(str(max(winning))) if winning else Decimal(0)
        largest_loss = Decimal(str(abs(min(losing)))) if losing else Decimal(0)

        gross_profit = sum(winning) if winning else 0
        gross_loss = abs(sum(losing)) if losing else 1
        profit_factor = Decimal(str(gross_profit / gross_loss)) if gross_loss > 0 else Decimal(0)

        # Expectancy: (Win% * Avg Win) - (Loss% * Avg Loss)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        # Trade duration and frequency
        durations = []
        for i in range(0, len(trades) - 1, 2):
            if i + 1 < len(trades):
                if "timestamp" in trades[i] and "timestamp" in trades[i + 1]:
                    duration = (trades[i + 1]["timestamp"] - trades[i]["timestamp"]).total_seconds() / 3600
                    durations.append(duration)

        avg_duration = np.mean(durations) if durations else 0

        # Trades per month
        if trades and "timestamp" in trades[0]:
            date_range = (trades[-1]["timestamp"] - trades[0]["timestamp"]).days
            months = date_range / 30.44 if date_range > 0 else 1
            trades_per_month = total_trades / months
        else:
            trades_per_month = 0

        return TradeMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_trade_duration=avg_duration,
            trades_per_month=trades_per_month,
        )

    def _calculate_trade_pnls(self, trades: list[dict]) -> list[float]:
        """Calculate P&L for each round-trip trade."""
        pnls = []
        open_trades: dict[str, list[dict]] = {}

        for trade in trades:
            symbol = trade["symbol"]
            if trade["side"] == "buy":
                if symbol not in open_trades:
                    open_trades[symbol] = []
                open_trades[symbol].append(trade)
            elif symbol in open_trades and open_trades[symbol]:
                buy = open_trades[symbol].pop(0)
                buy_price = float(buy["price"])
                sell_price = float(trade["price"])
                amount = float(trade["amount"])
                buy_fee = float(buy.get("fee", 0))
                sell_fee = float(trade.get("fee", 0))
                pnl = (sell_price - buy_price) * amount - buy_fee - sell_fee
                pnls.append(pnl)

        return pnls

    def _empty_return_metrics(self) -> ReturnMetrics:
        """Return empty return metrics."""
        return ReturnMetrics(
            total_return=Decimal(0),
            cagr=Decimal(0),
            monthly_returns=[],
            best_month=Decimal(0),
            worst_month=Decimal(0),
            positive_months=0,
            negative_months=0,
        )

    def _empty_risk_metrics(self) -> RiskMetrics:
        """Return empty risk metrics."""
        return RiskMetrics(
            volatility=Decimal(0),
            max_drawdown=Decimal(0),
            avg_drawdown=Decimal(0),
            max_drawdown_duration=0,
            var_95=Decimal(0),
            var_99=Decimal(0),
            cvar_95=Decimal(0),
        )

    def _empty_risk_adjusted_metrics(self) -> RiskAdjustedMetrics:
        """Return empty risk-adjusted metrics."""
        return RiskAdjustedMetrics(
            sharpe_ratio=Decimal(0),
            sortino_ratio=Decimal(0),
            calmar_ratio=Decimal(0),
            information_ratio=Decimal(0),
            omega_ratio=Decimal(0),
        )

    def _empty_trade_metrics(self) -> TradeMetrics:
        """Return empty trade metrics."""
        return TradeMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal(0),
            avg_win=Decimal(0),
            avg_loss=Decimal(0),
            largest_win=Decimal(0),
            largest_loss=Decimal(0),
            profit_factor=Decimal(0),
            expectancy=Decimal(0),
            avg_trade_duration=0,
            trades_per_month=0,
        )


def format_report(report: PerformanceReport) -> str:
    """Format performance report as human-readable text.

    Args:
        report: PerformanceReport to format.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("PERFORMANCE REPORT")
    lines.append("=" * 60)

    # Return Metrics
    lines.append("\nRETURN METRICS")
    lines.append("-" * 40)
    lines.append(f"Total Return:      {report.return_metrics.total_return:.2%}")
    lines.append(f"CAGR:              {report.return_metrics.cagr:.2%}")
    lines.append(f"Best Month:        {report.return_metrics.best_month:.2%}")
    lines.append(f"Worst Month:       {report.return_metrics.worst_month:.2%}")
    lines.append(f"Positive Months:   {report.return_metrics.positive_months}")
    lines.append(f"Negative Months:   {report.return_metrics.negative_months}")

    # Risk Metrics
    lines.append("\nRISK METRICS")
    lines.append("-" * 40)
    lines.append(f"Volatility:        {report.risk_metrics.volatility:.2%}")
    lines.append(f"Max Drawdown:      {report.risk_metrics.max_drawdown:.2%}")
    lines.append(f"Avg Drawdown:      {report.risk_metrics.avg_drawdown:.2%}")
    lines.append(f"Max DD Duration:   {report.risk_metrics.max_drawdown_duration} days")
    lines.append(f"VaR (95%):         {report.risk_metrics.var_95:.2%}")
    lines.append(f"VaR (99%):         {report.risk_metrics.var_99:.2%}")
    lines.append(f"CVaR (95%):        {report.risk_metrics.cvar_95:.2%}")

    # Risk-Adjusted Metrics
    lines.append("\nRISK-ADJUSTED METRICS")
    lines.append("-" * 40)
    lines.append(f"Sharpe Ratio:      {report.risk_adjusted_metrics.sharpe_ratio:.2f}")
    lines.append(f"Sortino Ratio:     {report.risk_adjusted_metrics.sortino_ratio:.2f}")
    lines.append(f"Calmar Ratio:      {report.risk_adjusted_metrics.calmar_ratio:.2f}")
    lines.append(f"Omega Ratio:       {report.risk_adjusted_metrics.omega_ratio:.2f}")

    # Trade Metrics
    lines.append("\nTRADE METRICS")
    lines.append("-" * 40)
    lines.append(f"Total Trades:      {report.trade_metrics.total_trades}")
    lines.append(f"Win Rate:          {report.trade_metrics.win_rate:.2%}")
    lines.append(f"Profit Factor:     {report.trade_metrics.profit_factor:.2f}")
    lines.append(f"Expectancy:        ${report.trade_metrics.expectancy:,.2f}")
    lines.append(f"Avg Win:           ${report.trade_metrics.avg_win:,.2f}")
    lines.append(f"Avg Loss:          ${report.trade_metrics.avg_loss:,.2f}")
    lines.append(f"Largest Win:       ${report.trade_metrics.largest_win:,.2f}")
    lines.append(f"Largest Loss:      ${report.trade_metrics.largest_loss:,.2f}")
    lines.append(f"Trades/Month:      {report.trade_metrics.trades_per_month:.1f}")

    lines.append("=" * 60)

    return "\n".join(lines)
