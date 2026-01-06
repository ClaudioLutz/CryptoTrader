---
title: 'Dashboard Hardening Phase 1'
slug: 'dashboard-hardening-phase1'
created: '2026-01-06'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
adversarial_review: 'completed-2026-01-06'
critical_issues_fixed: 5
high_priority_issues_fixed: 8
tech_stack:
  - python-binance>=1.0.19 (WebSocket)
  - pybreaker>=1.0.1 (circuit breaker)
  - NiceGUI 3.4.1
  - httpx (REST fallback)
  - structlog (logging)
files_to_modify:
  - pyproject.toml
  - dashboard/services/data_models.py
  - dashboard/services/api_client.py
  - dashboard/services/websocket_service.py (NEW)
  - dashboard/state.py
  - dashboard/components/header.py
  - dashboard/main.py
code_patterns:
  - async-first I/O (all network ops async)
  - Decimal for money (never float)
  - structlog logging (never print)
  - NiceGUI reactive bindings (bind_text_from)
  - Graceful degradation (return None, show stale)
  - Callback-based subscriptions (from existing WebSocketHandler)
test_patterns:
  - pytest-asyncio with asyncio_mode="auto"
  - E2E tests in tests/e2e/
  - @pytest.mark.integration marker
  - Fixtures in conftest.py
---

# Tech-Spec: Dashboard Hardening Phase 1

**Created:** 2026-01-06
**Adversarial Review:** 2026-01-06 (19 issues identified, 13 critical/high fixed)
**Status:** ✅ Ready for Development

---

## Adversarial Review Summary

This spec underwent comprehensive adversarial review before implementation. The following critical and high-priority issues were identified and resolved:

### Critical Blockers Fixed (5)
1. **Issue #11**: P&L Recalculation Architecture - Added in-memory trade cache to eliminate REST API calls on WebSocket events (was 36K calls/hour, now zero)
2. **Issue #14**: WebSocket Credential Management - Specified reuse of bot's `EXCHANGE__API_KEY` and `EXCHANGE__API_SECRET` from environment
3. **Issue #18**: Circuit Breaker Exception Handling - Clarified exception propagation pattern: raise for counting, catch `CircuitBreakerError` for graceful return
4. **Issue #7**: NiceGUI Reactivity - Added UI refresh callback system for WebSocket updates (`register_ui_refresh()`)
5. **Issue #12**: Trade History Synchronization - Defined sync strategy: REST on startup, WebSocket append, REST resync on reconnect

### High-Priority Issues Fixed (8)
6. **Issue #1**: Circuit Breaker Scope - Explicitly listed 12 public methods to wrap with `@exchange_breaker` decorator
7. **Issue #2**: REST Polling Skip Logic - Defined precise fallback behavior: health always REST, P&L uses cache, tickers from WebSocket when connected
8. **Issue #5**: ListenKey Keepalive - Documented that `python-binance` BinanceSocketManager handles this automatically
9. **Issue #6**: WebSocket State Management - Added `set_websocket_connected()` callback for connection state changes
10. **Issue #8**: Circuit Breaker Code Examples - Provided complete exception handling pattern with try/except/raise
11. **Issue #15**: Circuit Breaker vs Bot Health - Added circuit breaker state exposure for UI differentiation
12. **Issue #17**: Restart Behavior - Added "Restart and Reconnect Behavior" section defining cache initialization and sync
13. **Issue #10**: Dependency Conflicts - Documented `aiohttp` (python-binance) + `httpx` (REST client) coexistence as acceptable

### Medium-Priority Issues Noted (6)
Issues #3, #4, #9, #13, #16, #19 - Addressed via clarifications, documentation improvements, and inline notes.

**Confidence Level:** High - All critical execution gaps closed, implementation can proceed without major blockers.

---

## Overview

### Problem Statement

The current dashboard uses REST polling (2,400+ API weight/hour), lacks protection against cascade failures during exchange outages, and displays a single P&L value that confuses users about realized vs unrealized gains.

### Solution

