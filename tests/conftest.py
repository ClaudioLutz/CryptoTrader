"""Pytest configuration and shared fixtures."""

import pytest
from decimal import Decimal
from datetime import datetime, UTC

from tests.fixtures.mock_exchange import MockExchange


# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
def mock_exchange() -> MockExchange:
    """Create a mock exchange instance for testing."""
    return MockExchange()


@pytest.fixture
def mock_exchange_with_balance() -> MockExchange:
    """Create a mock exchange with custom balances."""
    return MockExchange(
        initial_balances={
            "USDT": Decimal("50000"),
            "BTC": Decimal("1.0"),
            "ETH": Decimal("10.0"),
        }
    )


@pytest.fixture
def mock_exchange_for_grid() -> MockExchange:
    """Create a mock exchange configured for grid trading tests."""
    exchange = MockExchange(
        initial_balances={
            "USDT": Decimal("10000"),
            "BTC": Decimal("0"),
        }
    )
    exchange.set_price("BTC/USDT", Decimal("42000"))
    return exchange


@pytest.fixture
def grid_config():
    """Create a basic grid configuration for testing."""
    from crypto_bot.strategies.grid_trading import GridConfig, GridSpacing

    return GridConfig(
        symbol="BTC/USDT",
        lower_price=Decimal("40000"),
        upper_price=Decimal("44000"),
        num_grids=5,
        total_investment=Decimal("10000"),
        spacing=GridSpacing.ARITHMETIC,
        stop_loss_pct=Decimal("0.10"),
    )


@pytest.fixture
def risk_config():
    """Create a basic risk configuration for testing."""
    from crypto_bot.risk.risk_manager import RiskConfig

    return RiskConfig(
        max_position_pct=Decimal("0.20"),
        max_daily_loss_pct=Decimal("0.05"),
        max_drawdown_pct=Decimal("0.15"),
        risk_per_trade_pct=Decimal("0.02"),
        max_consecutive_losses=5,
        cooldown_minutes=60,
    )


@pytest.fixture
def circuit_breaker_config():
    """Create circuit breaker configuration for testing."""
    from crypto_bot.risk.circuit_breaker import CircuitBreakerConfig

    return CircuitBreakerConfig(
        max_daily_loss_pct=Decimal("0.05"),
        max_consecutive_losses=3,
        max_drawdown_pct=Decimal("0.15"),
        cooldown_minutes=5,  # Minimum allowed value
    )


@pytest.fixture
def stop_loss_config():
    """Create stop-loss configuration for testing."""
    from crypto_bot.risk.stop_loss import StopLossConfig, StopLossType

    return StopLossConfig(
        type=StopLossType.PERCENTAGE,
        value=Decimal("0.05"),  # 5% stop loss
    )


@pytest.fixture
def position_sizer():
    """Create a position sizer for testing."""
    from crypto_bot.risk.position_sizer import FixedFractionalSizer

    return FixedFractionalSizer(risk_pct=Decimal("0.02"))


@pytest.fixture
def sample_ticker():
    """Create a sample ticker for testing."""
    from crypto_bot.exchange.base_exchange import Ticker

    return Ticker(
        symbol="BTC/USDT",
        bid=Decimal("41999"),
        ask=Decimal("42001"),
        last=Decimal("42000"),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    from crypto_bot.exchange.base_exchange import (
        Order,
        OrderSide,
        OrderType,
        OrderStatus,
    )

    return Order(
        id="TEST_ORDER_1",
        client_order_id=None,
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        status=OrderStatus.OPEN,
        price=Decimal("40000"),
        amount=Decimal("0.1"),
        filled=Decimal("0"),
        remaining=Decimal("0.1"),
        cost=Decimal("0"),
        fee=None,
        timestamp=datetime.now(UTC),
    )
