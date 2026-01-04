"""Strategy state persistence and reconciliation.

Provides state management for strategies including:
- State persistence to database
- State versioning and migration
- Startup reconciliation between local state and exchange
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol

import structlog

from crypto_bot.exchange.base_exchange import BaseExchange, OrderStatus
from crypto_bot.strategies.base_strategy import Strategy

logger = structlog.get_logger()


# =============================================================================
# State Store Protocol and Implementations (Story 2.4)
# =============================================================================


class StateStore(Protocol):
    """Interface for strategy state persistence.

    Implementations can use different backends (database, file, etc.)
    while maintaining a consistent interface.
    """

    async def save_state(self, strategy_name: str, state: dict[str, Any]) -> None:
        """Persist strategy state.

        Args:
            strategy_name: Unique identifier for the strategy.
            state: State dictionary to persist.
        """
        ...

    async def load_state(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """Load persisted state.

        Args:
            strategy_name: Unique identifier for the strategy.

        Returns:
            State dictionary if found, None otherwise.
        """
        ...

    async def delete_state(self, strategy_name: str) -> None:
        """Remove persisted state.

        Args:
            strategy_name: Unique identifier for the strategy.
        """
        ...

    async def list_strategies(self) -> list[str]:
        """List all persisted strategy names.

        Returns:
            List of strategy names with saved state.
        """
        ...


class DatabaseStateStore:
    """Database-backed state store using SQLAlchemy async session.

    Stores strategy state as JSON in the strategy_states table.
    Handles serialization of non-JSON-native types (Decimal, datetime).
    """

    def __init__(self, session_factory: Callable) -> None:
        """Initialize database state store.

        Args:
            session_factory: Async context manager that yields AsyncSession.
        """
        self._session_factory = session_factory
        self._logger = logger.bind(component="state_store")

    async def save_state(self, strategy_name: str, state: dict[str, Any]) -> None:
        """Persist strategy state to database.

        Uses upsert pattern to insert or update existing state.

        Args:
            strategy_name: Unique identifier for the strategy.
            state: State dictionary to persist.
        """
        from sqlalchemy import select, update

        from crypto_bot.data.models import StrategyState

        state_json = json.dumps(state, default=self._json_serializer)
        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            # Check if state exists
            result = await session.execute(
                select(StrategyState).where(StrategyState.name == strategy_name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing state
                existing.state_json = state_json
                existing.version = state.get("version", 1)
                existing.updated_at = now
            else:
                # Create new state record
                record = StrategyState(
                    name=strategy_name,
                    state_json=state_json,
                    version=state.get("version", 1),
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)

            await session.commit()
            self._logger.debug(
                "state_saved",
                strategy=strategy_name,
                version=state.get("version", 1),
            )

    async def load_state(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """Load persisted state from database.

        Args:
            strategy_name: Unique identifier for the strategy.

        Returns:
            State dictionary if found, None otherwise.
        """
        from sqlalchemy import select

        from crypto_bot.data.models import StrategyState

        async with self._session_factory() as session:
            result = await session.execute(
                select(StrategyState).where(StrategyState.name == strategy_name)
            )
            record = result.scalar_one_or_none()

            if not record:
                self._logger.debug("state_not_found", strategy=strategy_name)
                return None

            state = json.loads(record.state_json)
            self._logger.debug(
                "state_loaded",
                strategy=strategy_name,
                version=state.get("version"),
            )
            return state

    async def delete_state(self, strategy_name: str) -> None:
        """Remove persisted state from database.

        Args:
            strategy_name: Unique identifier for the strategy.
        """
        from sqlalchemy import delete

        from crypto_bot.data.models import StrategyState

        async with self._session_factory() as session:
            await session.execute(
                delete(StrategyState).where(StrategyState.name == strategy_name)
            )
            await session.commit()
            self._logger.info("state_deleted", strategy=strategy_name)

    async def list_strategies(self) -> list[str]:
        """List all persisted strategy names.

        Returns:
            List of strategy names with saved state.
        """
        from sqlalchemy import select

        from crypto_bot.data.models import StrategyState

        async with self._session_factory() as session:
            result = await session.execute(select(StrategyState.name))
            return [row[0] for row in result.fetchall()]

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """JSON serializer for non-native types.

        Args:
            obj: Object to serialize.

        Returns:
            JSON-serializable representation.

        Raises:
            TypeError: If object is not serializable.
        """
        from decimal import Decimal

        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class InMemoryStateStore:
    """In-memory state store for testing.

    Stores state in a dictionary. All data is lost on process exit.
    """

    def __init__(self) -> None:
        """Initialize in-memory state store."""
        self._states: dict[str, dict[str, Any]] = {}

    async def save_state(self, strategy_name: str, state: dict[str, Any]) -> None:
        """Save state to memory."""
        # Deep copy to prevent external mutation
        self._states[strategy_name] = json.loads(
            json.dumps(state, default=str)
        )

    async def load_state(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """Load state from memory."""
        state = self._states.get(strategy_name)
        if state:
            return json.loads(json.dumps(state))  # Deep copy
        return None

    async def delete_state(self, strategy_name: str) -> None:
        """Delete state from memory."""
        self._states.pop(strategy_name, None)

    async def list_strategies(self) -> list[str]:
        """List all stored strategies."""
        return list(self._states.keys())


class StateManager:
    """Manages strategy state lifecycle.

    Provides automatic state saving after order events and
    handles strategy restoration on startup.
    """

    def __init__(self, state_store: StateStore) -> None:
        """Initialize state manager.

        Args:
            state_store: Backend for state persistence.
        """
        self._store = state_store
        self._logger = logger.bind(component="state_manager")

    async def save_strategy_state(self, strategy: Strategy) -> None:
        """Save current strategy state.

        Should be called after every order event for crash recovery.

        Args:
            strategy: Strategy to save state for.
        """
        try:
            state = strategy.get_state()
            await self._store.save_state(strategy.name, state)
        except Exception as e:
            self._logger.error(
                "state_save_failed",
                strategy=strategy.name,
                error=str(e),
            )

    async def load_strategy_state(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """Load persisted strategy state.

        Args:
            strategy_name: Strategy identifier.

        Returns:
            State dictionary if found.
        """
        return await self._store.load_state(strategy_name)

    async def clear_strategy_state(self, strategy_name: str) -> None:
        """Clear persisted strategy state.

        Args:
            strategy_name: Strategy identifier.
        """
        await self._store.delete_state(strategy_name)


# =============================================================================
# State Reconciliation (Story 2.5)
# =============================================================================


@dataclass
class ReconciliationResult:
    """Results of state reconciliation with exchange.

    Attributes:
        orphan_orders: Orders on exchange not tracked by strategy.
        phantom_orders: Orders in strategy state but not on exchange.
        filled_orders: Orders that filled while bot was down.
        orders_to_recheck: Orders needing status verification.
    """

    orphan_orders: list[str] = field(default_factory=list)
    phantom_orders: list[str] = field(default_factory=list)
    filled_orders: list[str] = field(default_factory=list)
    orders_to_recheck: list[str] = field(default_factory=list)

    @property
    def needs_action(self) -> bool:
        """Check if reconciliation found issues requiring action."""
        return bool(
            self.orphan_orders
            or self.phantom_orders
            or self.filled_orders
        )

    @property
    def summary(self) -> str:
        """Human-readable summary of reconciliation results."""
        parts = []
        if self.orphan_orders:
            parts.append(f"{len(self.orphan_orders)} orphan orders")
        if self.phantom_orders:
            parts.append(f"{len(self.phantom_orders)} phantom orders")
        if self.filled_orders:
            parts.append(f"{len(self.filled_orders)} filled orders")
        return ", ".join(parts) if parts else "no issues found"


class ReconciliationError(Exception):
    """Raised when state reconciliation fails or requires manual intervention."""

    pass


class StateReconciler:
    """Reconciles strategy state with exchange reality on startup.

    Handles three types of state mismatches:
    1. Orphan orders: Exist on exchange but not in our state
    2. Phantom orders: In our state but not on exchange
    3. Filled orders: Were filled while bot was offline
    """

    def __init__(
        self,
        exchange: BaseExchange,
        state_store: StateStore,
    ) -> None:
        """Initialize state reconciler.

        Args:
            exchange: Exchange adapter for fetching order state.
            state_store: State persistence backend.
        """
        self._exchange = exchange
        self._state_store = state_store
        self._logger = logger.bind(component="reconciler")

    async def reconcile(self, strategy: Strategy) -> ReconciliationResult:
        """Reconcile strategy state with exchange reality.

        Compares tracked orders in strategy state with actual orders
        on the exchange to identify mismatches.

        Args:
            strategy: Strategy to reconcile.

        Returns:
            ReconciliationResult with identified issues.
        """
        result = ReconciliationResult()

        # Load persisted state
        persisted = await self._state_store.load_state(strategy.name)
        if not persisted:
            self._logger.info(
                "no_persisted_state",
                strategy=strategy.name,
            )
            return result

        # Get actual open orders from exchange
        try:
            exchange_orders = await self._exchange.fetch_open_orders(strategy.symbol)
        except Exception as e:
            self._logger.error(
                "fetch_orders_failed",
                strategy=strategy.name,
                error=str(e),
            )
            raise ReconciliationError(f"Failed to fetch orders: {e}")

        exchange_order_ids = {o.id for o in exchange_orders}

        # Get order IDs from persisted state
        persisted_order_ids = set(persisted.get("active_orders", []))

        # Find orphan orders (on exchange but not tracked)
        orphans = exchange_order_ids - persisted_order_ids
        for order_id in orphans:
            self._logger.warning(
                "orphan_order_found",
                order_id=order_id,
                strategy=strategy.name,
            )
            result.orphan_orders.append(order_id)

        # Find phantom orders (tracked but not on exchange)
        phantoms = persisted_order_ids - exchange_order_ids
        for order_id in phantoms:
            # Check if order was filled or cancelled
            try:
                order = await self._exchange.fetch_order(order_id, strategy.symbol)
                if order.status == OrderStatus.CLOSED:
                    self._logger.info(
                        "order_filled_while_offline",
                        order_id=order_id,
                    )
                    result.filled_orders.append(order_id)
                else:
                    self._logger.warning(
                        "phantom_order_found",
                        order_id=order_id,
                        status=order.status.value,
                    )
                    result.phantom_orders.append(order_id)
            except Exception:
                self._logger.warning(
                    "phantom_order_not_found",
                    order_id=order_id,
                )
                result.phantom_orders.append(order_id)

        self._logger.info(
            "reconciliation_complete",
            strategy=strategy.name,
            orphans=len(result.orphan_orders),
            phantoms=len(result.phantom_orders),
            filled=len(result.filled_orders),
        )

        return result

    async def apply_reconciliation(
        self,
        strategy: Strategy,
        result: ReconciliationResult,
        action: str = "prompt",
    ) -> None:
        """Apply reconciliation actions to resolve mismatches.

        Args:
            strategy: Strategy to reconcile.
            result: Reconciliation results.
            action: Action mode:
                - "prompt": Log warnings only (manual intervention)
                - "auto_fix": Automatically resolve issues
                - "abort": Raise error if issues found

        Raises:
            ReconciliationError: If action is "abort" and issues exist.
        """
        if not result.needs_action:
            return

        if action == "abort":
            raise ReconciliationError(
                f"State mismatch detected: {result.summary}. "
                "Manual intervention required."
            )

        if action == "prompt":
            self._logger.warning(
                "reconciliation_needs_review",
                summary=result.summary,
                orphans=result.orphan_orders,
                phantoms=result.phantom_orders,
            )
            return

        if action == "auto_fix":
            await self._auto_fix(strategy, result)

    async def _auto_fix(
        self,
        strategy: Strategy,
        result: ReconciliationResult,
    ) -> None:
        """Automatically fix reconciliation issues.

        - Cancels orphan orders
        - Removes phantom orders from state
        - Processes filled orders

        Args:
            strategy: Strategy to fix.
            result: Reconciliation results.
        """
        # Cancel orphan orders
        for order_id in result.orphan_orders:
            try:
                await self._exchange.cancel_order(order_id, strategy.symbol)
                self._logger.info(
                    "cancelled_orphan",
                    order_id=order_id,
                )
            except Exception as e:
                self._logger.error(
                    "cancel_orphan_failed",
                    order_id=order_id,
                    error=str(e),
                )

        # Remove phantom orders from strategy state
        for order_id in result.phantom_orders:
            if hasattr(strategy, "remove_order_from_state"):
                strategy.remove_order_from_state(order_id)
                self._logger.info(
                    "removed_phantom",
                    order_id=order_id,
                )

        # Process filled orders
        for order_id in result.filled_orders:
            try:
                order = await self._exchange.fetch_order(order_id, strategy.symbol)
                await strategy.on_order_filled(order)
                self._logger.info(
                    "processed_offline_fill",
                    order_id=order_id,
                )
            except Exception as e:
                self._logger.error(
                    "process_fill_failed",
                    order_id=order_id,
                    error=str(e),
                )

        self._logger.info(
            "auto_fix_complete",
            strategy=strategy.name,
        )


class ReconciliationPolicy:
    """Policy configuration for reconciliation behavior.

    Defines thresholds and actions for different reconciliation scenarios.
    """

    def __init__(
        self,
        auto_fix_threshold: int = 5,
        abort_threshold: int = 20,
        cancel_orphans: bool = True,
        process_offline_fills: bool = True,
    ) -> None:
        """Initialize reconciliation policy.

        Args:
            auto_fix_threshold: Max issues for auto_fix (more requires prompt).
            abort_threshold: Max issues before abort (safety limit).
            cancel_orphans: Whether to cancel orphan orders.
            process_offline_fills: Whether to process fills from downtime.
        """
        self.auto_fix_threshold = auto_fix_threshold
        self.abort_threshold = abort_threshold
        self.cancel_orphans = cancel_orphans
        self.process_offline_fills = process_offline_fills

    def determine_action(self, result: ReconciliationResult) -> str:
        """Determine appropriate action based on reconciliation results.

        Args:
            result: Reconciliation results.

        Returns:
            Action string: "auto_fix", "prompt", or "abort".
        """
        total_issues = (
            len(result.orphan_orders)
            + len(result.phantom_orders)
        )

        if total_issues == 0:
            return "auto_fix"
        elif total_issues <= self.auto_fix_threshold:
            return "auto_fix"
        elif total_issues <= self.abort_threshold:
            return "prompt"
        else:
            return "abort"
