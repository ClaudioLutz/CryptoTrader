"""Unit tests for risk management components.

Tests cover:
- Position sizing algorithms
- Circuit breaker logic
- Stop-loss handlers
- Drawdown tracking
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal


class TestPositionSizing:
    """Tests for position sizing algorithms."""

    def test_fixed_fractional_basic(self, position_sizer):
        """Test basic fixed fractional position sizing."""
        result = position_sizer.calculate(
            balance=Decimal("10000"),
            entry_price=Decimal("100"),
            stop_loss_price=Decimal("95"),
        )

        # Risk = 10000 * 0.02 = 200
        # Price risk per unit = 100 - 95 = 5
        # Position = 200 / 5 = 40 units
        assert result.amount == Decimal("40")
        assert result.risk_amount == Decimal("200")

    def test_fixed_fractional_position_value(self, position_sizer):
        """Test that position value is calculated correctly."""
        result = position_sizer.calculate(
            balance=Decimal("10000"),
            entry_price=Decimal("100"),
            stop_loss_price=Decimal("95"),
        )

        # 40 units at $100 = $4000 position value
        assert result.position_value == Decimal("4000")

    def test_fixed_fractional_zero_stop_raises(self, position_sizer):
        """Test that zero stop loss distance raises error."""
        with pytest.raises(ValueError):
            position_sizer.calculate(
                balance=Decimal("10000"),
                entry_price=Decimal("100"),
                stop_loss_price=Decimal("100"),  # Same as entry
            )

    def test_kelly_criterion_calculation(self):
        """Test Kelly criterion position sizing."""
        from crypto_bot.risk.position_sizer import KellySizer

        sizer = KellySizer(fraction=Decimal("0.5"))  # Half-Kelly

        kelly = sizer.calculate_kelly(
            win_rate=Decimal("0.6"),
            avg_win=Decimal("100"),
            avg_loss=Decimal("50"),
        )

        # Kelly = win_rate - (loss_rate / win_loss_ratio)
        # Kelly = 0.6 - (0.4 / 2) = 0.6 - 0.2 = 0.4
        # Half-Kelly = 0.2
        assert kelly == Decimal("0.2")

    def test_kelly_negative_expectation_returns_zero(self):
        """Test Kelly returns zero for negative expectation."""
        from crypto_bot.risk.position_sizer import KellySizer

        sizer = KellySizer(fraction=Decimal("0.5"))

        kelly = sizer.calculate_kelly(
            win_rate=Decimal("0.3"),  # Low win rate
            avg_win=Decimal("50"),
            avg_loss=Decimal("100"),  # Larger losses
        )

        # Should return 0 for negative expectation
        assert kelly == Decimal("0")


class TestCircuitBreaker:
    """Tests for circuit breaker."""

    def test_daily_loss_triggers(self, circuit_breaker_config):
        """Test circuit breaker trips on daily loss limit."""
        from crypto_bot.risk.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(circuit_breaker_config)
        cb.set_initial_equity(Decimal("10000"))

        # Record losing trades
        trigger = cb.record_trade(Decimal("-400"), Decimal("9600"))
        assert trigger is None
        assert cb.is_trading_allowed

        # This should trigger (> 5% loss = $500)
        trigger = cb.record_trade(Decimal("-200"), Decimal("9400"))
        assert trigger is not None
        assert not cb.is_trading_allowed

    def test_consecutive_losses_triggers(self, circuit_breaker_config):
        """Test circuit breaker trips on consecutive losses."""
        from crypto_bot.risk.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(circuit_breaker_config)
        cb.set_initial_equity(Decimal("10000"))

        # Record consecutive losses (config has max_consecutive_losses=3)
        cb.record_trade(Decimal("-10"), Decimal("9990"))
        cb.record_trade(Decimal("-10"), Decimal("9980"))
        assert cb.is_trading_allowed

        cb.record_trade(Decimal("-10"), Decimal("9970"))
        assert not cb.is_trading_allowed

    def test_win_resets_consecutive_losses(self, circuit_breaker_config):
        """Test that winning trade resets consecutive loss counter."""
        from crypto_bot.risk.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(circuit_breaker_config)
        cb.set_initial_equity(Decimal("10000"))

        cb.record_trade(Decimal("-10"), Decimal("9990"))
        cb.record_trade(Decimal("-10"), Decimal("9980"))
        cb.record_trade(Decimal("20"), Decimal("10000"))  # Win

        assert cb._state.consecutive_losses == 0
        assert cb.is_trading_allowed

    def test_manual_reset(self, circuit_breaker_config):
        """Test manual circuit breaker reset."""
        from crypto_bot.risk.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(circuit_breaker_config)
        cb.set_initial_equity(Decimal("10000"))

        # Trip the breaker with consecutive losses
        cb.record_trade(Decimal("-10"), Decimal("9990"))
        cb.record_trade(Decimal("-10"), Decimal("9980"))
        cb.record_trade(Decimal("-10"), Decimal("9970"))

        assert not cb.is_trading_allowed

        # Manual reset
        cb.manual_reset()
        assert cb.is_trading_allowed

    def test_daily_pnl_tracking(self, circuit_breaker_config):
        """Test daily P&L is tracked correctly."""
        from crypto_bot.risk.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(circuit_breaker_config)
        cb.set_initial_equity(Decimal("10000"))

        # Record trades
        cb.record_trade(Decimal("-100"), Decimal("9900"))
        assert cb._state.daily_pnl == Decimal("-100")

        cb.record_trade(Decimal("50"), Decimal("9950"))
        assert cb._state.daily_pnl == Decimal("-50")


class TestStopLoss:
    """Tests for stop-loss handlers."""

    def test_percentage_stop_loss(self):
        """Test percentage-based stop-loss calculation."""
        from crypto_bot.risk.stop_loss import StopLossConfig, StopLossType, StopLossHandler

        config = StopLossConfig(
            type=StopLossType.PERCENTAGE,
            value=Decimal("0.05"),
        )
        handler = StopLossHandler(config)
        state = handler.initialize(Decimal("100"), "buy")

        # 5% stop loss from entry of 100 = 95
        assert state.current_stop == Decimal("95")

    def test_percentage_stop_loss_short(self):
        """Test percentage stop-loss for short position."""
        from crypto_bot.risk.stop_loss import StopLossConfig, StopLossType, StopLossHandler

        config = StopLossConfig(
            type=StopLossType.PERCENTAGE,
            value=Decimal("0.05"),
        )
        handler = StopLossHandler(config)
        state = handler.initialize(Decimal("100"), "sell")

        # 5% stop loss for short = 105
        assert state.current_stop == Decimal("105")

    def test_trailing_stop_tracks_high(self):
        """Test trailing stop tracks highest price."""
        from crypto_bot.risk.stop_loss import StopLossConfig, StopLossType, StopLossHandler

        config = StopLossConfig(
            type=StopLossType.TRAILING,
            value=Decimal("0.05"),
        )
        handler = StopLossHandler(config)
        handler.initialize(Decimal("100"), "buy")

        # Price moves up
        handler.update(Decimal("110"), "buy")

        # Highest price should be tracked
        assert handler._state.highest_price == Decimal("110")

    def test_trailing_stop_initial_value(self):
        """Test trailing stop starts at correct level."""
        from crypto_bot.risk.stop_loss import StopLossConfig, StopLossType, StopLossHandler

        config = StopLossConfig(
            type=StopLossType.TRAILING,
            value=Decimal("0.05"),
        )
        handler = StopLossHandler(config)
        state = handler.initialize(Decimal("100"), "buy")

        # Initial stop should be 5% below entry
        assert state.current_stop == Decimal("95")

    def test_stop_initialization(self):
        """Test stop-loss initializes correctly."""
        from crypto_bot.risk.stop_loss import StopLossConfig, StopLossType, StopLossHandler

        config = StopLossConfig(
            type=StopLossType.PERCENTAGE,
            value=Decimal("0.05"),
        )
        handler = StopLossHandler(config)
        state = handler.initialize(Decimal("100"), "buy")

        # Check initial state
        assert state.entry_price == Decimal("100")
        assert state.current_stop == Decimal("95")
        assert not handler.is_triggered


class TestDrawdownTracking:
    """Tests for drawdown tracking."""

    def test_drawdown_calculation(self):
        """Test drawdown is calculated correctly."""
        from crypto_bot.risk.drawdown import DrawdownTracker

        tracker = DrawdownTracker(initial_equity=Decimal("10000"))

        # Update with higher equity (new peak)
        metrics = tracker.update(Decimal("11000"))
        assert metrics.current_drawdown_pct == Decimal("0")

        # Update with lower equity (drawdown)
        metrics = tracker.update(Decimal("9900"))

        # Drawdown = (11000 - 9900) / 11000 = 0.1 = 10%
        assert metrics.current_drawdown_pct == Decimal("0.1")

    def test_max_drawdown_preserved(self):
        """Test maximum drawdown is preserved."""
        from crypto_bot.risk.drawdown import DrawdownTracker

        tracker = DrawdownTracker(initial_equity=Decimal("10000"))

        # Create drawdown
        tracker.update(Decimal("11000"))
        metrics = tracker.update(Decimal("8800"))  # 20% drawdown

        # Recover
        metrics = tracker.update(Decimal("10500"))

        # Max drawdown should still be 20%
        assert metrics.max_drawdown_pct == Decimal("0.2")

    def test_peak_equity_tracked(self):
        """Test peak equity is tracked correctly."""
        from crypto_bot.risk.drawdown import DrawdownTracker

        tracker = DrawdownTracker(initial_equity=Decimal("10000"))

        # Update with higher value
        metrics = tracker.update(Decimal("12000"))
        assert metrics.peak_equity == Decimal("12000")

        # Update with lower value (should not change peak)
        metrics = tracker.update(Decimal("11000"))
        assert metrics.peak_equity == Decimal("12000")


class TestRiskConfig:
    """Tests for risk configuration."""

    def test_risk_config_defaults(self):
        """Test RiskConfig has sensible defaults."""
        from crypto_bot.risk.risk_manager import RiskConfig

        config = RiskConfig()

        assert config.risk_pct_per_trade == Decimal("0.02")
        assert config.max_position_pct == Decimal("0.20")
        assert config.max_daily_loss_pct == Decimal("0.05")

    def test_risk_config_validation(self):
        """Test RiskConfig validates parameters."""
        from crypto_bot.risk.risk_manager import RiskConfig
        from pydantic import ValidationError

        # Risk too high should fail
        with pytest.raises(ValidationError):
            RiskConfig(risk_pct_per_trade=Decimal("0.50"))

    def test_circuit_breaker_integration(self, circuit_breaker_config):
        """Test circuit breaker works with risk management."""
        from crypto_bot.risk.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(circuit_breaker_config)
        cb.set_initial_equity(Decimal("10000"))

        # Trading should be allowed initially
        assert cb.is_trading_allowed

        # Record losses to trip breaker
        for _ in range(3):
            cb.record_trade(Decimal("-10"), Decimal("9990"))

        # Should be tripped after consecutive losses
        assert not cb.is_trading_allowed
