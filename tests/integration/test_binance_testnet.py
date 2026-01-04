"""Integration tests for Binance testnet.

Setup Instructions:
1. Create a Binance testnet account at https://testnet.binance.vision/
2. Generate API keys from the testnet
3. Set environment variables:
   - EXCHANGE__API_KEY=your_testnet_api_key
   - EXCHANGE__API_SECRET=your_testnet_api_secret
   - EXCHANGE__TESTNET=true
   - EXCHANGE__NAME=binance

Run with: pytest tests/integration/ -m integration -v
"""

import os
from decimal import Decimal

import pytest

from crypto_bot.config.settings import ExchangeSettings
from crypto_bot.exchange.base_exchange import OrderSide, OrderStatus, OrderType
from crypto_bot.exchange.binance_adapter import BinanceAdapter


# Skip all tests if testnet credentials not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("EXCHANGE__API_KEY"),
        reason="Testnet credentials not configured",
    ),
]


@pytest.fixture
async def binance_adapter():
    """Create and connect Binance adapter for testing."""
    settings = ExchangeSettings(
        name="binance",
        testnet=True,
    )
    adapter = BinanceAdapter(settings)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_fetch_ticker(binance_adapter: BinanceAdapter) -> None:
    """Test fetching ticker data from testnet."""
    ticker = await binance_adapter.fetch_ticker("BTC/USDT")

    assert ticker.symbol == "BTC/USDT"
    assert ticker.bid > 0
    assert ticker.ask > 0
    assert ticker.ask >= ticker.bid
    assert ticker.last > 0
    assert ticker.timestamp is not None


@pytest.mark.asyncio
async def test_fetch_balance(binance_adapter: BinanceAdapter) -> None:
    """Test fetching account balance from testnet."""
    balances = await binance_adapter.fetch_balance()

    # Testnet accounts should have some balance
    assert isinstance(balances, dict)
    # Check that we can access balance structure
    for currency, balance in balances.items():
        assert balance.currency == currency
        assert balance.total >= 0
        assert balance.free >= 0
        assert balance.used >= 0


@pytest.mark.asyncio
async def test_fetch_ohlcv(binance_adapter: BinanceAdapter) -> None:
    """Test fetching OHLCV data from testnet."""
    ohlcv = await binance_adapter.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=10)

    assert len(ohlcv) > 0
    assert len(ohlcv) <= 10

    for candle in ohlcv:
        assert candle.open > 0
        assert candle.high > 0
        assert candle.low > 0
        assert candle.close > 0
        assert candle.volume >= 0
        assert candle.high >= candle.low
        assert candle.timestamp is not None


@pytest.mark.asyncio
async def test_fetch_open_orders(binance_adapter: BinanceAdapter) -> None:
    """Test fetching open orders from testnet."""
    orders = await binance_adapter.fetch_open_orders("BTC/USDT")

    assert isinstance(orders, list)
    # Orders may or may not exist, just verify structure
    for order in orders:
        assert order.id is not None
        assert order.symbol == "BTC/USDT"


@pytest.mark.asyncio
async def test_place_and_cancel_limit_order(binance_adapter: BinanceAdapter) -> None:
    """Test placing and canceling a limit order on testnet."""
    # Get current price to place order far from market
    ticker = await binance_adapter.fetch_ticker("BTC/USDT")

    # Place buy order at 50% below current price (won't fill)
    limit_price = ticker.bid * Decimal("0.5")

    order = await binance_adapter.create_order(
        symbol="BTC/USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        amount=Decimal("0.001"),
        price=limit_price,
    )

    assert order.id is not None
    assert order.symbol == "BTC/USDT"
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.LIMIT
    assert order.status == OrderStatus.OPEN
    assert order.amount == Decimal("0.001")

    # Fetch the order to verify it exists
    fetched_order = await binance_adapter.fetch_order(order.id, "BTC/USDT")
    assert fetched_order.id == order.id
    assert fetched_order.status == OrderStatus.OPEN

    # Cancel the order
    cancelled_order = await binance_adapter.cancel_order(order.id, "BTC/USDT")
    assert cancelled_order.id == order.id
    assert cancelled_order.status == OrderStatus.CANCELED


@pytest.mark.asyncio
async def test_market_info_loaded(binance_adapter: BinanceAdapter) -> None:
    """Test that market info is properly loaded."""
    markets = binance_adapter.markets

    assert "BTC/USDT" in markets
    btc_market = markets["BTC/USDT"]

    assert "precision" in btc_market
    assert "limits" in btc_market
    assert btc_market["active"] is True
