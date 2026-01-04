# Epic: Phase 1 - API Client & Data Layer

**Epic Owner:** Development Team
**Priority:** Critical - Required for backend communication
**Dependencies:** Epic 1 (Project Setup), Backend API (Phase 4 of core bot)

---

## Overview

This epic implements the backend communication layer using httpx with connection pooling, caching strategies, and async batch fetching for optimal performance.

### Key Deliverables
- httpx client with connection pooling
- Endpoint-specific fetch functions with appropriate caching
- Async batch fetching for dashboard initialization
- Error handling and retry logic

### Backend Endpoints (from core bot)
| Endpoint | Purpose |
|----------|---------|
| `/api/trades` | Recent trade history |
| `/api/positions` | Current open positions |
| `/api/pnl` | Profit/loss summary |
| `/api/equity` | Equity curve data |
| `/api/status` | Bot operational status |
| `/health` | Health check |

---

## Story 3.1: Create httpx Client with Connection Pooling

**Story Points:** 3
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a cached httpx client with connection pooling
**So that** API calls are efficient and don't create new connections per request

### Background
httpx is preferred over requests because it supports both sync and async APIs with built-in connection pooling, critical for dashboards polling multiple endpoints.

### Acceptance Criteria

- [ ] Create `components/api_client.py`:
  ```python
  import httpx
  import streamlit as st
  from typing import Dict, Any

  API_BASE_URL = "http://localhost:8080"

  @st.cache_resource
  def get_http_client() -> httpx.Client:
      """Get cached HTTP client with connection pooling."""
      return httpx.Client(
          base_url=API_BASE_URL,
          timeout=httpx.Timeout(10.0, connect=5.0),
          limits=httpx.Limits(
              max_keepalive_connections=5,
              max_connections=10
          )
      )
  ```
- [ ] Configure appropriate timeouts (10s request, 5s connect)
- [ ] Set connection pool limits (5 keepalive, 10 max)
- [ ] Use `@st.cache_resource` for singleton pattern
- [ ] Support configurable base URL (environment variable)
- [ ] Handle client lifecycle on app shutdown

### Technical Notes
- `@st.cache_resource` ensures single client instance across sessions
- Connection pooling reuses TCP connections, reducing latency
- Timeout of 10s balances responsiveness with API reliability
- Consider adding retry middleware for transient failures

### Definition of Done
- HTTP client initializes with connection pooling
- Client reused across multiple API calls
- Timeouts prevent hanging on unresponsive backend
- Base URL configurable via environment variable

---

## Story 3.2: Implement Endpoint-Specific Fetch Functions

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** typed fetch functions for each API endpoint
**So that** data fetching is consistent and type-safe

### Acceptance Criteria

- [ ] Implement fetch functions with appropriate TTLs:
  ```python
  @st.cache_data(ttl=5)
  def fetch_trades() -> Dict[str, Any]:
      """Fetch recent trades (5s cache)."""
      try:
          response = get_http_client().get("/api/trades")
          response.raise_for_status()
          return response.json()
      except httpx.HTTPError as e:
          st.error(f"Failed to fetch trades: {e}")
          return {"trades": [], "error": str(e)}

  @st.cache_data(ttl=5)
  def fetch_positions() -> Dict[str, Any]:
      """Fetch open positions (5s cache)."""
      try:
          response = get_http_client().get("/api/positions")
          response.raise_for_status()
          return response.json()
      except httpx.HTTPError as e:
          st.error(f"Failed to fetch positions: {e}")
          return {"positions": [], "error": str(e)}

  @st.cache_data(ttl=10)
  def fetch_pnl() -> Dict[str, Any]:
      """Fetch P&L summary (10s cache)."""
      try:
          response = get_http_client().get("/api/pnl")
          response.raise_for_status()
          return response.json()
      except httpx.HTTPError as e:
          st.error(f"Failed to fetch P&L: {e}")
          return {"total": 0, "unrealized": 0, "error": str(e)}

  @st.cache_data(ttl=10)
  def fetch_equity() -> Dict[str, Any]:
      """Fetch equity curve data (10s cache)."""
      try:
          response = get_http_client().get("/api/equity")
          response.raise_for_status()
          return response.json()
      except httpx.HTTPError as e:
          st.error(f"Failed to fetch equity: {e}")
          return {"data": [], "error": str(e)}

  @st.cache_data(ttl=30)
  def fetch_status() -> Dict[str, Any]:
      """Fetch bot status (30s cache)."""
      try:
          response = get_http_client().get("/api/status")
          response.raise_for_status()
          return response.json()
      except httpx.HTTPError as e:
          st.error(f"Failed to fetch status: {e}")
          return {"running": False, "error": str(e)}

  @st.cache_data(ttl=60)
  def fetch_health() -> Dict[str, Any]:
      """Fetch health check (60s cache)."""
      try:
          response = get_http_client().get("/health")
          response.raise_for_status()
          return response.json()
      except httpx.HTTPError as e:
          return {"healthy": False, "error": str(e)}
  ```
