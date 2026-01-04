"""SQLAlchemy 2.0 ORM models for trading data persistence.

Uses modern SQLAlchemy 2.0 patterns with:
- Mapped columns with type hints
- Async-compatible design
- Proper indexing for query performance
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models.

    All models inherit from this class which provides the SQLAlchemy
    declarative base configuration.
    """

    pass


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamp columns.

    These columns are automatically set on insert and update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Trade(Base, TimestampMixin):
    """Trade record representing a complete trade cycle.

    A trade consists of an entry and exit, tracking profit/loss
    and associated orders.

    Attributes:
        id: Primary key.
        exchange: Exchange where trade occurred.
        symbol: Trading pair symbol.
        strategy: Strategy that created this trade.
        is_open: Whether trade is still active.
        side: Trade direction (buy/sell for entry).
        open_rate: Entry price.
        close_rate: Exit price (when closed).
        amount: Trade size in base currency.
        open_date: Entry timestamp.
        close_date: Exit timestamp.
        stop_loss: Stop-loss price if set.
        take_profit: Take-profit price if set.
        profit: Realized profit/loss (when closed).
        profit_pct: Profit as percentage of entry.
        fee: Total fees paid.
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy or sell

    # Entry details
    open_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    open_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Exit details (nullable until closed)
    close_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    close_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Risk management
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)

    # Profit tracking (nullable until closed)
    profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    profit_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)

    # Relationships
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="trade", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_trades_strategy_open", "strategy", "is_open"),
        Index("ix_trades_symbol_open", "symbol", "is_open"),
        Index("ix_trades_close_date", "close_date"),
    )

    def __repr__(self) -> str:
        """String representation of trade."""
        status = "open" if self.is_open else "closed"
        return (
            f"<Trade(id={self.id}, symbol={self.symbol}, "
            f"side={self.side}, status={status})>"
        )


class Order(Base, TimestampMixin):
    """Order record tracking exchange orders.

    Links to trades and tracks order lifecycle from creation
    through fill or cancellation.

    Attributes:
        id: Primary key.
        order_id: Exchange-assigned order ID.
        trade_id: Foreign key to associated trade.
        exchange: Exchange where order was placed.
        symbol: Trading pair symbol.
        side: Order direction (buy/sell).
        order_type: Order type (market/limit).
        status: Current order status.
        price: Limit price (None for market orders).
        amount: Order size in base currency.
        filled: Amount filled so far.
        remaining: Amount remaining to fill.
        cost: Total cost (price * filled).
        fee: Fees paid for this order.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    trade_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("trades.id"), nullable=True
    )

    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy or sell
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)  # market/limit
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # open/closed/canceled

    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    filled: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal(0))
    remaining: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Relationship
    trade: Mapped[Optional["Trade"]] = relationship("Trade", back_populates="orders")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_orders_status_symbol", "status", "symbol"),
        Index("ix_orders_trade_id", "trade_id"),
    )

    def __repr__(self) -> str:
        """String representation of order."""
        return (
            f"<Order(id={self.id}, order_id={self.order_id}, "
            f"symbol={self.symbol}, side={self.side}, status={self.status})>"
        )


class StrategyState(Base, TimestampMixin):
    """Persisted strategy state for crash recovery.

    Stores serialized strategy state as JSON for restoration
    after bot restarts.

    Attributes:
        id: Primary key.
        name: Strategy identifier (unique).
        state_json: JSON-serialized strategy state.
        version: State schema version for migrations.
    """

    __tablename__ = "strategy_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    def __repr__(self) -> str:
        """String representation of strategy state."""
        return f"<StrategyState(name={self.name}, version={self.version})>"


class BalanceSnapshot(Base):
    """Point-in-time snapshot of account balances.

    Used for equity tracking and performance analysis over time.

    Attributes:
        id: Primary key.
        timestamp: When snapshot was taken.
        exchange: Exchange for this balance.
        currency: Currency code.
        total: Total balance (free + used).
        free: Available balance.
        used: Balance in open orders.
    """

    __tablename__ = "balance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    free: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    used: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    # Composite index for time-series queries
    __table_args__ = (
        Index("ix_balance_exchange_currency_time", "exchange", "currency", "timestamp"),
    )

    def __repr__(self) -> str:
        """String representation of balance snapshot."""
        return (
            f"<BalanceSnapshot(currency={self.currency}, "
            f"total={self.total}, timestamp={self.timestamp})>"
        )


class OHLCVCache(Base):
    """Cached OHLCV (candlestick) data.

    Stores historical price data to reduce API calls and
    improve backtesting performance.

    Attributes:
        id: Primary key.
        exchange: Exchange source.
        symbol: Trading pair symbol.
        timeframe: Candle timeframe (1m, 5m, 1h, etc.).
        timestamp: Candle open time.
        open: Open price.
        high: High price.
        low: Low price.
        close: Close price.
        volume: Trading volume.
    """

    __tablename__ = "ohlcv_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    # Unique constraint and indexes for efficient querying
    __table_args__ = (
        Index(
            "ix_ohlcv_lookup",
            "exchange",
            "symbol",
            "timeframe",
            "timestamp",
            unique=True,
        ),
        Index("ix_ohlcv_symbol_timeframe", "symbol", "timeframe"),
    )

    def __repr__(self) -> str:
        """String representation of OHLCV candle."""
        return (
            f"<OHLCVCache(symbol={self.symbol}, timeframe={self.timeframe}, "
            f"timestamp={self.timestamp})>"
        )


class AlertLog(Base, TimestampMixin):
    """Log of sent alerts and notifications.

    Tracks alerts sent to various channels for debugging
    and rate limiting purposes.

    Attributes:
        id: Primary key.
        alert_type: Type of alert (error, warning, info, etc.).
        channel: Delivery channel (telegram, discord, etc.).
        message: Alert message content.
        metadata_json: Additional context as JSON.
        delivered: Whether alert was successfully delivered.
    """

    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_alert_type_created", "alert_type", "created_at"),)

    def __repr__(self) -> str:
        """String representation of alert log."""
        return f"<AlertLog(type={self.alert_type}, channel={self.channel})>"
