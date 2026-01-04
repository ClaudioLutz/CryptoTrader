# Epic: Phase 3B - Backtesting Infrastructure

**Epic Owner:** Development Team
**Priority:** High - Required for strategy validation
**Dependencies:** Phase 2 (Strategy Framework, Data Persistence), Phase 3A (Risk Management)

---

## Overview

Backtesting infrastructure enables strategy validation on historical data before risking real capital. This epic implements a backtesting framework that shares code with live trading through the adapter pattern, with realistic simulation of fees, slippage, and latency.

### Key Deliverables
- Backtest execution context sharing code with live trading
- Realistic fee and slippage simulation
- Event-driven backtest engine
- Performance metrics and reporting
- Parameter optimization support

### Research & Best Practices Applied

Based on current 2025 best practices:
- **Framework Choice:** [VectorBT for speed](https://vectorbt.dev/), custom engine for event-driven accuracy
- **Simulation Accuracy:** [Model fees (0.1%), slippage (0.05-0.1%)](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0), and latency
- **Validation:** [30-90 days paper trading](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025) before live deployment
- **Code Reuse:** Same strategy code runs in backtest and live via adapter pattern

---

## Story 3.6: Define Execution Context Interface

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** an execution context abstraction
**So that** strategies run unchanged in backtest and live modes

### Background
The [adapter pattern](https://github.com/AsyncAlgoTrading/aat) allows the same strategy code to execute against both simulated and real exchanges. This is critical for ensuring backtest results translate to live performance.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/backtest/execution_context.py`
- [ ] Define ExecutionContext Protocol:
  ```python
  from typing import Protocol, Optional
  from decimal import Decimal
  from datetime import datetime

  class ExecutionContext(Protocol):
      """Abstract interface for order execution."""

      @property
      def timestamp(self) -> datetime:
          """Current simulation/market timestamp."""
          ...

      @property
      def is_live(self) -> bool:
          """Whether this is live trading."""
          ...

      async def get_current_price(self, symbol: str) -> Decimal:
          """Get current market price for symbol."""
          ...

      async def get_balance(self, currency: str) -> Decimal:
          """Get available balance for currency."""
          ...

      async def get_position(self, symbol: str) -> Optional[Decimal]:
          """Get current position size for symbol."""
          ...

      async def place_order(
          self,
          symbol: str,
          side: str,
          amount: Decimal,
          price: Optional[Decimal] = None,
          order_type: str = "limit",
      ) -> str:
          """
          Place an order.

          Args:
              symbol: Trading pair (e.g., "BTC/USDT")
              side: "buy" or "sell"
              amount: Order quantity
              price: Limit price (None for market order)
              order_type: "limit" or "market"

          Returns:
              Order ID
          """
          ...

      async def cancel_order(self, order_id: str, symbol: str) -> bool:
          """
          Cancel an order.

          Returns:
              True if cancelled, False if not found
          """
          ...

      async def get_order_status(self, order_id: str, symbol: str) -> dict:
          """Get order status and fill information."""
          ...

      async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
          """Get all open orders."""
          ...
  ```
- [ ] Ensure strategy interface uses ExecutionContext:
  ```python
  # Strategy should depend only on ExecutionContext
  class Strategy(Protocol):
      async def initialize(self, context: ExecutionContext) -> None: ...
      async def on_tick(self, ticker: Ticker) -> None: ...
      # ... rest of methods
  ```
- [ ] Write documentation explaining the pattern

### Technical Notes
- Protocol allows duck typing without inheritance
- All time-dependent operations use context.timestamp
- Strategies never import exchange directly

### Definition of Done
- ExecutionContext Protocol defined
- All strategy interactions go through context
- Documentation explains adapter pattern

---

## Story 3.7: Build Backtest Execution Context

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a simulated execution context for backtesting
**So that** strategies can be tested on historical data

### Acceptance Criteria

- [ ] Create `src/crypto_bot/backtest/backtest_context.py`
- [ ] Implement BacktestContext:
  ```python
  from decimal import Decimal
  from datetime import datetime
  from typing import Optional
  from dataclasses import dataclass, field
  import pandas as pd

  @dataclass
  class SimulatedOrder:
      id: str
      symbol: str
      side: str
      order_type: str
      amount: Decimal
      price: Optional[Decimal]
      filled: Decimal = Decimal(0)
      status: str = "open"
      created_at: datetime = field(default_factory=datetime.utcnow)
      filled_at: Optional[datetime] = None
      fill_price: Optional[Decimal] = None
      fee: Decimal = Decimal(0)

  class BacktestContext:
      """Simulated execution context for backtesting."""

      def __init__(
          self,
          initial_balance: dict[str, Decimal],
          fee_rate: Decimal = Decimal("0.001"),  # 0.1%
          slippage_rate: Decimal = Decimal("0.0005"),  # 0.05%
          latency_ms: int = 100,
      ):
          self._initial_balance = initial_balance.copy()
          self._balance = initial_balance.copy()
          self._positions: dict[str, Decimal] = {}
          self._fee_rate = fee_rate
          self._slippage_rate = slippage_rate
          self._latency_ms = latency_ms

          self._orders: dict[str, SimulatedOrder] = {}
          self._order_counter = 0
          self._trades: list[dict] = []

          self._current_timestamp: datetime = datetime.utcnow()
          self._current_prices: dict[str, Decimal] = {}

      @property
      def timestamp(self) -> datetime:
          return self._current_timestamp

      @property
      def is_live(self) -> bool:
          return False

      def set_market_state(self, timestamp: datetime, prices: dict[str, Decimal]) -> None:
          """Update market state for current bar."""
          self._current_timestamp = timestamp
          self._current_prices = prices
          self._process_pending_orders()

      async def get_current_price(self, symbol: str) -> Decimal:
          if symbol not in self._current_prices:
              raise ValueError(f"No price data for {symbol}")
          return self._current_prices[symbol]

      async def get_balance(self, currency: str) -> Decimal:
          return self._balance.get(currency, Decimal(0))

      async def get_position(self, symbol: str) -> Optional[Decimal]:
          return self._positions.get(symbol)
  ```
- [ ] Implement order placement with simulated fill:
  ```python
  async def place_order(
      self,
      symbol: str,
      side: str,
      amount: Decimal,
      price: Optional[Decimal] = None,
      order_type: str = "limit",
  ) -> str:
      self._order_counter += 1
      order_id = f"BT_{self._order_counter}"

      order = SimulatedOrder(
          id=order_id,
          symbol=symbol,
          side=side,
          order_type=order_type,
          amount=amount,
          price=price,
          created_at=self._current_timestamp,
      )
      self._orders[order_id] = order

      # Market orders fill immediately
      if order_type == "market":
          self._fill_order(order, self._current_prices[symbol])

      return order_id

  def _fill_order(self, order: SimulatedOrder, market_price: Decimal) -> None:
      """Simulate order fill with slippage and fees."""
      # Apply slippage
      if order.side == "buy":
          fill_price = market_price * (1 + self._slippage_rate)
      else:
          fill_price = market_price * (1 - self._slippage_rate)

      # Use limit price if better
      if order.price:
          if order.side == "buy" and order.price < fill_price:
              fill_price = order.price
          elif order.side == "sell" and order.price > fill_price:
              fill_price = order.price

      # Calculate fee
      fee = fill_price * order.amount * self._fee_rate

      # Update order
      order.filled = order.amount
      order.fill_price = fill_price
      order.fee = fee
      order.status = "closed"
      order.filled_at = self._current_timestamp

      # Update balance and position
      base, quote = order.symbol.split("/")

      if order.side == "buy":
          cost = fill_price * order.amount + fee
          self._balance[quote] -= cost
          self._positions[order.symbol] = (
              self._positions.get(order.symbol, Decimal(0)) + order.amount
          )
      else:
          proceeds = fill_price * order.amount - fee
          self._balance[quote] += proceeds
          self._positions[order.symbol] = (
              self._positions.get(order.symbol, Decimal(0)) - order.amount
          )

      # Record trade
      self._trades.append({
          "timestamp": self._current_timestamp,
          "symbol": order.symbol,
          "side": order.side,
          "amount": order.amount,
          "price": fill_price,
          "fee": fee,
          "order_id": order.id,
      })
  ```
- [ ] Implement limit order processing:
  ```python
  def _process_pending_orders(self) -> None:
      """Process pending limit orders against current prices."""
      for order in list(self._orders.values()):
          if order.status != "open" or order.order_type != "limit":
              continue

          symbol = order.symbol
          if symbol not in self._current_prices:
              continue

          current_price = self._current_prices[symbol]

          # Check if limit order can fill
          can_fill = False
          if order.side == "buy" and current_price <= order.price:
              can_fill = True
          elif order.side == "sell" and current_price >= order.price:
              can_fill = True

          if can_fill:
              self._fill_order(order, current_price)
  ```
- [ ] Implement order management methods:
  ```python
  async def cancel_order(self, order_id: str, symbol: str) -> bool:
      if order_id in self._orders:
          order = self._orders[order_id]
          if order.status == "open":
              order.status = "canceled"
              return True
      return False

  async def get_order_status(self, order_id: str, symbol: str) -> dict:
      if order_id not in self._orders:
          raise ValueError(f"Order {order_id} not found")

      order = self._orders[order_id]
      return {
          "id": order.id,
          "status": order.status,
          "filled": order.filled,
          "remaining": order.amount - order.filled,
          "price": order.fill_price,
          "fee": order.fee,
      }

  async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
      result = []
      for order in self._orders.values():
          if order.status == "open":
              if symbol is None or order.symbol == symbol:
                  result.append({
                      "id": order.id,
                      "symbol": order.symbol,
                      "side": order.side,
                      "amount": order.amount,
                      "price": order.price,
                  })
      return result
  ```
- [ ] Add portfolio value calculation:
  ```python
  def get_portfolio_value(self) -> Decimal:
      """Calculate total portfolio value in quote currency."""
      total = self._balance.get("USDT", Decimal(0))

      for symbol, amount in self._positions.items():
          if amount != 0 and symbol in self._current_prices:
              total += amount * self._current_prices[symbol]

      return total

  def get_trade_history(self) -> list[dict]:
      """Get all executed trades."""
      return self._trades.copy()

  def get_metrics(self) -> dict:
      """Get backtest summary metrics."""
      initial_value = sum(self._initial_balance.values())
      final_value = self.get_portfolio_value()

      return {
          "initial_balance": initial_value,
          "final_balance": final_value,
          "total_return": (final_value - initial_value) / initial_value,
          "total_trades": len(self._trades),
          "total_fees": sum(t["fee"] for t in self._trades),
      }
  ```
- [ ] Write comprehensive unit tests

### Technical Notes
- Slippage applied based on order direction (adverse fill)
- Fees deducted from balance on each trade
- Limit orders processed on each bar
- Portfolio value calculated in quote currency

### Definition of Done
- BacktestContext implements ExecutionContext
- Order simulation with slippage and fees
- Limit order processing on price updates
- Portfolio and trade tracking working
- Unit tests pass

---

## Story 3.8: Implement Fee and Slippage Simulation

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** realistic fee and slippage modeling
**So that** backtest results approximate live trading performance

### Background
Per [backtesting best practices](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0), ignoring slippage is a common pitfall. The difference between expected and actual execution prices significantly impacts results.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/backtest/simulation.py`
- [ ] Implement configurable fee model:
  ```python
  from decimal import Decimal
  from enum import Enum
  from dataclasses import dataclass
  from typing import Optional

  class FeeType(str, Enum):
      PERCENTAGE = "percentage"
      FIXED = "fixed"
      TIERED = "tiered"

  @dataclass
  class FeeConfig:
      type: FeeType = FeeType.PERCENTAGE
      maker_rate: Decimal = Decimal("0.001")  # 0.1%
      taker_rate: Decimal = Decimal("0.001")  # 0.1%
      fixed_fee: Decimal = Decimal(0)

      # Tiered fee structure (30-day volume -> rate)
      volume_tiers: Optional[dict[Decimal, Decimal]] = None

  class FeeCalculator:
      """Calculate trading fees based on configuration."""

      def __init__(self, config: FeeConfig):
          self._config = config
          self._30d_volume = Decimal(0)

      def calculate(
          self,
          amount: Decimal,
          price: Decimal,
          is_maker: bool = False,
      ) -> Decimal:
          """Calculate fee for a trade."""
          notional = amount * price

          if self._config.type == FeeType.FIXED:
              return self._config.fixed_fee

          elif self._config.type == FeeType.PERCENTAGE:
              rate = self._config.maker_rate if is_maker else self._config.taker_rate
              return notional * rate

          elif self._config.type == FeeType.TIERED:
              rate = self._get_tiered_rate(is_maker)
              return notional * rate

          return Decimal(0)

      def _get_tiered_rate(self, is_maker: bool) -> Decimal:
          """Get fee rate based on 30-day volume."""
          if not self._config.volume_tiers:
              return self._config.maker_rate if is_maker else self._config.taker_rate

          # Find applicable tier
          applicable_rate = self._config.taker_rate
          for volume_threshold, rate in sorted(self._config.volume_tiers.items()):
              if self._30d_volume >= volume_threshold:
                  applicable_rate = rate
              else:
                  break

          return applicable_rate

      def update_volume(self, trade_value: Decimal) -> None:
          """Update 30-day rolling volume."""
          self._30d_volume += trade_value
  ```
- [ ] Implement slippage models:
  ```python
  from abc import ABC, abstractmethod
  import random

  class SlippageModel(ABC):
      """Base class for slippage models."""

      @abstractmethod
      def calculate(
          self,
          price: Decimal,
          amount: Decimal,
          side: str,
          volume: Optional[Decimal] = None,
      ) -> Decimal:
          """Calculate slippage-adjusted price."""
          pass

  class FixedSlippage(SlippageModel):
      """Fixed percentage slippage."""

      def __init__(self, rate: Decimal = Decimal("0.0005")):
          self._rate = rate

      def calculate(
          self,
          price: Decimal,
          amount: Decimal,
          side: str,
          volume: Optional[Decimal] = None,
      ) -> Decimal:
          if side == "buy":
              return price * (1 + self._rate)
          else:
              return price * (1 - self._rate)

  class VolumeBasedSlippage(SlippageModel):
      """Slippage based on order size relative to volume."""

      def __init__(
          self,
          base_rate: Decimal = Decimal("0.0001"),
          volume_impact: Decimal = Decimal("0.1"),
      ):
          self._base_rate = base_rate
          self._volume_impact = volume_impact

      def calculate(
          self,
          price: Decimal,
          amount: Decimal,
          side: str,
          volume: Optional[Decimal] = None,
      ) -> Decimal:
          # Base slippage
          slippage = self._base_rate

          # Add volume impact
          if volume and volume > 0:
              order_pct = (amount * price) / volume
              slippage += order_pct * self._volume_impact

          if side == "buy":
              return price * (1 + slippage)
          else:
              return price * (1 - slippage)

  class RandomSlippage(SlippageModel):
      """Random slippage within a range for realistic simulation."""

      def __init__(
          self,
          min_rate: Decimal = Decimal("0.0001"),
          max_rate: Decimal = Decimal("0.001"),
      ):
          self._min_rate = float(min_rate)
          self._max_rate = float(max_rate)

      def calculate(
          self,
          price: Decimal,
          amount: Decimal,
          side: str,
          volume: Optional[Decimal] = None,
      ) -> Decimal:
          rate = Decimal(str(random.uniform(self._min_rate, self._max_rate)))

          if side == "buy":
              return price * (1 + rate)
          else:
              return price * (1 - rate)
  ```
- [ ] Implement latency simulation:
  ```python
  @dataclass
  class LatencyConfig:
      min_ms: int = 50
      max_ms: int = 200
      spike_probability: float = 0.01  # 1% chance of spike
      spike_max_ms: int = 2000

  class LatencySimulator:
      """Simulate network latency for order execution."""

      def __init__(self, config: LatencyConfig):
          self._config = config

      def get_latency_ms(self) -> int:
          """Get simulated latency in milliseconds."""
          if random.random() < self._config.spike_probability:
              return random.randint(self._config.max_ms, self._config.spike_max_ms)
          return random.randint(self._config.min_ms, self._config.max_ms)

      def get_execution_price(
          self,
          order_price: Decimal,
          price_at_execution: Decimal,
          order_type: str,
          side: str,
      ) -> Decimal:
          """
          Get execution price accounting for latency.

          For market orders, use price at execution time.
          For limit orders, use limit price if still valid.
          """
          if order_type == "market":
              return price_at_execution

          # Limit order - check if still valid
          if side == "buy":
              if price_at_execution <= order_price:
                  return order_price  # Fill at limit
              else:
                  return None  # Price moved, order not filled
          else:
              if price_at_execution >= order_price:
                  return order_price
              else:
                  return None
  ```
- [ ] Write tests for all simulation components

### Technical Notes
- Binance taker fee is typically 0.1% for spot
- Slippage of 0.05-0.1% is realistic for liquid pairs
- Volume-based slippage models large order impact
- Latency spikes can cause significant price drift

### Definition of Done
- Fee calculator supports percentage, fixed, tiered
- Multiple slippage models implemented
- Latency simulation working
- Tests verify realistic simulation

---

## Story 3.9: Build Backtest Engine

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a backtest engine that runs strategies on historical data
**So that** strategy performance can be evaluated before live trading

### Acceptance Criteria

- [ ] Create `src/crypto_bot/backtest/engine.py`
- [ ] Implement BacktestEngine:
  ```python
  import pandas as pd
  from datetime import datetime
  from decimal import Decimal
  from typing import Optional, Type
  import structlog

  logger = structlog.get_logger()

  @dataclass
  class BacktestConfig:
      start_date: datetime
      end_date: datetime
      initial_balance: dict[str, Decimal]
      symbols: list[str]
      timeframe: str = "1h"
      fee_config: FeeConfig = field(default_factory=FeeConfig)
      slippage_model: SlippageModel = field(default_factory=FixedSlippage)

  @dataclass
  class BacktestResult:
      config: BacktestConfig
      strategy_name: str
      start_date: datetime
      end_date: datetime
      initial_balance: Decimal
      final_balance: Decimal
      total_return: Decimal
      total_trades: int
      winning_trades: int
      losing_trades: int
      win_rate: Decimal
      profit_factor: Decimal
      max_drawdown: Decimal
      sharpe_ratio: Decimal
      equity_curve: pd.DataFrame
      trades: list[dict]

  class BacktestEngine:
      """Event-driven backtesting engine."""

      def __init__(
          self,
          data_provider: OHLCVFetcher,
          config: BacktestConfig,
      ):
          self._data_provider = data_provider
          self._config = config
          self._context: Optional[BacktestContext] = None

      async def run(
          self,
          strategy_class: Type,
          strategy_config: dict,
      ) -> BacktestResult:
          """Run backtest with given strategy."""
          logger.info("backtest_starting",
                      strategy=strategy_class.__name__,
                      start=self._config.start_date.isoformat(),
                      end=self._config.end_date.isoformat())

          # Load historical data
          data = await self._load_data()

          # Initialize context and strategy
          self._context = BacktestContext(
              initial_balance=self._config.initial_balance,
              fee_rate=self._config.fee_config.taker_rate,
              slippage_rate=Decimal("0.0005"),
          )

          strategy = strategy_class(strategy_config)
          await strategy.initialize(self._context)

          # Track equity curve
          equity_curve = []

          # Iterate through data
          for timestamp, row in data.iterrows():
              # Update market state
              prices = {
                  symbol: Decimal(str(row[f"{symbol}_close"]))
                  for symbol in self._config.symbols
                  if f"{symbol}_close" in row
              }
              self._context.set_market_state(timestamp, prices)

              # Create ticker for strategy
              for symbol in self._config.symbols:
                  if f"{symbol}_close" in row:
                      ticker = Ticker(
                          symbol=symbol,
                          bid=Decimal(str(row[f"{symbol}_close"])) * Decimal("0.9999"),
                          ask=Decimal(str(row[f"{symbol}_close"])) * Decimal("1.0001"),
                          last=Decimal(str(row[f"{symbol}_close"])),
                          timestamp=timestamp,
                      )
                      await strategy.on_tick(ticker)

              # Record equity
              equity_curve.append({
                  "timestamp": timestamp,
                  "equity": self._context.get_portfolio_value(),
              })

          # Shutdown strategy
          await strategy.shutdown()

          # Calculate results
          return self._calculate_results(strategy, equity_curve)
  ```
- [ ] Implement data loading:
  ```python
  async def _load_data(self) -> pd.DataFrame:
      """Load and merge OHLCV data for all symbols."""
      dfs = []

      for symbol in self._config.symbols:
          df = await self._data_provider.fetch(
              symbol=symbol,
              timeframe=self._config.timeframe,
              start=self._config.start_date,
              end=self._config.end_date,
          )
          # Prefix columns with symbol
          df = df.add_prefix(f"{symbol}_")
          dfs.append(df)

      # Merge on timestamp
      if len(dfs) == 1:
          return dfs[0]

      result = dfs[0]
      for df in dfs[1:]:
          result = result.join(df, how="outer")

      return result.fillna(method="ffill")
  ```
- [ ] Implement results calculation:
  ```python
  def _calculate_results(
      self,
      strategy,
      equity_curve: list[dict],
  ) -> BacktestResult:
      """Calculate backtest performance metrics."""
      trades = self._context.get_trade_history()
      equity_df = pd.DataFrame(equity_curve)

      # Basic metrics
      initial = self._config.initial_balance.get("USDT", Decimal(0))
      final = self._context.get_portfolio_value()
      total_return = (final - initial) / initial if initial > 0 else Decimal(0)

      # Trade analysis
      pnls = self._calculate_trade_pnls(trades)
      winning = [p for p in pnls if p > 0]
      losing = [p for p in pnls if p < 0]

      win_rate = Decimal(len(winning)) / len(pnls) if pnls else Decimal(0)

      gross_profit = sum(winning) if winning else Decimal(0)
      gross_loss = abs(sum(losing)) if losing else Decimal(1)
      profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal(0)

      # Drawdown
      equity_series = equity_df["equity"].astype(float)
      peak = equity_series.expanding().max()
      drawdown = (peak - equity_series) / peak
      max_drawdown = Decimal(str(drawdown.max()))

      # Sharpe ratio (assuming daily returns)
      returns = equity_series.pct_change().dropna()
      if len(returns) > 0 and returns.std() > 0:
          sharpe = Decimal(str((returns.mean() / returns.std()) * (252 ** 0.5)))
      else:
          sharpe = Decimal(0)

      return BacktestResult(
          config=self._config,
          strategy_name=strategy.name,
          start_date=self._config.start_date,
          end_date=self._config.end_date,
          initial_balance=initial,
          final_balance=final,
          total_return=total_return,
          total_trades=len(trades),
          winning_trades=len(winning),
          losing_trades=len(losing),
          win_rate=win_rate,
          profit_factor=profit_factor,
          max_drawdown=max_drawdown,
          sharpe_ratio=sharpe,
          equity_curve=equity_df,
          trades=trades,
      )

  def _calculate_trade_pnls(self, trades: list[dict]) -> list[Decimal]:
      """Calculate P&L for each completed trade cycle."""
      pnls = []
      open_trades: dict[str, dict] = {}

      for trade in trades:
          symbol = trade["symbol"]
          if trade["side"] == "buy":
              open_trades[symbol] = trade
          elif symbol in open_trades:
              buy = open_trades.pop(symbol)
              pnl = (
                  (trade["price"] - buy["price"]) * trade["amount"]
                  - trade["fee"] - buy["fee"]
              )
              pnls.append(pnl)

      return pnls
  ```
- [ ] Write integration tests

### Technical Notes
- Event-driven approach matches live trading behavior
- Equity curve recorded at each bar for analysis
- Trade P&L calculated per round-trip

### Definition of Done
- BacktestEngine runs strategies on historical data
- Results include all key metrics
- Equity curve generated
- Trade history captured

---

## Story 3.10: Implement Performance Metrics Calculator

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** developer
**I want** comprehensive performance metrics from backtests
**So that** strategies can be compared objectively

### Acceptance Criteria

- [ ] Create `src/crypto_bot/backtest/metrics.py`
- [ ] Implement metrics calculator:
  ```python
  import pandas as pd
  import numpy as np
  from decimal import Decimal
  from dataclasses import dataclass
  from typing import Optional

  @dataclass
  class PerformanceMetrics:
      # Returns
      total_return: Decimal
      annualized_return: Decimal
      monthly_returns: list[Decimal]

      # Risk metrics
      volatility: Decimal
      sharpe_ratio: Decimal
      sortino_ratio: Decimal
      calmar_ratio: Decimal
      max_drawdown: Decimal
      avg_drawdown: Decimal
      max_drawdown_duration_days: int

      # Trade metrics
      total_trades: int
      win_rate: Decimal
      profit_factor: Decimal
      avg_win: Decimal
      avg_loss: Decimal
      largest_win: Decimal
      largest_loss: Decimal
      avg_trade_duration_hours: Decimal
      expectancy: Decimal

      # Risk-adjusted
      risk_reward_ratio: Decimal
      recovery_factor: Decimal

  class MetricsCalculator:
      """Calculate comprehensive trading performance metrics."""

      def __init__(self, risk_free_rate: Decimal = Decimal("0.05")):
          self._risk_free_rate = risk_free_rate

      def calculate(
          self,
          equity_curve: pd.DataFrame,
          trades: list[dict],
          trading_days: int = 365,
      ) -> PerformanceMetrics:
          """Calculate all performance metrics."""
          returns = self._calculate_returns(equity_curve)
          trade_pnls = self._extract_trade_pnls(trades)

          return PerformanceMetrics(
              # Returns
              total_return=self._total_return(equity_curve),
              annualized_return=self._annualized_return(equity_curve, trading_days),
              monthly_returns=self._monthly_returns(equity_curve),

              # Risk
              volatility=self._volatility(returns, trading_days),
              sharpe_ratio=self._sharpe_ratio(returns, trading_days),
              sortino_ratio=self._sortino_ratio(returns, trading_days),
              calmar_ratio=self._calmar_ratio(equity_curve, trading_days),
              max_drawdown=self._max_drawdown(equity_curve),
              avg_drawdown=self._avg_drawdown(equity_curve),
              max_drawdown_duration_days=self._max_drawdown_duration(equity_curve),

              # Trades
              total_trades=len(trade_pnls),
              win_rate=self._win_rate(trade_pnls),
              profit_factor=self._profit_factor(trade_pnls),
              avg_win=self._avg_win(trade_pnls),
              avg_loss=self._avg_loss(trade_pnls),
              largest_win=max(trade_pnls) if trade_pnls else Decimal(0),
              largest_loss=min(trade_pnls) if trade_pnls else Decimal(0),
              avg_trade_duration_hours=self._avg_duration(trades),
              expectancy=self._expectancy(trade_pnls),

              # Risk-adjusted
              risk_reward_ratio=self._risk_reward(trade_pnls),
              recovery_factor=self._recovery_factor(equity_curve),
          )

      def _sharpe_ratio(self, returns: pd.Series, trading_days: int) -> Decimal:
          """Calculate annualized Sharpe ratio."""
          if len(returns) < 2 or returns.std() == 0:
              return Decimal(0)

          excess_returns = returns - (float(self._risk_free_rate) / trading_days)
          sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(trading_days)
          return Decimal(str(round(sharpe, 4)))

      def _sortino_ratio(self, returns: pd.Series, trading_days: int) -> Decimal:
          """Calculate Sortino ratio (downside deviation only)."""
          if len(returns) < 2:
              return Decimal(0)

          downside_returns = returns[returns < 0]
          if len(downside_returns) == 0 or downside_returns.std() == 0:
              return Decimal(0)

          excess_return = returns.mean() - (float(self._risk_free_rate) / trading_days)
          sortino = (excess_return / downside_returns.std()) * np.sqrt(trading_days)
          return Decimal(str(round(sortino, 4)))

      def _calmar_ratio(self, equity_curve: pd.DataFrame, trading_days: int) -> Decimal:
          """Calculate Calmar ratio (return / max drawdown)."""
          ann_return = float(self._annualized_return(equity_curve, trading_days))
          max_dd = float(self._max_drawdown(equity_curve))

          if max_dd == 0:
              return Decimal(0)

          return Decimal(str(round(ann_return / max_dd, 4)))

      def _expectancy(self, pnls: list[Decimal]) -> Decimal:
          """Calculate trade expectancy (average profit per trade)."""
          if not pnls:
              return Decimal(0)

          wins = [p for p in pnls if p > 0]
          losses = [p for p in pnls if p < 0]

          win_rate = len(wins) / len(pnls)
          avg_win = sum(wins) / len(wins) if wins else Decimal(0)
          avg_loss = abs(sum(losses) / len(losses)) if losses else Decimal(0)

          expectancy = (win_rate * float(avg_win)) - ((1 - win_rate) * float(avg_loss))
          return Decimal(str(round(expectancy, 4)))
  ```
- [ ] Implement report generation:
  ```python
  def generate_report(
      self,
      result: BacktestResult,
      metrics: PerformanceMetrics,
      output_format: str = "markdown",
  ) -> str:
      """Generate human-readable performance report."""
      if output_format == "markdown":
          return self._markdown_report(result, metrics)
      elif output_format == "json":
          return self._json_report(result, metrics)
      else:
          raise ValueError(f"Unknown format: {output_format}")

  def _markdown_report(self, result: BacktestResult, metrics: PerformanceMetrics) -> str:
      return f"""
  # Backtest Report: {result.strategy_name}

  ## Summary
  - **Period:** {result.start_date.date()} to {result.end_date.date()}
  - **Initial Balance:** ${result.initial_balance:,.2f}
  - **Final Balance:** ${result.final_balance:,.2f}
  - **Total Return:** {metrics.total_return:.2%}
  - **Annualized Return:** {metrics.annualized_return:.2%}

  ## Risk Metrics
  | Metric | Value |
  |--------|-------|
  | Sharpe Ratio | {metrics.sharpe_ratio:.2f} |
  | Sortino Ratio | {metrics.sortino_ratio:.2f} |
  | Calmar Ratio | {metrics.calmar_ratio:.2f} |
  | Max Drawdown | {metrics.max_drawdown:.2%} |
  | Volatility | {metrics.volatility:.2%} |

  ## Trade Statistics
  | Metric | Value |
  |--------|-------|
  | Total Trades | {metrics.total_trades} |
  | Win Rate | {metrics.win_rate:.2%} |
  | Profit Factor | {metrics.profit_factor:.2f} |
  | Expectancy | ${metrics.expectancy:,.2f} |
  | Avg Win | ${metrics.avg_win:,.2f} |
  | Avg Loss | ${metrics.avg_loss:,.2f} |
  """
  ```
- [ ] Export results to CSV/JSON
- [ ] Write tests for metrics calculations

### Definition of Done
- All metrics calculated correctly
- Report generation in multiple formats
- Export functionality working
- Tests validate calculations

---

## Story 3.11: Create Parameter Optimization Framework

**Story Points:** 8
**Priority:** P2 - Medium

### Description
**As a** developer
**I want** parameter optimization for strategy tuning
**So that** optimal parameters can be discovered systematically

### Background
[VectorBT](https://vectorbt.dev/) can test thousands of parameter combinations quickly due to vectorization. For event-driven backtests, grid search or Bayesian optimization are alternatives.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/backtest/optimization.py`
- [ ] Implement grid search optimizer:
  ```python
  from itertools import product
  from typing import Any, Callable
  from dataclasses import dataclass
  import asyncio

  @dataclass
  class OptimizationResult:
      best_params: dict[str, Any]
      best_score: Decimal
      all_results: list[tuple[dict, Decimal]]
      optimization_metric: str

  class GridSearchOptimizer:
      """Brute-force grid search over parameter space."""

      def __init__(
          self,
          engine: BacktestEngine,
          strategy_class: Type,
          param_grid: dict[str, list[Any]],
          optimization_metric: str = "sharpe_ratio",
          n_parallel: int = 4,
      ):
          self._engine = engine
          self._strategy_class = strategy_class
          self._param_grid = param_grid
          self._metric = optimization_metric
          self._n_parallel = n_parallel

      async def optimize(self) -> OptimizationResult:
          """Run grid search optimization."""
          # Generate all parameter combinations
          param_names = list(self._param_grid.keys())
          param_values = list(self._param_grid.values())
          combinations = list(product(*param_values))

          logger.info("optimization_starting",
                      total_combinations=len(combinations),
                      metric=self._metric)

          results: list[tuple[dict, Decimal]] = []

          # Run backtests in parallel batches
          for i in range(0, len(combinations), self._n_parallel):
              batch = combinations[i:i + self._n_parallel]
              tasks = []

              for combo in batch:
                  params = dict(zip(param_names, combo))
                  tasks.append(self._run_single(params))

              batch_results = await asyncio.gather(*tasks)
              results.extend(batch_results)

              logger.info("optimization_progress",
                          completed=len(results),
                          total=len(combinations))

          # Find best result
          results.sort(key=lambda x: x[1], reverse=True)
          best_params, best_score = results[0]

          logger.info("optimization_complete",
                      best_params=best_params,
                      best_score=float(best_score))

          return OptimizationResult(
              best_params=best_params,
              best_score=best_score,
              all_results=results,
              optimization_metric=self._metric,
          )

      async def _run_single(self, params: dict) -> tuple[dict, Decimal]:
          """Run single backtest with given parameters."""
          result = await self._engine.run(
              strategy_class=self._strategy_class,
              strategy_config=params,
          )

          score = getattr(result, self._metric, Decimal(0))
          return params, score
  ```
- [ ] Implement walk-forward optimization:
  ```python
  class WalkForwardOptimizer:
      """Walk-forward optimization for out-of-sample validation."""

      def __init__(
          self,
          engine: BacktestEngine,
          strategy_class: Type,
          param_grid: dict[str, list[Any]],
          in_sample_pct: float = 0.7,
          n_folds: int = 5,
      ):
          self._engine = engine
          self._strategy_class = strategy_class
          self._param_grid = param_grid
          self._in_sample_pct = in_sample_pct
          self._n_folds = n_folds

      async def optimize(self) -> list[OptimizationResult]:
          """Run walk-forward optimization."""
          results = []

          # Split data into folds
          total_days = (
              self._engine._config.end_date - self._engine._config.start_date
          ).days
          fold_size = total_days // self._n_folds

          for fold in range(self._n_folds):
              fold_start = self._engine._config.start_date + timedelta(days=fold * fold_size)
              fold_end = fold_start + timedelta(days=fold_size)

              # Split into in-sample and out-of-sample
              in_sample_days = int(fold_size * self._in_sample_pct)
              in_sample_end = fold_start + timedelta(days=in_sample_days)

              # Optimize on in-sample
              in_sample_engine = BacktestEngine(
                  self._engine._data_provider,
                  BacktestConfig(
                      start_date=fold_start,
                      end_date=in_sample_end,
                      **self._engine._config.__dict__
                  )
              )
              grid_opt = GridSearchOptimizer(
                  in_sample_engine,
                  self._strategy_class,
                  self._param_grid,
              )
              opt_result = await grid_opt.optimize()

              # Validate on out-of-sample
              out_sample_engine = BacktestEngine(
                  self._engine._data_provider,
                  BacktestConfig(
                      start_date=in_sample_end,
                      end_date=fold_end,
                      **self._engine._config.__dict__
                  )
              )
              validation = await out_sample_engine.run(
                  self._strategy_class,
                  opt_result.best_params,
              )

              results.append({
                  "fold": fold,
                  "best_params": opt_result.best_params,
                  "in_sample_score": opt_result.best_score,
                  "out_sample_score": validation.sharpe_ratio,
              })

          return results
  ```
- [ ] Add result visualization helpers
- [ ] Write tests for optimization

### Technical Notes
- Grid search tests all combinations (exponential complexity)
- Walk-forward validates on out-of-sample data
- Parallel execution speeds up optimization
- Be wary of overfitting

### Definition of Done
- Grid search optimizer working
- Walk-forward optimization implemented
- Results include in-sample and out-of-sample metrics
- Tests verify optimization logic

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 3.6 Execution Context Interface | 3 | P0 | Phase 2 |
| 3.7 Backtest Execution Context | 8 | P0 | 3.6 |
| 3.8 Fee and Slippage Simulation | 5 | P0 | 3.7 |
| 3.9 Backtest Engine | 8 | P0 | 3.7, 3.8 |
| 3.10 Performance Metrics | 5 | P1 | 3.9 |
| 3.11 Parameter Optimization | 8 | P2 | 3.9 |
| **Total** | **37** | | |

---

## Sources & References

- [VectorBT Documentation](https://vectorbt.dev/)
- [From Backtest to Live with VectorBT 2025](https://medium.com/@samuel.tinnerholm/from-backtest-to-live-going-live-with-vectorbt-in-2025-step-by-step-guide-681ff5e3376e)
- [Comparing VectorBT, Zipline, and Backtrader](https://medium.com/@trading.dude/battle-tested-backtesters-comparing-vectorbt-zipline-and-backtrader-for-financial-strategy-dee33d33a9e0)
- [Backtrader Documentation](https://www.backtrader.com/)
- [AsyncAlgoTrading Framework](https://github.com/AsyncAlgoTrading/aat)
- [AI Trading Bot Risk Management 2025](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025)
