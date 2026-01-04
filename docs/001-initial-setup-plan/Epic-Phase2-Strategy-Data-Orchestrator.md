# Epic: Phase 2 - Strategy Framework, Data Persistence & Bot Orchestrator

**Epic Owner:** Development Team
**Priority:** Critical - Core functionality
**Dependencies:** Phase 1 (Foundation & Exchange Integration)

---

## Overview

Phase 2 builds the core trading functionality: a pluggable strategy framework with grid trading implementation, persistent data storage using SQLAlchemy 2.0 async, and the main bot orchestrator that coordinates all components.

### Key Deliverables
- Strategy Protocol/interface for pluggable strategies
- Grid trading strategy with arithmetic and geometric spacing
- SQLAlchemy 2.0 async models for trades, orders, and state
- OHLCV caching system
- Bot orchestrator managing the trading loop
- State persistence and recovery after restarts

### Research & Best Practices Applied

Based on current 2025 best practices:
- **Strategy Pattern:** Python Protocol (PEP 544) for duck-typed interfaces
- **Grid Trading:** [Geometric spacing for volatile assets](https://zignaly.com/crypto-trading/algorithmic-strategies/grid-trading), 20-25 grids recommended
- **Database:** [SQLAlchemy 2.0 async patterns](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) with `expire_on_commit=False`
- **State Management:** Event-sourced approach for recovery

---

## Story 2.1: Define Strategy Protocol Interface

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a strategy interface using Python Protocol
**So that** strategies can be plugged in without requiring inheritance

### Background
Python's [Protocol (PEP 544)](https://peps.python.org/pep-0544/) enables structural subtyping (duck typing with type hints). This allows third-party strategies to integrate without modifying base classes.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/strategies/base_strategy.py`
- [ ] Define `Strategy` Protocol:
  ```python
  from typing import Protocol, Optional, Any
  from decimal import Decimal
  from crypto_bot.exchange.base_exchange import Ticker, Order, BaseExchange

  class ExecutionContext(Protocol):
      """Abstraction over live/backtest execution."""

      async def get_current_price(self, symbol: str) -> Decimal:
          """Get current market price."""
          ...

      async def place_order(
          self,
          symbol: str,
          side: str,
          amount: Decimal,
          price: Optional[Decimal] = None
      ) -> str:
          """Place order, return order ID."""
          ...

      async def cancel_order(self, order_id: str, symbol: str) -> bool:
          """Cancel order, return success."""
          ...

      async def get_balance(self, currency: str) -> Decimal:
          """Get available balance for currency."""
          ...


  class Strategy(Protocol):
      """Protocol defining strategy interface."""

      @property
      def name(self) -> str:
          """Strategy identifier."""
          ...

      @property
      def symbol(self) -> str:
          """Trading pair symbol."""
          ...

      async def initialize(self, context: ExecutionContext) -> None:
          """Initialize strategy with execution context."""
          ...

      async def on_tick(self, ticker: Ticker) -> None:
          """Handle price update."""
          ...

      async def on_order_filled(self, order: Order) -> None:
          """Handle order fill notification."""
          ...

      async def on_order_cancelled(self, order: Order) -> None:
          """Handle order cancellation."""
          ...

      def get_state(self) -> dict[str, Any]:
          """Serialize strategy state for persistence."""
          ...

      @classmethod
      def from_state(cls, state: dict[str, Any], context: ExecutionContext) -> "Strategy":
          """Restore strategy from persisted state."""
          ...

      async def shutdown(self) -> None:
          """Clean up resources, cancel open orders if needed."""
          ...
  ```
- [ ] Define `StrategyConfig` base model:
  ```python
  from pydantic import BaseModel, Field

  class StrategyConfig(BaseModel):
      """Base configuration for all strategies."""
      name: str
      symbol: str
      enabled: bool = True
      dry_run: bool = False
  ```
- [ ] Create `StrategyFactory` for instantiation:
  ```python
  class StrategyFactory:
      _registry: dict[str, type[Strategy]] = {}

      @classmethod
      def register(cls, name: str, strategy_class: type[Strategy]) -> None:
          cls._registry[name] = strategy_class

      @classmethod
      def create(cls, config: StrategyConfig, context: ExecutionContext) -> Strategy:
          if config.name not in cls._registry:
              raise ValueError(f"Unknown strategy: {config.name}")
          return cls._registry[config.name](config, context)
  ```
- [ ] Document strategy lifecycle (init -> tick -> fill -> shutdown)
- [ ] Write protocol compliance tests

### Technical Notes
- Protocol allows duck typing - any class with matching methods works
- Use `@runtime_checkable` decorator for isinstance() checks
- StrategyFactory enables configuration-driven strategy selection

### Definition of Done
- Protocol defined with full type hints
- ExecutionContext Protocol defined
- StrategyFactory implemented
- Documentation explains lifecycle
- Tests verify protocol compliance

---

## Story 2.2: Implement Grid Configuration and Level Calculator

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** grid level calculation supporting arithmetic and geometric spacing
**So that** grids can be configured appropriately for different market conditions

### Background
Per [grid trading best practices](https://zignaly.com/crypto-trading/algorithmic-strategies/grid-trading):
- **Arithmetic spacing:** Equal dollar intervals - best for stable pairs
- **Geometric spacing:** Equal percentage intervals - best for volatile assets like BTC
- Recommended: 20-25 grids for standard setups

### Acceptance Criteria

- [ ] Create grid configuration model:
  ```python
  from pydantic import BaseModel, Field, field_validator
  from decimal import Decimal
  from enum import Enum

  class GridSpacing(str, Enum):
      ARITHMETIC = "arithmetic"
      GEOMETRIC = "geometric"

  class GridConfig(BaseModel):
      """Configuration for grid trading strategy."""
      symbol: str
      lower_price: Decimal = Field(gt=0)
      upper_price: Decimal = Field(gt=0)
      num_grids: int = Field(ge=3, le=100, default=20)
      total_investment: Decimal = Field(gt=0)
      spacing: GridSpacing = GridSpacing.GEOMETRIC
      # Risk settings
      stop_loss_pct: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
      take_profit_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)

      @field_validator("upper_price")
      @classmethod
      def upper_must_exceed_lower(cls, v, info):
          if "lower_price" in info.data and v <= info.data["lower_price"]:
              raise ValueError("upper_price must be greater than lower_price")
          return v

      @property
      def grid_range_pct(self) -> Decimal:
          """Calculate percentage range of grid."""
          return (self.upper_price - self.lower_price) / self.lower_price
  ```
- [ ] Implement grid level calculator:
  ```python
  from dataclasses import dataclass

  @dataclass
  class GridLevel:
      """Represents a single grid level."""
      index: int
      price: Decimal
      buy_order_id: Optional[str] = None
      sell_order_id: Optional[str] = None
      filled_buy: bool = False
      filled_sell: bool = False

  def calculate_grid_levels(config: GridConfig) -> list[GridLevel]:
      """Calculate grid price levels based on spacing type."""
      levels: list[GridLevel] = []

      if config.spacing == GridSpacing.ARITHMETIC:
          # Equal dollar intervals
          step = (config.upper_price - config.lower_price) / (config.num_grids - 1)
          for i in range(config.num_grids):
              price = config.lower_price + (step * i)
              levels.append(GridLevel(index=i, price=price))
      else:
          # Equal percentage intervals (geometric)
          ratio = (config.upper_price / config.lower_price) ** (
              Decimal(1) / (config.num_grids - 1)
          )
          for i in range(config.num_grids):
              price = config.lower_price * (ratio ** i)
              levels.append(GridLevel(index=i, price=price.quantize(Decimal("0.01"))))

      return levels


  def calculate_order_size(config: GridConfig, num_active_grids: int) -> Decimal:
      """Calculate order size per grid level."""
      # Allocate investment across active grid levels
      # Reserve 20% for volatility buffer
      active_capital = config.total_investment * Decimal("0.80")
      return active_capital / num_active_grids
  ```
- [ ] Add validation helpers:
  ```python
  def validate_grid_config(config: GridConfig, current_price: Decimal) -> list[str]:
      """Validate grid config against current market."""
      warnings: list[str] = []

      if current_price < config.lower_price:
          warnings.append(f"Current price {current_price} below grid range")
      if current_price > config.upper_price:
          warnings.append(f"Current price {current_price} above grid range")
      if config.grid_range_pct > Decimal("0.5"):
          warnings.append(f"Grid range {config.grid_range_pct:.0%} is very wide")
      if config.num_grids < 10:
          warnings.append("Less than 10 grids may miss opportunities")

      return warnings
  ```
- [ ] Write comprehensive unit tests for both spacing types

### Technical Notes
- Geometric spacing is recommended for crypto due to percentage-based price movements
- 20-25 grids is the sweet spot between opportunity capture and fee efficiency
- Reserve 20% capital for volatility - don't allocate 100% to grid orders
- Stop-loss typically 5-10% below lower grid boundary

### Definition of Done
- GridConfig model validates all parameters
- Both arithmetic and geometric calculators work
- Order size calculation accounts for capital reserve
- Unit tests cover edge cases
- Validation warns about suboptimal configurations

---

## Story 2.3: Build Grid Trading Strategy Core

**Story Points:** 13
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a grid trading strategy that places and manages grid orders
**So that** the bot can profit from price oscillations within the grid range

### Acceptance Criteria

- [ ] Create `src/crypto_bot/strategies/grid_trading.py`
- [ ] Implement `GridTradingStrategy` class:
  ```python
  import structlog
  from typing import Optional, Any
  from decimal import Decimal
  from crypto_bot.strategies.base_strategy import Strategy, ExecutionContext
  from crypto_bot.exchange.base_exchange import Ticker, Order, OrderSide, OrderStatus

  logger = structlog.get_logger()

  class GridTradingStrategy:
      """Grid trading strategy implementation."""

      def __init__(self, config: GridConfig):
          self._config = config
          self._context: Optional[ExecutionContext] = None
          self._grid_levels: list[GridLevel] = []
          self._active_orders: dict[str, GridLevel] = {}  # order_id -> level
          self._total_profit: Decimal = Decimal(0)
          self._completed_cycles: int = 0

      @property
      def name(self) -> str:
          return f"grid_{self._config.symbol}"

      @property
      def symbol(self) -> str:
          return self._config.symbol

      async def initialize(self, context: ExecutionContext) -> None:
          """Initialize strategy and place initial grid orders."""
          self._context = context
          self._grid_levels = calculate_grid_levels(self._config)

          current_price = await context.get_current_price(self.symbol)
          logger.info("grid_initializing",
                      symbol=self.symbol,
                      current_price=str(current_price),
                      num_levels=len(self._grid_levels))

          # Place buy orders below current price
          await self._place_initial_orders(current_price)

      async def _place_initial_orders(self, current_price: Decimal) -> None:
          """Place buy orders for all grid levels below current price."""
          order_size = calculate_order_size(
              self._config,
              len([l for l in self._grid_levels if l.price < current_price])
          )

          for level in self._grid_levels:
              if level.price < current_price:
                  order_id = await self._context.place_order(
                      symbol=self.symbol,
                      side="buy",
                      amount=order_size,
                      price=level.price,
                  )
                  level.buy_order_id = order_id
                  self._active_orders[order_id] = level
                  logger.info("grid_order_placed",
                              side="buy",
                              level=level.index,
                              price=str(level.price))
  ```
- [ ] Implement `on_tick` for price monitoring:
  ```python
  async def on_tick(self, ticker: Ticker) -> None:
      """Monitor price and check for stop-loss."""
      stop_loss_price = self._config.lower_price * (1 - self._config.stop_loss_pct)

      if ticker.last < stop_loss_price:
          logger.warning("stop_loss_triggered",
                        current_price=str(ticker.last),
                        stop_loss=str(stop_loss_price))
          await self._execute_stop_loss()
  ```
- [ ] Implement `on_order_filled`:
  ```python
  async def on_order_filled(self, order: Order) -> None:
      """Handle order fill - place counter order."""
      if order.id not in self._active_orders:
          return

      level = self._active_orders.pop(order.id)

      if order.side == OrderSide.BUY:
          # Buy filled -> place sell at next level up
          level.filled_buy = True
          next_level = self._get_next_level_up(level)
          if next_level:
              sell_order_id = await self._context.place_order(
                  symbol=self.symbol,
                  side="sell",
                  amount=order.filled,
                  price=next_level.price,
              )
              level.sell_order_id = sell_order_id
              self._active_orders[sell_order_id] = level
              logger.info("grid_counter_order",
                          buy_price=str(level.price),
                          sell_price=str(next_level.price))

      elif order.side == OrderSide.SELL:
          # Sell filled -> record profit, place new buy
          level.filled_sell = True
          profit = self._calculate_profit(level, order)
          self._total_profit += profit
          self._completed_cycles += 1

          logger.info("grid_cycle_complete",
                      level=level.index,
                      profit=str(profit),
                      total_profit=str(self._total_profit))

          # Place new buy order at this level
          await self._place_buy_at_level(level)
  ```
- [ ] Implement profit calculation:
  ```python
  def _calculate_profit(self, level: GridLevel, sell_order: Order) -> Decimal:
      """Calculate profit from grid cycle (sell - buy - fees)."""
      buy_price = level.price
      sell_price = sell_order.price
      amount = sell_order.filled
      fee_rate = Decimal("0.001")  # 0.1% per side

      gross_profit = (sell_price - buy_price) * amount
      fees = (buy_price + sell_price) * amount * fee_rate
      return gross_profit - fees
  ```
- [ ] Implement state serialization:
  ```python
  def get_state(self) -> dict[str, Any]:
      """Serialize strategy state for persistence."""
      return {
          "config": self._config.model_dump(),
          "grid_levels": [
              {
                  "index": l.index,
                  "price": str(l.price),
                  "buy_order_id": l.buy_order_id,
                  "sell_order_id": l.sell_order_id,
                  "filled_buy": l.filled_buy,
                  "filled_sell": l.filled_sell,
              }
              for l in self._grid_levels
          ],
          "active_orders": list(self._active_orders.keys()),
          "total_profit": str(self._total_profit),
          "completed_cycles": self._completed_cycles,
      }

  @classmethod
  def from_state(cls, state: dict[str, Any], context: ExecutionContext) -> "GridTradingStrategy":
      """Restore strategy from persisted state."""
      config = GridConfig(**state["config"])
      strategy = cls(config)
      strategy._context = context
      strategy._total_profit = Decimal(state["total_profit"])
      strategy._completed_cycles = state["completed_cycles"]
      # Restore grid levels...
      return strategy
  ```
- [ ] Implement shutdown with order cancellation
- [ ] Write unit tests with mock execution context

### Technical Notes
- Grid cycles: Buy fills -> place sell above -> sell fills -> place buy again
- Track order IDs to match fills with grid levels
- Calculate profit net of fees (typically 0.1% per side)
- Stop-loss should cancel all orders and exit positions

### Definition of Done
- Grid strategy places initial orders correctly
- Buy fills trigger sell orders at correct levels
- Sell fills record profit and re-place buy orders
- State serialization/deserialization works
- Stop-loss triggers when price breaches threshold
- Unit tests verify all scenarios

---

## Story 2.4: Implement Strategy State Persistence

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** strategy state persisted to database
**So that** the bot can recover after restarts without losing position tracking

### Acceptance Criteria

- [ ] Create `src/crypto_bot/strategies/strategy_state.py`
- [ ] Define state persistence interface:
  ```python
  from typing import Protocol, Optional, Any

  class StateStore(Protocol):
      """Interface for strategy state persistence."""

      async def save_state(self, strategy_name: str, state: dict[str, Any]) -> None:
          """Persist strategy state."""
          ...

      async def load_state(self, strategy_name: str) -> Optional[dict[str, Any]]:
          """Load persisted state, None if not found."""
          ...

      async def delete_state(self, strategy_name: str) -> None:
          """Remove persisted state."""
          ...
  ```
- [ ] Implement database-backed state store:
  ```python
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy import select
  import json

  class DatabaseStateStore:
      def __init__(self, session_factory):
          self._session_factory = session_factory

      async def save_state(self, strategy_name: str, state: dict[str, Any]) -> None:
          async with self._session_factory() as session:
              # Upsert strategy state
              existing = await session.execute(
                  select(StrategyStateModel).where(
                      StrategyStateModel.name == strategy_name
                  )
              )
              record = existing.scalar_one_or_none()

              if record:
                  record.state_json = json.dumps(state, default=str)
                  record.updated_at = datetime.utcnow()
              else:
                  record = StrategyStateModel(
                      name=strategy_name,
                      state_json=json.dumps(state, default=str),
                  )
                  session.add(record)

              await session.commit()
  ```
- [ ] Implement state versioning for migrations:
  ```python
  STATE_VERSION = 1

  def migrate_state(state: dict[str, Any]) -> dict[str, Any]:
      """Migrate state from older versions."""
      version = state.get("version", 0)
      if version < STATE_VERSION:
          # Apply migrations
          state = _migrate_v0_to_v1(state)
      state["version"] = STATE_VERSION
      return state
  ```
- [ ] Add auto-save on every order event
- [ ] Write tests for save/load cycle

### Technical Notes
- Save state after every order placement/fill for crash recovery
- Use JSON serialization with custom encoder for Decimal
- Version state to handle schema changes
- Consider event sourcing for complete audit trail

### Definition of Done
- State saves to database on every order event
- State loads correctly on restart
- State versioning handles schema changes
- Tests verify persistence round-trip

---

## Story 2.5: Build State Reconciliation on Startup

**Story Points:** 8
**Priority:** P1 - High

### Description
**As a** developer
**I want** startup reconciliation between local state and exchange
**So that** orphan orders are handled and the strategy state matches reality

### Acceptance Criteria

- [ ] Create reconciliation logic:
  ```python
  class StateReconciler:
      def __init__(self, exchange: BaseExchange, state_store: StateStore):
          self._exchange = exchange
          self._state_store = state_store

      async def reconcile(self, strategy: Strategy) -> ReconciliationResult:
          """Reconcile strategy state with exchange reality."""
          result = ReconciliationResult()

          # Load persisted state
          persisted = await self._state_store.load_state(strategy.name)
          if not persisted:
              logger.info("no_persisted_state", strategy=strategy.name)
              return result

          # Get actual open orders from exchange
          exchange_orders = await self._exchange.fetch_open_orders(strategy.symbol)
          exchange_order_ids = {o.id for o in exchange_orders}

          # Get order IDs from persisted state
          persisted_order_ids = set(persisted.get("active_orders", []))

          # Find orphan orders (on exchange but not tracked)
          orphans = exchange_order_ids - persisted_order_ids
          for order_id in orphans:
              logger.warning("orphan_order_found", order_id=order_id)
              result.orphan_orders.append(order_id)

          # Find phantom orders (tracked but not on exchange)
          phantoms = persisted_order_ids - exchange_order_ids
          for order_id in phantoms:
              logger.warning("phantom_order_found", order_id=order_id)
              result.phantom_orders.append(order_id)

          return result


  @dataclass
  class ReconciliationResult:
      orphan_orders: list[str] = field(default_factory=list)
      phantom_orders: list[str] = field(default_factory=list)
      orders_to_replace: list[str] = field(default_factory=list)

      @property
      def needs_action(self) -> bool:
          return bool(self.orphan_orders or self.phantom_orders)
  ```
- [ ] Implement reconciliation actions:
  ```python
  async def apply_reconciliation(
      self,
      strategy: GridTradingStrategy,
      result: ReconciliationResult,
      action: str = "prompt"  # "prompt", "auto_fix", "abort"
  ) -> None:
      """Apply reconciliation actions."""
      if action == "abort" and result.needs_action:
          raise ReconciliationError("State mismatch detected, aborting")

      if action == "auto_fix":
          # Cancel orphan orders
          for order_id in result.orphan_orders:
              await self._exchange.cancel_order(order_id, strategy.symbol)
              logger.info("cancelled_orphan", order_id=order_id)

          # Remove phantom orders from state
          for order_id in result.phantom_orders:
              strategy.remove_order_from_state(order_id)
              logger.info("removed_phantom", order_id=order_id)
  ```
- [ ] Add startup reconciliation to bot orchestrator
- [ ] Send alerts on significant state mismatch
- [ ] Write tests for reconciliation scenarios

### Technical Notes
- Orphan orders: exist on exchange but not in our state (maybe placed manually)
- Phantom orders: in our state but not on exchange (filled/cancelled while bot was down)
- Always reconcile before resuming trading
- Consider human review for large mismatches

### Definition of Done
- Reconciliation detects orphan and phantom orders
- Auto-fix mode cancels orphans and removes phantoms
- Alerts sent on significant mismatch
- Tests cover all reconciliation scenarios

---

## Story 2.6: Define SQLAlchemy ORM Models

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** database models for trades, orders, and strategy state
**So that** trading data is persisted and queryable

### Background
[SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) provides async support with improved type hints. Use `mapped_column` for better IDE support.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/data/models.py`
- [ ] Define base model with common fields:
  ```python
  from datetime import datetime
  from sqlalchemy import DateTime, func
  from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

  class Base(DeclarativeBase):
      pass

  class TimestampMixin:
      created_at: Mapped[datetime] = mapped_column(
          DateTime, default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime, default=func.now(), onupdate=func.now(), nullable=False
      )
  ```
- [ ] Define Trade model:
  ```python
  from decimal import Decimal
  from sqlalchemy import String, Numeric, Boolean, ForeignKey
  from sqlalchemy.orm import relationship

  class Trade(Base, TimestampMixin):
      __tablename__ = "trades"

      id: Mapped[int] = mapped_column(primary_key=True)
      exchange: Mapped[str] = mapped_column(String(50), nullable=False)
      symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
      strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

      is_open: Mapped[bool] = mapped_column(Boolean, default=True)
      side: Mapped[str] = mapped_column(String(10), nullable=False)

      open_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
      close_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
      amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

      open_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
      close_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

      stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
      take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))

      profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
      profit_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
      fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))

      orders: Mapped[list["Order"]] = relationship(back_populates="trade")
  ```
- [ ] Define Order model:
  ```python
  class Order(Base, TimestampMixin):
      __tablename__ = "orders"

      id: Mapped[int] = mapped_column(primary_key=True)
      order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
      trade_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trades.id"))

      exchange: Mapped[str] = mapped_column(String(50), nullable=False)
      symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
      side: Mapped[str] = mapped_column(String(10), nullable=False)
      order_type: Mapped[str] = mapped_column(String(20), nullable=False)
      status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

      price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
      amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
      filled: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
      remaining: Mapped[Decimal] = mapped_column(Numeric(20, 8))
      cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))
      fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8))

      trade: Mapped[Optional["Trade"]] = relationship(back_populates="orders")
  ```
- [ ] Define StrategyState model:
  ```python
  class StrategyState(Base, TimestampMixin):
      __tablename__ = "strategy_states"

      id: Mapped[int] = mapped_column(primary_key=True)
      name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
      state_json: Mapped[str] = mapped_column(Text, nullable=False)
      version: Mapped[int] = mapped_column(default=1)
  ```
- [ ] Define BalanceSnapshot model for equity tracking:
  ```python
  class BalanceSnapshot(Base):
      __tablename__ = "balance_snapshots"

      id: Mapped[int] = mapped_column(primary_key=True)
      timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
      exchange: Mapped[str] = mapped_column(String(50), nullable=False)
      currency: Mapped[str] = mapped_column(String(20), nullable=False)
      total: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
      free: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
      used: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
  ```
- [ ] Add appropriate indexes for query performance
- [ ] Create Alembic migration setup

### Technical Notes
- Use `Numeric(20, 8)` for crypto amounts (8 decimal places)
- Index frequently queried columns (symbol, strategy, status)
- `expire_on_commit=False` in session for async access after commit
- Consider partitioning large tables by date

### Definition of Done
- All models defined with proper types
- Relationships configured correctly
- Indexes added for query performance
- Alembic configured for migrations
- Models can be imported without errors

---

## Story 2.7: Implement Async Database Session Management

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** proper async database session lifecycle management
**So that** connections are handled correctly in the async context

### Background
Per [SQLAlchemy 2.0 async best practices](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), create a single engine and sessionmaker, then hand sessions to request scopes.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/data/persistence.py`
- [ ] Implement database engine factory:
  ```python
  from sqlalchemy.ext.asyncio import (
      AsyncEngine,
      AsyncSession,
      async_sessionmaker,
      create_async_engine,
  )
  from crypto_bot.config.settings import DatabaseSettings

  class Database:
      def __init__(self, settings: DatabaseSettings):
          self._settings = settings
          self._engine: Optional[AsyncEngine] = None
          self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

      async def connect(self) -> None:
          """Initialize database connection."""
          self._engine = create_async_engine(
              self._settings.url,
              echo=self._settings.echo,
              pool_size=self._settings.pool_size,
              pool_pre_ping=True,  # Verify connections are alive
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

          logger.info("database_connected", url=self._settings.url)

      async def disconnect(self) -> None:
          """Close database connection."""
          if self._engine:
              await self._engine.dispose()
              self._engine = None
              logger.info("database_disconnected")

      @asynccontextmanager
      async def session(self) -> AsyncGenerator[AsyncSession, None]:
          """Provide a transactional session scope."""
          if not self._session_factory:
              raise RuntimeError("Database not connected")

          session = self._session_factory()
          try:
              yield session
              await session.commit()
          except Exception:
              await session.rollback()
              raise
          finally:
              await session.close()
  ```
