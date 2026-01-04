"""Pytest configuration and shared fixtures."""

import pytest

from tests.fixtures.mock_exchange import MockExchange


@pytest.fixture
def mock_exchange() -> MockExchange:
    """Create a mock exchange instance for testing."""
    return MockExchange()


@pytest.fixture
def mock_exchange_with_balance() -> MockExchange:
    """Create a mock exchange with custom balances."""
    from decimal import Decimal

    return MockExchange(
        initial_balances={
            "USDT": Decimal("50000"),
            "BTC": Decimal("1.0"),
            "ETH": Decimal("10.0"),
        }
    )
