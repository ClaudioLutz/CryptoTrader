# Epic: Phase 3 - Real-Time Updates & WebSocket Integration

**Epic Owner:** Development Team
**Priority:** Medium - Enhanced real-time experience
**Dependencies:** Epic 4 (Dashboard Pages), Epic 5 (Charting)

---

## Overview

This epic implements advanced real-time update patterns using `@st.fragment` and optional WebSocket integration for sub-second price updates. These features enhance the trading experience but require careful implementation to avoid server overload.

### Key Deliverables
- Optimized st.fragment configuration for auto-refresh
- Optional WebSocket price feed integration
- Queue-based pattern for real-time data flow

### Performance Considerations
- Limit to 3-4 auto-refreshing fragments per page
- Use appropriate refresh intervals (2-5 seconds for most data)
- WebSocket for sub-second updates only when needed
- Monitor server load with multiple concurrent users

---

## Story 6.1: Configure st.fragment for Auto-Refresh Components

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** optimized st.fragment configurations
**So that** components refresh independently without page flicker

### Background
`@st.fragment(run_every=)` is stable since Streamlit 1.37. It enables partial page updates without full script reruns—essential for trading dashboards requiring 1-5 second refresh intervals.

### Acceptance Criteria

- [ ] Document fragment best practices:
  ```python
  # ✅ GOOD: Fragment for independent data refresh
  @st.fragment(run_every="2s")
  def live_metrics():
      data = fetch_cached_data()
      st.metric("Price", f"${data['price']:,.2f}")

  # ✅ GOOD: Static content outside fragment
  st.title("Dashboard")  # Doesn't refresh
  live_metrics()         # Refreshes every 2s

  # ❌ BAD: Complex widgets inside auto-refresh fragment
  @st.fragment(run_every="1s")
  def bad_fragment():
      st.selectbox("Choice", ["A", "B"])  # Resets on refresh!
      st.text_input("Input")              # Loses focus!

  # ✅ GOOD: Interactive widgets in non-auto fragment
  @st.fragment  # No run_every
  def interactive_panel():
      if st.button("Refresh"):
          st.rerun()
      st.selectbox("Filter", ["All", "BTC", "ETH"])
  ```
- [ ] Configure recommended refresh intervals:
  - Price metrics: 2 seconds
  - Position data: 3 seconds
  - Risk metrics: 5 seconds
  - Status indicators: 5 seconds
- [ ] Implement fragment error handling:
  ```python
  @st.fragment(run_every="2s")
  def safe_fragment():
      try:
          data = fetch_data()
          render_data(data)
      except Exception as e:
          st.error(f"Update failed: {e}")
          # Don't raise - let next refresh retry
  ```
- [ ] Limit fragments per page to 3-4
- [ ] Test with multiple concurrent users

### Technical Notes

**Fragment Limitations:**
- Cannot render widgets to externally created containers
- Return values ignored during fragment reruns (use session_state)
- Elements in external containers accumulate until full-app rerun
- Interactive widgets (buttons, inputs) may behave unexpectedly in auto-refresh fragments

**Recommended Pattern:**
```python
# Page structure
st.title("Page Title")           # Static

@st.fragment(run_every="2s")
def data_panel():                # Auto-refresh
    # Display-only content
    pass

data_panel()

@st.fragment                     # User-triggered refresh
def controls_panel():
    # Interactive widgets
    pass

controls_panel()
```

### Definition of Done
- Fragment patterns documented
- Refresh intervals configured per data type
- Error handling in all fragments
- No more than 4 fragments per page
- Tested with concurrent users

---

## Story 6.2: Implement WebSocket Price Feed (Optional)

**Story Points:** 8
**Priority:** P2 - Enhancement

### Description
**As a** trader
**I want** sub-second price updates via WebSocket
**So that** I see prices update in real-time without polling

### Background
For sub-second tick data, REST polling is inefficient. WebSocket with queue pattern provides real-time updates while maintaining Streamlit's execution model.