- [ ] Support SQLite for development:
  ```python
  # SQLite async requires aiosqlite
  # URL: sqlite+aiosqlite:///./trading.db
  ```
- [ ] Support PostgreSQL for production:
  ```python
  # PostgreSQL async requires asyncpg
  # URL: postgresql+asyncpg://user:pass@host/db
  ```
- [ ] Add connection health check:
  ```python
  async def health_check(self) -> bool:
      """Verify database connection is healthy."""
      try:
          async with self.session() as session:
              await session.execute(text("SELECT 1"))
          return True
      except Exception as e:
          logger.error("database_health_check_failed", error=str(e))
          return False
  ```
- [ ] Write tests for session lifecycle

### Technical Notes
- `expire_on_commit=False` is crucial for async - allows attribute access after commit
- `pool_pre_ping=True` handles stale connections
- Single engine per service, sessions per request/operation
- SQLite doesn't support concurrent writes - use PostgreSQL for production

### Definition of Done
- Database class manages connection lifecycle
- Session context manager handles transactions
- SQLite and PostgreSQL both work
- Health check verifies connectivity
- Tests verify session behavior

---

## Story 2.8: Build Trade and Order Repositories

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** developer
**I want** repositories for trade and order CRUD operations
**So that** data access is encapsulated and testable

