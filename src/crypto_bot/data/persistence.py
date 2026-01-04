"""Database persistence layer with async session management and repositories.

Provides:
- Async database connection management
- Session lifecycle with proper transaction handling
- Repository pattern for Trade and Order CRUD operations
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from crypto_bot.config.settings import DatabaseSettings
from crypto_bot.data.models import (
    BalanceSnapshot,
    Base,
    Order,
    StrategyState,
    Trade,
)

logger = structlog.get_logger()


# =============================================================================
# Database Connection Management (Story 2.7)
# =============================================================================


class Database:
    """Async database connection manager.

    Manages the database engine lifecycle and provides session factories
    for transactional operations.

    Example:
        >>> db = Database(settings)
        >>> await db.connect()
        >>> async with db.session() as session:
        ...     # Perform database operations
        >>> await db.disconnect()
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        """Initialize database manager.

        Args:
            settings: Database configuration settings.
        """
        self._settings = settings
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._logger = logger.bind(component="database")

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._engine is not None

    async def connect(self) -> None:
        """Initialize database connection and create tables.

        Creates the async engine and session factory. Also creates
        all tables defined in the ORM models if they don't exist.
        """
        if self._engine:
            self._logger.warning("database_already_connected")
            return

        # Build engine kwargs - SQLite doesn't support pool_size
        engine_kwargs: dict = {
            "echo": self._settings.echo,
        }

        # Only add pool options for non-SQLite databases
        if not self._settings.url.startswith("sqlite"):
            engine_kwargs["pool_size"] = self._settings.pool_size
            engine_kwargs["pool_pre_ping"] = True

        self._engine = create_async_engine(
            self._settings.url,
            **engine_kwargs,
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Allow attribute access after commit
            autoflush=False,
        )

        # Create tables if they don't exist
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._logger.info(
            "database_connected",
            url=self._redact_url(self._settings.url),
            pool_size=self._settings.pool_size,
        )

    async def disconnect(self) -> None:
        """Close database connection and dispose of engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._logger.info("database_disconnected")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional session scope.

        Automatically commits on success or rolls back on exception.

        Yields:
            AsyncSession: Database session for operations.

        Raises:
            RuntimeError: If database is not connected.
        """
        if not self._session_factory:
            raise RuntimeError("Database not connected. Call connect() first.")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def health_check(self) -> bool:
        """Verify database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self._logger.error("database_health_check_failed", error=str(e))
            return False

    @staticmethod
    def _redact_url(url: str) -> str:
        """Redact password from database URL for logging.

        Args:
            url: Database connection URL.

        Returns:
            URL with password replaced by asterisks.
        """
        # Simple redaction - replace password portion
        if "@" in url and ":" in url.split("@")[0]:
            parts = url.split("@")
            auth_parts = parts[0].rsplit(":", 1)
            if len(auth_parts) == 2:
                return f"{auth_parts[0]}:****@{parts[1]}"
        return url


# =============================================================================
# Trade Repository (Story 2.8)
# =============================================================================


class TradeRepository:
    """Repository for Trade CRUD operations.

    Provides data access methods for trades with proper async
    session handling.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize trade repository.

        Args:
            session: Active database session.
        """
        self._session = session

    async def create(self, trade: Trade) -> Trade:
        """Create a new trade record.

        Args:
            trade: Trade object to persist.

        Returns:
            Persisted trade with ID assigned.
        """
        self._session.add(trade)
        await self._session.flush()
        return trade

    async def get_by_id(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID.

        Args:
            trade_id: Primary key.

        Returns:
            Trade if found, None otherwise.
        """
        result = await self._session.execute(
            select(Trade).where(Trade.id == trade_id)
        )
        return result.scalar_one_or_none()

    async def get_open_trades(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> list[Trade]:
        """Get all open trades with optional filters.

        Args:
            symbol: Filter by trading pair.
            strategy: Filter by strategy name.

        Returns:
            List of matching open trades.
        """
        query = select(Trade).where(Trade.is_open == True)
        if symbol:
            query = query.where(Trade.symbol == symbol)
        if strategy:
            query = query.where(Trade.strategy == strategy)
        query = query.order_by(Trade.open_date.desc())

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def close_trade(
        self,
        trade_id: int,
        close_rate: Decimal,
        close_date: datetime,
        profit: Decimal,
        fee: Decimal,
    ) -> Trade:
        """Close an open trade.

        Args:
            trade_id: Trade to close.
            close_rate: Exit price.
            close_date: Exit timestamp.
            profit: Realized profit/loss.
            fee: Total fees paid.

        Returns:
            Updated trade.

        Raises:
            ValueError: If trade not found.
        """
        trade = await self.get_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        trade.is_open = False
        trade.close_rate = close_rate
        trade.close_date = close_date
        trade.profit = profit
        trade.profit_pct = (close_rate - trade.open_rate) / trade.open_rate
        trade.fee = fee

        return trade

    async def get_trade_history(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Trade]:
        """Get historical (closed) trades with filters.

        Args:
            symbol: Filter by trading pair.
            strategy: Filter by strategy name.
            start_date: Filter trades closed after this time.
            end_date: Filter trades closed before this time.
            limit: Maximum number of trades to return.

        Returns:
            List of matching closed trades, newest first.
        """
        query = select(Trade).where(Trade.is_open == False)

        if symbol:
            query = query.where(Trade.symbol == symbol)
        if strategy:
            query = query.where(Trade.strategy == strategy)
        if start_date:
            query = query.where(Trade.close_date >= start_date)
        if end_date:
            query = query.where(Trade.close_date <= end_date)

        query = query.order_by(Trade.close_date.desc()).limit(limit)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self, strategy: str) -> dict:
        """Calculate trading statistics for a strategy.

        Args:
            strategy: Strategy name to analyze.

        Returns:
            Dictionary with trading metrics.
        """
        trades = await self.get_trade_history(strategy=strategy, limit=1000)

        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_profit": Decimal(0),
                "avg_profit": Decimal(0),
                "max_win": Decimal(0),
                "max_loss": Decimal(0),
            }

        wins = [t for t in trades if t.profit and t.profit > 0]
        losses = [t for t in trades if t.profit and t.profit < 0]

        total_profit = sum(t.profit for t in trades if t.profit) or Decimal(0)
        avg_profit = total_profit / len(trades) if trades else Decimal(0)

        return {
            "total_trades": len(trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "total_profit": total_profit,
            "avg_profit": avg_profit,
            "max_win": max((t.profit for t in wins), default=Decimal(0)),
            "max_loss": min((t.profit for t in losses), default=Decimal(0)),
        }


# =============================================================================
# Order Repository (Story 2.8)
# =============================================================================


class OrderRepository:
    """Repository for Order CRUD operations.

    Provides data access methods for orders with proper async
    session handling.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize order repository.

        Args:
            session: Active database session.
        """
        self._session = session

    async def create(self, order: Order) -> Order:
        """Create a new order record.

        Args:
            order: Order object to persist.

        Returns:
            Persisted order with ID assigned.
        """
        self._session.add(order)
        await self._session.flush()
        return order

    async def get_by_order_id(self, order_id: str) -> Optional[Order]:
        """Get order by exchange order ID.

        Args:
            order_id: Exchange-assigned order ID.

        Returns:
            Order if found, None otherwise.
        """
        result = await self._session.execute(
            select(Order).where(Order.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, id: int) -> Optional[Order]:
        """Get order by primary key.

        Args:
            id: Database primary key.

        Returns:
            Order if found, None otherwise.
        """
        result = await self._session.execute(
            select(Order).where(Order.id == id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        order_id: str,
        status: str,
        filled: Decimal,
        cost: Optional[Decimal] = None,
        fee: Optional[Decimal] = None,
    ) -> Order:
        """Update order status after fill/cancel.

        Args:
            order_id: Exchange order ID.
            status: New order status.
            filled: Amount filled.
            cost: Total cost (optional).
            fee: Fees paid (optional).

        Returns:
            Updated order.

        Raises:
            ValueError: If order not found.
        """
        order = await self.get_by_order_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        order.status = status
        order.filled = filled
        order.remaining = order.amount - filled
        if cost is not None:
            order.cost = cost
        if fee is not None:
            order.fee = fee

        return order

    async def get_open_orders(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> list[Order]:
        """Get all open orders.

        Args:
            symbol: Filter by trading pair.
            exchange: Filter by exchange.

        Returns:
            List of open orders.
        """
        query = select(Order).where(Order.status == "open")

        if symbol:
            query = query.where(Order.symbol == symbol)
        if exchange:
            query = query.where(Order.exchange == exchange)

        query = query.order_by(Order.created_at.desc())

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_orders_by_trade(self, trade_id: int) -> list[Order]:
        """Get all orders for a specific trade.

        Args:
            trade_id: Trade ID to filter by.

        Returns:
            List of orders for the trade.
        """
        result = await self._session.execute(
            select(Order)
            .where(Order.trade_id == trade_id)
            .order_by(Order.created_at.asc())
        )
        return list(result.scalars().all())


# =============================================================================
# Balance Snapshot Repository
# =============================================================================


class BalanceSnapshotRepository:
    """Repository for balance snapshot operations.

    Tracks account balances over time for equity analysis.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize balance snapshot repository.

        Args:
            session: Active database session.
        """
        self._session = session

    async def create(self, snapshot: BalanceSnapshot) -> BalanceSnapshot:
        """Create a new balance snapshot.

        Args:
            snapshot: Snapshot to persist.

        Returns:
            Persisted snapshot.
        """
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def create_from_balances(
        self,
        exchange: str,
        balances: dict[str, dict[str, Decimal]],
        timestamp: Optional[datetime] = None,
    ) -> list[BalanceSnapshot]:
        """Create snapshots from exchange balance response.

        Args:
            exchange: Exchange name.
            balances: Dictionary mapping currency to balance info.
            timestamp: Snapshot time (defaults to now).

        Returns:
            List of created snapshots.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        snapshots = []
        for currency, balance in balances.items():
            snapshot = BalanceSnapshot(
                timestamp=timestamp,
                exchange=exchange,
                currency=currency,
                total=balance.get("total", Decimal(0)),
                free=balance.get("free", Decimal(0)),
                used=balance.get("used", Decimal(0)),
            )
            self._session.add(snapshot)
            snapshots.append(snapshot)

        await self._session.flush()
        return snapshots

    async def get_latest(
        self,
        exchange: str,
        currency: str,
    ) -> Optional[BalanceSnapshot]:
        """Get most recent balance snapshot.

        Args:
            exchange: Exchange name.
            currency: Currency code.

        Returns:
            Latest snapshot if found.
        """
        result = await self._session.execute(
            select(BalanceSnapshot)
            .where(BalanceSnapshot.exchange == exchange)
            .where(BalanceSnapshot.currency == currency)
            .order_by(BalanceSnapshot.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        exchange: str,
        currency: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[BalanceSnapshot]:
        """Get balance history over time.

        Args:
            exchange: Exchange name.
            currency: Currency code.
            start_date: Filter snapshots after this time.
            end_date: Filter snapshots before this time.
            limit: Maximum records to return.

        Returns:
            List of balance snapshots, oldest first.
        """
        query = (
            select(BalanceSnapshot)
            .where(BalanceSnapshot.exchange == exchange)
            .where(BalanceSnapshot.currency == currency)
        )

        if start_date:
            query = query.where(BalanceSnapshot.timestamp >= start_date)
        if end_date:
            query = query.where(BalanceSnapshot.timestamp <= end_date)

        query = query.order_by(BalanceSnapshot.timestamp.asc()).limit(limit)

        result = await self._session.execute(query)
        return list(result.scalars().all())


# =============================================================================
# Unit of Work Pattern
# =============================================================================


class UnitOfWork:
    """Unit of Work pattern for coordinated repository operations.

    Provides access to all repositories through a single session,
    ensuring transactional consistency.

    Example:
        >>> async with UnitOfWork(db) as uow:
        ...     trade = await uow.trades.create(new_trade)
        ...     order = await uow.orders.create(new_order)
        ...     # Both operations commit together
    """

    def __init__(self, database: Database) -> None:
        """Initialize Unit of Work.

        Args:
            database: Database connection manager.
        """
        self._database = database
        self._session: Optional[AsyncSession] = None

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context and create session."""
        self._session = self._database._session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context, committing or rolling back."""
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
        await self._session.close()
        self._session = None

    @property
    def trades(self) -> TradeRepository:
        """Get trade repository."""
        return TradeRepository(self._session)

    @property
    def orders(self) -> OrderRepository:
        """Get order repository."""
        return OrderRepository(self._session)

    @property
    def balance_snapshots(self) -> BalanceSnapshotRepository:
        """Get balance snapshot repository."""
        return BalanceSnapshotRepository(self._session)
