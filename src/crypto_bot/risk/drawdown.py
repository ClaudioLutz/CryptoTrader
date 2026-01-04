"""Drawdown calculator and tracker for portfolio risk monitoring.

Provides real-time drawdown tracking with historical analysis:
- Current drawdown from peak
- Maximum drawdown over time
- Drawdown periods with duration tracking
- Recovery analysis

Key Metrics:
- Current Drawdown: (Peak - Current) / Peak
- Max Drawdown: Worst historical drawdown
- Recovery %: Percentage gain needed to return to peak
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class DrawdownMetrics:
    """Current drawdown metrics snapshot.

    Attributes:
        current_drawdown: Absolute drawdown amount.
        current_drawdown_pct: Drawdown as percentage of peak.
        max_drawdown: Maximum absolute drawdown seen.
        max_drawdown_pct: Maximum drawdown percentage.
        max_drawdown_date: When max drawdown occurred.
        peak_equity: Highest equity value seen.
        current_equity: Current equity value.
        recovery_needed_pct: Percentage gain needed to recover.
    """

    current_drawdown: Decimal
    current_drawdown_pct: Decimal
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    max_drawdown_date: Optional[datetime]
    peak_equity: Decimal
    current_equity: Decimal
    recovery_needed_pct: Decimal


@dataclass
class DrawdownPeriod:
    """Represents a single drawdown period.

    A drawdown period starts when equity falls below peak and ends
    when equity recovers to a new peak.

    Attributes:
        start_date: When drawdown started.
        end_date: When drawdown ended (recovered or ongoing).
        peak_equity: Equity at period start.
        trough_equity: Lowest equity during period.
        drawdown_pct: Maximum drawdown percentage.
        duration_days: Number of days in drawdown.
        recovered: Whether recovery has occurred.
    """

    start_date: datetime
    end_date: Optional[datetime]
    peak_equity: Decimal
    trough_equity: Decimal
    drawdown_pct: Decimal
    duration_days: int
    recovered: bool


@dataclass
class EquityPoint:
    """Single equity data point for history tracking."""

    timestamp: datetime
    equity: Decimal


class DrawdownTracker:
    """Tracks drawdown metrics over time.

    Maintains equity history and calculates real-time drawdown metrics.
    Records drawdown periods for historical analysis.

    Example:
        >>> tracker = DrawdownTracker(initial_equity=Decimal("10000"))
        >>> metrics = tracker.update(Decimal("9500"))
        >>> print(f"Current drawdown: {metrics.current_drawdown_pct:.2%}")
        >>> print(f"Recovery needed: {metrics.recovery_needed_pct:.2%}")
    """

    def __init__(
        self,
        initial_equity: Decimal,
        history_size: int = 10000,
    ) -> None:
        """Initialize drawdown tracker.

        Args:
            initial_equity: Starting equity value.
            history_size: Maximum equity history entries to keep.
        """
        self._peak_equity = initial_equity
        self._current_equity = initial_equity
        self._max_drawdown = Decimal(0)
        self._max_drawdown_pct = Decimal(0)
        self._max_drawdown_date: Optional[datetime] = None

        # Track drawdown periods
        self._current_period: Optional[DrawdownPeriod] = None
        self._historical_periods: list[DrawdownPeriod] = []

        # Equity history for analysis
        self._equity_history: deque[EquityPoint] = deque(maxlen=history_size)

        # Store initial point
        now = datetime.utcnow()
        self._equity_history.append(EquityPoint(timestamp=now, equity=initial_equity))

        self._logger = logger.bind(component="drawdown_tracker")
        self._logger.info("drawdown_tracker_initialized", initial_equity=str(initial_equity))

    @property
    def peak_equity(self) -> Decimal:
        """Get peak equity value."""
        return self._peak_equity

    @property
    def current_equity(self) -> Decimal:
        """Get current equity value."""
        return self._current_equity

    @property
    def max_drawdown_pct(self) -> Decimal:
        """Get maximum drawdown percentage."""
        return self._max_drawdown_pct

    def update(
        self,
        equity: Decimal,
        timestamp: Optional[datetime] = None,
    ) -> DrawdownMetrics:
        """Update with new equity value and recalculate metrics.

        Args:
            equity: New equity value.
            timestamp: Timestamp for this update (defaults to now).

        Returns:
            Updated DrawdownMetrics.
        """
        timestamp = timestamp or datetime.utcnow()
        self._current_equity = equity
        self._equity_history.append(EquityPoint(timestamp=timestamp, equity=equity))

        # Update peak
        if equity > self._peak_equity:
            self._peak_equity = equity
            # End current drawdown period if any
            if self._current_period:
                self._current_period.end_date = timestamp
                self._current_period.recovered = True
                self._current_period.duration_days = (
                    timestamp - self._current_period.start_date
                ).days
                self._historical_periods.append(self._current_period)
                self._logger.info(
                    "drawdown_period_ended",
                    max_drawdown=f"{self._current_period.drawdown_pct:.2%}",
                    duration_days=self._current_period.duration_days,
                )
                self._current_period = None

        # Calculate current drawdown
        current_dd = self._peak_equity - equity
        current_dd_pct = current_dd / self._peak_equity if self._peak_equity > 0 else Decimal(0)

        # Track max drawdown
        if current_dd_pct > self._max_drawdown_pct:
            self._max_drawdown = current_dd
            self._max_drawdown_pct = current_dd_pct
            self._max_drawdown_date = timestamp
            self._logger.warning(
                "new_max_drawdown",
                max_drawdown_pct=f"{self._max_drawdown_pct:.2%}",
                equity=str(equity),
            )

        # Start new drawdown period if needed
        if current_dd_pct > 0 and not self._current_period:
            self._current_period = DrawdownPeriod(
                start_date=timestamp,
                end_date=None,
                peak_equity=self._peak_equity,
                trough_equity=equity,
                drawdown_pct=current_dd_pct,
                duration_days=0,
                recovered=False,
            )
            self._logger.info(
                "drawdown_period_started",
                peak_equity=str(self._peak_equity),
            )
        elif self._current_period and equity < self._current_period.trough_equity:
            # Update trough
            self._current_period.trough_equity = equity
            self._current_period.drawdown_pct = current_dd_pct
            self._current_period.duration_days = (
                timestamp - self._current_period.start_date
            ).days

        # Calculate recovery needed
        recovery_needed = (
            (self._peak_equity / equity - 1) if equity > 0 else Decimal(0)
        )

        return DrawdownMetrics(
            current_drawdown=current_dd,
            current_drawdown_pct=current_dd_pct,
            max_drawdown=self._max_drawdown,
            max_drawdown_pct=self._max_drawdown_pct,
            max_drawdown_date=self._max_drawdown_date,
            peak_equity=self._peak_equity,
            current_equity=self._current_equity,
            recovery_needed_pct=recovery_needed,
        )

    def get_current_metrics(self) -> DrawdownMetrics:
        """Get current drawdown metrics without updating equity.

        Returns:
            Current DrawdownMetrics.
        """
        return self.update(self._current_equity)

    def get_drawdown_periods(
        self,
        min_drawdown_pct: Decimal = Decimal("0.05"),
    ) -> list[DrawdownPeriod]:
        """Get historical drawdown periods exceeding threshold.

        Args:
            min_drawdown_pct: Minimum drawdown percentage to include.

        Returns:
            List of DrawdownPeriod objects meeting criteria.
        """
        periods = [
            p for p in self._historical_periods
            if p.drawdown_pct >= min_drawdown_pct
        ]

        # Include current period if significant
        if (
            self._current_period
            and self._current_period.drawdown_pct >= min_drawdown_pct
        ):
            periods.append(self._current_period)

        return periods

    def get_equity_curve(self) -> list[tuple[datetime, Decimal]]:
        """Get equity history for charting.

        Returns:
            List of (timestamp, equity) tuples.
        """
        return [(p.timestamp, p.equity) for p in self._equity_history]

    def get_statistics(self) -> dict:
        """Calculate comprehensive drawdown statistics.

        Returns:
            Dictionary with drawdown statistics.
        """
        periods = self.get_drawdown_periods(min_drawdown_pct=Decimal("0.01"))
        if not periods:
            return {
                "num_drawdown_periods": 0,
                "avg_drawdown_pct": Decimal(0),
                "max_drawdown_pct": self._max_drawdown_pct,
                "avg_duration_days": 0,
                "max_duration_days": 0,
                "total_time_in_drawdown_pct": Decimal(0),
            }

        durations = [p.duration_days for p in periods]
        drawdowns = [p.drawdown_pct for p in periods]

        # Calculate total time in drawdown
        total_drawdown_days = sum(durations)
        if self._equity_history:
            first_ts = self._equity_history[0].timestamp
            last_ts = self._equity_history[-1].timestamp
            total_days = max((last_ts - first_ts).days, 1)
            time_in_drawdown_pct = Decimal(total_drawdown_days) / Decimal(total_days)
        else:
            time_in_drawdown_pct = Decimal(0)

        return {
            "num_drawdown_periods": len(periods),
            "avg_drawdown_pct": sum(drawdowns) / len(drawdowns),
            "max_drawdown_pct": max(drawdowns),
            "avg_duration_days": sum(durations) / len(durations) if durations else 0,
            "max_duration_days": max(durations) if durations else 0,
            "total_time_in_drawdown_pct": time_in_drawdown_pct,
        }

    def get_underwater_equity(self) -> list[tuple[datetime, Decimal]]:
        """Get underwater equity curve (% below peak over time).

        Returns:
            List of (timestamp, underwater_pct) tuples.
        """
        if not self._equity_history:
            return []

        result: list[tuple[datetime, Decimal]] = []
        running_peak = Decimal(0)

        for point in self._equity_history:
            if point.equity > running_peak:
                running_peak = point.equity

            if running_peak > 0:
                underwater = (running_peak - point.equity) / running_peak
            else:
                underwater = Decimal(0)

            result.append((point.timestamp, underwater))

        return result

    def reset(self, new_initial_equity: Optional[Decimal] = None) -> None:
        """Reset tracker state.

        Args:
            new_initial_equity: New starting equity. If None, keeps current.
        """
        equity = new_initial_equity or self._current_equity

        self._peak_equity = equity
        self._current_equity = equity
        self._max_drawdown = Decimal(0)
        self._max_drawdown_pct = Decimal(0)
        self._max_drawdown_date = None
        self._current_period = None
        self._historical_periods.clear()
        self._equity_history.clear()

        now = datetime.utcnow()
        self._equity_history.append(EquityPoint(timestamp=now, equity=equity))

        self._logger.info("drawdown_tracker_reset", new_equity=str(equity))


class DrawdownAnalyzer:
    """Advanced drawdown analysis utilities.

    Provides additional analysis functions for drawdown data:
    - Calmar ratio calculation
    - Recovery time analysis
    - Risk-adjusted metrics
    """

    @staticmethod
    def calculate_calmar_ratio(
        annualized_return: Decimal,
        max_drawdown_pct: Decimal,
    ) -> Decimal:
        """Calculate Calmar ratio (annualized return / max drawdown).

        Args:
            annualized_return: Annual return percentage.
            max_drawdown_pct: Maximum drawdown percentage.

        Returns:
            Calmar ratio. Higher is better.
        """
        if max_drawdown_pct == 0:
            return Decimal(0)
        return annualized_return / max_drawdown_pct

    @staticmethod
    def calculate_recovery_factor(
        total_return: Decimal,
        max_drawdown: Decimal,
    ) -> Decimal:
        """Calculate recovery factor (total return / max drawdown).

        Args:
            total_return: Total absolute return.
            max_drawdown: Maximum absolute drawdown.

        Returns:
            Recovery factor. Higher is better.
        """
        if max_drawdown == 0:
            return Decimal(0)
        return total_return / max_drawdown

    @staticmethod
    def analyze_recovery_times(
        periods: list[DrawdownPeriod],
    ) -> dict:
        """Analyze recovery times from drawdown periods.

        Args:
            periods: List of completed drawdown periods.

        Returns:
            Dictionary with recovery time statistics.
        """
        recovered = [p for p in periods if p.recovered]
        if not recovered:
            return {
                "avg_recovery_days": 0,
                "max_recovery_days": 0,
                "min_recovery_days": 0,
                "recovery_rate": Decimal(0),
            }

        recovery_days = [p.duration_days for p in recovered]

        return {
            "avg_recovery_days": sum(recovery_days) / len(recovery_days),
            "max_recovery_days": max(recovery_days),
            "min_recovery_days": min(recovery_days),
            "recovery_rate": Decimal(len(recovered)) / Decimal(len(periods)),
        }

    @staticmethod
    def categorize_drawdown(drawdown_pct: Decimal) -> str:
        """Categorize drawdown severity.

        Args:
            drawdown_pct: Drawdown percentage.

        Returns:
            Category string.
        """
        if drawdown_pct < Decimal("0.05"):
            return "minor"
        elif drawdown_pct < Decimal("0.10"):
            return "moderate"
        elif drawdown_pct < Decimal("0.20"):
            return "significant"
        elif drawdown_pct < Decimal("0.30"):
            return "severe"
        else:
            return "critical"

    @staticmethod
    def estimate_recovery_time(
        current_drawdown_pct: Decimal,
        avg_daily_return: Decimal,
    ) -> Optional[int]:
        """Estimate days needed to recover from current drawdown.

        Args:
            current_drawdown_pct: Current drawdown percentage.
            avg_daily_return: Average daily return percentage.

        Returns:
            Estimated days to recovery, None if negative returns.
        """
        if avg_daily_return <= 0:
            return None

        if current_drawdown_pct == 0:
            return 0

        # Days needed: -ln(1 - dd) / ln(1 + r)
        # Simplified approximation: dd / r
        import math

        try:
            dd = float(current_drawdown_pct)
            r = float(avg_daily_return)

            if r >= 1:
                return 0

            # Use logarithmic formula for accuracy
            days = -math.log(1 - dd) / math.log(1 + r)
            return max(0, int(days))
        except (ValueError, ZeroDivisionError):
            return None


class DrawdownAlert:
    """Drawdown alert system with configurable thresholds.

    Monitors drawdown levels and generates alerts when thresholds
    are breached.

    Example:
        >>> alert = DrawdownAlert(
        ...     warning_threshold=Decimal("0.05"),
        ...     critical_threshold=Decimal("0.10"),
        ... )
        >>> alert.check(metrics)
    """

    def __init__(
        self,
        warning_threshold: Decimal = Decimal("0.05"),
        critical_threshold: Decimal = Decimal("0.10"),
        recovery_threshold: Decimal = Decimal("0.02"),
    ) -> None:
        """Initialize drawdown alert.

        Args:
            warning_threshold: Drawdown % for warning alert.
            critical_threshold: Drawdown % for critical alert.
            recovery_threshold: Drawdown % to consider recovered.
        """
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._recovery_threshold = recovery_threshold

        self._last_alert_level: Optional[str] = None
        self._logger = logger.bind(component="drawdown_alert")

    def check(self, metrics: DrawdownMetrics) -> Optional[str]:
        """Check drawdown metrics and generate alert if needed.

        Args:
            metrics: Current drawdown metrics.

        Returns:
            Alert level ("warning", "critical", "recovered") or None.
        """
        dd_pct = metrics.current_drawdown_pct

        # Check for recovery
        if (
            self._last_alert_level
            and dd_pct <= self._recovery_threshold
        ):
            self._logger.info(
                "drawdown_recovered",
                current_drawdown=f"{dd_pct:.2%}",
            )
            self._last_alert_level = None
            return "recovered"

        # Check for critical
        if dd_pct >= self._critical_threshold:
            if self._last_alert_level != "critical":
                self._logger.error(
                    "drawdown_critical",
                    current_drawdown=f"{dd_pct:.2%}",
                    threshold=f"{self._critical_threshold:.2%}",
                )
                self._last_alert_level = "critical"
                return "critical"

        # Check for warning
        elif dd_pct >= self._warning_threshold:
            if self._last_alert_level != "warning":
                self._logger.warning(
                    "drawdown_warning",
                    current_drawdown=f"{dd_pct:.2%}",
                    threshold=f"{self._warning_threshold:.2%}",
                )
                self._last_alert_level = "warning"
                return "warning"

        return None

    def reset(self) -> None:
        """Reset alert state."""
        self._last_alert_level = None