### Acceptance Criteria

- [ ] Create `src/crypto_bot/data/repositories.py`
- [ ] Implement TradeRepository:
  ```python
  from sqlalchemy import select, and_
  from sqlalchemy.ext.asyncio import AsyncSession

  class TradeRepository:
      def __init__(self, session: AsyncSession):
          self._session = session

      async def create(self, trade: Trade) -> Trade:
          """Create new trade record."""
          self._session.add(trade)
          await self._session.flush()
          return trade

      async def get_by_id(self, trade_id: int) -> Optional[Trade]:
          """Get trade by ID."""
          result = await self._session.execute(
              select(Trade).where(Trade.id == trade_id)
          )
          return result.scalar_one_or_none()

      async def get_open_trades(
          self,
          symbol: Optional[str] = None,
          strategy: Optional[str] = None,
      ) -> list[Trade]:
          """Get all open trades with optional filters."""
          query = select(Trade).where(Trade.is_open == True)
          if symbol:
              query = query.where(Trade.symbol == symbol)
          if strategy:
              query = query.where(Trade.strategy == strategy)
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
          """Close an open trade."""
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
          """Get historical trades with filters."""
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
          """Calculate trading statistics for a strategy."""
          trades = await self.get_trade_history(strategy=strategy, limit=1000)
          if not trades:
              return {}

          wins = [t for t in trades if t.profit and t.profit > 0]
          losses = [t for t in trades if t.profit and t.profit < 0]

          return {
              "total_trades": len(trades),
              "win_rate": len(wins) / len(trades) if trades else 0,
              "total_profit": sum(t.profit for t in trades if t.profit),
              "avg_profit": sum(t.profit for t in trades if t.profit) / len(trades),
              "max_win": max((t.profit for t in wins), default=0),
              "max_loss": min((t.profit for t in losses), default=0),
          }
  ```