### Acceptance Criteria

- [ ] Create WebSocket handler:
  ```python
  import websocket
  import threading
  import queue
  import json
  import streamlit as st
  from streamlit.runtime.scriptrunner import add_script_run_ctx

  class PriceWebSocket:
      """WebSocket handler for real-time price updates."""

      def __init__(self, url: str):
          self.url = url
          self.queue = queue.Queue(maxsize=1000)
          self._ws = None
          self._thread = None
          self._running = False

      def _on_message(self, ws, message):
          """Handle incoming WebSocket message."""
          try:
              data = json.loads(message)
              # Only keep latest price, drop old if queue full
              if self.queue.full():
                  try:
                      self.queue.get_nowait()
                  except queue.Empty:
                      pass
              self.queue.put(data)
          except json.JSONDecodeError:
              pass

      def _on_error(self, ws, error):
          """Handle WebSocket error."""
          print(f"WebSocket error: {error}")

      def _on_close(self, ws, close_status_code, close_msg):
          """Handle WebSocket close."""
          self._running = False

      def _run(self):
          """Run WebSocket in background thread."""
          self._ws = websocket.WebSocketApp(
              self.url,
              on_message=self._on_message,
              on_error=self._on_error,
              on_close=self._on_close,
          )
          self._ws.run_forever()

      def start(self):
          """Start WebSocket connection."""
          if self._running:
              return
          self._running = True
          self._thread = threading.Thread(target=self._run, daemon=True)
          add_script_run_ctx(self._thread)  # Required for Streamlit
          self._thread.start()

      def stop(self):
          """Stop WebSocket connection."""
          self._running = False
          if self._ws:
              self._ws.close()

      def get_latest_price(self) -> dict | None:
          """Get latest price from queue."""
          latest = None
          while not self.queue.empty():
              try:
                  latest = self.queue.get_nowait()
              except queue.Empty:
                  break
          return latest
  ```
- [ ] Initialize WebSocket in session state:
  ```python
  def init_price_websocket():
      if "price_ws" not in st.session_state:
          ws = PriceWebSocket("wss://stream.binance.com:9443/ws/btcusdt@trade")
          ws.start()
          st.session_state.price_ws = ws

  init_price_websocket()
  ```
- [ ] Create display fragment:
  ```python
  @st.fragment(run_every="500ms")
  def live_price_display():
      ws = st.session_state.get("price_ws")
      if ws:
          price_data = ws.get_latest_price()
          if price_data:
              st.session_state.last_price = price_data.get("p")

      price = st.session_state.get("last_price", 0)
      st.metric("BTC/USDT", f"${float(price):,.2f}")
  ```
- [ ] Handle reconnection on disconnect
- [ ] Clean up WebSocket on session end
- [ ] Provide REST fallback when WebSocket unavailable

### Technical Notes
- `add_script_run_ctx` is required to access Streamlit context from threads
- Queue with `maxsize=1000` prevents memory issues
- Latest price pattern: drain queue, keep only most recent
- Fragment at 500ms polls queue, not network
- Binance WebSocket format: `{"e":"trade","p":"42500.00",...}`

### Definition of Done
- WebSocket connects to price stream
- Prices update sub-second in UI
- Reconnection handles disconnects
- Memory usage bounded
- Falls back to REST on failure

---

## Story 6.3: Build Queue-Based Price Update Pattern

**Story Points:** 5
**Priority:** P2 - Enhancement

### Description
**As a** developer
**I want** a clean pattern for real-time data flow
**So that** WebSocket data integrates seamlessly with Streamlit

### Acceptance Criteria

