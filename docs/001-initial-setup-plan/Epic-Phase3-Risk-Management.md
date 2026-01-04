# Epic: Phase 3A - Risk Management

**Epic Owner:** Development Team
**Priority:** Critical - Prevents catastrophic losses
**Dependencies:** Phase 2 (Strategy Framework, Data Persistence)

---

## Overview

Risk management is the foundation of sustainable trading. This epic implements multi-layer protection including position sizing, stop-losses, circuit breakers, and drawdown controls to prevent catastrophic losses during adverse market conditions.

### Key Deliverables
- Position sizing algorithms (Fixed Fractional, Kelly Criterion)
- Adaptive stop-loss handlers (fixed, percentage, trailing, ATR-based)
- Circuit breaker system with multiple trigger conditions
- Drawdown tracking and protection
- Risk manager orchestrating all components

### Research & Best Practices Applied

Based on current 2025 best practices:
- **Position Sizing:** [1-2% risk per trade](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025) is industry standard
- **Stop-Losses:** [Adaptive ATR-based stops](https://www.alwin.io/risk-management-strategies) outperform static percentages in volatile crypto markets
- **Circuit Breakers:** [5% daily loss limit](https://3commas.io/blog/ai-trading-bot-risk-management-guide) is recommended threshold
- **Risk/Reward:** Minimum 2:1 ratio enforced before trade entry

---

## Story 3.1: Implement Position Sizing Algorithms

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** systematic position sizing based on account balance and risk tolerance
**So that** no single trade can cause outsized losses

### Background
Per [2025 risk management best practices](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025), the fixed percentage method (risking 1-2% per trade) ensures that no single trade can significantly impact your portfolio.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/risk/position_sizer.py`
- [ ] Implement Fixed Fractional position sizing:
  ```python
  from decimal import Decimal
  from dataclasses import dataclass

  @dataclass
  class PositionSize:
      """Result of position size calculation."""
      amount: Decimal
      risk_amount: Decimal
      position_value: Decimal
      risk_pct_actual: Decimal

  class FixedFractionalSizer:
      """Position sizing using fixed percentage of capital at risk."""

      def __init__(self, risk_pct: Decimal = Decimal("0.02")):
          """
          Args:
              risk_pct: Percentage of capital to risk per trade (default 2%)
          """
          if not Decimal("0.001") <= risk_pct <= Decimal("0.10"):
              raise ValueError("risk_pct must be between 0.1% and 10%")
          self._risk_pct = risk_pct

      def calculate(
          self,
          balance: Decimal,
          entry_price: Decimal,
          stop_loss_price: Decimal,
      ) -> PositionSize:
          """Calculate position size based on risk parameters."""
          risk_amount = balance * self._risk_pct
          price_risk = abs(entry_price - stop_loss_price)

          if price_risk == 0:
              raise ValueError("Stop loss cannot equal entry price")

          amount = risk_amount / price_risk
          position_value = amount * entry_price

          return PositionSize(
              amount=amount,
              risk_amount=risk_amount,
              position_value=position_value,
              risk_pct_actual=self._risk_pct,
          )
  ```
- [ ] Implement Kelly Criterion with fractional variants:
  ```python
  class KellySizer:
      """Position sizing using Kelly Criterion."""

      def __init__(self, fraction: Decimal = Decimal("0.5")):
          """
          Args:
              fraction: Kelly fraction (0.5 = half-Kelly, 0.25 = quarter-Kelly)
          """
          self._fraction = fraction

      def calculate_kelly(
          self,
          win_rate: Decimal,
          avg_win: Decimal,
          avg_loss: Decimal,
      ) -> Decimal:
          """Calculate Kelly fraction for position sizing."""
          if avg_loss == 0:
              return Decimal(0)

          win_loss_ratio = avg_win / avg_loss
          kelly = win_rate - ((1 - win_rate) / win_loss_ratio)

          # Apply fractional Kelly and clamp to reasonable range
          adjusted = max(Decimal(0), kelly * self._fraction)
          return min(adjusted, Decimal("0.25"))  # Cap at 25%

      def calculate(
          self,
          balance: Decimal,
          entry_price: Decimal,
          win_rate: Decimal,
          avg_win: Decimal,
          avg_loss: Decimal,
      ) -> PositionSize:
          """Calculate position size using Kelly Criterion."""
          kelly_pct = self.calculate_kelly(win_rate, avg_win, avg_loss)
          risk_amount = balance * kelly_pct
          amount = risk_amount / entry_price

          return PositionSize(
              amount=amount,
              risk_amount=risk_amount,
              position_value=amount * entry_price,
              risk_pct_actual=kelly_pct,
          )
  ```
- [ ] Implement grid-specific allocation (reserve capital):
  ```python
  class GridPositionSizer:
      """Position sizing optimized for grid trading."""

      def __init__(
          self,
          allocation_pct: Decimal = Decimal("0.80"),  # 80% to grid
          reserve_pct: Decimal = Decimal("0.20"),      # 20% reserve
      ):
          self._allocation_pct = allocation_pct
          self._reserve_pct = reserve_pct

      def calculate_per_grid(
          self,
          balance: Decimal,
          num_grids: int,
          active_grids: int,
      ) -> Decimal:
          """Calculate amount per grid level."""
          allocated_capital = balance * self._allocation_pct
          return allocated_capital / active_grids
  ```
- [ ] Add position limits validation:
  ```python
  def validate_position(
      self,
      position_size: PositionSize,
      balance: Decimal,
      max_position_pct: Decimal = Decimal("0.20"),
  ) -> list[str]:
      """Validate position size against limits."""
      warnings = []

      if position_size.position_value > balance * max_position_pct:
          warnings.append(
              f"Position exceeds {max_position_pct:.0%} of balance"
          )

      if position_size.risk_pct_actual > Decimal("0.05"):
          warnings.append(
              f"Risk {position_size.risk_pct_actual:.1%} exceeds 5% threshold"
          )

      return warnings
  ```
- [ ] Write comprehensive unit tests

### Technical Notes
- Half-Kelly or quarter-Kelly recommended over full Kelly (less volatile equity curve)
- Grid trading should reserve 20% capital for volatility spikes
- Maximum 20% of portfolio in single position regardless of calculation

### Definition of Done
- Fixed Fractional and Kelly siziers implemented
- Grid-specific allocation with reserve capital
- Position limits enforced
- Unit tests achieve >90% coverage

---

## Story 3.2: Build Stop-Loss Handler

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** automated stop-loss execution with multiple strategies
**So that** positions are closed when price moves against me

### Background
Per [2025 best practices](https://www.alwin.io/risk-management-strategies), static 5% stop-losses don't work in crypto where BTC can move ±8% daily. Adaptive approaches like ATR-based stops adjust to volatility.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/risk/stop_loss.py`
- [ ] Define stop-loss types:
  ```python
  from enum import Enum
  from decimal import Decimal
  from dataclasses import dataclass
  from typing import Optional
  from datetime import datetime

  class StopLossType(str, Enum):
      FIXED = "fixed"           # Fixed price level
      PERCENTAGE = "percentage" # Percentage from entry
      TRAILING = "trailing"     # Trailing stop
      ATR = "atr"              # ATR-based adaptive

  @dataclass
  class StopLossConfig:
      type: StopLossType
      value: Decimal  # Price, percentage, or ATR multiplier
      trailing_activation: Optional[Decimal] = None  # Activate trailing after X% profit

  @dataclass
  class StopLossState:
      config: StopLossConfig
      entry_price: Decimal
      current_stop: Decimal
      highest_price: Decimal  # For trailing
      triggered: bool = False
      triggered_at: Optional[datetime] = None
  ```
- [ ] Implement fixed and percentage stop-loss:
  ```python
  class StopLossHandler:
      """Handles stop-loss calculation and monitoring."""

      def __init__(self, config: StopLossConfig):
          self._config = config
          self._state: Optional[StopLossState] = None

      def initialize(self, entry_price: Decimal, side: str) -> StopLossState:
          """Initialize stop-loss for a new position."""
          if self._config.type == StopLossType.FIXED:
              stop_price = self._config.value
          elif self._config.type == StopLossType.PERCENTAGE:
              if side == "buy":
                  stop_price = entry_price * (1 - self._config.value)
              else:
                  stop_price = entry_price * (1 + self._config.value)
          else:
              stop_price = self._calculate_initial_stop(entry_price, side)

          self._state = StopLossState(
              config=self._config,
              entry_price=entry_price,
              current_stop=stop_price,
              highest_price=entry_price,
          )
          return self._state
  ```
- [ ] Implement trailing stop-loss:
  ```python
  def update_trailing(self, current_price: Decimal, side: str) -> bool:
      """Update trailing stop based on price movement."""
      if self._config.type != StopLossType.TRAILING:
          return False

      if side == "buy":
          # Long position - trail below highest price
          if current_price > self._state.highest_price:
              self._state.highest_price = current_price
              new_stop = current_price * (1 - self._config.value)
              if new_stop > self._state.current_stop:
                  self._state.current_stop = new_stop
                  logger.info("trailing_stop_updated",
                              new_stop=str(new_stop),
                              highest=str(current_price))
                  return True
      else:
          # Short position - trail above lowest price
          if current_price < self._state.highest_price:
              self._state.highest_price = current_price
              new_stop = current_price * (1 + self._config.value)
              if new_stop < self._state.current_stop:
                  self._state.current_stop = new_stop
                  return True

      return False
  ```
- [ ] Implement ATR-based adaptive stop:
  ```python
  def calculate_atr_stop(
      self,
      entry_price: Decimal,
      atr: Decimal,
      multiplier: Decimal = Decimal("2.0"),
      side: str = "buy",
  ) -> Decimal:
      """Calculate stop-loss based on Average True Range."""
      atr_distance = atr * multiplier

      if side == "buy":
          return entry_price - atr_distance
      else:
          return entry_price + atr_distance

  async def update_atr_stop(
      self,
      current_price: Decimal,
      atr: Decimal,
      side: str,
  ) -> None:
      """Update ATR-based stop with new volatility data."""
      if self._config.type != StopLossType.ATR:
          return

      new_stop = self.calculate_atr_stop(
          self._state.highest_price,
          atr,
          self._config.value,
          side,
      )

      # Only move stop in favorable direction
      if side == "buy" and new_stop > self._state.current_stop:
          self._state.current_stop = new_stop
      elif side == "sell" and new_stop < self._state.current_stop:
          self._state.current_stop = new_stop
  ```
- [ ] Implement stop-loss check and trigger:
  ```python
  def check_stop(self, current_price: Decimal, side: str) -> bool:
      """Check if stop-loss should trigger."""
      if self._state.triggered:
          return False

      triggered = False
      if side == "buy":
          triggered = current_price <= self._state.current_stop
      else:
          triggered = current_price >= self._state.current_stop

      if triggered:
          self._state.triggered = True
          self._state.triggered_at = datetime.utcnow()
          logger.warning("stop_loss_triggered",
                        current_price=str(current_price),
                        stop_price=str(self._state.current_stop),
                        side=side)

      return triggered

  async def execute_stop(
      self,
      context: ExecutionContext,
      symbol: str,
      amount: Decimal,
      side: str,
  ) -> str:
      """Execute stop-loss market order."""
      close_side = "sell" if side == "buy" else "buy"
      order_id = await context.place_order(
          symbol=symbol,
          side=close_side,
          amount=amount,
          price=None,  # Market order
      )
      logger.info("stop_loss_executed", order_id=order_id, amount=str(amount))
      return order_id
  ```
- [ ] Add grid-specific stop-loss (below lower boundary):
  ```python
  class GridStopLoss:
      """Stop-loss handler for grid trading."""

      def __init__(self, lower_grid_price: Decimal, buffer_pct: Decimal = Decimal("0.10")):
          """
          Args:
              lower_grid_price: Lowest grid price level
              buffer_pct: Buffer below lower grid (default 10%)
          """
          self._stop_price = lower_grid_price * (1 - buffer_pct)

      @property
      def stop_price(self) -> Decimal:
          return self._stop_price

      def check(self, current_price: Decimal) -> bool:
          """Check if price breached grid stop-loss."""
          return current_price <= self._stop_price
  ```
- [ ] Write tests for all stop-loss types

### Technical Notes
- ATR-based stops adapt to market volatility automatically
- Trailing stops should only move in favorable direction (never backwards)
- Grid stop-loss typically 5-10% below lower grid boundary
- Market orders for stop execution (guaranteed fill)

### Definition of Done
- All stop-loss types implemented (fixed, percentage, trailing, ATR)
- Trailing stop updates correctly on price movement
- Grid-specific stop-loss working
- Stop execution uses market orders
- Unit tests cover all scenarios

---

## Story 3.3: Implement Circuit Breaker System

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** automatic trading pause when risk limits are breached
**So that** losses don't compound during adverse market conditions

### Background
Per [2025 best practices](https://3commas.io/blog/ai-trading-bot-risk-management-guide), circuit breakers halt trading when markets behave abnormally. Triggers include daily loss exceeding 5%, consecutive losses, and abnormal conditions.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/risk/circuit_breaker.py`
- [ ] Define circuit breaker configuration:
  ```python
  from pydantic import BaseModel, Field
  from decimal import Decimal
  from datetime import datetime, timedelta
  from enum import Enum

  class CircuitBreakerTrigger(str, Enum):
      DAILY_LOSS = "daily_loss"
      CONSECUTIVE_LOSSES = "consecutive_losses"
      MAX_DRAWDOWN = "max_drawdown"
      MANUAL = "manual"
      ERROR_RATE = "error_rate"

  class CircuitBreakerConfig(BaseModel):
      max_daily_loss_pct: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
      max_consecutive_losses: int = Field(default=5, ge=1, le=20)
      max_drawdown_pct: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
      max_error_rate: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
      cooldown_minutes: int = Field(default=60, ge=5, le=1440)
      auto_reset_daily: bool = True
  ```
- [ ] Implement circuit breaker state tracking:
  ```python
  @dataclass
  class CircuitBreakerState:
      is_tripped: bool = False
      trigger: Optional[CircuitBreakerTrigger] = None
      tripped_at: Optional[datetime] = None
      cooldown_until: Optional[datetime] = None

      # Daily tracking
      daily_pnl: Decimal = Decimal(0)
      daily_trades: int = 0
      daily_errors: int = 0
      day_start: datetime = field(default_factory=lambda: datetime.utcnow().replace(
          hour=0, minute=0, second=0, microsecond=0
      ))

      # Consecutive tracking
      consecutive_losses: int = 0
      consecutive_wins: int = 0

      # Drawdown tracking
      peak_equity: Decimal = Decimal(0)
      current_equity: Decimal = Decimal(0)
      current_drawdown: Decimal = Decimal(0)

  class CircuitBreaker:
      """Multi-condition circuit breaker for trading protection."""

      def __init__(self, config: CircuitBreakerConfig):
          self._config = config
          self._state = CircuitBreakerState()
          self._alerter: Optional[AlertManager] = None

      def set_alerter(self, alerter: AlertManager) -> None:
          """Set alerter for notifications."""
          self._alerter = alerter

      @property
      def is_trading_allowed(self) -> bool:
          """Check if trading is currently allowed."""
          if self._state.is_tripped:
              # Check if cooldown has passed
              if self._state.cooldown_until and datetime.utcnow() >= self._state.cooldown_until:
                  self._reset()
                  return True
              return False
          return True
  ```
- [ ] Implement trade recording and limit checking:
  ```python
  def record_trade(self, pnl: Decimal, equity: Decimal) -> Optional[CircuitBreakerTrigger]:
      """Record trade result and check limits."""
      self._maybe_reset_daily()
      self._state.daily_trades += 1
      self._state.daily_pnl += pnl
      self._state.current_equity = equity

      # Update peak equity and drawdown
      if equity > self._state.peak_equity:
          self._state.peak_equity = equity
      self._state.current_drawdown = (
          (self._state.peak_equity - equity) / self._state.peak_equity
          if self._state.peak_equity > 0 else Decimal(0)
      )

      # Track consecutive losses/wins
      if pnl < 0:
          self._state.consecutive_losses += 1
          self._state.consecutive_wins = 0
      else:
          self._state.consecutive_wins += 1
          self._state.consecutive_losses = 0

      # Check all limits
      return self._check_limits()

  def _check_limits(self) -> Optional[CircuitBreakerTrigger]:
      """Check all circuit breaker conditions."""
      trigger = None

      # Daily loss limit
      daily_loss_pct = abs(self._state.daily_pnl) / self._state.peak_equity
      if self._state.daily_pnl < 0 and daily_loss_pct >= self._config.max_daily_loss_pct:
          trigger = CircuitBreakerTrigger.DAILY_LOSS
          logger.warning("circuit_breaker_daily_loss",
                        daily_loss_pct=f"{daily_loss_pct:.2%}",
                        limit=f"{self._config.max_daily_loss_pct:.2%}")

      # Consecutive losses
      elif self._state.consecutive_losses >= self._config.max_consecutive_losses:
          trigger = CircuitBreakerTrigger.CONSECUTIVE_LOSSES
          logger.warning("circuit_breaker_consecutive_losses",
                        count=self._state.consecutive_losses)

      # Max drawdown
      elif self._state.current_drawdown >= self._config.max_drawdown_pct:
          trigger = CircuitBreakerTrigger.MAX_DRAWDOWN
          logger.warning("circuit_breaker_max_drawdown",
                        drawdown=f"{self._state.current_drawdown:.2%}",
                        limit=f"{self._config.max_drawdown_pct:.2%}")

      if trigger:
          self._trip(trigger)

      return trigger
  ```
- [ ] Implement trip and reset logic:
  ```python
  def _trip(self, trigger: CircuitBreakerTrigger) -> None:
      """Trip the circuit breaker."""
      self._state.is_tripped = True
      self._state.trigger = trigger
      self._state.tripped_at = datetime.utcnow()
      self._state.cooldown_until = (
          datetime.utcnow() + timedelta(minutes=self._config.cooldown_minutes)
      )

      logger.error("circuit_breaker_tripped",
                  trigger=trigger.value,
                  cooldown_until=self._state.cooldown_until.isoformat())

      # Send alert
      if self._alerter:
          asyncio.create_task(self._alerter.send_critical(
              f"Circuit breaker tripped: {trigger.value}",
              {
                  "daily_pnl": str(self._state.daily_pnl),
                  "consecutive_losses": self._state.consecutive_losses,
                  "drawdown": f"{self._state.current_drawdown:.2%}",
              }
          ))

  def _reset(self) -> None:
      """Reset circuit breaker state."""
      logger.info("circuit_breaker_reset")
      self._state.is_tripped = False
      self._state.trigger = None
      self._state.tripped_at = None
      self._state.cooldown_until = None
      self._state.consecutive_losses = 0

  def manual_reset(self) -> None:
      """Manually reset circuit breaker (requires confirmation)."""
      logger.warning("circuit_breaker_manual_reset")
      self._reset()

  def manual_trip(self, reason: str) -> None:
      """Manually trip circuit breaker."""
      logger.warning("circuit_breaker_manual_trip", reason=reason)
      self._trip(CircuitBreakerTrigger.MANUAL)
  ```
- [ ] Add error rate tracking:
  ```python
  def record_error(self) -> Optional[CircuitBreakerTrigger]:
      """Record an error and check error rate limit."""
      self._state.daily_errors += 1

      if self._state.daily_trades > 0:
          error_rate = Decimal(self._state.daily_errors) / self._state.daily_trades
          if error_rate >= self._config.max_error_rate:
              self._trip(CircuitBreakerTrigger.ERROR_RATE)
              return CircuitBreakerTrigger.ERROR_RATE

      return None
  ```
- [ ] Write comprehensive tests

### Technical Notes
- Circuit breaker should pause trading, not exit positions
- Cooldown period prevents immediate re-entry
- Daily reset at midnight UTC
- Alert on every trip event

### Definition of Done
- All trigger conditions implemented
- Cooldown mechanism working
- Manual trip/reset functionality
- Alerts sent on trip
- Unit tests cover all scenarios

---

## Story 3.4: Create Drawdown Calculator and Tracker

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** trader
**I want** real-time drawdown tracking with historical analysis
**So that** I can monitor risk exposure and evaluate strategy performance

### Acceptance Criteria

- [ ] Create `src/crypto_bot/risk/drawdown.py`
- [ ] Implement drawdown calculator:
  ```python
  from decimal import Decimal
  from dataclasses import dataclass, field
  from datetime import datetime
  from typing import Optional
  from collections import deque

  @dataclass
  class DrawdownMetrics:
      current_drawdown: Decimal
      current_drawdown_pct: Decimal
      max_drawdown: Decimal
      max_drawdown_pct: Decimal
      max_drawdown_date: Optional[datetime]
      peak_equity: Decimal
      current_equity: Decimal
      recovery_needed_pct: Decimal  # % gain needed to recover

  @dataclass
  class DrawdownPeriod:
      start_date: datetime
      end_date: Optional[datetime]
      peak_equity: Decimal
      trough_equity: Decimal
      drawdown_pct: Decimal
      duration_days: int
      recovered: bool

  class DrawdownTracker:
      """Tracks drawdown metrics over time."""

      def __init__(self, initial_equity: Decimal):
          self._peak_equity = initial_equity
          self._current_equity = initial_equity
          self._max_drawdown = Decimal(0)
          self._max_drawdown_pct = Decimal(0)
          self._max_drawdown_date: Optional[datetime] = None

          # Track drawdown periods
          self._current_period: Optional[DrawdownPeriod] = None
          self._historical_periods: list[DrawdownPeriod] = []

          # Equity history for analysis
          self._equity_history: deque[tuple[datetime, Decimal]] = deque(maxlen=10000)

      def update(self, equity: Decimal, timestamp: Optional[datetime] = None) -> DrawdownMetrics:
          """Update with new equity value."""
          timestamp = timestamp or datetime.utcnow()
          self._current_equity = equity
          self._equity_history.append((timestamp, equity))

          # Update peak
          if equity > self._peak_equity:
              self._peak_equity = equity
              # End current drawdown period if any
              if self._current_period:
                  self._current_period.end_date = timestamp
                  self._current_period.recovered = True
                  self._historical_periods.append(self._current_period)
                  self._current_period = None

          # Calculate current drawdown
          current_dd = self._peak_equity - equity
          current_dd_pct = current_dd / self._peak_equity if self._peak_equity > 0 else Decimal(0)

          # Track max drawdown
          if current_dd_pct > self._max_drawdown_pct:
              self._max_drawdown = current_dd
              self._max_drawdown_pct = current_dd_pct
              self._max_drawdown_date = timestamp

          # Start new drawdown period if needed
          if current_dd_pct > 0 and not self._current_period:
              self._current_period = DrawdownPeriod(
                  start_date=timestamp,
                  end_date=None,
                  peak_equity=self._peak_equity,
                  trough_equity=equity,
                  drawdown_pct=current_dd_pct,
                  duration_days=0,
                  recovered=False,
              )
          elif self._current_period and equity < self._current_period.trough_equity:
              self._current_period.trough_equity = equity
              self._current_period.drawdown_pct = current_dd_pct

          # Calculate recovery needed
          recovery_needed = (
              (self._peak_equity / equity - 1) if equity > 0 else Decimal(0)
          )

          return DrawdownMetrics(
              current_drawdown=current_dd,
              current_drawdown_pct=current_dd_pct,
              max_drawdown=self._max_drawdown,
              max_drawdown_pct=self._max_drawdown_pct,
              max_drawdown_date=self._max_drawdown_date,
              peak_equity=self._peak_equity,
              current_equity=self._current_equity,
              recovery_needed_pct=recovery_needed,
          )
  ```
- [ ] Add analysis methods:
  ```python
  def get_drawdown_periods(self, min_drawdown_pct: Decimal = Decimal("0.05")) -> list[DrawdownPeriod]:
      """Get historical drawdown periods exceeding threshold."""
      return [
          p for p in self._historical_periods
          if p.drawdown_pct >= min_drawdown_pct
      ]

  def get_equity_curve(self) -> list[tuple[datetime, Decimal]]:
      """Get equity history for charting."""
      return list(self._equity_history)

  def get_statistics(self) -> dict:
      """Calculate drawdown statistics."""
      periods = self.get_drawdown_periods()
      if not periods:
          return {}

      durations = [p.duration_days for p in periods]
      drawdowns = [p.drawdown_pct for p in periods]

      return {
          "num_drawdown_periods": len(periods),
          "avg_drawdown_pct": sum(drawdowns) / len(drawdowns),
          "max_drawdown_pct": max(drawdowns),
          "avg_duration_days": sum(durations) / len(durations),
          "max_duration_days": max(durations),
      }
  ```
- [ ] Write tests for drawdown tracking

### Technical Notes
- Track both absolute and percentage drawdown
- Maintain history for analysis
- Recovery percentage shows how far from break-even

### Definition of Done
- Drawdown tracker updates correctly
- Max drawdown tracked over time
- Drawdown periods recorded
- Statistics calculation working
- Unit tests pass

---

## Story 3.5: Build Risk Manager Orchestrator

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a central risk manager coordinating all risk components
**So that** risk checks happen consistently before and after every trade

### Acceptance Criteria

- [ ] Create `src/crypto_bot/risk/risk_manager.py`
- [ ] Implement risk manager:
  ```python
  from typing import Optional
  from decimal import Decimal
  import structlog

  logger = structlog.get_logger()

  @dataclass
  class TradeValidation:
      allowed: bool
      position_size: Optional[PositionSize]
      stop_loss_price: Optional[Decimal]
      warnings: list[str]
      rejection_reason: Optional[str]

  class RiskManager:
      """Central risk management orchestrator."""

      def __init__(
          self,
          position_sizer: FixedFractionalSizer,
          circuit_breaker: CircuitBreaker,
          drawdown_tracker: DrawdownTracker,
          config: RiskConfig,
      ):
          self._position_sizer = position_sizer
          self._circuit_breaker = circuit_breaker
          self._drawdown_tracker = drawdown_tracker
          self._config = config
          self._stop_handlers: dict[str, StopLossHandler] = {}

      async def validate_trade(
          self,
          symbol: str,
          side: str,
          entry_price: Decimal,
          balance: Decimal,
          stop_loss_pct: Optional[Decimal] = None,
      ) -> TradeValidation:
          """Validate trade before execution."""
          warnings: list[str] = []

          # Check circuit breaker
          if not self._circuit_breaker.is_trading_allowed:
              return TradeValidation(
                  allowed=False,
                  position_size=None,
                  stop_loss_price=None,
                  warnings=[],
                  rejection_reason="Circuit breaker is tripped",
              )

          # Check drawdown limit
          metrics = self._drawdown_tracker.update(balance)
          if metrics.current_drawdown_pct >= self._config.max_drawdown_warning:
              warnings.append(
                  f"Drawdown at {metrics.current_drawdown_pct:.1%}, "
                  f"approaching limit of {self._config.max_drawdown_limit:.1%}"
              )

          # Calculate stop-loss price
          stop_loss_pct = stop_loss_pct or self._config.default_stop_loss_pct
          if side == "buy":
              stop_loss_price = entry_price * (1 - stop_loss_pct)
          else:
              stop_loss_price = entry_price * (1 + stop_loss_pct)

          # Calculate position size
          try:
              position_size = self._position_sizer.calculate(
                  balance=balance,
                  entry_price=entry_price,
                  stop_loss_price=stop_loss_price,
              )
          except ValueError as e:
              return TradeValidation(
                  allowed=False,
                  position_size=None,
                  stop_loss_price=None,
                  warnings=[],
                  rejection_reason=str(e),
              )

          # Validate position limits
          position_warnings = self._position_sizer.validate_position(
              position_size, balance, self._config.max_position_pct
          )
          warnings.extend(position_warnings)

          # Check risk/reward ratio
          # (would need take-profit price for full calculation)

          logger.info("trade_validated",
                      symbol=symbol,
                      side=side,
                      amount=str(position_size.amount),
                      stop_loss=str(stop_loss_price),
                      warnings=warnings)

          return TradeValidation(
              allowed=True,
              position_size=position_size,
              stop_loss_price=stop_loss_price,
              warnings=warnings,
              rejection_reason=None,
          )
  ```
- [ ] Implement post-trade recording:
  ```python
  async def record_trade_result(
      self,
      symbol: str,
      pnl: Decimal,
      equity: Decimal,
  ) -> Optional[CircuitBreakerTrigger]:
      """Record trade result and update risk metrics."""
      # Update drawdown tracker
      self._drawdown_tracker.update(equity)

      # Update circuit breaker
      trigger = self._circuit_breaker.record_trade(pnl, equity)

      if trigger:
          logger.warning("risk_limit_triggered",
                        trigger=trigger.value,
                        pnl=str(pnl),
                        equity=str(equity))

      return trigger

  async def record_error(self) -> Optional[CircuitBreakerTrigger]:
      """Record an error occurrence."""
      return self._circuit_breaker.record_error()
  ```
- [ ] Add stop-loss management:
  ```python
  def register_stop_loss(
      self,
      position_id: str,
      config: StopLossConfig,
      entry_price: Decimal,
      side: str,
  ) -> StopLossState:
      """Register stop-loss for a position."""
      handler = StopLossHandler(config)
      state = handler.initialize(entry_price, side)
      self._stop_handlers[position_id] = handler
      return state

  async def check_stop_losses(
      self,
      current_prices: dict[str, Decimal],
      positions: dict[str, tuple[str, Decimal]],  # position_id -> (side, amount)
  ) -> list[str]:
      """Check all stop-losses and return triggered position IDs."""
      triggered = []

      for position_id, handler in self._stop_handlers.items():
          if position_id not in positions:
              continue

          side, _ = positions[position_id]
          symbol = position_id.split("_")[0]  # Extract symbol from position_id
          price = current_prices.get(symbol)

          if price and handler.check_stop(price, side):
              triggered.append(position_id)

      return triggered

  def remove_stop_loss(self, position_id: str) -> None:
      """Remove stop-loss for closed position."""
      self._stop_handlers.pop(position_id, None)
  ```
- [ ] Add risk metrics exposure:
  ```python
  def get_risk_metrics(self) -> dict:
      """Get current risk metrics for monitoring."""
      dd_metrics = self._drawdown_tracker.update(self._drawdown_tracker._current_equity)

      return {
          "circuit_breaker_tripped": self._circuit_breaker._state.is_tripped,
          "circuit_breaker_trigger": (
              self._circuit_breaker._state.trigger.value
              if self._circuit_breaker._state.trigger else None
          ),
          "daily_pnl": str(self._circuit_breaker._state.daily_pnl),
          "consecutive_losses": self._circuit_breaker._state.consecutive_losses,
          "current_drawdown_pct": f"{dd_metrics.current_drawdown_pct:.2%}",
          "max_drawdown_pct": f"{dd_metrics.max_drawdown_pct:.2%}",
          "active_stop_losses": len(self._stop_handlers),
      }
  ```
- [ ] Write integration tests

### Technical Notes
- Risk manager is the single entry point for all risk operations
- Pre-trade validation prevents bad trades
- Post-trade recording updates all risk metrics
- Metrics exposed for monitoring dashboard

### Definition of Done
- Risk manager coordinates all components
- Pre-trade validation working
- Post-trade recording updates metrics
- Stop-loss management integrated
- Risk metrics accessible for monitoring

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 3.1 Position Sizing Algorithms | 5 | P0 | Phase 2 |
| 3.2 Stop-Loss Handler | 8 | P0 | 3.1 |
| 3.3 Circuit Breaker System | 8 | P0 | Phase 2 |
| 3.4 Drawdown Calculator | 5 | P1 | Phase 2 |
| 3.5 Risk Manager Orchestrator | 8 | P0 | 3.1, 3.2, 3.3, 3.4 |
| **Total** | **34** | | |

---

## Sources & References

- [AI Trading Bot Risk Management Guide 2025](https://3commas.io/blog/ai-trading-bot-risk-management-guide-2025)
- [5 Essential Risk Management Strategies](https://www.alwin.io/risk-management-strategies)
- [Automated Risk Management in Crypto Trading](https://wundertrading.com/journal/en/learn/article/automated-risk-management-in-crypto-trading)
- [Crypto Trading Bot Risk Management Strategies](https://www.fourchain.com/trading-bot/crypto-trading-bot-risk-management-strategies)
- [Risk Management Settings for AI Trading Bots](https://3commas.io/blog/ai-trading-bot-risk-management-guide)
- [Effective Crypto Trading Risk Management 2025](https://algobot.com/crypto-trading-risk-management/)