- [ ] Handle HTTP errors gracefully with fallback values
- [ ] Show user-friendly error messages
- [ ] Return typed dictionaries with sensible defaults

### Technical Notes

**Caching Strategy by Data Type:**

| Endpoint | TTL | Rationale |
|----------|-----|-----------|
| `/api/trades`, `/api/positions` | 5s | Real-time trading data |
| `/api/pnl`, `/api/equity` | 10s | Computed values, slightly stale OK |
| `/api/status` | 30s | Slow-changing operational state |
| `/health` | 60s | Infrastructure status |

### Definition of Done
- All fetch functions implemented with appropriate TTLs
- HTTP errors caught and handled gracefully
- Fallback values prevent UI crashes
- Type hints on all functions

---

## Story 3.3: Build Async Batch Fetching for Dashboard Init

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** developer
**I want** concurrent API fetching on dashboard load
**So that** initial page render is fast

### Acceptance Criteria

- [ ] Implement async batch fetch:
  ```python
  import asyncio
  import httpx

  async def fetch_all_dashboard_data() -> Dict[str, Any]:
      """Fetch all dashboard data concurrently."""
      async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
          tasks = [
              client.get("/api/trades"),
              client.get("/api/positions"),
              client.get("/api/pnl"),
              client.get("/api/equity"),
              client.get("/api/status"),
          ]
          responses = await asyncio.gather(*tasks, return_exceptions=True)

          return {
              "trades": _parse_response(responses[0], {}),
              "positions": _parse_response(responses[1], {}),
              "pnl": _parse_response(responses[2], {}),
              "equity": _parse_response(responses[3], {}),
              "status": _parse_response(responses[4], {}),
          }

  def _parse_response(response, default):
      """Parse response or return default on error."""
      if isinstance(response, Exception):
          return default
      try:
          response.raise_for_status()
          return response.json()
      except:
          return default

  @st.cache_data(ttl=5)
  def get_all_data() -> Dict[str, Any]:
      """Cached wrapper for batch fetch."""
      return asyncio.run(fetch_all_dashboard_data())
  ```
- [ ] Use `asyncio.gather` for concurrent requests
- [ ] Handle individual request failures without failing all
- [ ] Cache combined result with short TTL
- [ ] Reduce dashboard load time by ~5x vs sequential

### Technical Notes
- `asyncio.gather` executes all requests concurrently
- `return_exceptions=True` prevents one failure from canceling all
- Async client created per batch (not cached) for isolation
- Sequential fetches: ~500ms each × 5 = 2.5s
- Concurrent fetches: ~500ms total (network bound)

### Definition of Done
- Batch fetch reduces dashboard load time
- Individual failures don't break entire fetch
- Results cached appropriately
- Works correctly with Streamlit's execution model

---

## Story 3.4: Configure Caching Strategy

**Story Points:** 2
**Priority:** P1 - High

### Description
**As a** developer
**I want** documented caching configuration
**So that** cache behavior is predictable and tunable

### Acceptance Criteria

- [ ] Document caching strategy in code comments
- [ ] Create cache clear utility:
  ```python
  def clear_all_caches():
      """Clear all data caches. Called on refresh."""
      st.cache_data.clear()

  def clear_trading_caches():
      """Clear only real-time trading data caches."""
      fetch_trades.clear()
      fetch_positions.clear()
  ```
- [ ] Support selective cache invalidation per endpoint
- [ ] Add cache statistics display (optional):
  ```python
  def show_cache_stats():
      """Display cache statistics in sidebar."""
      # Show cache hit/miss rates if available
      pass
  ```
- [ ] Configure cache TTLs via environment variables (optional)

### Technical Notes
- `@st.cache_data` caches by function arguments
- `.clear()` method available on cached functions
- Consider cache warming on app startup
- Monitor cache memory usage in production

### Definition of Done
- Caching strategy documented
- Cache clear functions available
- Selective invalidation works correctly
- Cache behavior predictable

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 3.1 Create httpx Client | 3 | P0 | Epic 1 |
| 3.2 Implement Fetch Functions | 5 | P0 | 3.1 |
| 3.3 Build Async Batch Fetching | 3 | P1 | 3.1 |
| 3.4 Configure Caching Strategy | 2 | P1 | 3.2 |
| **Total** | **13** | | |

---

## Sources & References

- [httpx Documentation](https://www.python-httpx.org/)
- [Streamlit Caching](https://docs.streamlit.io/library/advanced-features/caching)
- [asyncio.gather](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather)