- [ ] Create reusable data queue component:
  ```python
  from dataclasses import dataclass, field
  from typing import Generic, TypeVar, Optional
  import queue
  from datetime import datetime

  T = TypeVar('T')

  @dataclass
  class QueuedData(Generic[T]):
      """Container for queued data with timestamp."""
      data: T
      timestamp: datetime = field(default_factory=datetime.utcnow)

  class DataQueue(Generic[T]):
      """Thread-safe queue for real-time data."""

      def __init__(self, maxsize: int = 100):
          self._queue: queue.Queue[QueuedData[T]] = queue.Queue(maxsize=maxsize)
          self._latest: Optional[QueuedData[T]] = None

      def put(self, data: T) -> None:
          """Add data to queue, dropping oldest if full."""
          item = QueuedData(data=data)
          if self._queue.full():
              try:
                  self._queue.get_nowait()
              except queue.Empty:
                  pass
          self._queue.put(item)
          self._latest = item

      def get_latest(self) -> Optional[T]:
          """Get most recent data, draining queue."""
          while not self._queue.empty():
              try:
                  self._latest = self._queue.get_nowait()
              except queue.Empty:
                  break
          return self._latest.data if self._latest else None

      def get_all(self) -> list[T]:
          """Get all queued data."""
          items = []
          while not self._queue.empty():
              try:
                  item = self._queue.get_nowait()
                  items.append(item.data)
                  self._latest = item
              except queue.Empty:
                  break
          return items
  ```
- [ ] Integrate with session state:
  ```python
  def get_price_queue() -> DataQueue:
      if "price_queue" not in st.session_state:
          st.session_state.price_queue = DataQueue(maxsize=1000)
      return st.session_state.price_queue
  ```
- [ ] Create polling fragment pattern:
  ```python
  @st.fragment(run_every="1s")
  def poll_and_display():
      queue = get_price_queue()
      latest = queue.get_latest()

      if latest:
          st.metric("Price", f"${latest['price']:,.2f}")
          st.caption(f"Updated: {latest['timestamp']}")
      else:
          st.info("Waiting for data...")
  ```
- [ ] Support multiple data streams (price, orders, status)
- [ ] Add timestamp tracking for staleness detection
- [ ] Implement data expiry (optional)

### Technical Notes
- Generic queue works for any data type
- `get_latest` drains queue to prevent backlog
- `get_all` useful for batch processing (e.g., chart updates)
- Timestamp enables staleness detection
- Consider TTL for automatic data expiry

### Definition of Done
- DataQueue class implemented and tested
- Integration with session state clean
- Multiple queues supported
- Timestamp tracking functional
- Pattern documented for reuse

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 6.1 Configure st.fragment Auto-Refresh | 5 | P0 | Epic 4 |
| 6.2 Implement WebSocket Price Feed | 8 | P2 | 6.1 |
| 6.3 Build Queue-Based Update Pattern | 5 | P2 | 6.2 |
| **Total** | **18** | | |

---

## Performance Guidelines

### Fragment Refresh Intervals

| Data Type | Interval | Rationale |
|-----------|----------|-----------|
| Price metrics | 2s | Balance freshness vs load |
| Positions | 3s | Changes infrequently |
| Risk metrics | 5s | Computed values |
| System status | 5s | Slow-changing |
| Charts | Manual | User-triggered refresh |

### Fragments Per Page Limits

| Page | Max Fragments | Auto-Refresh |
|------|---------------|--------------|
| Dashboard | 4 | 3 |
| Positions | 3 | 2 |
| Trade History | 2 | 0 |
| Risk Management | 3 | 2 |
| Grid Strategy | 2 | 1 |
| Configuration | 1 | 0 |

### Server Load Considerations
- Each auto-refresh fragment generates server request
- 4 fragments × 2s interval = 2 requests/second/user
- 10 concurrent users = 20 requests/second
- Monitor with multiple users before production

---

## Sources & References

- [Streamlit Fragments Documentation](https://docs.streamlit.io/library/api-reference/execution-flow/st.fragment)
- [websocket-client Python Library](https://websocket-client.readthedocs.io/)
- [Binance WebSocket Streams](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams)
- [Python Queue Documentation](https://docs.python.org/3/library/queue.html)