- [ ] Implement OrderRepository:
  ```python
  class OrderRepository:
      def __init__(self, session: AsyncSession):
          self._session = session

      async def create(self, order: Order) -> Order:
          """Create new order record."""
          self._session.add(order)
          await self._session.flush()
          return order

      async def get_by_order_id(self, order_id: str) -> Optional[Order]:
          """Get order by exchange order ID."""
          result = await self._session.execute(
              select(Order).where(Order.order_id == order_id)
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
          """Update order status after fill/cancel."""
          order = await self.get_by_order_id(order_id)
          if not order:
              raise ValueError(f"Order {order_id} not found")

          order.status = status
          order.filled = filled
          order.remaining = order.amount - filled
          if cost:
              order.cost = cost
          if fee:
              order.fee = fee
          return order

      async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
          """Get all open orders."""
          query = select(Order).where(Order.status == "open")
          if symbol:
              query = query.where(Order.symbol == symbol)
          result = await self._session.execute(query)
          return list(result.scalars().all())
  ```
- [ ] Write unit tests with in-memory SQLite

### Definition of Done
- TradeRepository with CRUD + statistics
- OrderRepository with CRUD + status updates
- All methods have proper error handling
- Unit tests pass with in-memory database

---

## Story 2.9: Implement OHLCV Data Cache

