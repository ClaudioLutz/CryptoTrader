"""Data persistence and caching module.

Provides:
- SQLAlchemy ORM models for trades, orders, and state
- Async database session management
- Repository pattern for CRUD operations
- OHLCV data caching with multi-layer storage
"""

from crypto_bot.data.models import (
    AlertLog,
    BalanceSnapshot,
    Base,
    OHLCVCache,
    Order,
    StrategyState,
    TimestampMixin,
    Trade,
)
from crypto_bot.data.ohlcv_cache import (
    OHLCVCache as OHLCVCacheManager,
    OHLCVDataManager,
    OHLCVFetcher,
)
from crypto_bot.data.persistence import (
    BalanceSnapshotRepository,
    Database,
    OrderRepository,
    TradeRepository,
    UnitOfWork,
)

__all__ = [
    # ORM Models
    "AlertLog",
    "BalanceSnapshot",
    "Base",
    "OHLCVCache",
    "Order",
    "StrategyState",
    "TimestampMixin",
    "Trade",
    # Database
    "Database",
    # Repositories
    "BalanceSnapshotRepository",
    "OrderRepository",
    "TradeRepository",
    "UnitOfWork",
    # OHLCV Cache
    "OHLCVCacheManager",
    "OHLCVDataManager",
    "OHLCVFetcher",
]
