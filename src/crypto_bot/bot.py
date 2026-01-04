"""Bot orchestrator managing the trading lifecycle.

Coordinates all components:
- Exchange connection
- Database persistence
- Strategy execution
- State management
- Graceful shutdown
"""

import asyncio
from decimal import Decimal
from typing import Optional

import structlog

from crypto_bot.config.settings import AppSettings
from crypto_bot.data.models import Order as OrderModel
from crypto_bot.data.persistence import Database, OrderRepository
from crypto_bot.exchange.base_exchange import (
    Balance,
    BaseExchange,
    OrderNotFoundError,
    OrderSide,
    OrderStatus,
    OrderType,
)
from crypto_bot.strategies.base_strategy import ExecutionContext, Strategy
from crypto_bot.strategies.strategy_state import (
    DatabaseStateStore,
    ReconciliationPolicy,
    StateManager,
    StateReconciler,
)

logger = structlog.get_logger()


# =============================================================================
# Execution Contexts (Story 2.10 & 2.11)
# =============================================================================


class LiveExecutionContext:
    """Execution context for live trading.

    Connects strategy operations to the real exchange and database.
    """

    def __init__(
        self,
        exchange: BaseExchange,
        database: Database,
        exchange_name: str = "binance",
    ) -> None:
        """Initialize live execution context.

        Args:
            exchange: Exchange adapter for order operations.
            database: Database connection for persistence.
            exchange_name: Name of the exchange for records.
        """
        self._exchange = exchange
        self._database = database
        self._exchange_name = exchange_name
        self._logger = logger.bind(context="live")

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price from exchange.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Current last traded price.
        """
        ticker = await self._exchange.fetch_ticker(symbol)
        return ticker.last

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
    ) -> str:
        """Place an order on the exchange.

        Args:
            symbol: Trading pair symbol.
            side: "buy" or "sell".
            amount: Order quantity.
            price: Limit price (None for market order).

        Returns:
            Exchange-assigned order ID.
        """
        order_type = OrderType.LIMIT if price else OrderType.MARKET

        order = await self._exchange.create_order(
            symbol=symbol,
            order_type=order_type,
            side=OrderSide(side),
            amount=amount,
            price=price,
        )

        # Persist order to database
        async with self._database.session() as session:
            repo = OrderRepository(session)
            await repo.create(
                OrderModel(
                    order_id=order.id,
                    exchange=self._exchange_name,
                    symbol=symbol,
                    side=side,
                    order_type=order_type.value,
                    status=order.status.value,
                    price=price,
                    amount=amount,
                    filled=order.filled,
                    remaining=order.remaining,
                )
            )

        self._logger.info(
            "order_placed",
            order_id=order.id,
            symbol=symbol,
            side=side,
            amount=str(amount),
            price=str(price) if price else "market",
        )

        return order.id

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order on the exchange.

        Args:
            order_id: Exchange order ID.
            symbol: Trading pair symbol.

        Returns:
            True if cancelled successfully.
        """
        try:
            await self._exchange.cancel_order(order_id, symbol)

            # Update order in database
            async with self._database.session() as session:
                repo = OrderRepository(session)
                try:
                    await repo.update_status(
                        order_id=order_id,
                        status="canceled",
                        filled=Decimal(0),
                    )
                except ValueError:
                    pass  # Order might not be in our database

            self._logger.info("order_cancelled", order_id=order_id)
            return True

        except OrderNotFoundError:
            self._logger.warning("order_not_found_for_cancel", order_id=order_id)
            return False

    async def get_balance(self, currency: str) -> Decimal:
        """Get available balance for a currency.

        Args:
            currency: Currency code.

        Returns:
            Available (free) balance.
        """
        balances = await self._exchange.fetch_balance()
        balance = balances.get(currency)
        if balance:
            return balance.free
        return Decimal(0)