**Story Points:** 5
**Priority:** P2 - Medium

### Description
**As a** developer
**I want** multi-layer OHLCV caching
**So that** historical data queries are fast and don't hit rate limits

### Acceptance Criteria

- [ ] Create `src/crypto_bot/data/ohlcv_cache.py`
- [ ] Implement multi-layer cache:
  ```python
  from functools import lru_cache
  from pathlib import Path
  import pandas as pd

  class OHLCVCache:
      def __init__(
          self,
          cache_dir: Path = Path("./data/ohlcv_cache"),
          memory_cache_size: int = 100,
      ):
          self._cache_dir = cache_dir
          self._cache_dir.mkdir(parents=True, exist_ok=True)
          self._memory_cache: dict[str, pd.DataFrame] = {}
          self._memory_cache_size = memory_cache_size

      def _cache_key(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> str:
          """Generate cache key."""
          return f"{symbol}_{timeframe}_{start.date()}_{end.date()}"

      async def get(
          self,
          symbol: str,
          timeframe: str,
          start: datetime,
          end: datetime,
      ) -> Optional[pd.DataFrame]:
          """Get cached OHLCV data."""
          key = self._cache_key(symbol, timeframe, start, end)

          # Check memory cache first
          if key in self._memory_cache:
              logger.debug("ohlcv_cache_hit", layer="memory", key=key)
              return self._memory_cache[key]

          # Check disk cache
          cache_file = self._cache_dir / f"{key}.parquet"
          if cache_file.exists():
              df = pd.read_parquet(cache_file)
              self._add_to_memory_cache(key, df)
              logger.debug("ohlcv_cache_hit", layer="disk", key=key)
              return df

          return None

      async def put(
          self,
          symbol: str,
          timeframe: str,
          start: datetime,
          end: datetime,
          data: pd.DataFrame,
      ) -> None:
          """Cache OHLCV data."""
          key = self._cache_key(symbol, timeframe, start, end)

          # Save to disk
          cache_file = self._cache_dir / f"{key}.parquet"
          data.to_parquet(cache_file)

          # Add to memory cache
          self._add_to_memory_cache(key, data)
          logger.debug("ohlcv_cached", key=key, rows=len(data))

      def _add_to_memory_cache(self, key: str, data: pd.DataFrame) -> None:
          """Add to memory cache with LRU eviction."""
          if len(self._memory_cache) >= self._memory_cache_size:
              # Remove oldest entry
              oldest = next(iter(self._memory_cache))
              del self._memory_cache[oldest]
          self._memory_cache[key] = data

      def clear(self) -> None:
          """Clear all caches."""
          self._memory_cache.clear()
          for f in self._cache_dir.glob("*.parquet"):
              f.unlink()
  ```