Implement WebSocket streams for real-time data (User Data Stream + Market tickers), add circuit breakers around all API calls, and separate P&L into Realized Grid Profit, Unrealized P&L, and Total P&L. Maintain REST as fallback when WebSocket is unavailable.

### Scope

**In Scope:**
- User Data Stream WebSocket for order/balance updates
- Market data WebSocket for tickers (replace REST polling)
- Circuit breaker with `pybreaker` around all API calls
- Separated P&L display: Realized / Unrealized / Total
- REST fallback when WebSocket unavailable
- `python-binance` library for WebSocket integration

**Out of Scope:**
- SQLite persistence for trade history (Phase 2)
- APR and fee impact calculations (Phase 2)
- Max drawdown, win rate, profit factor metrics (Phase 3)
- Rate limit monitoring with auto-throttle (Phase 3)
- Grid visualization overlay on charts (Phase 3)

## Context for Development

### Codebase Patterns

From `project-context.md` and code analysis:

- **Async-First:** All I/O operations must be async (`async def`, `await`)
- **Type Hints Required:** mypy strict mode - all functions need type hints
- **Decimal for Money:** Use `Decimal` not `float` for financial calculations
- **No print():** Use `structlog` logger, never `print()` statements
- **NiceGUI Bindings:** Use `bind_text_from()` for reactive UI updates
- **Graceful Degradation:** Return None/defaults on failure, show stale indicators
- **Callback Subscriptions:** Existing `WebSocketHandler` uses callback pattern for ticker updates

### Credentials and Authentication

**WebSocket Connection to Binance:**
- Dashboard reuses bot's Binance API credentials from `.env`
- Credentials accessed via: `EXCHANGE__API_KEY` and `EXCHANGE__API_SECRET`
- Dashboard config (Pydantic Settings) will read these from environment
- **CRITICAL**: API key must have "Enable Reading" + "Enable Spot & Margin Trading" permissions
- **NEVER** enable withdrawal permission on API key used by dashboard
- Dashboard WebSocket is READ-ONLY (receives updates, never places orders)

### Existing Infrastructure (REUSE)

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| `PnLResult` dataclass | `dashboard/services/pnl_calculator.py:14` | Already has `realized_pnl`, `unrealized_pnl`, `total_pnl` - expose in state |
| `calculate_pnl_from_trades()` | `dashboard/services/pnl_calculator.py:27` | Already calculates separated P&L - use output |
| `WebSocketHandler` pattern | `src/crypto_bot/exchange/websocket_handler.py` | Follow callback subscription pattern, exponential backoff |
| `DashboardState._calculate_pnl_from_trades()` | `dashboard/state.py:188` | Modify to store separated P&L values |

### Files to Modify

| File | Changes |
|------|---------|
| `pyproject.toml` | Add `python-binance`, `pybreaker` dependencies |
| `dashboard/services/data_models.py` | Add `PnLBreakdown` model for separated P&L |
| `dashboard/services/api_client.py` | Wrap all methods with pybreaker circuit breaker |
| `dashboard/services/websocket_service.py` | **NEW** - Binance WebSocket streams for User Data + Market Data |
| `dashboard/state.py` | Add `realized_pnl`, `unrealized_pnl` attrs; integrate WebSocket updates |
| `dashboard/components/header.py` | Show 3-value P&L display (Realized / Unrealized / Total) |
| `dashboard/main.py` | Initialize WebSocket service, manage lifecycle |

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| WebSocket Library | `python-binance` | Matches research code samples, native Binance User Data Stream support |
| Circuit Breaker | `pybreaker` (not existing bot circuit breaker) | Bot's circuit breaker is for trading risk limits; pybreaker is for API fault tolerance |
| Data Flow | WebSocket → State → UI via NiceGUI push | NiceGUI automatically pushes state changes via its internal WebSocket |
| ListenKey | 25-minute keepalive task | Binance requires PUT every 30 min; 25 min gives margin |
| Fallback Strategy | REST polling when WebSocket unavailable | Hybrid pattern from research - professional platforms use this |

## Implementation Plan

### Tasks