class DryRunExecutionContext:
    """Simulated execution context for testing without real orders.

    Simulates order placement and tracks balances locally.
    All logs are clearly marked as DRY-RUN.
    """

    def __init__(
        self,
        exchange: BaseExchange,
        initial_balance: dict[str, Decimal],
    ) -> None:
        """Initialize dry-run execution context.

        Args:
            exchange: Exchange adapter (for price data only).
            initial_balance: Starting balances per currency.
        """
        self._exchange = exchange
        self._balance = initial_balance.copy()
        self._orders: dict[str, dict] = {}
        self._order_counter = 0
        self._logger = logger.bind(context="dry_run")

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price from exchange.

        Price data is real even in dry-run mode.

        Args:
            symbol: Trading pair symbol.

        Returns:
            Current last traded price.
        """
        ticker = await self._exchange.fetch_ticker(symbol)
        return ticker.last

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
    ) -> str:
        """Simulate placing an order.

        Args:
            symbol: Trading pair symbol.
            side: "buy" or "sell".
            amount: Order quantity.
            price: Limit price.

        Returns:
            Simulated order ID.
        """
        self._order_counter += 1
        order_id = f"DRY_{self._order_counter:06d}"

        self._orders[order_id] = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "open",
            "filled": Decimal(0),
        }

        self._logger.info(
            "DRY-RUN order_placed",
            order_id=order_id,
            symbol=symbol,
            side=side,
            amount=str(amount),
            price=str(price) if price else "market",
        )

        return order_id

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Simulate cancelling an order.

        Args:
            order_id: Simulated order ID.
            symbol: Trading pair symbol (unused).

        Returns:
            True if order existed and was cancelled.
        """
        if order_id in self._orders:
            self._orders[order_id]["status"] = "canceled"
            self._logger.info("DRY-RUN order_cancelled", order_id=order_id)
            return True

        self._logger.warning("DRY-RUN order_not_found", order_id=order_id)
        return False

    async def get_balance(self, currency: str) -> Decimal:
        """Get simulated balance for a currency.

        Args:
            currency: Currency code.

        Returns:
            Simulated available balance.
        """
        return self._balance.get(currency, Decimal(0))

    def simulate_fill(self, order_id: str) -> bool:
        """Manually simulate an order fill for testing.

        Args:
            order_id: Order to fill.

        Returns:
            True if order was found and filled.
        """
        if order_id in self._orders:
            order = self._orders[order_id]
            order["status"] = "closed"
            order["filled"] = order["amount"]

            # Update simulated balance
            symbol = order["symbol"]
            base, quote = symbol.split("/")
            amount = order["amount"]
            price = order["price"] or Decimal(0)

            if order["side"] == "buy":
                self._balance[base] = self._balance.get(base, Decimal(0)) + amount
                self._balance[quote] = self._balance.get(quote, Decimal(0)) - (
                    amount * price
                )
            else:
                self._balance[base] = self._balance.get(base, Decimal(0)) - amount
                self._balance[quote] = self._balance.get(quote, Decimal(0)) + (
                    amount * price
                )

            self._logger.info("DRY-RUN order_filled", order_id=order_id)
            return True

        return False


# =============================================================================
# Trading Bot Orchestrator (Story 2.10)
# =============================================================================