- [ ] Implement cache-aware data fetcher:
  ```python
  class OHLCVFetcher:
      def __init__(self, exchange: BaseExchange, cache: OHLCVCache):
          self._exchange = exchange
          self._cache = cache

      async def fetch(
          self,
          symbol: str,
          timeframe: str,
          start: datetime,
          end: datetime,
      ) -> pd.DataFrame:
          """Fetch OHLCV data with caching."""
          # Try cache first
          cached = await self._cache.get(symbol, timeframe, start, end)
          if cached is not None:
              return cached

          # Fetch from exchange
          logger.info("fetching_ohlcv", symbol=symbol, timeframe=timeframe)
          ohlcv = await self._exchange.fetch_ohlcv(
              symbol, timeframe, since=int(start.timestamp() * 1000)
          )

          df = pd.DataFrame(
              ohlcv,
              columns=["timestamp", "open", "high", "low", "close", "volume"]
          )
          df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
          df = df.set_index("timestamp")

          # Cache result
          await self._cache.put(symbol, timeframe, start, end, df)
          return df
  ```
- [ ] Write tests for cache hit/miss scenarios

### Technical Notes
- Parquet format is efficient for time-series data
- Memory cache reduces disk I/O for hot data
- Cache reduces API calls by 90%+ for repeated queries
- Consider cache invalidation for recent data

### Definition of Done
- Multi-layer cache (memory + disk) working
- Cache-aware fetcher falls back to exchange
- Parquet files stored efficiently
- Tests verify cache behavior

---