#### Task 1: Add Dependencies
- **File:** `pyproject.toml`
- **Action:** Add new dependencies to `[project.dependencies]` section
- **Details:**
  ```toml
  "python-binance>=1.0.19",
  "pybreaker>=1.0.1",
  ```
- **Notes:** Run `pip install -e .` after to install

#### Task 2: Add PnLBreakdown Data Model
- **File:** `dashboard/services/data_models.py`
- **Action:** Add new Pydantic model for separated P&L display
- **Details:**
  ```python
  class PnLBreakdown(BaseModel):
      """Separated P&L for professional display."""
      realized_pnl: Decimal = Field(default=Decimal("0"), description="Locked-in grid profits")
      unrealized_pnl: Decimal = Field(default=Decimal("0"), description="Mark-to-market floating P&L")
      total_pnl: Decimal = Field(default=Decimal("0"), description="Sum of realized + unrealized")
  ```
- **Notes:** Used by state and header components

#### Task 3: Add Circuit Breaker to API Client
- **File:** `dashboard/services/api_client.py`
- **Action:** Wrap all public API methods with pybreaker circuit breaker
- **Details:**
  1. Import pybreaker at top of file
  2. Create module-level circuit breaker instance:
     ```python
     import pybreaker

     # Circuit breaker for API fault tolerance
     exchange_breaker = pybreaker.CircuitBreaker(
         fail_max=5,          # Open after 5 consecutive failures
         reset_timeout=60,    # Try half-open after 60 seconds
         name="BotAPICircuitBreaker",
     )
     ```
  3. Wrap the following PUBLIC methods with decorator (12 total):
     - `get_health()`, `get_status()`, `get_pairs()`, `get_orders()`, `get_trades()`
     - `get_pnl()`, `get_total_pnl()`, `get_ohlcv()`, `get_grid_config()`, `get_bot_config()`
     - `get_dashboard_data()` (delegates to other methods, wrap it too)
  4. **Exception Handling Pattern** - Add try/except for `CircuitBreakerError`:
     ```python
     @exchange_breaker
     async def get_health(self) -> HealthResponse | None:
         """Fetch bot health status."""
         try:
             if not self._client:
                 logger.error("API client not initialized")
                 return None

             response = await self._client.get("/health")
             response.raise_for_status()
             # ... parse response ...
         except pybreaker.CircuitBreakerError:
             logger.warning("Circuit breaker is OPEN - API calls blocked")
             return None
         except httpx.RequestError as e:
             logger.error("Health request failed: connection error: %s", e)
             raise  # Let circuit breaker count this failure
         except httpx.HTTPStatusError as e:
             logger.error("Health request returned error status: %s", e.response.status_code)
             raise  # Let circuit breaker count this failure
     ```
  5. **CRITICAL**: Exceptions must PROPAGATE to pybreaker to count failures, then catch `CircuitBreakerError` at method level to return None gracefully
- **Notes:**
  - Do NOT wrap `_get_current_price()` (private helper called within decorated methods)
  - Circuit breaker state exposed via `exchange_breaker.current_state` (for UI display)

#### Task 4: Trade Cache and Synchronization Strategy
- **File:** `dashboard/state.py` (additions)
- **Action:** Add in-memory trade cache to avoid REST API calls on every WebSocket event
- **Details:**
  1. **Trade Cache Design:**
     ```python
     # Add to DashboardState.__init__
     self._trade_cache: list[TradeData] = []  # In-memory cache of all trades
     self._trade_cache_initialized: bool = False
     self._cache_last_sync: datetime | None = None
     ```
  2. **Synchronization Strategy:**
     - **On Startup**: Fetch last 200 trades from REST API (`get_trades(limit=200)`)
     - **WebSocket Connected**: Append new `executionReport` events to cache
     - **WebSocket Reconnect**: Fetch trades since last sync (`timestamp > cache_last_sync`)
     - **P&L Calculation**: Use cached trades, NOT API call
  3. **Cache Update Method:**
     ```python
     async def _update_trade_cache_from_websocket(self, trade_event: dict) -> None:
         """Append WebSocket trade event to cache."""
         trade = TradeData(
             trade_id=trade_event['t'],
             symbol=trade_event['s'],
             side='buy' if trade_event['S'] == 'BUY' else 'sell',
             price=Decimal(trade_event['p']),
             amount=Decimal(trade_event['q']),
             timestamp=datetime.fromtimestamp(trade_event['T'] / 1000, tz=timezone.utc),
             # ... parse other fields
         )
         self._trade_cache.append(trade)
         self._cache_last_sync = trade.timestamp

         # Keep cache size manageable (last 500 trades)
         if len(self._trade_cache) > 500:
             self._trade_cache = self._trade_cache[-500:]
     ```
  4. **Modified P&L Calculation** (line 188-263):
     - Change `_calculate_pnl_from_trades()` to use `self._trade_cache` instead of API call
     - Only call API if cache not initialized
