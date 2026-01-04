"""Exchange integration module with CCXT wrapper and adapters."""

from crypto_bot.exchange.base_exchange import (
    OHLCV,
    AuthenticationError,
    Balance,
    BaseExchange,
    ExchangeError,
    InsufficientFundsError,
    InvalidOrderError,
    Order,
    OrderNotFoundError,
    OrderSide,
    OrderStatus,
    OrderType,
    RateLimitError,
    Ticker,
)
from crypto_bot.exchange.binance_adapter import BinanceAdapter
from crypto_bot.exchange.ccxt_wrapper import CCXTExchange
from crypto_bot.exchange.websocket_handler import WebSocketHandler, WebSocketManager

__all__ = [
    # Base classes and interfaces
    "BaseExchange",
    "CCXTExchange",
    "BinanceAdapter",
    # WebSocket
    "WebSocketHandler",
    "WebSocketManager",
    # Data classes
    "Balance",
    "OHLCV",
    "Order",
    "Ticker",
    # Enums
    "OrderSide",
    "OrderStatus",
    "OrderType",
    # Exceptions
    "AuthenticationError",
    "ExchangeError",
    "InsufficientFundsError",
    "InvalidOrderError",
    "OrderNotFoundError",
    "RateLimitError",
]
