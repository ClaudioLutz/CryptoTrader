"""Base strategy interface using Python Protocol (PEP 544).

This module defines the Strategy Protocol and related types that enable
pluggable strategies without requiring inheritance. Any class implementing
the required methods can be used as a strategy.

Strategy Lifecycle:
1. initialize() - Called once to set up the strategy with execution context
2. on_tick() - Called on each price update
3. on_order_filled() - Called when an order is filled
4. on_order_cancelled() - Called when an order is cancelled
5. shutdown() - Called during graceful shutdown
"""

from decimal import Decimal
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from crypto_bot.exchange.base_exchange import Order, Ticker


@runtime_checkable
class ExecutionContext(Protocol):
    """Abstraction over live/backtest execution.

    This protocol defines the interface for order execution that strategies
    use. By abstracting the execution layer, the same strategy code can run
    in live trading, dry-run mode, or backtesting.
    """

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT").

        Returns:
            The current last traded price.
        """
        ...

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
    ) -> str:
        """Place an order.

        Args:
            symbol: Trading pair symbol.
            side: "buy" or "sell".
            amount: Order quantity in base currency.
            price: Limit price (None for market order).

        Returns:
            The order ID assigned by the exchange.
        """
        ...

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: The exchange order ID.
            symbol: Trading pair symbol.

        Returns:
            True if cancellation succeeded, False otherwise.
        """
        ...

    async def get_balance(self, currency: str) -> Decimal:
        """Get available balance for a currency.

        Args:
            currency: Currency code (e.g., "BTC", "USDT").

        Returns:
            Available (free) balance for the currency.
        """
        ...


@runtime_checkable
class Strategy(Protocol):
    """Protocol defining the strategy interface.

    Any class implementing these methods can be used as a trading strategy.
    The @runtime_checkable decorator allows isinstance() checks.

    Example:
        >>> class MyStrategy:
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_strategy"
        ...     # ... implement other methods
        >>> isinstance(MyStrategy(), Strategy)
        True
    """

    @property
    def name(self) -> str:
        """Strategy identifier.

        Returns:
            Unique name identifying this strategy instance.
        """
        ...

    @property
    def symbol(self) -> str:
        """Trading pair symbol.

        Returns:
            The symbol this strategy trades (e.g., "BTC/USDT").
        """
        ...

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize strategy with execution context.

        Called once before the strategy starts receiving ticks.
        Use this to set up initial state and place opening orders.

        Args:
            context: The execution context for order operations.
        """
        ...

    async def on_tick(self, ticker: Ticker) -> None:
        """Handle price update.

        Called on each price update from the exchange.

        Args:
            ticker: Current ticker data with bid, ask, and last prices.
        """
        ...

    async def on_order_filled(self, order: Order) -> None:
        """Handle order fill notification.

        Called when an order placed by this strategy is filled.

        Args:
            order: The filled order with execution details.
        """
        ...

    async def on_order_cancelled(self, order: Order) -> None:
        """Handle order cancellation.

        Called when an order is cancelled (by strategy, user, or exchange).

        Args:
            order: The cancelled order.
        """
        ...

    def get_state(self) -> dict[str, Any]:
        """Serialize strategy state for persistence.

        Returns:
            Dictionary containing all state needed to restore the strategy.
            Must be JSON-serializable (use str for Decimal, datetime, etc.).
        """
        ...

    @classmethod
    def from_state(
        cls, state: dict[str, Any], context: ExecutionContext
    ) -> "Strategy":
        """Restore strategy from persisted state.

        Args:
            state: Dictionary from get_state().
            context: Execution context for the restored strategy.

        Returns:
            Restored strategy instance.
        """
        ...

    async def shutdown(self) -> None:
        """Clean up resources and optionally cancel open orders.

        Called during graceful shutdown. Implementations should:
        - Cancel any open orders if configured to do so
        - Release any held resources
        - Save final state
        """
        ...


class StrategyConfig(BaseModel):
    """Base configuration for all strategies.

    All strategy configurations should inherit from this class
    to ensure consistent handling of common settings.

    Attributes:
        name: Strategy type identifier (e.g., "grid", "dca").
        symbol: Trading pair symbol.
        enabled: Whether the strategy is active.
        dry_run: If True, simulate orders without real execution.
    """

    name: str = Field(..., description="Strategy type identifier")
    symbol: str = Field(..., description="Trading pair symbol (e.g., BTC/USDT)")
    enabled: bool = Field(default=True, description="Whether strategy is active")
    dry_run: bool = Field(default=False, description="Simulate without real orders")

    model_config = {"frozen": False, "extra": "allow"}


class StrategyFactory:
    """Factory for creating strategy instances from configuration.

    Provides a registry pattern for strategy types, allowing
    configuration-driven strategy instantiation.

    Example:
        >>> StrategyFactory.register("grid", GridTradingStrategy)
        >>> config = GridConfig(name="grid", symbol="BTC/USDT", ...)
        >>> strategy = StrategyFactory.create(config, context)
    """

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, strategy_class: type) -> None:
        """Register a strategy class with a name.

        Args:
            name: Strategy type identifier.
            strategy_class: The strategy class to register.
        """
        cls._registry[name] = strategy_class

    @classmethod
    def create(
        cls,
        config: StrategyConfig,
        context: ExecutionContext,
    ) -> Strategy:
        """Create a strategy instance from configuration.

        Args:
            config: Strategy configuration with type and parameters.
            context: Execution context for order operations.

        Returns:
            Initialized strategy instance.

        Raises:
            ValueError: If strategy type is not registered.
        """
        if config.name not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(
                f"Unknown strategy: '{config.name}'. Available: {available}"
            )
        strategy_class = cls._registry[config.name]
        return strategy_class(config, context)

    @classmethod
    def get_registered(cls) -> list[str]:
        """Get list of registered strategy names.

        Returns:
            List of registered strategy type identifiers.
        """
        return list(cls._registry.keys())

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a strategy class.

        Args:
            name: Strategy type identifier to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in cls._registry:
            del cls._registry[name]
            return True
        return False
