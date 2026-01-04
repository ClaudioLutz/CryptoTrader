# Epic: Phase 4B - Testing & Quality Assurance

**Epic Owner:** Development Team
**Priority:** High - Production readiness
**Dependencies:** All previous phases

---

## Overview

Comprehensive testing ensures the trading bot operates reliably and correctly. This epic implements unit tests with mocked exchange, integration tests against testnets, and CI/CD pipeline for automated quality checks.

### Key Deliverables
- Mock exchange for deterministic unit testing
- Unit tests for all core components (>90% coverage)
- Integration tests against Binance testnet
- CI/CD pipeline with automated testing
- Code quality checks (linting, type checking)

### Research & Best Practices Applied

Based on current 2025 best practices:
- **Async Testing:** [pytest-asyncio](https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/) for async test functions
- **Mocking:** [AsyncMock](https://docs.python.org/3/library/unittest.mock.html) for async function mocking
- **Fixtures:** [Hierarchical fixture scoping](https://www.glukhov.org/post/2025/10/unit-testing-in-python/) for resource optimization
- **Enterprise Patterns:** [Centralized configuration](https://www.johal.in/python-testing-frameworks-pytest-advanced-features-and-mocking-strategies-for-unit-tests-2025/) with conftest.py

---

## Story 4.7: Create Mock Exchange for Testing

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a mock exchange simulating order execution
**So that** tests run fast and deterministically without network calls

### Background
Per [async testing best practices](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html), mocking external services enables fast, reliable tests that don't depend on external systems.

### Acceptance Criteria

- [ ] Create `tests/fixtures/mock_exchange.py`
- [ ] Implement MockExchange:
  ```python
  from decimal import Decimal
  from datetime import datetime
  from typing import Optional
  from unittest.mock import AsyncMock
  from crypto_bot.exchange.base_exchange import (
      BaseExchange, Ticker, Balance, Order,
      OrderSide, OrderType, OrderStatus,
  )

  class MockExchange(BaseExchange):
      """Mock exchange for unit testing."""

      def __init__(
          self,
          initial_balance: Optional[dict[str, Decimal]] = None,
          ticker_data: Optional[dict[str, Decimal]] = None,
      ):
          self._balance = initial_balance or {"USDT": Decimal("10000")}
          self._ticker_data = ticker_data or {"BTC/USDT": Decimal("42000")}
          self._orders: dict[str, Order] = {}
          self._order_counter = 0
          self._positions: dict[str, Decimal] = {}

          # Track method calls for assertions
          self.create_order_calls: list[dict] = []
          self.cancel_order_calls: list[dict] = []

          # Configurable behaviors
          self.should_fail_orders = False
          self.order_fill_delay = 0  # Bars until fill
          self.slippage_rate = Decimal("0")

      async def connect(self) -> None:
          """No-op for mock."""
          pass

      async def disconnect(self) -> None:
          """No-op for mock."""
          pass

      async def fetch_ticker(self, symbol: str) -> Ticker:
          """Return configured ticker data."""
          price = self._ticker_data.get(symbol, Decimal("100"))
          return Ticker(
              symbol=symbol,
              bid=price * Decimal("0.9999"),
              ask=price * Decimal("1.0001"),
              last=price,
              timestamp=datetime.utcnow(),
          )

      async def fetch_balance(self) -> dict[str, Balance]:
          """Return configured balance."""
          return {
              currency: Balance(
                  currency=currency,
                  free=amount,
                  used=Decimal(0),
                  total=amount,
              )
              for currency, amount in self._balance.items()
          }

      async def create_order(
          self,
          symbol: str,
          order_type: OrderType,
          side: OrderSide,
          amount: Decimal,
          price: Optional[Decimal] = None,
      ) -> Order:
          """Simulate order creation."""
          # Track call
          self.create_order_calls.append({
              "symbol": symbol,
              "order_type": order_type,
              "side": side,
              "amount": amount,
              "price": price,
          })

          if self.should_fail_orders:
              from crypto_bot.exchange.base_exchange import ExchangeError
              raise ExchangeError("Simulated order failure")

          self._order_counter += 1
          order_id = f"MOCK_{self._order_counter}"

          # Determine fill price
          market_price = self._ticker_data.get(symbol, Decimal("100"))
          if order_type == OrderType.MARKET:
              fill_price = market_price
              if side == OrderSide.BUY:
                  fill_price *= (1 + self.slippage_rate)
              else:
                  fill_price *= (1 - self.slippage_rate)
              status = OrderStatus.CLOSED
              filled = amount
          else:
              fill_price = price
              status = OrderStatus.OPEN
              filled = Decimal(0)

          order = Order(
              id=order_id,
              client_order_id=None,
              symbol=symbol,
              side=side,
              order_type=order_type,
              status=status,
              price=fill_price,
              amount=amount,
              filled=filled,
              remaining=amount - filled,
              cost=fill_price * filled if filled else Decimal(0),
              fee=fill_price * filled * Decimal("0.001") if filled else None,
              timestamp=datetime.utcnow(),
          )

          self._orders[order_id] = order

          # Update balance for filled orders
          if status == OrderStatus.CLOSED:
              self._update_balance_for_fill(symbol, side, amount, fill_price)

          return order

      def _update_balance_for_fill(
          self,
          symbol: str,
          side: OrderSide,
          amount: Decimal,
          price: Decimal,
      ) -> None:
          """Update balance after order fill."""
          base, quote = symbol.split("/")
          cost = amount * price
          fee = cost * Decimal("0.001")

          if side == OrderSide.BUY:
              self._balance[quote] -= (cost + fee)
              self._balance[base] = self._balance.get(base, Decimal(0)) + amount
          else:
              self._balance[quote] += (cost - fee)
              self._balance[base] = self._balance.get(base, Decimal(0)) - amount

      async def cancel_order(self, order_id: str, symbol: str) -> Order:
          """Simulate order cancellation."""
          self.cancel_order_calls.append({"order_id": order_id, "symbol": symbol})

          if order_id not in self._orders:
              from crypto_bot.exchange.base_exchange import OrderNotFoundError
              raise OrderNotFoundError(f"Order {order_id} not found")

          order = self._orders[order_id]
          order.status = OrderStatus.CANCELED
          return order

      async def fetch_order(self, order_id: str, symbol: str) -> Order:
          """Return order by ID."""
          if order_id not in self._orders:
              from crypto_bot.exchange.base_exchange import OrderNotFoundError
              raise OrderNotFoundError(f"Order {order_id} not found")
          return self._orders[order_id]

      async def fetch_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
          """Return open orders."""
          result = []
          for order in self._orders.values():
              if order.status == OrderStatus.OPEN:
                  if symbol is None or order.symbol == symbol:
                      result.append(order)
          return result

      async def fetch_ohlcv(
          self,
          symbol: str,
          timeframe: str = "1h",
          limit: int = 100,
      ) -> list:
          """Return mock OHLCV data."""
          price = float(self._ticker_data.get(symbol, Decimal("100")))
          now = datetime.utcnow()
          data = []

          for i in range(limit):
              timestamp = now.timestamp() * 1000 - (i * 3600000)  # hourly
              data.append([
                  timestamp,
                  price * 0.99,  # open
                  price * 1.01,  # high
                  price * 0.98,  # low
                  price,         # close
                  1000.0,        # volume
              ])

          return list(reversed(data))

      # Test helper methods
      def set_price(self, symbol: str, price: Decimal) -> None:
          """Set price for a symbol."""
          self._ticker_data[symbol] = price

      def fill_order(self, order_id: str) -> None:
          """Manually fill an open order."""
          if order_id in self._orders:
              order = self._orders[order_id]
              if order.status == OrderStatus.OPEN:
                  order.status = OrderStatus.CLOSED
                  order.filled = order.amount
                  order.remaining = Decimal(0)
                  self._update_balance_for_fill(
                      order.symbol, order.side, order.amount, order.price
                  )

      def reset(self) -> None:
          """Reset mock state."""
          self._orders.clear()
          self._order_counter = 0
          self.create_order_calls.clear()
          self.cancel_order_calls.clear()
  ```
- [ ] Create pytest fixtures in `tests/conftest.py`:
  ```python
  import pytest
  from decimal import Decimal
  from tests.fixtures.mock_exchange import MockExchange

  @pytest.fixture
  def mock_exchange():
      """Create a fresh mock exchange for each test."""
      return MockExchange(
          initial_balance={"USDT": Decimal("10000"), "BTC": Decimal("0")},
          ticker_data={"BTC/USDT": Decimal("42000")},
      )

  @pytest.fixture
  def mock_exchange_with_btc():
      """Mock exchange with existing BTC position."""
      return MockExchange(
          initial_balance={"USDT": Decimal("5000"), "BTC": Decimal("0.1")},
          ticker_data={"BTC/USDT": Decimal("42000")},
      )
  ```
- [ ] Add failure injection capabilities
- [ ] Write tests for the mock itself

### Technical Notes
- Mock tracks all method calls for assertions
- Configurable behaviors (fail orders, slippage)
- Balance updates on order fills
- Helper methods for test setup

### Definition of Done
- MockExchange implements BaseExchange interface
- All methods work correctly in tests
- Call tracking enables assertions
- Failure injection working
- Mock has its own tests

---

## Story 4.8: Write Unit Tests for Grid Strategy

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** unit tests covering grid strategy logic
**So that** grid calculations and state management are verified

### Acceptance Criteria

- [ ] Create `tests/unit/test_grid_strategy.py`
- [ ] Test grid level calculation:
  ```python
  import pytest
  from decimal import Decimal
  from crypto_bot.strategies.grid_trading import (
      GridConfig, GridSpacing, calculate_grid_levels, calculate_order_size,
  )

  class TestGridLevelCalculation:
      """Tests for grid level calculation."""

      def test_arithmetic_spacing(self):
          """Test arithmetic (equal dollar) spacing."""
          config = GridConfig(
              symbol="BTC/USDT",
              lower_price=Decimal("40000"),
              upper_price=Decimal("50000"),
              num_grids=11,
              total_investment=Decimal("10000"),
              spacing=GridSpacing.ARITHMETIC,
          )

          levels = calculate_grid_levels(config)

          assert len(levels) == 11
          assert levels[0].price == Decimal("40000")
          assert levels[-1].price == Decimal("50000")
          # Check equal spacing
          spacing = levels[1].price - levels[0].price
          assert spacing == Decimal("1000")
          for i in range(1, len(levels)):
              assert levels[i].price - levels[i-1].price == spacing

      def test_geometric_spacing(self):
          """Test geometric (equal percentage) spacing."""
          config = GridConfig(
              symbol="BTC/USDT",
              lower_price=Decimal("40000"),
              upper_price=Decimal("50000"),
              num_grids=11,
              total_investment=Decimal("10000"),
              spacing=GridSpacing.GEOMETRIC,
          )

          levels = calculate_grid_levels(config)

          assert len(levels) == 11
          # Check prices are within range
          assert levels[0].price >= Decimal("39999")
          assert levels[-1].price <= Decimal("50001")
          # Check geometric ratio is constant
          ratio = levels[1].price / levels[0].price
          for i in range(2, len(levels)):
              current_ratio = levels[i].price / levels[i-1].price
              assert abs(current_ratio - ratio) < Decimal("0.0001")

      def test_order_size_calculation(self):
          """Test order size based on investment and grid count."""
          config = GridConfig(
              symbol="BTC/USDT",
              lower_price=Decimal("40000"),
              upper_price=Decimal("50000"),
              num_grids=10,
              total_investment=Decimal("10000"),
          )

          # Assuming 5 active grids below current price
          size = calculate_order_size(config, num_active_grids=5)

          # 80% of 10000 / 5 = 1600 per grid
          assert size == Decimal("1600")

      def test_invalid_config_raises(self):
          """Test that invalid config raises validation error."""
          with pytest.raises(ValueError):
              GridConfig(
                  symbol="BTC/USDT",
                  lower_price=Decimal("50000"),  # Lower > Upper
                  upper_price=Decimal("40000"),
                  num_grids=10,
                  total_investment=Decimal("10000"),
              )
  ```
- [ ] Test strategy initialization:
  ```python
  @pytest.mark.asyncio
  class TestGridStrategyInitialization:
      """Tests for grid strategy initialization."""

      async def test_places_initial_buy_orders(self, mock_exchange):
          """Test that initial buy orders are placed below current price."""
          config = GridConfig(
              symbol="BTC/USDT",
              lower_price=Decimal("40000"),
              upper_price=Decimal("44000"),
              num_grids=5,
              total_investment=Decimal("10000"),
          )

          mock_exchange.set_price("BTC/USDT", Decimal("42000"))
          context = MockExecutionContext(mock_exchange)

          strategy = GridTradingStrategy(config)
          await strategy.initialize(context)

          # Should place buy orders at 40000, 41000 (below 42000)
          assert len(mock_exchange.create_order_calls) == 2
          for call in mock_exchange.create_order_calls:
              assert call["side"] == OrderSide.BUY
              assert call["price"] < Decimal("42000")

      async def test_no_orders_if_price_below_grid(self, mock_exchange):
          """Test behavior when price is below grid range."""
          config = GridConfig(
              symbol="BTC/USDT",
              lower_price=Decimal("40000"),
              upper_price=Decimal("44000"),
              num_grids=5,
              total_investment=Decimal("10000"),
          )

          mock_exchange.set_price("BTC/USDT", Decimal("39000"))
          context = MockExecutionContext(mock_exchange)

          strategy = GridTradingStrategy(config)
          await strategy.initialize(context)

          # No buy orders should be placed (price below all grid levels)
          assert len(mock_exchange.create_order_calls) == 0
  ```
- [ ] Test order fill handling:
  ```python
  @pytest.mark.asyncio
  class TestGridOrderFills:
      """Tests for order fill handling."""

      async def test_buy_fill_triggers_sell_order(self, mock_exchange, initialized_strategy):
          """Test that buy fill triggers sell order at next level."""
          strategy, context = initialized_strategy

          # Simulate buy order fill
          buy_order = Order(
              id="MOCK_1",
              symbol="BTC/USDT",
              side=OrderSide.BUY,
              order_type=OrderType.LIMIT,
              status=OrderStatus.CLOSED,
              price=Decimal("40000"),
              amount=Decimal("0.1"),
              filled=Decimal("0.1"),
              remaining=Decimal(0),
              cost=Decimal("4000"),
              fee=Decimal("4"),
              timestamp=datetime.utcnow(),
          )

          mock_exchange.create_order_calls.clear()
          await strategy.on_order_filled(buy_order)

          # Should place sell order at next level up
          assert len(mock_exchange.create_order_calls) == 1
          call = mock_exchange.create_order_calls[0]
          assert call["side"] == OrderSide.SELL
          assert call["price"] > Decimal("40000")

      async def test_sell_fill_records_profit(self, mock_exchange, initialized_strategy):
          """Test that sell fill records profit correctly."""
          strategy, context = initialized_strategy

          # Setup: Simulate completed buy at 40000
          strategy._grid_levels[0].filled_buy = True
          strategy._grid_levels[0].buy_price = Decimal("40000")

          # Simulate sell fill at 41000
          sell_order = Order(
              id="MOCK_2",
              symbol="BTC/USDT",
              side=OrderSide.SELL,
              order_type=OrderType.LIMIT,
              status=OrderStatus.CLOSED,
              price=Decimal("41000"),
              amount=Decimal("0.1"),
              filled=Decimal("0.1"),
              remaining=Decimal(0),
              cost=Decimal("4100"),
              fee=Decimal("4.1"),
              timestamp=datetime.utcnow(),
          )

          await strategy.on_order_filled(sell_order)

          # Profit = (41000 - 40000) * 0.1 - fees
          assert strategy._total_profit > 0
          assert strategy._completed_cycles == 1
  ```
- [ ] Test state serialization:
  ```python
  class TestGridStateSerilization:
      """Tests for state persistence."""

      def test_state_roundtrip(self, initialized_strategy):
          """Test state can be serialized and restored."""
          strategy, _ = initialized_strategy

          # Modify state
          strategy._total_profit = Decimal("100")
          strategy._completed_cycles = 5

          # Serialize
          state = strategy.get_state()

          # Verify state structure
          assert "config" in state
          assert "grid_levels" in state
          assert state["total_profit"] == "100"
          assert state["completed_cycles"] == 5

          # Restore
          new_strategy = GridTradingStrategy.from_state(state, None)

          assert new_strategy._total_profit == Decimal("100")
          assert new_strategy._completed_cycles == 5
  ```
- [ ] Achieve >90% coverage for strategy module

### Definition of Done
- All grid calculation tests pass
- Initialization tests verify correct orders
- Fill handling tests verify counter-orders
- State serialization tests pass
- Coverage >90%

---

## Story 4.9: Write Unit Tests for Risk Management

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** unit tests covering risk components
**So that** risk limits are enforced correctly

### Acceptance Criteria

- [ ] Create `tests/unit/test_risk_management.py`
- [ ] Test position sizing:
  ```python
  import pytest
  from decimal import Decimal
  from crypto_bot.risk.position_sizer import FixedFractionalSizer, KellySizer

  class TestPositionSizing:
      """Tests for position sizing algorithms."""

      def test_fixed_fractional_2_percent(self):
          """Test 2% risk position sizing."""
          sizer = FixedFractionalSizer(risk_pct=Decimal("0.02"))

          result = sizer.calculate(
              balance=Decimal("10000"),
              entry_price=Decimal("100"),
              stop_loss_price=Decimal("95"),
          )

          # Risk = 10000 * 0.02 = 200
          # Price risk = 100 - 95 = 5
          # Position = 200 / 5 = 40 units
          assert result.amount == Decimal("40")
          assert result.risk_amount == Decimal("200")

      def test_kelly_criterion(self):
          """Test Kelly criterion calculation."""
          sizer = KellySizer(fraction=Decimal("0.5"))  # Half-Kelly

          kelly = sizer.calculate_kelly(
              win_rate=Decimal("0.6"),
              avg_win=Decimal("100"),
              avg_loss=Decimal("50"),
          )

          # Kelly = 0.6 - (0.4 / 2) = 0.6 - 0.2 = 0.4
          # Half-Kelly = 0.2
          assert kelly == Decimal("0.2")

      def test_zero_stop_loss_raises(self):
          """Test that zero stop loss raises error."""
          sizer = FixedFractionalSizer()

          with pytest.raises(ValueError):
              sizer.calculate(
                  balance=Decimal("10000"),
                  entry_price=Decimal("100"),
                  stop_loss_price=Decimal("100"),  # Same as entry
              )
  ```
- [ ] Test circuit breaker:
  ```python
  class TestCircuitBreaker:
      """Tests for circuit breaker."""

      def test_daily_loss_triggers(self):
          """Test circuit breaker trips on daily loss limit."""
          cb = CircuitBreaker(CircuitBreakerConfig(
              max_daily_loss_pct=Decimal("0.05"),
          ))

          # Record losing trades
          trigger = cb.record_trade(Decimal("-500"), Decimal("10000"))
          assert trigger is None
          assert cb.is_trading_allowed

          trigger = cb.record_trade(Decimal("-600"), Decimal("9400"))
          assert trigger == CircuitBreakerTrigger.DAILY_LOSS
          assert not cb.is_trading_allowed

      def test_consecutive_losses_triggers(self):
          """Test circuit breaker trips on consecutive losses."""
          cb = CircuitBreaker(CircuitBreakerConfig(
              max_consecutive_losses=3,
          ))

          for i in range(2):
              cb.record_trade(Decimal("-10"), Decimal("10000"))
          assert cb.is_trading_allowed

          cb.record_trade(Decimal("-10"), Decimal("10000"))
          assert not cb.is_trading_allowed

      def test_win_resets_consecutive_losses(self):
          """Test that winning trade resets consecutive loss counter."""
          cb = CircuitBreaker(CircuitBreakerConfig(
              max_consecutive_losses=3,
          ))

          cb.record_trade(Decimal("-10"), Decimal("10000"))
          cb.record_trade(Decimal("-10"), Decimal("10000"))
          cb.record_trade(Decimal("20"), Decimal("10000"))  # Win

          assert cb._state.consecutive_losses == 0
          assert cb.is_trading_allowed

      def test_cooldown_resets_breaker(self):
          """Test circuit breaker resets after cooldown."""
          cb = CircuitBreaker(CircuitBreakerConfig(
              max_consecutive_losses=1,
              cooldown_minutes=0,  # Immediate reset for test
          ))

          cb.record_trade(Decimal("-10"), Decimal("10000"))
          assert not cb.is_trading_allowed

          # After cooldown
          cb._state.cooldown_until = datetime.utcnow() - timedelta(minutes=1)
          assert cb.is_trading_allowed
  ```
- [ ] Test stop-loss handlers:
  ```python
  class TestStopLoss:
      """Tests for stop-loss handlers."""

      def test_percentage_stop_loss(self):
          """Test percentage-based stop-loss calculation."""
          config = StopLossConfig(
              type=StopLossType.PERCENTAGE,
              value=Decimal("0.05"),  # 5%
          )
          handler = StopLossHandler(config)

          state = handler.initialize(Decimal("100"), "buy")

          assert state.current_stop == Decimal("95")  # 100 * 0.95

      def test_trailing_stop_updates(self):
          """Test trailing stop moves with price."""
          config = StopLossConfig(
              type=StopLossType.TRAILING,
              value=Decimal("0.05"),
          )
          handler = StopLossHandler(config)
          handler.initialize(Decimal("100"), "buy")

          # Price moves up
          handler.update_trailing(Decimal("110"), "buy")

          # Stop should trail at 5% below new high
          assert handler._state.current_stop == Decimal("104.5")
          assert handler._state.highest_price == Decimal("110")

      def test_trailing_stop_never_moves_down(self):
          """Test trailing stop never decreases."""
          config = StopLossConfig(
              type=StopLossType.TRAILING,
              value=Decimal("0.05"),
          )
          handler = StopLossHandler(config)
          handler.initialize(Decimal("100"), "buy")
          handler.update_trailing(Decimal("110"), "buy")

          initial_stop = handler._state.current_stop

          # Price moves down
          handler.update_trailing(Decimal("105"), "buy")

          # Stop should not move down
          assert handler._state.current_stop == initial_stop

      def test_stop_triggers_correctly(self):
          """Test stop-loss trigger detection."""
          config = StopLossConfig(
              type=StopLossType.PERCENTAGE,
              value=Decimal("0.05"),
          )
          handler = StopLossHandler(config)
          handler.initialize(Decimal("100"), "buy")

          assert not handler.check_stop(Decimal("96"), "buy")
          assert handler.check_stop(Decimal("94"), "buy")
          assert handler._state.triggered
  ```
- [ ] Write tests for drawdown tracking

### Definition of Done
- Position sizing tests pass
- Circuit breaker tests cover all triggers
- Stop-loss tests cover all types
- Drawdown tracking tests pass
- Coverage >90%

---

## Story 4.10: Write Unit Tests for Exchange Wrapper

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** developer
**I want** unit tests for exchange error handling
**So that** retry logic and error classification work correctly

### Acceptance Criteria

- [ ] Create `tests/unit/test_exchange.py`
- [ ] Test retry logic:
  ```python
  import pytest
  from unittest.mock import AsyncMock, patch
  import ccxt
  from crypto_bot.utils.retry import retry_with_backoff, RETRYABLE_EXCEPTIONS

  class TestRetryLogic:
      """Tests for retry decorator."""

      @pytest.mark.asyncio
      async def test_retries_on_network_error(self):
          """Test retry on transient network error."""
          mock_func = AsyncMock(side_effect=[
              ccxt.NetworkError("Connection failed"),
              ccxt.NetworkError("Connection failed"),
              {"result": "success"},
          ])

          decorated = retry_with_backoff(max_retries=3, base_delay=0.01)(mock_func)
          result = await decorated()

          assert result == {"result": "success"}
          assert mock_func.call_count == 3

      @pytest.mark.asyncio
      async def test_no_retry_on_auth_error(self):
          """Test no retry on authentication error."""
          mock_func = AsyncMock(side_effect=ccxt.AuthenticationError("Invalid key"))

          decorated = retry_with_backoff(max_retries=3)(mock_func)

          with pytest.raises(ccxt.AuthenticationError):
              await decorated()

          assert mock_func.call_count == 1

      @pytest.mark.asyncio
      async def test_raises_after_max_retries(self):
          """Test raises after exhausting retries."""
          mock_func = AsyncMock(side_effect=ccxt.NetworkError("Always fails"))

          decorated = retry_with_backoff(max_retries=3, base_delay=0.01)(mock_func)

          with pytest.raises(ccxt.NetworkError):
              await decorated()

          assert mock_func.call_count == 3
  ```
- [ ] Test CCXT wrapper:
  ```python
  class TestCCXTWrapper:
      """Tests for CCXT exchange wrapper."""

      @pytest.mark.asyncio
      async def test_converts_ticker_to_dataclass(self, mock_ccxt):
          """Test CCXT response converted to Ticker dataclass."""
          mock_ccxt.fetch_ticker.return_value = {
              "symbol": "BTC/USDT",
              "bid": 41999.0,
              "ask": 42001.0,
              "last": 42000.0,
              "timestamp": 1704326400000,
          }

          wrapper = CCXTExchange(exchange_settings)
          wrapper._exchange = mock_ccxt

          ticker = await wrapper.fetch_ticker("BTC/USDT")

          assert isinstance(ticker, Ticker)
          assert ticker.symbol == "BTC/USDT"
          assert ticker.last == Decimal("42000")

      @pytest.mark.asyncio
      async def test_precision_handling(self, mock_ccxt):
          """Test order amount rounded to exchange precision."""
          mock_ccxt.markets = {
              "BTC/USDT": {
                  "precision": {"amount": 4, "price": 2},
                  "limits": {"amount": {"min": 0.0001}},
              }
          }
          mock_ccxt.create_order.return_value = {"id": "123", "status": "open"}

          wrapper = CCXTExchange(exchange_settings)
          wrapper._exchange = mock_ccxt
          wrapper._markets = mock_ccxt.markets

          await wrapper.create_order(
              "BTC/USDT", OrderType.LIMIT, OrderSide.BUY,
              Decimal("0.123456789"),  # More precision than allowed
              Decimal("42000.123"),
          )

          # Verify order placed with correct precision
          call_args = mock_ccxt.create_order.call_args
          assert call_args[0][3] == 0.1235  # Rounded to 4 decimals
  ```
- [ ] Test error mapping
- [ ] Test WebSocket reconnection

### Definition of Done
- Retry logic tests pass
- CCXT wrapper tests pass
- Error mapping verified
- WebSocket tests pass

---

## Story 4.11: Create Integration Tests for Testnet

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** developer
**I want** integration tests running against Binance testnet
**So that** real exchange behavior is validated

### Acceptance Criteria

- [ ] Create `tests/integration/test_binance_testnet.py`
- [ ] Document testnet setup in README
- [ ] Implement integration tests:
  ```python
  import pytest
  from decimal import Decimal
  import os

  # Skip if no testnet credentials
  pytestmark = pytest.mark.skipif(
      not os.getenv("BINANCE_TESTNET_API_KEY"),
      reason="Binance testnet credentials not configured",
  )

  @pytest.fixture(scope="module")
  async def binance_adapter():
      """Create Binance adapter connected to testnet."""
      from crypto_bot.exchange.binance_adapter import BinanceAdapter
      from crypto_bot.config.settings import ExchangeSettings

      settings = ExchangeSettings(
          name="binance",
          api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
          api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
          testnet=True,
      )

      adapter = BinanceAdapter(settings)
      await adapter.connect()
      yield adapter
      await adapter.disconnect()


  @pytest.mark.integration
  @pytest.mark.asyncio
  class TestBinanceTestnet:
      """Integration tests against Binance testnet."""

      async def test_fetch_ticker(self, binance_adapter):
          """Test fetching ticker from testnet."""
          ticker = await binance_adapter.fetch_ticker("BTC/USDT")

          assert ticker.symbol == "BTC/USDT"
          assert ticker.bid > 0
          assert ticker.ask > 0
          assert ticker.ask >= ticker.bid

      async def test_fetch_balance(self, binance_adapter):
          """Test fetching balance from testnet."""
          balances = await binance_adapter.fetch_balance()

          assert "USDT" in balances
          assert balances["USDT"].total >= 0

      async def test_place_and_cancel_order(self, binance_adapter):
          """Test placing and canceling a limit order."""
          # Get current price
          ticker = await binance_adapter.fetch_ticker("BTC/USDT")

          # Place order far from market (won't fill)
          limit_price = ticker.bid * Decimal("0.5")

          order = await binance_adapter.create_order(
              symbol="BTC/USDT",
              order_type=OrderType.LIMIT,
              side=OrderSide.BUY,
              amount=Decimal("0.001"),
              price=limit_price,
          )

          assert order.status == OrderStatus.OPEN
          assert order.id is not None

          # Cancel the order
          cancelled = await binance_adapter.cancel_order(order.id, "BTC/USDT")
          assert cancelled.status == OrderStatus.CANCELED

      async def test_fetch_ohlcv(self, binance_adapter):
          """Test fetching historical OHLCV data."""
          ohlcv = await binance_adapter.fetch_ohlcv(
              "BTC/USDT",
              timeframe="1h",
              limit=10,
          )

          assert len(ohlcv) == 10
          assert len(ohlcv[0]) == 6  # timestamp, o, h, l, c, v
  ```
- [ ] Create pytest markers in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
      "slow: marks tests as slow (deselect with '-m \"not slow\"')",
  ]
  asyncio_mode = "auto"
  ```
- [ ] Add teardown to cancel any orphan orders

### Definition of Done
- Integration tests run on testnet
- Tests are skipped without credentials
- Proper cleanup in teardown
- Documentation for testnet setup

---

## Story 4.12: Set Up CI/CD Pipeline

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** automated testing on every commit
**So that** regressions are caught early

### Acceptance Criteria

- [ ] Create `.github/workflows/ci.yml`:
  ```yaml
  name: CI

  on:
    push:
      branches: [main, develop]
    pull_request:
      branches: [main]

  jobs:
    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: "3.11"

        - name: Install dependencies
          run: |
            python -m pip install --upgrade pip
            pip install ruff mypy

        - name: Run Ruff
          run: ruff check src/ tests/

        - name: Run MyPy
          run: mypy src/

    test:
      runs-on: ubuntu-latest
      needs: lint
      steps:
        - uses: actions/checkout@v4

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: "3.11"

        - name: Cache pip packages
          uses: actions/cache@v4
          with:
            path: ~/.cache/pip
            key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}

        - name: Install dependencies
          run: |
            python -m pip install --upgrade pip
            pip install -e ".[dev]"

        - name: Run unit tests
          run: |
            pytest tests/unit -v --cov=src/crypto_bot --cov-report=xml

        - name: Upload coverage
          uses: codecov/codecov-action@v4
          with:
            files: ./coverage.xml
            fail_ci_if_error: true

    integration:
      runs-on: ubuntu-latest
      needs: test
      if: github.event_name == 'push' && github.ref == 'refs/heads/main'
      steps:
        - uses: actions/checkout@v4

        - name: Set up Python
          uses: actions/setup-python@v5
          with:
            python-version: "3.11"

        - name: Install dependencies
          run: pip install -e ".[dev]"

        - name: Run integration tests
          env:
            BINANCE_TESTNET_API_KEY: ${{ secrets.BINANCE_TESTNET_API_KEY }}
            BINANCE_TESTNET_API_SECRET: ${{ secrets.BINANCE_TESTNET_API_SECRET }}
          run: |
            pytest tests/integration -v -m integration
  ```
- [ ] Add coverage threshold:
  ```yaml
  # In pytest config or .coveragerc
  [tool.coverage.report]
  fail_under = 80
  ```
- [ ] Add branch protection rules documentation
- [ ] Create pre-commit hooks:
  ```yaml
  # .pre-commit-config.yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.1.9
      hooks:
        - id: ruff
          args: [--fix]
        - id: ruff-format

    - repo: https://github.com/pre-commit/mirrors-mypy
      rev: v1.8.0
      hooks:
        - id: mypy
          additional_dependencies: [pydantic]
  ```

### Definition of Done
- CI runs on every PR and push
- Linting with Ruff
- Type checking with MyPy
- Unit tests with coverage
- Integration tests on main branch
- Coverage threshold enforced

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 4.7 Mock Exchange | 5 | P0 | Phase 2 |
| 4.8 Grid Strategy Tests | 8 | P0 | 4.7 |
| 4.9 Risk Management Tests | 5 | P0 | 4.7 |
| 4.10 Exchange Wrapper Tests | 5 | P1 | 4.7 |
| 4.11 Testnet Integration Tests | 5 | P1 | Phase 2 |
| 4.12 CI/CD Pipeline | 5 | P0 | 4.8, 4.9 |
| **Total** | **33** | | |

---

## Sources & References

- [Async Test Patterns for Pytest](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html)
- [pytest-asyncio Guide](https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/)
- [Python Unit Testing Guide 2025](https://www.glukhov.org/post/2025/10/unit-testing-in-python/)
- [Pytest Advanced Features 2025](https://www.johal.in/python-testing-frameworks-pytest-advanced-features-and-mocking-strategies-for-unit-tests-2025/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Mock Anything in Python](https://medium.com/@bhagyarana80/mock-anything-in-python-pytest-unittest-mock-deep-dive-for-real-world-testing-d4ed26f65649)
