# Epic: Phase 1 - Foundation & Exchange Integration

**Epic Owner:** Development Team
**Priority:** Critical - Must be completed before Phase 2
**Dependencies:** None (starting point)

---

## Overview

Phase 1 establishes the foundational infrastructure for the crypto trading bot, including project structure, configuration management, and exchange connectivity. This phase delivers a functional CLI that can execute trades on Binance testnet.

### Key Deliverables
- Well-organized src-layout project structure
- Type-safe configuration with Pydantic Settings v2
- Robust CCXT wrapper with retry logic and rate limiting
- Binance adapter with testnet support
- CLI that executes a single trade on testnet

### Research & Best Practices Applied

Based on current 2025 best practices:
- **Project Structure:** Using [src-layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) per Python Packaging Authority recommendations
- **Configuration:** [Pydantic Settings v2.12+](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) with SecretStr for credentials
- **Exchange API:** [CCXT 4.x](https://github.com/ccxt/ccxt) with performance optimizations (orjson, coincurve)
- **Async Architecture:** asyncio-first design with proper session management

---

## Story 1.1: Initialize Project Structure with Src-Layout

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a well-organized project structure following Python packaging best practices
**So that** code is maintainable, testable, and follows modern Python standards

### Background
The [src-layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) is recommended by the Python Packaging Authority because it prevents import confusion between installed packages and local development code, ensuring tests run against the installed version.

### Acceptance Criteria

- [ ] Create root project directory `crypto_trading_bot/`
- [ ] Create `src/` directory with package subdirectory `crypto_bot/`
- [ ] Create module directories:
  ```
  src/crypto_bot/
  ├── __init__.py
  ├── main.py
  ├── bot.py
  ├── config/
  │   ├── __init__.py
  │   ├── settings.py
  │   └── logging_config.py
  ├── exchange/
  │   ├── __init__.py
  │   ├── base_exchange.py
  │   ├── ccxt_wrapper.py
  │   └── binance_adapter.py
  ├── strategies/
  │   ├── __init__.py
  │   ├── base_strategy.py
  │   ├── grid_trading.py
  │   └── strategy_state.py
  ├── risk/
  │   ├── __init__.py
  │   ├── position_sizer.py
  │   ├── stop_loss.py
  │   └── circuit_breaker.py
  ├── data/
  │   ├── __init__.py
  │   ├── models.py
  │   ├── ohlcv_cache.py
  │   └── persistence.py
  └── utils/
      ├── __init__.py
      ├── retry.py
      └── alerting.py
  ```
- [ ] Create `tests/` directory with `unit/`, `integration/`, `fixtures/` subdirectories
- [ ] Create `config/` directory for runtime configuration files
- [ ] Create `.gitignore` with Python, IDE, and secrets exclusions
- [ ] Verify structure with `tree` command or equivalent

### Technical Notes
- Use `__init__.py` files to make directories importable packages
- Keep `__init__.py` files minimal - avoid complex re-exports
- Place type stubs in `src/crypto_bot/py.typed` marker file for PEP 561 compliance

### Definition of Done
- Directory structure created and committed
- All `__init__.py` files present
- `.gitignore` includes `.env`, `*.pyc`, `__pycache__/`, `.venv/`, `*.db`

---

## Story 1.2: Configure pyproject.toml with Dependencies

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** all dependencies defined in pyproject.toml with pinned versions
**So that** builds are reproducible and compatible across environments

### Background
[pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) is the modern standard for Python project configuration, replacing setup.py and setup.cfg. It centralizes build configuration, dependencies, and tool settings.

### Acceptance Criteria

- [ ] Create `pyproject.toml` with `[build-system]` table using setuptools
- [ ] Define `[project]` metadata:
  - name: `crypto-trading-bot`
  - version: `0.1.0` (or dynamic from `__init__.py`)
  - description, authors, license, Python version requirement (>=3.11)
- [ ] Define core dependencies with version constraints:
  ```toml
  dependencies = [
      "ccxt>=4.0.0",
      "pydantic>=2.0.0",
      "pydantic-settings>=2.0.0",
      "sqlalchemy[asyncio]>=2.0.0",
      "aiosqlite>=0.19.0",
      "asyncpg>=0.29.0",
      "structlog>=24.0.0",
      "aiohttp>=3.9.0",
      "python-dotenv>=1.0.0",
      "orjson>=3.9.0",
      "coincurve>=19.0.0",
  ]
  ```
- [ ] Define `[project.optional-dependencies]` for dev tools:
  ```toml
  [project.optional-dependencies]
  dev = [
      "pytest>=7.0.0",
      "pytest-asyncio>=0.23.0",
      "pytest-cov>=4.0.0",
      "black>=24.0.0",
      "ruff>=0.1.0",
      "mypy>=1.8.0",
  ]
  backtesting = [
      "vectorbt>=0.26.0",
      "pandas>=2.0.0",
      "numpy>=1.24.0",
  ]
  ```
- [ ] Configure `[tool.setuptools.packages.find]` for src-layout
- [ ] Configure `[tool.ruff]` for linting rules
- [ ] Configure `[tool.mypy]` for type checking
- [ ] Configure `[tool.pytest.ini_options]` for test discovery
- [ ] Create `requirements.txt` for pip fallback (generated from pyproject.toml)

### Technical Notes
- Use `>=` constraints for flexibility, pin exact versions in lock file
- orjson and coincurve are auto-detected by CCXT for [10x+ performance improvements](https://github.com/ccxt/ccxt)
- SQLAlchemy `[asyncio]` extra includes greenlet for async support

### Example pyproject.toml Structure
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "crypto-trading-bot"
version = "0.1.0"
description = "Modular crypto trading bot with grid strategy"
requires-python = ">=3.11"
dependencies = [...]

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

### Definition of Done
- `pyproject.toml` created with all sections
- `pip install -e ".[dev]"` succeeds in clean virtualenv
- `ruff check src/` runs without configuration errors
- `mypy src/` runs without configuration errors

---

## Story 1.3: Implement Pydantic Settings Configuration

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** type-safe configuration management with environment variable overrides
**So that** settings are validated at startup and secrets are handled securely

### Background
[Pydantic Settings v2](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) provides automatic environment variable loading, type coercion, and validation. SecretStr prevents accidental logging of sensitive values.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/config/settings.py`
- [ ] Implement `ExchangeSettings` model:
  ```python
  from pydantic import Field, SecretStr
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class ExchangeSettings(BaseSettings):
      model_config = SettingsConfigDict(env_prefix="EXCHANGE_")

      name: str = "binance"
      api_key: SecretStr
      api_secret: SecretStr
      testnet: bool = True
      rate_limit_ms: int = Field(default=100, ge=50, le=1000)
      timeout_ms: int = Field(default=30000, ge=5000, le=60000)
  ```
- [ ] Implement `DatabaseSettings` model:
  ```python
  class DatabaseSettings(BaseSettings):
      model_config = SettingsConfigDict(env_prefix="DB_")

      url: str = "sqlite+aiosqlite:///./trading.db"
      echo: bool = False
      pool_size: int = Field(default=5, ge=1, le=20)
  ```
- [ ] Implement `TradingSettings` model:
  ```python
  class TradingSettings(BaseSettings):
      model_config = SettingsConfigDict(env_prefix="TRADING_")

      symbol: str = "BTC/USDT"
      dry_run: bool = True
      max_position_pct: float = Field(default=0.1, ge=0.01, le=1.0)
  ```
- [ ] Implement `AlertSettings` model for Telegram/Discord
- [ ] Implement root `AppSettings` with nested models:
  ```python
  class AppSettings(BaseSettings):
      model_config = SettingsConfigDict(
          env_file=".env",
          env_file_encoding="utf-8",
          env_nested_delimiter="__",
          extra="ignore",
      )

      exchange: ExchangeSettings = Field(default_factory=ExchangeSettings)
      database: DatabaseSettings = Field(default_factory=DatabaseSettings)
      trading: TradingSettings = Field(default_factory=TradingSettings)
      log_level: str = "INFO"
  ```
- [ ] Create `.env.example` template file (without real secrets)
- [ ] Add `.env` to `.gitignore`
- [ ] Implement `get_settings()` function with caching (lru_cache)
- [ ] Write unit tests for settings validation

### Technical Notes
- Use `env_nested_delimiter="__"` for nested env vars: `EXCHANGE__API_KEY=xxx`
- SecretStr exposes `.get_secret_value()` method for actual value access
- Pydantic validates on instantiation - invalid config fails fast at startup
- Consider using [pydantic-settings-manager](https://pypi.org/project/pydantic-settings-manager/) for complex multi-environment setups

### Environment Variable Examples
```bash
# .env file
EXCHANGE__API_KEY=your_api_key_here
EXCHANGE__API_SECRET=your_api_secret_here
EXCHANGE__TESTNET=true
DB__URL=sqlite+aiosqlite:///./trading.db
TRADING__DRY_RUN=true
LOG_LEVEL=DEBUG
```

### Definition of Done
- Settings models created with full type hints
- Environment variables load correctly
- Invalid values raise ValidationError with clear messages
- SecretStr values don't appear in str() or repr()
- Unit tests pass for all validation scenarios

---

## Story 1.4: Set Up Structured Logging with structlog

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** developer
**I want** structured JSON logging with consistent fields
**So that** logs are searchable and integrable with log aggregation systems

### Background
[structlog](https://www.structlog.org/) provides structured logging that outputs JSON, making logs machine-parseable while remaining human-readable during development.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/config/logging_config.py`
- [ ] Implement `configure_logging()` function:
  ```python
  import structlog
  from structlog.typing import Processor

  def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
      processors: list[Processor] = [
          structlog.contextvars.merge_contextvars,
          structlog.processors.add_log_level,
          structlog.processors.TimeStamper(fmt="iso", utc=True),
          structlog.processors.StackInfoRenderer(),
          structlog.processors.format_exc_info,
      ]

      if json_output:
          processors.append(structlog.processors.JSONRenderer())
      else:
          processors.append(structlog.dev.ConsoleRenderer(colors=True))

      structlog.configure(
          processors=processors,
          wrapper_class=structlog.make_filtering_bound_logger(
              getattr(logging, log_level.upper())
          ),
          context_class=dict,
          logger_factory=structlog.PrintLoggerFactory(),
          cache_logger_on_first_use=True,
      )
  ```
- [ ] Implement secret redaction processor:
  ```python
  def redact_secrets(_, __, event_dict: dict) -> dict:
      sensitive_keys = {"api_key", "api_secret", "password", "token"}
      for key in event_dict:
          if any(s in key.lower() for s in sensitive_keys):
              event_dict[key] = "***REDACTED***"
      return event_dict
  ```
- [ ] Add context binding for request/trade tracking
- [ ] Create development mode with colored console output
- [ ] Create production mode with JSON output
- [ ] Write tests verifying secret redaction

### Technical Notes
- Use `structlog.contextvars` for request-scoped context (trade_id, order_id)
- JSON logs integrate with ELK stack, Datadog, CloudWatch
- Console renderer helpful during local development

### Log Output Examples
```json
{"event": "order_placed", "symbol": "BTC/USDT", "side": "buy", "amount": 0.01, "price": 42500.0, "order_id": "abc123", "timestamp": "2025-01-04T12:00:00Z", "level": "info"}
```

### Definition of Done
- Logging configuration complete
- JSON and console modes working
- Secrets are redacted in all output
- Context binding works across async calls

---

## Story 1.5: Create Application Entry Point

**Story Points:** 2
**Priority:** P1 - High

### Description
**As a** developer
**I want** a clean main entry point that initializes all components
**So that** the application starts correctly with proper error handling

### Acceptance Criteria

- [ ] Create `src/crypto_bot/main.py`:
  ```python
  import asyncio
  import signal
  import sys
  from crypto_bot.config.settings import get_settings
  from crypto_bot.config.logging_config import configure_logging

  async def main() -> int:
      settings = get_settings()
      configure_logging(settings.log_level)

      logger = structlog.get_logger()
      logger.info("starting_bot", version="0.1.0", dry_run=settings.trading.dry_run)

      # Initialize components...
      return 0

  def cli() -> None:
      sys.exit(asyncio.run(main()))

  if __name__ == "__main__":
      cli()
  ```
- [ ] Add CLI entry point in `pyproject.toml`:
  ```toml
  [project.scripts]
  crypto-bot = "crypto_bot.main:cli"
  ```
- [ ] Implement graceful shutdown on SIGINT/SIGTERM
- [ ] Display startup banner with configuration summary (redacted secrets)
- [ ] Handle configuration errors with clear error messages
- [ ] Return appropriate exit codes (0=success, 1=error)

### Technical Notes
- Use `asyncio.run()` as the single entry point for async code
- Register signal handlers for graceful shutdown
- Log startup configuration for debugging (with secrets redacted)

### Definition of Done
- `python -m crypto_bot` runs successfully
- `crypto-bot` CLI command works after pip install
- SIGINT triggers graceful shutdown
- Configuration errors produce helpful messages

---

## Story 1.6: Define Abstract Exchange Interface

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** an abstract base class defining the exchange interface
**So that** strategies are exchange-agnostic and can work with any CCXT-supported exchange

### Acceptance Criteria

- [ ] Create `src/crypto_bot/exchange/base_exchange.py`
- [ ] Define data classes for exchange responses:
  ```python
  from dataclasses import dataclass
  from datetime import datetime
  from decimal import Decimal
  from enum import Enum
  from typing import Optional

  class OrderSide(str, Enum):
      BUY = "buy"
      SELL = "sell"

  class OrderType(str, Enum):
      MARKET = "market"
      LIMIT = "limit"

  class OrderStatus(str, Enum):
      OPEN = "open"
      CLOSED = "closed"
      CANCELED = "canceled"
      EXPIRED = "expired"

  @dataclass(frozen=True)
  class Ticker:
      symbol: str
      bid: Decimal
      ask: Decimal
      last: Decimal
      timestamp: datetime

  @dataclass(frozen=True)
  class Balance:
      currency: str
      free: Decimal
      used: Decimal
      total: Decimal

  @dataclass
  class Order:
      id: str
      client_order_id: Optional[str]
      symbol: str
      side: OrderSide
      order_type: OrderType
      status: OrderStatus
      price: Optional[Decimal]
      amount: Decimal
      filled: Decimal
      remaining: Decimal
      cost: Decimal
      fee: Optional[Decimal]
      timestamp: datetime
  ```
- [ ] Define `BaseExchange` abstract base class:
  ```python
  from abc import ABC, abstractmethod

  class BaseExchange(ABC):
      @abstractmethod
      async def connect(self) -> None:
          """Initialize connection and load markets."""

      @abstractmethod
      async def disconnect(self) -> None:
          """Clean up connections."""

      @abstractmethod
      async def fetch_ticker(self, symbol: str) -> Ticker:
          """Get current ticker for symbol."""

      @abstractmethod
      async def fetch_balance(self) -> dict[str, Balance]:
          """Get account balances."""

      @abstractmethod
      async def create_order(
          self,
          symbol: str,
          order_type: OrderType,
          side: OrderSide,
          amount: Decimal,
          price: Optional[Decimal] = None,
      ) -> Order:
          """Place a new order."""

      @abstractmethod
      async def cancel_order(self, order_id: str, symbol: str) -> Order:
          """Cancel an existing order."""

      @abstractmethod
      async def fetch_order(self, order_id: str, symbol: str) -> Order:
          """Get order status."""

      @abstractmethod
      async def fetch_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
          """Get all open orders."""

      @abstractmethod
      async def fetch_ohlcv(
          self,
          symbol: str,
          timeframe: str = "1h",
          limit: int = 100,
      ) -> list[tuple[datetime, Decimal, Decimal, Decimal, Decimal, Decimal]]:
          """Get OHLCV candle data."""
  ```
- [ ] Add type hints and docstrings for all methods
- [ ] Define custom exceptions:
  ```python
  class ExchangeError(Exception):
      """Base exception for exchange errors."""

  class AuthenticationError(ExchangeError):
      """API key or signature invalid."""

  class InsufficientFundsError(ExchangeError):
      """Not enough balance for order."""

  class OrderNotFoundError(ExchangeError):
      """Order ID does not exist."""

  class RateLimitError(ExchangeError):
      """Rate limit exceeded."""
  ```

### Technical Notes
- Use `Decimal` for all monetary values to avoid floating-point errors
- Frozen dataclasses ensure immutability of exchange responses
- Custom exceptions enable specific error handling in strategies

### Definition of Done
- All interfaces defined with full type hints
- Custom exceptions defined
- Docstrings explain each method's purpose and parameters
- No implementation code - pure interface definition

---

## Story 1.7: Implement Retry Utility with Exponential Backoff

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a reusable retry decorator with exponential backoff and jitter
**So that** transient network errors are handled gracefully without manual retry logic

### Background
Per [CCXT best practices](https://github.com/ccxt/ccxt), network errors are common and should be retried. Exponential backoff with jitter prevents thundering herd problems when services recover.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/retry.py`
- [ ] Define retryable exception types:
  ```python
  import ccxt

  RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
      ccxt.NetworkError,
      ccxt.RateLimitExceeded,
      ccxt.ExchangeNotAvailable,
      ccxt.RequestTimeout,
      ccxt.DDoSProtection,
      ConnectionError,
      TimeoutError,
  )

  NON_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
      ccxt.AuthenticationError,
      ccxt.InvalidOrder,
      ccxt.InsufficientFunds,
      ccxt.BadSymbol,
  )
  ```
- [ ] Implement async retry decorator:
  ```python
  import asyncio
  import random
  from functools import wraps
  from typing import TypeVar, Callable, Any
  import structlog

  T = TypeVar("T")
  logger = structlog.get_logger()

  def retry_with_backoff(
      max_retries: int = 5,
      base_delay: float = 1.0,
      max_delay: float = 60.0,
      exponential_base: float = 2.0,
      jitter: bool = True,
  ) -> Callable[[Callable[..., T]], Callable[..., T]]:
      def decorator(func: Callable[..., T]) -> Callable[..., T]:
          @wraps(func)
          async def wrapper(*args: Any, **kwargs: Any) -> T:
              last_exception: Exception | None = None

              for attempt in range(max_retries):
                  try:
                      return await func(*args, **kwargs)
                  except NON_RETRYABLE_EXCEPTIONS:
                      raise  # Don't retry auth/validation errors
                  except RETRYABLE_EXCEPTIONS as e:
                      last_exception = e
                      if attempt == max_retries - 1:
                          raise

                      delay = min(
                          base_delay * (exponential_base ** attempt),
                          max_delay
                      )
                      if jitter:
                          delay *= (0.5 + random.random())

                      logger.warning(
                          "retry_scheduled",
                          attempt=attempt + 1,
                          max_retries=max_retries,
                          delay_seconds=round(delay, 2),
                          error_type=type(e).__name__,
                          error_msg=str(e),
                      )
                      await asyncio.sleep(delay)

              raise last_exception  # Should not reach here
          return wrapper
      return decorator
  ```
- [ ] Add support for custom exception handlers
- [ ] Write comprehensive unit tests:
  - Test successful retry after transient failure
  - Test immediate failure on non-retryable exception
  - Test max retries exhaustion
  - Test backoff timing (mock sleep)

### Technical Notes
- Jitter (randomization) prevents multiple clients from retrying simultaneously
- Separate retryable from non-retryable exceptions to fail fast on auth errors
- Log each retry attempt for debugging

### Definition of Done
- Retry decorator implemented and tested
- Works with async functions
- Logs retry attempts with context
- Non-retryable exceptions fail immediately

---

## Story 1.8: Build CCXT Wrapper with Error Handling

**Story Points:** 8
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a CCXT wrapper that handles common exchange operations
**So that** exchange-specific details and error handling are encapsulated

### Background
[CCXT](https://github.com/ccxt/ccxt) provides unified API for 100+ exchanges. The wrapper should enable rate limiting, pre-load markets, and convert CCXT responses to our internal data classes.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/exchange/ccxt_wrapper.py`
- [ ] Implement `CCXTExchange` class:
  ```python
  import ccxt.async_support as ccxt
  from decimal import Decimal
  from crypto_bot.exchange.base_exchange import BaseExchange, Ticker, Balance, Order
  from crypto_bot.config.settings import ExchangeSettings
  from crypto_bot.utils.retry import retry_with_backoff

  class CCXTExchange(BaseExchange):
      def __init__(self, settings: ExchangeSettings):
          self._settings = settings
          self._exchange: ccxt.Exchange | None = None
          self._markets: dict = {}

      async def connect(self) -> None:
          exchange_class = getattr(ccxt, self._settings.name)
          self._exchange = exchange_class({
              "apiKey": self._settings.api_key.get_secret_value(),
              "secret": self._settings.api_secret.get_secret_value(),
              "enableRateLimit": True,
              "rateLimit": self._settings.rate_limit_ms,
              "timeout": self._settings.timeout_ms,
              "options": {"defaultType": "spot"},
          })

          if self._settings.testnet:
              self._exchange.set_sandbox_mode(True)

          # Pre-load markets to avoid redundant API calls
          self._markets = await self._exchange.load_markets()
          logger.info("exchange_connected",
                      exchange=self._settings.name,
                      testnet=self._settings.testnet,
                      markets_loaded=len(self._markets))

      async def disconnect(self) -> None:
          if self._exchange:
              await self._exchange.close()
              self._exchange = None
  ```
- [ ] Implement `fetch_ticker` with retry:
  ```python
  @retry_with_backoff(max_retries=3)
  async def fetch_ticker(self, symbol: str) -> Ticker:
      raw = await self._exchange.fetch_ticker(symbol)
      return Ticker(
          symbol=raw["symbol"],
          bid=Decimal(str(raw["bid"])),
          ask=Decimal(str(raw["ask"])),
          last=Decimal(str(raw["last"])),
          timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, tz=UTC),
      )
  ```
- [ ] Implement `fetch_balance` with retry
- [ ] Implement `create_order` with:
  - Precision handling (amount/price rounding per market rules)
  - Minimum order size validation
  - Retry logic for transient failures
- [ ] Implement `cancel_order` with retry
- [ ] Implement `fetch_order` with retry
- [ ] Implement `fetch_open_orders` with retry
- [ ] Implement `fetch_ohlcv` with retry
- [ ] Add helper methods:
  ```python
  def _round_to_precision(self, value: Decimal, precision: int) -> Decimal:
      """Round value to exchange's required precision."""

  def _validate_order_size(self, symbol: str, amount: Decimal) -> None:
      """Check minimum order size."""
  ```
- [ ] Map CCXT exceptions to custom exceptions
- [ ] Write integration tests (mocked CCXT)

### Technical Notes
- Always use `Decimal(str(float_value))` to avoid precision loss
- `load_markets()` caches symbol precision/limits - call once on connect
- CCXT's `enableRateLimit: True` handles rate limiting automatically
- Use `set_sandbox_mode(True)` for testnet

### Definition of Done
- All BaseExchange methods implemented
- Rate limiting enabled
- Markets pre-loaded on connect
- Precision handling for all numeric values
- CCXT exceptions mapped to custom exceptions
- Unit tests with mocked CCXT

---

## Story 1.9: Create Binance-Specific Adapter

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** developer
**I want** a Binance-specific adapter handling exchange quirks
**So that** Binance-specific behaviors and optimizations are isolated

### Acceptance Criteria

- [ ] Create `src/crypto_bot/exchange/binance_adapter.py`
- [ ] Extend `CCXTExchange` with Binance specifics:
  ```python
  class BinanceAdapter(CCXTExchange):
      def __init__(self, settings: ExchangeSettings):
          if settings.name != "binance":
              raise ValueError("BinanceAdapter requires exchange name 'binance'")
          super().__init__(settings)

      async def connect(self) -> None:
          await super().connect()
          # Binance-specific initialization
          if self._settings.testnet:
              logger.info("using_binance_testnet",
                          url="testnet.binance.vision")
  ```
- [ ] Handle Binance-specific order types (OCO, etc.)
- [ ] Implement Binance-specific error code handling:
  ```python
  BINANCE_ERROR_CODES = {
      -1000: "Unknown error",
      -1003: "Too many requests",
      -1015: "Too many orders",
      -2010: "Insufficient balance",
      -2011: "Unknown order",
  }
  ```
- [ ] Add Binance-specific filters validation:
  - LOT_SIZE (quantity step/min/max)
  - PRICE_FILTER (price precision/min/max)
  - MIN_NOTIONAL (minimum order value)
- [ ] Implement `validate_order_params`:
  ```python
  def validate_order_params(
      self,
      symbol: str,
      amount: Decimal,
      price: Optional[Decimal]
  ) -> tuple[Decimal, Optional[Decimal]]:
      """Validate and adjust order parameters per Binance filters."""
      market = self._markets[symbol]
      limits = market["limits"]
      precision = market["precision"]

      # Adjust amount to LOT_SIZE
      adjusted_amount = self._round_to_step(amount, limits["amount"]["min"])

      # Validate MIN_NOTIONAL
      if price and (adjusted_amount * price) < Decimal(str(limits["cost"]["min"])):
          raise InsufficientFundsError(f"Order value below minimum: {limits['cost']['min']}")

      return adjusted_amount, price
  ```
- [ ] Support Binance testnet URL configuration
- [ ] Write tests specific to Binance behaviors

### Technical Notes
- Binance testnet: `testnet.binance.vision` (spot), `testnet.binancefuture.com` (futures)
- Binance uses specific error codes - handle for better error messages
- LOT_SIZE filter requires quantities to be multiples of step size

### Definition of Done
- BinanceAdapter extends CCXTExchange correctly
- Binance filters validated before order submission
- Testnet mode works correctly
- Binance error codes produce meaningful messages

---

## Story 1.10: Implement WebSocket Support for Real-Time Data

**Story Points:** 8
**Priority:** P2 - Medium

### Description
**As a** developer
**I want** WebSocket connectivity for real-time price feeds
**So that** the bot receives market data with minimal latency

### Background
Per [CCXT recommendations](https://github.com/ccxt/ccxt), use WebSockets for price feeds and REST for order placement. CCXT Pro (included in ccxt package) provides unified WebSocket API.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/exchange/websocket_handler.py`
- [ ] Implement WebSocket ticker subscription:
  ```python
  class WebSocketHandler:
      def __init__(self, exchange: ccxt.Exchange):
          self._exchange = exchange
          self._running = False
          self._callbacks: dict[str, list[Callable]] = {}

      async def subscribe_ticker(
          self,
          symbol: str,
          callback: Callable[[Ticker], Awaitable[None]]
      ) -> None:
          """Subscribe to real-time ticker updates."""
          if symbol not in self._callbacks:
              self._callbacks[symbol] = []
          self._callbacks[symbol].append(callback)

      async def start(self) -> None:
          """Start WebSocket listener."""
          self._running = True
          while self._running:
              for symbol in self._callbacks:
                  try:
                      ticker = await self._exchange.watch_ticker(symbol)
                      for callback in self._callbacks[symbol]:
                          await callback(self._convert_ticker(ticker))
                  except Exception as e:
                      logger.error("websocket_error", symbol=symbol, error=str(e))

      async def stop(self) -> None:
          """Stop WebSocket listener."""
          self._running = False
  ```
- [ ] Implement automatic reconnection on disconnect:
  ```python
  async def _reconnect(self) -> None:
      """Reconnect with exponential backoff."""
      await asyncio.sleep(self._reconnect_delay)
      self._reconnect_delay = min(self._reconnect_delay * 2, 60)
      await self.start()
  ```
- [ ] Implement orderbook subscription (optional)
- [ ] Add fallback to REST polling when WebSocket unavailable
- [ ] Handle connection lifecycle (connect, disconnect, reconnect)
- [ ] Write tests for WebSocket handling

### Technical Notes
- CCXT Pro methods: `watch_ticker()`, `watch_order_book()`, `watch_trades()`
- WebSocket reduces API calls and latency vs polling
- Always have REST fallback for reliability
- Consider heartbeat/ping to detect stale connections

### Definition of Done
- WebSocket ticker subscription works
- Automatic reconnection on disconnect
- REST fallback available
- Callbacks notify strategy of price updates

---

## Story 1.11: Create Testnet Integration Test

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** developer
**I want** integration tests running against Binance testnet
**So that** real exchange behavior is validated before production

### Acceptance Criteria

- [ ] Create `tests/integration/test_binance_testnet.py`
- [ ] Document testnet setup:
  - Create Binance testnet account at testnet.binance.vision
  - Generate API keys for testnet
  - Set environment variables for tests
- [ ] Implement integration tests:
  ```python
  import pytest
  from decimal import Decimal

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_fetch_ticker(binance_adapter):
      ticker = await binance_adapter.fetch_ticker("BTC/USDT")
      assert ticker.symbol == "BTC/USDT"
      assert ticker.bid > 0
      assert ticker.ask > 0
      assert ticker.ask >= ticker.bid

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_fetch_balance(binance_adapter):
      balances = await binance_adapter.fetch_balance()
      assert "USDT" in balances
      assert balances["USDT"].total >= 0

  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_place_and_cancel_order(binance_adapter):
      # Place a limit order far from market price
      ticker = await binance_adapter.fetch_ticker("BTC/USDT")
      limit_price = ticker.bid * Decimal("0.5")  # 50% below market

      order = await binance_adapter.create_order(
          symbol="BTC/USDT",
          order_type=OrderType.LIMIT,
          side=OrderSide.BUY,
          amount=Decimal("0.001"),
          price=limit_price,
      )
      assert order.status == OrderStatus.OPEN

      # Cancel the order
      cancelled = await binance_adapter.cancel_order(order.id, "BTC/USDT")
      assert cancelled.status == OrderStatus.CANCELED
  ```
- [ ] Create pytest fixture for adapter setup/teardown
- [ ] Mark tests as slow/integration for separate CI runs
- [ ] Add pytest marker configuration in `pyproject.toml`

### Technical Notes
- Binance testnet provides free test funds
- Tests should clean up (cancel orders) in teardown
- Don't run integration tests on every commit - separate CI job

### Definition of Done
- Integration tests run successfully on testnet
- Tests are marked and can be skipped in fast CI
- Documentation explains testnet setup
- Fixture handles connect/disconnect lifecycle

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 1.1 Initialize Project Structure | 3 | P0 | None |
| 1.2 Configure pyproject.toml | 3 | P0 | 1.1 |
| 1.3 Implement Pydantic Settings | 5 | P0 | 1.2 |
| 1.4 Set Up Structured Logging | 3 | P1 | 1.2 |
| 1.5 Create Application Entry Point | 2 | P1 | 1.3, 1.4 |
| 1.6 Define Exchange Interface | 5 | P0 | 1.1 |
| 1.7 Implement Retry Utility | 3 | P0 | 1.2 |
| 1.8 Build CCXT Wrapper | 8 | P0 | 1.6, 1.7 |
| 1.9 Create Binance Adapter | 5 | P1 | 1.8 |
| 1.10 WebSocket Support | 8 | P2 | 1.8 |
| 1.11 Testnet Integration Test | 3 | P1 | 1.9 |
| **Total** | **48** | | |

---

## Sources & References

- [CCXT GitHub Repository](https://github.com/ccxt/ccxt)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Python Packaging - src-layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [How to Build Profitable Trading Bots 2025](https://www.diego-rodriguez.work/blog/how-to-build-profitable-trading-bots-2025)
- [Automated Trading with Python 2025](https://wundertrading.com/journal/en/learn/article/automated-trading-with-python)