- **Why This Solves Issue #11:** WebSocket events update cache in-memory → P&L recalc uses cache → Zero API calls after initialization

#### Task 4a: Create WebSocket Service
- **File:** `dashboard/services/websocket_service.py` (NEW)
- **Action:** Create new module for Binance WebSocket streams
- **Details:**
  1. Create `BinanceWebSocketService` class with:
     - `__init__`: Store API credentials (from config), initialize state, store reference to DashboardState
     - `start()`: Start User Data Stream + Market Data streams
     - `stop()`: Clean shutdown of all streams
     - `_start_user_stream()`: User Data Stream for orders/balances
     - `_start_market_stream()`: Combined ticker stream for all symbols
     - `_handle_user_event()`: Route executionReport → update trade cache, outboundAccountPosition → trigger refresh
     - `_handle_ticker_event()`: Update prices from ticker stream → trigger UI refresh
  2. **Credential Management:**
     ```python
     from dashboard.config import config
     # Read bot's Binance credentials from environment
     api_key = os.getenv("EXCHANGE__API_KEY", "")
     api_secret = os.getenv("EXCHANGE__API_SECRET", "")

     # Create Binance AsyncClient
     self._client = await AsyncClient.create(api_key, api_secret, testnet=False)
     ```
  3. Follow existing `WebSocketHandler` pattern from `src/crypto_bot/exchange/websocket_handler.py`:
     - Callback-based subscriptions
     - Exponential backoff for reconnection (1s, 2s, 4s... up to 60s)
     - Graceful fallback flag when WebSocket unavailable
     - Connection state callback: `on_connection_change(bool)` → updates `state._websocket_connected`
  4. Use `python-binance`:
     ```python
     from binance import AsyncClient, BinanceSocketManager

     async def _start_user_stream(self):
         """Start User Data Stream for order/balance updates.

         Note: BinanceSocketManager handles listenKey creation and keepalive automatically.
         The library sends keepalive pings every 30 minutes internally.
         """
         bm = BinanceSocketManager(self._client, user_timeout=60)
         async with bm.user_socket() as stream:
             while self._running:
                 msg = await stream.recv()
                 if msg['e'] == 'executionReport':
                     # Trade executed - update cache
                     await self._state._update_trade_cache_from_websocket(msg)
                     await self._state._calculate_pnl_from_trades()  # Recalc from cache
                 elif msg['e'] == 'outboundAccountPosition':
                     # Balance changed - trigger tier1 refresh
                     await self._state.refresh_tier1()
     ```
  5. **Market Data Stream** (ticker updates):
     ```python
     async def _start_market_stream(self, symbols: list[str]):
         """Start combined ticker stream for all symbols."""
         streams = [f"{s.lower().replace('/', '')}@ticker" for s in symbols]
         bm = BinanceSocketManager(self._client)
         async with bm.multiplex_socket(streams) as stream:
             while self._running:
                 msg = await stream.recv()
                 symbol = msg['data']['s']  # e.g., 'BTCUSDT'
                 price = Decimal(msg['data']['c'])  # Close price
                 await self._state.on_websocket_ticker(symbol, price)
     ```