class TradingBot:
    """Central orchestrator managing the bot lifecycle.

    Coordinates:
    - Component initialization
    - State reconciliation
    - Trading loop execution
    - Graceful shutdown
    """

    DEFAULT_TICK_INTERVAL = 1.0  # seconds

    def __init__(
        self,
        settings: AppSettings,
        exchange: BaseExchange,
        database: Database,
        strategy: Strategy,
    ) -> None:
        """Initialize trading bot.

        Args:
            settings: Application configuration.
            exchange: Exchange adapter.
            database: Database connection.
            strategy: Trading strategy to execute.
        """
        self._settings = settings
        self._exchange = exchange
        self._database = database
        self._strategy = strategy
        self._running = False
        self._context: Optional[ExecutionContext] = None
        self._state_manager: Optional[StateManager] = None
        self._logger = logger.bind(
            bot="trading_bot",
            strategy=strategy.name,
        )

    @property
    def is_running(self) -> bool:
        """Check if bot is currently running."""
        return self._running

    async def start(self) -> None:
        """Initialize and start the bot.

        Performs:
        1. Component connection
        2. State reconciliation
        3. Strategy initialization
        4. Trading loop start
        """
        self._logger.info(
            "bot_starting",
            strategy=self._strategy.name,
            symbol=self._strategy.symbol,
            dry_run=self._settings.trading.dry_run,
        )

        # Connect components
        await self._exchange.connect()
        await self._database.connect()

        # Set up state management
        state_store = DatabaseStateStore(self._database.session)
        self._state_manager = StateManager(state_store)

        # Reconcile state with exchange
        await self._reconcile_state(state_store)

        # Create execution context
        if self._settings.trading.dry_run:
            # Get initial balance for dry run
            balances = await self._exchange.fetch_balance()
            initial_balance = {
                currency: balance.free for currency, balance in balances.items()
            }
            self._context = DryRunExecutionContext(self._exchange, initial_balance)
            self._logger.info("dry_run_mode_enabled")
        else:
            self._context = LiveExecutionContext(
                self._exchange,
                self._database,
                self._settings.exchange.name,
            )

        # Initialize strategy
        await self._strategy.initialize(self._context)

        # Save initial state
        await self._state_manager.save_strategy_state(self._strategy)

        # Start trading loop
        self._running = True
        self._logger.info("bot_started")
        await self._run_loop()

    async def _reconcile_state(self, state_store) -> None:
        """Reconcile strategy state with exchange on startup.

        Args:
            state_store: State persistence backend.
        """
        reconciler = StateReconciler(self._exchange, state_store)
        policy = ReconciliationPolicy()

        try:
            result = await reconciler.reconcile(self._strategy)

            if result.needs_action:
                action = policy.determine_action(result)
                self._logger.warning(
                    "state_reconciliation_needed",
                    summary=result.summary,
                    action=action,
                )
                await reconciler.apply_reconciliation(self._strategy, result, action)
            else:
                self._logger.info("state_reconciliation_clean")

        except Exception as e:
            self._logger.error("reconciliation_failed", error=str(e))
            # Continue anyway - strategy will start fresh

    async def _run_loop(self) -> None:
        """Main trading loop.

        Continuously:
        1. Fetches current price
        2. Updates strategy
        3. Checks for order fills
        4. Saves state
        """
        tick_interval = self.DEFAULT_TICK_INTERVAL

        while self._running:
            try:
                # Fetch current price
                ticker = await self._exchange.fetch_ticker(self._strategy.symbol)

                # Update strategy
                await self._strategy.on_tick(ticker)

                # Check for filled orders
                await self._check_order_fills()

                # Save state after every tick
                await self._state_manager.save_strategy_state(self._strategy)

                # Wait for next tick
                await asyncio.sleep(tick_interval)

            except asyncio.CancelledError:
                self._logger.info("trading_loop_cancelled")
                break
            except Exception as e:
                self._logger.error("trading_loop_error", error=str(e))
                # Back off on error
                await asyncio.sleep(5)

    async def _check_order_fills(self) -> None:
        """Poll for order status changes."""
        # Skip for dry-run mode - fills are simulated
        if self._settings.trading.dry_run:
            return

        try:
            open_orders = await self._exchange.fetch_open_orders(
                self._strategy.symbol
            )
            open_order_ids = {o.id for o in open_orders}

            # Check tracked orders for fills
            if hasattr(self._strategy, "_active_orders"):
                for order_id in list(self._strategy._active_orders.keys()):
                    if order_id not in open_order_ids:
                        # Order no longer open - check if filled
                        order = await self._exchange.fetch_order(
                            order_id, self._strategy.symbol
                        )
                        if order.status == OrderStatus.CLOSED:
                            await self._strategy.on_order_filled(order)
                        elif order.status == OrderStatus.CANCELED:
                            await self._strategy.on_order_cancelled(order)

        except Exception as e:
            self._logger.error("order_check_failed", error=str(e))

    async def stop(self) -> None:
        """Gracefully stop the bot.

        Performs:
        1. Stop trading loop
        2. Strategy shutdown
        3. Final state save
        4. Component disconnect
        """
        if not self._running:
            return

        self._logger.info("bot_stopping")
        self._running = False

        # Shutdown strategy
        try:
            await self._strategy.shutdown()
        except Exception as e:
            self._logger.error("strategy_shutdown_error", error=str(e))

        # Save final state
        if self._state_manager:
            try:
                await self._state_manager.save_strategy_state(self._strategy)
            except Exception as e:
                self._logger.error("final_state_save_error", error=str(e))

        # Disconnect components
        try:
            await self._exchange.disconnect()
        except Exception as e:
            self._logger.error("exchange_disconnect_error", error=str(e))

        try:
            await self._database.disconnect()
        except Exception as e:
            self._logger.error("database_disconnect_error", error=str(e))

        self._logger.info("bot_stopped")


class BotBuilder:
    """Builder for constructing TradingBot instances.

    Simplifies bot construction with fluent interface.

    Example:
        >>> bot = (BotBuilder()
        ...     .with_settings(settings)
        ...     .with_exchange(exchange)
        ...     .with_database(database)
        ...     .with_strategy(strategy)
        ...     .build())
    """

    def __init__(self) -> None:
        """Initialize bot builder."""
        self._settings: Optional[AppSettings] = None
        self._exchange: Optional[BaseExchange] = None
        self._database: Optional[Database] = None
        self._strategy: Optional[Strategy] = None

    def with_settings(self, settings: AppSettings) -> "BotBuilder":
        """Set application settings."""
        self._settings = settings
        return self

    def with_exchange(self, exchange: BaseExchange) -> "BotBuilder":
        """Set exchange adapter."""
        self._exchange = exchange
        return self

    def with_database(self, database: Database) -> "BotBuilder":
        """Set database connection."""
        self._database = database
        return self

    def with_strategy(self, strategy: Strategy) -> "BotBuilder":
        """Set trading strategy."""
        self._strategy = strategy
        return self

    def build(self) -> TradingBot:
        """Build and return TradingBot instance.

        Returns:
            Configured TradingBot.

        Raises:
            ValueError: If required components are missing.
        """
        if not self._settings:
            raise ValueError("Settings required")
        if not self._exchange:
            raise ValueError("Exchange required")
        if not self._database:
            raise ValueError("Database required")
        if not self._strategy:
            raise ValueError("Strategy required")

        return TradingBot(
            settings=self._settings,
            exchange=self._exchange,
            database=self._database,
            strategy=self._strategy,
        )