## Story 2.10: Create Bot Orchestrator

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a central orchestrator managing bot lifecycle
**So that** all components work together correctly

### Acceptance Criteria

- [ ] Create `src/crypto_bot/bot.py`
- [ ] Implement Bot orchestrator:
  ```python
  import asyncio
  import signal
  from typing import Optional

  class TradingBot:
      def __init__(
          self,
          settings: AppSettings,
          exchange: BaseExchange,
          database: Database,
          strategy: Strategy,
      ):
          self._settings = settings
          self._exchange = exchange
          self._database = database
          self._strategy = strategy
          self._running = False
          self._shutdown_event = asyncio.Event()

      async def start(self) -> None:
          """Initialize and start the bot."""
          logger.info("bot_starting", strategy=self._strategy.name)

          # Connect components
          await self._exchange.connect()
          await self._database.connect()

          # Load/reconcile state
          state_store = DatabaseStateStore(self._database.session)
          reconciler = StateReconciler(self._exchange, state_store)
          result = await reconciler.reconcile(self._strategy)

          if result.needs_action:
              logger.warning("state_reconciliation_needed",
                            orphans=len(result.orphan_orders),
                            phantoms=len(result.phantom_orders))
              await reconciler.apply_reconciliation(self._strategy, result, "auto_fix")

          # Initialize strategy
          context = LiveExecutionContext(self._exchange, self._database)
          await self._strategy.initialize(context)

          # Start trading loop
          self._running = True
          await self._run_loop()

      async def _run_loop(self) -> None:
          """Main trading loop."""
          tick_interval = 1.0  # seconds

          while self._running:
              try:
                  # Fetch current price
                  ticker = await self._exchange.fetch_ticker(self._strategy.symbol)

                  # Update strategy
                  await self._strategy.on_tick(ticker)

                  # Check for filled orders
                  await self._check_order_fills()

                  # Save state
                  await self._save_state()

                  # Wait for next tick
                  await asyncio.sleep(tick_interval)

              except asyncio.CancelledError:
                  break
              except Exception as e:
                  logger.error("trading_loop_error", error=str(e))
                  await asyncio.sleep(5)  # Back off on error

      async def _check_order_fills(self) -> None:
          """Poll for order status changes."""
          open_orders = await self._exchange.fetch_open_orders(self._strategy.symbol)
          open_order_ids = {o.id for o in open_orders}

          # Find orders that were filled (no longer open)
          for order_id in list(self._strategy._active_orders.keys()):
              if order_id not in open_order_ids:
                  order = await self._exchange.fetch_order(
                      order_id, self._strategy.symbol
                  )
                  if order.status == OrderStatus.CLOSED:
                      await self._strategy.on_order_filled(order)

      async def stop(self) -> None:
          """Gracefully stop the bot."""
          logger.info("bot_stopping")
          self._running = False

          # Shutdown strategy
          await self._strategy.shutdown()

          # Disconnect components
          await self._exchange.disconnect()
          await self._database.disconnect()

          logger.info("bot_stopped")

      def setup_signal_handlers(self) -> None:
          """Setup OS signal handlers for graceful shutdown."""
          loop = asyncio.get_event_loop()

          for sig in (signal.SIGINT, signal.SIGTERM):
              loop.add_signal_handler(
                  sig,
                  lambda: asyncio.create_task(self.stop())
              )
  ```
- [ ] Implement LiveExecutionContext:
  ```python
  class LiveExecutionContext:
      """Execution context for live trading."""

      def __init__(self, exchange: BaseExchange, database: Database):
          self._exchange = exchange
          self._database = database

      async def get_current_price(self, symbol: str) -> Decimal:
          ticker = await self._exchange.fetch_ticker(symbol)
          return ticker.last

      async def place_order(
          self,
          symbol: str,
          side: str,
          amount: Decimal,
          price: Optional[Decimal] = None,
      ) -> str:
          order_type = OrderType.LIMIT if price else OrderType.MARKET
          order = await self._exchange.create_order(
              symbol=symbol,
              order_type=order_type,
              side=OrderSide(side),
              amount=amount,
              price=price,
          )

          # Persist order
          async with self._database.session() as session:
              repo = OrderRepository(session)
              await repo.create(Order(
                  order_id=order.id,
                  symbol=symbol,
                  side=side,
                  order_type=order_type.value,
                  status=order.status.value,
                  price=price,
                  amount=amount,
                  filled=order.filled,
                  remaining=order.remaining,
              ))

          return order.id

      async def cancel_order(self, order_id: str, symbol: str) -> bool:
          try:
              await self._exchange.cancel_order(order_id, symbol)
              return True
          except OrderNotFoundError:
              return False

      async def get_balance(self, currency: str) -> Decimal:
          balances = await self._exchange.fetch_balance()
          return balances.get(currency, Balance(currency, 0, 0, 0)).free
  ```
- [ ] Add graceful shutdown handling
- [ ] Write integration tests

### Definition of Done
- Bot orchestrates all components correctly
- Startup reconciles state with exchange
- Trading loop polls prices and checks fills
- Graceful shutdown cancels orders if configured
- Signal handlers work for SIGINT/SIGTERM

---

## Story 2.11: Implement Dry-Run Mode

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** developer
**I want** a dry-run mode that simulates trading
**So that** strategies can be tested safely without real money

### Acceptance Criteria