- **Notes:**
  - WebSocket URL: `wss://stream.binance.com:9443/stream?streams=...` (handled by library)
  - Expose `is_connected` property for UI status
  - Store reference to `DashboardState` for cache updates
  - **listenKey Keepalive**: `python-binance` BinanceSocketManager handles this automatically (Issue #5 resolved)

#### Task 5: Update DashboardState for Separated P&L
- **File:** `dashboard/state.py`
- **Action:** Expose existing realized/unrealized P&L calculation (currently discarded)
- **Details:**
  1. Add new state attributes after existing `total_pnl` (line ~62):
     ```python
     self.realized_pnl: Decimal = Decimal("0")
     self.unrealized_pnl: Decimal = Decimal("0")
     # total_pnl already exists
     ```
  2. **REPLACE lines 224-238** in `_calculate_pnl_from_trades()`:
     - Current code receives `total_realized` and `total_unrealized` but only stores `total_pnl`
     - New code stores all three values:
       ```python
       # Calculate portfolio P&L
       total_realized, total_unrealized, total_pnl, total_cycles = (
           calculate_portfolio_pnl(trades_by_symbol, current_prices)
       )

       self.realized_pnl = total_realized      # NEW: expose realized
       self.unrealized_pnl = total_unrealized  # NEW: expose unrealized
       self.total_pnl = total_pnl              # EXISTING
       ```
  3. **Modify P&L calculation to use trade cache** (line 203-205):
     ```python
     # Fetch trades from cache (initialized on startup, updated by WebSocket)
     if not self._trade_cache_initialized:
         all_trades = await self._api_client.get_trades(limit=200)
         self._trade_cache = all_trades
         self._trade_cache_initialized = True
     else:
         all_trades = self._trade_cache  # Use cached trades
     ```
- **Notes:** The calculation logic already exists in `pnl_calculator.py` - we're just exposing values that were previously discarded

#### Task 6: Update DashboardState for WebSocket Integration and UI Reactivity
- **File:** `dashboard/state.py`
- **Action:** Add WebSocket service integration, fallback logic, and UI refresh mechanism
- **Details:**
  1. Add WebSocket service reference and UI refresh callback (line ~57):
     ```python
     self._websocket_service: BinanceWebSocketService | None = None
     self._websocket_connected: bool = False
     self._ui_refresh_callback: callable | None = None  # For NiceGUI reactivity
     ```
  2. Add UI refresh registration method:
     ```python
     def register_ui_refresh(self, callback: callable) -> None:
         """Register UI refresh callback for WebSocket updates (Issue #7 fix)."""
         self._ui_refresh_callback = callback
     ```
  3. Add WebSocket ticker update handler with UI refresh:
     ```python
     async def on_websocket_ticker(self, symbol: str, price: Decimal) -> None:
         """Callback for WebSocket ticker updates - triggers UI refresh."""
         for pair in self.pairs:
             if pair.symbol == symbol:
                 pair.current_price = price
                 break

         # Trigger NiceGUI UI refresh if registered
         if self._ui_refresh_callback:
             self._ui_refresh_callback()
     ```
  4. **REST Polling Fallback Strategy** (modifies lines 343-360):
     ```python
     async def refresh_tier1(self) -> None:
         """Tier 1: Health + P&L (2s interval).

         Behavior:
         - Always check health via REST (no WebSocket equivalent)
         - Always calculate P&L (uses cached trades, not API call)
         - Skip fetching current prices if WebSocket connected (ticker stream provides)
         """
         if not self._websocket_connected:
             await self._refresh_with_retry()  # Full refresh via REST
         else:
             # WebSocket connected - only refresh health via REST
             if self._api_client:
                 self.health = await self._api_client.get_health()
                 self.connection_status = "connected" if self.health else self.connection_status
             # P&L always calculated from cache (no API call)
             await self._calculate_pnl_from_trades()

     async def refresh_tier2(self) -> None:
         """Tier 2: Pairs table, charts (5s interval).

         Behavior:
         - Skip if WebSocket connected (ticker stream + user stream provide this data)
         - Full refresh via REST if WebSocket offline
         """
         if not self._websocket_connected:
             await self.refresh()  # Full REST refresh
         # If WebSocket connected, data comes from streams - no action needed
     ```
  5. Add connection state change handler (called by WebSocket service):
     ```python
     def set_websocket_connected(self, connected: bool) -> None:
         """Update WebSocket connection state (called by WebSocketService)."""
         self._websocket_connected = connected
         if not connected:
             logger.warning("WebSocket disconnected - falling back to REST polling")
         else:
             logger.info("WebSocket connected - reducing REST polling")
     ```
- **Notes:**
  - Health checks ALWAYS use REST (no WebSocket equivalent)
  - P&L calculation uses trade cache (zero API calls after init)
  - Ticker prices from WebSocket when connected, REST when offline
  - UI reactivity handled via callback pattern (NiceGUI can call `.refresh()` on components)

#### Task 7: Update Header for 3-Value P&L Display
- **File:** `dashboard/components/header.py`
- **Action:** Replace single P&L display with Realized / Unrealized / Total
- **Details:**
  1. Modify `_create_pnl_content()` function:
     ```python
     def _create_pnl_content() -> None:
         """Create professional 3-value P&L display."""
         with ui.row().classes("pnl-breakdown gap-4"):
             # Realized (Grid Profit)
             with ui.column().classes("pnl-item"):
                 ui.label("Realized").classes("pnl-label text-xs")
                 _create_pnl_value(state.realized_pnl, "realized")

             # Unrealized (Floating)
             with ui.column().classes("pnl-item"):
                 ui.label("Unrealized").classes("pnl-label text-xs")
                 _create_pnl_value(state.unrealized_pnl, "unrealized")

             # Total
             with ui.column().classes("pnl-item"):
                 ui.label("Total").classes("pnl-label text-xs font-bold")
                 _create_pnl_value(state.total_pnl, "total")
     ```
  2. Extract value formatting to helper:
     ```python
     def _create_pnl_value(pnl: Decimal, pnl_type: str) -> None:
         if pnl > 0:
             pnl_class = "pnl-positive"
             pnl_text = f"+€{pnl:.2f}"
         elif pnl < 0:
             pnl_class = "pnl-negative"
             pnl_text = f"-€{abs(pnl):.2f}"
         else:
             pnl_class = "pnl-neutral"
             pnl_text = "€0.00"
         ui.label(pnl_text).classes(f"pnl-value {pnl_class} {pnl_type}")
     ```
- **Notes:**
  - Use industry colors: green (#4CAF50) for profit, red (#F44336) for loss
  - Consider adding CSS for brief color flash on value change (200-500ms)

#### Task 8: Update Main for WebSocket Lifecycle and UI Refresh
- **File:** `dashboard/main.py`
- **Action:** Initialize WebSocket service, manage lifecycle, and wire UI refresh callbacks
- **Details:**
  1. Import WebSocket service:
     ```python
     from dashboard.services.websocket_service import BinanceWebSocketService
     from dashboard.services.api_client import exchange_breaker  # For status display
     ```
  2. Create global WebSocket service instance
  3. Modify `setup_polling()`:
     ```python
     async def setup_polling() -> None:
         # Initialize state and API client (existing)
         await state.initialize()

         # Initialize trade cache from REST before starting WebSocket
         await state._calculate_pnl_from_trades()  # Populates cache

         # Start WebSocket service
         ws_service = BinanceWebSocketService(state)
         try:
             await ws_service.start()
             state._websocket_service = ws_service
             state.set_websocket_connected(True)  # Use method for proper logging
             logger.info("WebSocket streams started")
         except Exception as e:
             logger.warning("WebSocket failed, using REST fallback: %s", e)
             state.set_websocket_connected(False)

         # REST polling as fallback (existing timers)
         ui.timer(config.poll_interval_tier1, state.refresh_tier1)
         ui.timer(config.poll_interval_tier2, state.refresh_tier2)
     ```
  4. **Register UI refresh callback** in `create_ui()` (after header created):
     ```python
     def create_ui() -> None:
         # ... existing UI setup ...

         # Create header
         header_container = create_header()

         # Register UI refresh callback for WebSocket updates (Issue #7 fix)
         def refresh_ui():
             if header_container:
                 header_container.refresh()
         state.register_ui_refresh(refresh_ui)

         # ... rest of UI setup ...
     ```
  5. Modify `shutdown_polling()`:
     ```python
     async def shutdown_polling() -> None:
         if state._websocket_service:
             await state._websocket_service.stop()
         await state.shutdown()
     ```
  6. **Add circuit breaker state to header** (address Issue #15):
     - In header status display, check `exchange_breaker.current_state`
     - Show "OFFLINE (Circuit Breaker)" vs "OFFLINE (No Response)"
- **Notes:**
  - WebSocket failure should NOT crash dashboard - fallback to REST
  - Trade cache initialized BEFORE WebSocket to avoid race condition
  - UI refresh callback ensures NiceGUI updates on WebSocket events

#### Task 9: Add CSS for P&L Display
- **File:** `dashboard/assets/css/theme.css`
- **Action:** Add styles for 3-value P&L layout
- **Details:**
  ```css
  .pnl-breakdown {
      display: flex;
      gap: 1rem;
  }
  .pnl-item {
      text-align: center;
  }
  .pnl-label {
      color: #9e9e9e;
      font-size: 0.75rem;
  }
  .pnl-value {
      font-size: 1rem;
      font-weight: 600;
  }
  .pnl-value.total {
      font-size: 1.25rem;
  }
  ```
- **Notes:** Follow existing theme patterns in the file

#### Task 10: Add Unit Tests for WebSocket Service
- **File:** `tests/unit/test_websocket_service.py` (NEW)
- **Action:** Test WebSocket reconnection and circuit breaker behavior
- **Details:**
  - Test exponential backoff calculation
  - Test graceful degradation when connection fails
  - Test callback invocation on message receipt
  - Mock `python-binance` client
- **Notes:** Use `pytest-asyncio` with `asyncio_mode="auto"`

#### Task 11: Add E2E Test for P&L Display
- **File:** `tests/e2e/test_dashboard_pnl.py` (NEW)
- **Action:** Verify P&L display shows 3 values
- **Details:**
  - Test that header contains "Realized", "Unrealized", "Total" labels
  - Test that positive P&L shows green styling
  - Test that negative P&L shows red styling
- **Notes:** Follow existing E2E patterns in `tests/e2e/test_dashboard_load.py`

### Acceptance Criteria

#### AC 1: Circuit Breaker Protection
- [ ] **Given** the Binance API is unavailable, **when** the dashboard makes 5 consecutive failed API calls, **then** the circuit breaker opens and subsequent calls return None immediately without attempting network requests.
- [ ] **Given** the circuit breaker is open, **when** 60 seconds have passed, **then** the circuit breaker enters half-open state and allows one test request.

#### AC 2: WebSocket Real-Time Updates
- [ ] **Given** WebSocket is connected, **when** a ticker price update arrives, **then** the corresponding pair's `current_price` is updated within 100ms.
- [ ] **Given** WebSocket is connected, **when** an order execution event arrives, **then** P&L is recalculated and UI reflects the new values.
- [ ] **Given** WebSocket connection drops, **when** reconnection attempts begin, **then** exponential backoff is applied (1s, 2s, 4s... up to 60s max).

#### AC 3: REST Fallback
- [ ] **Given** WebSocket fails to connect, **when** the dashboard starts, **then** REST polling continues at configured intervals (2s/5s).
- [ ] **Given** WebSocket was connected but disconnects, **when** reconnection fails, **then** REST polling resumes automatically.

#### AC 4: Separated P&L Display
- [ ] **Given** the dashboard is loaded, **when** trades exist, **then** the header displays three P&L values: "Realized", "Unrealized", and "Total".
- [ ] **Given** realized P&L is positive, **when** viewing the header, **then** the realized value shows green color (#4CAF50) with "+" prefix.
- [ ] **Given** unrealized P&L is negative, **when** viewing the header, **then** the unrealized value shows red color (#F44336) with "-" prefix.
- [ ] **Given** total P&L equals realized + unrealized, **when** values update, **then** the total always equals the sum of the other two.

#### AC 5: WebSocket Stream Reliability
- [ ] **Given** User Data Stream is active, **when** connection is maintained for >30 minutes, **then** the stream remains connected (keepalive handled by `python-binance` library automatically).
- [ ] **Given** WebSocket disconnects, **when** reconnection succeeds, **then** trade cache syncs trades since last known timestamp before resuming real-time updates.
- [ ] **Given** dashboard restarts while bot running, **when** startup completes, **then** trade cache populated from last 200 REST trades within 2 seconds.

## Additional Context

### Restart and Reconnect Behavior

**Dashboard Restart (while bot running):**
1. On startup, fetch last 200 trades from REST API → populate trade cache
2. Calculate initial P&L from cached trades
3. Start WebSocket streams
4. WebSocket events append to cache going forward
5. **Expected**: Brief (1-2s) stale data while cache initializes, then real-time updates

**WebSocket Reconnect (after disconnect):**
1. Exponential backoff reconnection (1s, 2s, 4s, 8s, 16s, max 60s)
2. On reconnect, fetch trades since `_cache_last_sync` timestamp
3. Merge new trades into cache (deduplicate by trade_id)
4. Recalculate P&L from updated cache
5. **Expected**: Short data gap filled by REST sync, then resume WebSocket updates

**Cache Size Management:**
- Keep last 500 trades in memory (rolling window)
- Older trades automatically pruned when cache exceeds limit
- 500 trades ≈ 2-3 days of active grid trading (sufficient for P&L calculation)

### Dependencies

**New packages to add to `pyproject.toml`:**
```toml
"python-binance>=1.0.19",
"pybreaker>=1.0.1",
```

**Dependency Considerations:**
- `python-binance` uses `aiohttp` for async HTTP
- Current stack uses `httpx` for REST API client
- Both libraries will coexist (acceptable for this phase)
- Future optimization: Consider migrating REST client to `aiohttp` or using `ccxt.pro` (Phase 2+)

**Runtime dependencies:**
- Binance API credentials (existing in environment: `EXCHANGE__API_KEY`, `EXCHANGE__API_SECRET`)
- Network access to `stream.binance.com:9443`

### Testing Strategy

| Test Type | File | Scope |
|-----------|------|-------|
| Unit | `tests/unit/test_websocket_service.py` | WebSocket reconnection logic, callback routing |
| Unit | `tests/unit/test_circuit_breaker.py` | Circuit breaker state transitions |
| Integration | `tests/integration/test_api_circuit_breaker.py` | Circuit breaker with real httpx client (mocked server) |
| E2E | `tests/e2e/test_dashboard_pnl.py` | P&L display shows 3 values in UI |

**Manual Testing Steps:**
1. Start dashboard with bot running → verify WebSocket connects (check logs)
2. Stop bot API → verify circuit breaker trips after 5 failures (check logs)
3. Restart bot API → verify circuit breaker recovers after 60s
4. Verify P&L header shows Realized/Unrealized/Total columns
5. Execute a trade → verify P&L values update in real-time via WebSocket

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| python-binance API changes | Low | High | Pin version, monitor releases |
| WebSocket connection instability | Medium | Medium | Robust reconnection with exponential backoff |
| Circuit breaker false positives | Low | Medium | Tune fail_max and reset_timeout based on observed behavior |
| P&L calculation edge cases | Low | High | Reuse existing tested `pnl_calculator.py` logic |

### Notes

- **Source Research:** `docs/dashboard/dashboard-research-2025-06-01.md`
- **Phase:** 1 of 3-phase hardening roadmap
- **KEY INSIGHT:** P&L separation logic already exists in `pnl_calculator.py` - this spec primarily exposes it in UI
- **Bot's existing `WebSocketHandler`** uses CCXT Pro; dashboard needs Binance-native streams for User Data Stream
- **DO NOT** modify bot core code - dashboard is a consumer only