- [ ] Create `DryRunExecutionContext`:
  ```python
  class DryRunExecutionContext:
      """Simulated execution context for testing."""

      def __init__(self, exchange: BaseExchange, initial_balance: dict[str, Decimal]):
          self._exchange = exchange
          self._balance = initial_balance.copy()
          self._orders: dict[str, Order] = {}
          self._order_counter = 0

      async def get_current_price(self, symbol: str) -> Decimal:
          ticker = await self._exchange.fetch_ticker(symbol)
          return ticker.last

      async def place_order(
          self,
          symbol: str,
          side: str,
          amount: Decimal,
          price: Optional[Decimal] = None,
      ) -> str:
          self._order_counter += 1
          order_id = f"DRY_{self._order_counter}"

          logger.info("dry_run_order",
                      order_id=order_id,
                      symbol=symbol,
                      side=side,
                      amount=str(amount),
                      price=str(price))

          # Simulate order
          self._orders[order_id] = {
              "id": order_id,
              "symbol": symbol,
              "side": side,
              "amount": amount,
              "price": price,
              "status": "open",
          }

          return order_id

      async def cancel_order(self, order_id: str, symbol: str) -> bool:
          if order_id in self._orders:
              self._orders[order_id]["status"] = "canceled"
              logger.info("dry_run_cancel", order_id=order_id)
              return True
          return False
  ```
- [ ] Add `dry_run` configuration flag
- [ ] Clearly label all logs as DRY-RUN
- [ ] Track simulated balance changes
- [ ] Support switching between dry-run and live

### Definition of Done
- Dry-run mode simulates all order operations
- Logs clearly indicate DRY-RUN mode
- Balance tracking works in simulation
- Can switch to live without code changes

---

## Story 2.12: Create CLI Interface

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** user
**I want** a command-line interface for bot control
**So that** I can start, stop, and monitor the bot easily

### Acceptance Criteria

- [ ] Update `src/crypto_bot/main.py`:
  ```python
  import argparse
  import asyncio
  import sys

  def parse_args() -> argparse.Namespace:
      parser = argparse.ArgumentParser(
          description="Crypto Trading Bot",
          formatter_class=argparse.RawDescriptionHelpFormatter,
      )
      parser.add_argument(
          "--config", "-c",
          type=str,
          default="config/config.yaml",
          help="Path to configuration file",
      )
      parser.add_argument(
          "--dry-run",
          action="store_true",
          help="Run in simulation mode without real trades",
      )
      parser.add_argument(
          "--log-level",
          choices=["DEBUG", "INFO", "WARNING", "ERROR"],
          default="INFO",
          help="Logging verbosity level",
      )
      parser.add_argument(
          "--version",
          action="version",
          version="%(prog)s 0.1.0",
      )
      return parser.parse_args()


  def display_banner(settings: AppSettings) -> None:
      """Display startup banner with config summary."""
      banner = """
  ╔═══════════════════════════════════════════════════════════╗
  ║           CRYPTO TRADING BOT v0.1.0                       ║
  ╚═══════════════════════════════════════════════════════════╝
      """
      print(banner)
      print(f"  Exchange:  {settings.exchange.name}")
      print(f"  Testnet:   {settings.exchange.testnet}")
      print(f"  Dry Run:   {settings.trading.dry_run}")
      print(f"  Symbol:    {settings.trading.symbol}")
      print()


  async def main() -> int:
      args = parse_args()
      settings = get_settings()

      # Override from CLI args
      if args.dry_run:
          settings.trading.dry_run = True

      configure_logging(args.log_level)
      display_banner(settings)

      # Build components
      exchange = BinanceAdapter(settings.exchange)
      database = Database(settings.database)
      strategy = GridTradingStrategy(GridConfig(...))

      bot = TradingBot(settings, exchange, database, strategy)
      bot.setup_signal_handlers()

      try:
          await bot.start()
          return 0
      except KeyboardInterrupt:
          await bot.stop()
          return 0
      except Exception as e:
          logger.exception("bot_crashed", error=str(e))
          return 1


  def cli() -> None:
      sys.exit(asyncio.run(main()))


  if __name__ == "__main__":
      cli()
  ```
- [ ] Add entry point to `pyproject.toml`
- [ ] Display startup banner with config summary
- [ ] Return appropriate exit codes
- [ ] Handle keyboard interrupt gracefully

### Definition of Done
- `crypto-bot` command works after install
- `--help` shows all options
- `--dry-run` enables simulation mode
- Startup banner shows configuration
- Exit codes indicate success/failure

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 2.1 Define Strategy Protocol | 5 | P0 | Phase 1 |
| 2.2 Grid Level Calculator | 5 | P0 | 2.1 |
| 2.3 Grid Trading Strategy Core | 13 | P0 | 2.2 |
| 2.4 Strategy State Persistence | 5 | P0 | 2.3, 2.6 |
| 2.5 State Reconciliation | 8 | P1 | 2.4 |
| 2.6 SQLAlchemy ORM Models | 5 | P0 | Phase 1 |
| 2.7 Async Database Sessions | 5 | P0 | 2.6 |
| 2.8 Trade/Order Repositories | 5 | P1 | 2.7 |
| 2.9 OHLCV Data Cache | 5 | P2 | 2.7 |
| 2.10 Bot Orchestrator | 8 | P0 | 2.3, 2.7 |
| 2.11 Dry-Run Mode | 3 | P1 | 2.10 |
| 2.12 CLI Interface | 3 | P1 | 2.10 |
| **Total** | **70** | | |

---

## Sources & References

- [Grid Trading Strategy Guide 2025](https://zignaly.com/crypto-trading/algorithmic-strategies/grid-trading)
- [Best Grid Bot Settings](https://wundertrading.com/journal/en/learn/article/best-grid-bot-settings)
- [Grid Bot Guide 2025](https://coinrule.com/blog/trading-tips/grid-bot-guide-2025-to-master-automated-crypto-trading/)
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [10 SQLAlchemy 2.0 Patterns](https://medium.com/@ThinkingLoop/10-sqlalchemy-2-0-patterns-for-clean-async-postgres-af8c4bcd86fe)
- [AsyncAlgoTrading Framework](https://github.com/AsyncAlgoTrading/aat)
- [Python Protocol PEP 544](https://peps.python.org/pep-0544/)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
