---
stepsCompleted: [1, 2, 3, 4, 7, 8, 9, 10, 11]
workflowStatus: complete
inputDocuments:
  - '_bmad-output/analysis/brainstorming-session-2026-01-05-dashboard-design.md'
  - '_bmad-output/analysis/brainstorming-session-2026-01-05.md'
  - 'docs/index.md'
  - 'docs/002-streamlit-dashboard/Epics-and-Stories-Overview.md'
workflowType: 'prd'
lastStep: 0
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 2
  projectDocs: 2
---

# Product Requirements Document - CryptoTrader

**Author:** Claudio
**Date:** 2026-01-05

## Executive Summary

CryptoTrader is an existing modular cryptocurrency trading platform consisting of a Python async trading bot (grid trading strategy, risk management, Binance integration) and a Streamlit-based monitoring dashboard.

We will replace the Streamlit dashboard with a NiceGUI-based dashboard that uses WebSocket reactive bindings to eliminate full-page refresh flickering - enabling sub-second updates for critical trading data.

### The Problem

The current Streamlit dashboard re-runs the entire script on every data refresh, causing distracting visual flickering. For a trading dashboard requiring frequent updates (1-10 second intervals), this creates more than just a poor user experience - it creates **anxiety**.

When checking positions at 3am during a volatile market, flickering makes it impossible to tell if the data is stale, if something broke, or if your money is safe. The current workaround of slowing refresh rates to 10-15 seconds is a compromise that delays critical information when it matters most.

### Why Now?

With trading activity increasing, the current 10-15 second refresh workaround is no longer acceptable. Critical price movements can occur in seconds - delayed or flickering data during volatile markets creates real risk of missed information.

### The Solution

Replace the Streamlit dashboard with a NiceGUI-based dashboard that uses WebSocket reactive bindings to update only changed DOM elements.

Think of it this way: *Unlike Streamlit which repaints the entire canvas on every update, NiceGUI surgically updates only what changed - like editing a single cell in a spreadsheet rather than reprinting the entire document.*

This eliminates flickering while enabling sub-second updates for critical data.

### What Makes This Special

This isn't just a technology swap. The migration is designed around **three distinct user personas**:

1. **Panic Mode (3am alert)** - Dashboard answers "Is everything okay?" in 10-30 seconds
2. **Coffee Mode (morning review)** - Performance trends and charts for reflection
3. **Glance Mode (5 seconds)** - Single-glance confirmation: "Up or down? Anything on fire?"

The key design principle: **A fixed header strip that answers the "5-second rule"** - system health, today's P&L, and key counts visible without scrolling or clicking.

### Information Hierarchy

The dashboard follows a deliberate three-tier information architecture:

- **Tier 1 (Always Visible):** System health indicator, total P&L, per-pair P&L summary
- **Tier 2 (Main Screen):** Price chart, open orders count
- **Tier 3 (One Click Away):** Trade history, grid details, configuration

### Implementation Approach

The migration follows a phased roadmap:

- **MVP (v1):** Fixed header, RAG status, all-pairs table, WebSocket updates, interactive chart, dark theme
- **v1.5:** Expandable row details, timeframe performance row, candlestick toggle
- **v2:** Trade history tab, grid visualization, configuration page

## Project Classification

**Technical Type:** Web Application (SPA-like dashboard)
**Domain:** Fintech (Cryptocurrency Trading)
**Complexity:** High
**Project Context:** Brownfield - replacing frontend component of existing system

### Technical Constraints

- Must integrate with existing aiohttp REST API (port 8080)
- NiceGUI runs on FastAPI - potential for API consolidation in future
- Must use existing Plotly charting patterns where possible
- Single user, laptop-first design (13-15" screen)
- 4-5 trading pairs displayed simultaneously
- Real-time updates via WebSocket for Tier 1 data (health, P&L)
- Dashboard will consume existing API unchanged; no backend modifications required for MVP

### Success Criteria (Preview)

- Dashboard updates in <1 second with zero visible flickering
- All current Streamlit dashboard features available in NiceGUI
- No backend API modifications required for MVP

### Non-Goals

- Mobile or tablet support (laptop-first design)
- Multi-user access or authentication changes
- Changes to trading strategy logic or risk parameters
- Real-time trade execution from dashboard (watch-only)

## Success Criteria

### User Success

**The Core Win:** "Finally, a dashboard that doesn't fight me."

- **Zero friction** - Dashboard feels responsive and smooth, never laggy or jumpy
- **Trust the data** - No uncertainty about whether displayed data is current
- **All info visible** - All trading pairs and key metrics visible without filtering or clicking
- **Anxiety reduction** - 3am checks are quick and reassuring, not a source of stress
- **Confidence in the bot** - Clear visibility that the trading system is working correctly

### Business Success

For a single-user personal trading tool, business success means:

- **Informed decisions** - Never miss critical information due to delayed or confusing data
- **Reduced stress** - Mental bandwidth freed from wrestling with the dashboard
- **Bot confidence** - Trust that the automated trading system is functioning as expected
- **Worth the effort** - Migration completed in weeks, not months

### Technical Success

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Initial render | <1 second | Time from navigation to first meaningful paint |
| Chart populated | <3 seconds | Time until price chart displays data |
| Tier 1 update latency | <1 second | Time from REST API response to DOM update |
| Visual stability | Zero flickering | Manual verification: no full-page redraws on data refresh |
| Feature parity | 100% MVP features | Checklist verification (see MVP scope) |
| Backend changes | None for MVP | No modifications to existing bot API |
| Runtime stability | 24+ hours | Memory stays within 100MB of startup baseline |
| Browser support | Chrome on laptop | Primary use case verified |

### Architecture Note

The dashboard uses **NiceGUI's internal WebSocket** for UI reactivity while **polling the existing REST API** for data. This means:
- Bot API remains unchanged (REST endpoints on port 8080)
- NiceGUI handles pushing data updates to the browser via its built-in WebSocket
- No new WebSocket endpoints needed on the bot backend

### Measurable Outcomes

- [ ] Dashboard initial render in <1 second
- [ ] Price chart populated within 3 seconds of page load
- [ ] Tier 1 data (header) updates in <1 second with no visible flicker
- [ ] All 4-5 trading pairs visible simultaneously without scrolling header
- [ ] RAG status indicator correctly reflects bot health state
- [ ] Price chart renders and updates without full re-draw
- [ ] P&L calculations match current Streamlit dashboard values
- [ ] Dashboard runs 24+ hours without memory growth >100MB

## Product Scope

### MVP - Minimum Viable Product

**Goal:** Replace Streamlit with functional NiceGUI dashboard - feature parity for daily monitoring.

**Streamlit Features Included in MVP:**
| Current Streamlit Page | MVP Coverage |
|------------------------|--------------|
| Dashboard (overview) | ✅ Full - header, P&L, chart |
| Positions & Orders | ✅ Partial - visible in pairs table |
| Risk Management | ✅ Partial - RAG status in header |
| Trade History | ❌ Deferred to v2 |
| Grid Strategy | ❌ Deferred to v2 |
| Configuration | ❌ Deferred to v2 |

**MVP Feature Table:**
| Feature | Priority | Notes |
|---------|----------|-------|
| Fixed header strip | Must | Status + P&L + counts, always visible |
| RAG health indicator | Must | Green/Yellow/Red based on bot /health endpoint |
| All-pairs table | Must | Horizontal rows showing all 4-5 pairs |
| Real-time updates | Must | NiceGUI timer + REST polling, WS push to browser |
| Interactive price chart | Must | Plotly line chart, hover for details |
| Dark theme | Must | Expected for trading UI |
| No authentication | Must | Single-user localhost - simplify for MVP |

### Growth Features (v1.5)

| Feature | Priority | Details |
|---------|----------|---------|
| Expandable row details | Should | Click pair row to show: open orders for that pair, position details, recent trades (last 5) |
| Timeframe performance row | Should | 1H / 24H / 7D / 30D P&L summary below header |
| Candlestick toggle | Could | Switch chart from line to candlestick mode |

### Vision (v2 and Beyond)

| Feature | Priority | Notes |
|---------|----------|-------|
| Trade history tab | Could | Port Streamlit trade history with filtering |
| Grid visualization | Could | Visual grid levels display |
| Configuration page | Could | Read-only settings view |
| Direct Binance WebSocket | Could | Bypass bot API for real-time prices |
| Simple auth | Could | Password prompt if needed for remote access |

## User Journeys

### Journey 1: Panic Claudio - The 3am Alert

Claudio wakes at 3:17am to his phone buzzing. A price alert: BTC just dropped 8% in the last hour. Heart racing, he grabs his laptop and opens the trading dashboard.

With the old Streamlit dashboard, this moment was torture. The page would load, then flicker as it refreshed. Is that P&L number current or stale? Did the refresh fail? The flickering made it impossible to trust what he was seeing, and the anxiety of not knowing whether his bot handled the volatility correctly kept him awake for another hour.

But tonight is different. The NiceGUI dashboard loads and stays stable. The fixed header immediately shows him what matters: 🟢 HEALTHY - the bot is running. His total P&L is down €23 for the day, but that's within his risk tolerance. The all-pairs table shows each position's status - some red, some green, all updating smoothly without the jarring full-page refresh.

He watches for thirty seconds. The prices tick. The P&L adjusts. No flickering, no uncertainty. He can see the bot executed three trades during the drop, buying at lower levels exactly as designed. The grid strategy is working.

Claudio closes his laptop and goes back to sleep. Total time awake: 4 minutes instead of the usual 45.

**This journey reveals requirements for:**
- Fixed header with health status always visible (no scrolling needed)
- RAG (Red/Amber/Green) status indicator based on bot health endpoint
- Total P&L prominently displayed with clear positive/negative indication
- All trading pairs visible simultaneously (no filtering required)
- Smooth real-time updates without page flickering
- Sub-second update latency for critical Tier 1 data

### Journey 2: Coffee Claudio - The Morning Review

It's 8:30am on a Saturday. Claudio makes his coffee and settles into his morning ritual: reviewing how his trading bot performed overnight and through the week.

The dashboard greets him with the fixed header strip: 🟢 HEALTHY, +€156.23 today, all 4 pairs active. Good start. But this morning isn't about quick glances - he wants to understand the story behind the numbers.

He notices the timeframe summary row below the header: +€156 (24H), +€412 (7D), +€1,847 (30D). The trend is positive and consistent. He feels good about his grid settings.

Curious about BTC's performance specifically, he clicks the BTC/USDT row in the pairs table. It expands smoothly, revealing detailed information: 15 open orders forming the grid, his current position size, and the last 5 trades executed. Three sells overnight at incrementally higher prices - the bot captured the upward movement perfectly.

He hovers over the price chart, and a tooltip shows him exactly where each trade occurred. The chart is interactive - he zooms into the overnight period, seeing the price action that triggered his sells. No flickering, no page reload, just smooth exploration.

After 10 minutes of satisfying review, he knows his bot is performing well. He closes the laptop and enjoys his coffee. The dashboard gave him exactly what he needed: detailed information when he wanted it, never forced upon him during quick checks.

**This journey reveals requirements for:**
- Timeframe performance summary (1H/24H/7D/30D)
- Expandable row details for per-pair deep dive
- Trade history visibility within pair details
- Interactive chart with hover tooltips
- Zoom/pan capabilities on price chart
- Trade markers showing execution points on chart

### Journey 3: Glance Claudio - The Five-Second Sanity Check

Claudio is in the middle of a video call with a client when his mind wanders to his trading bot. He hasn't checked it since this morning. Without missing a beat in the conversation, he switches to the dashboard tab already open in his browser.

The fixed header strip is all he needs. His eyes scan left to right in two seconds: 🟢 HEALTHY - good. +€47.32 Today in green text - up, not down. 4/4 pairs active - all running. Nothing red, nothing yellow, nothing flashing for attention.

He switches back to his video call. Total time away: five seconds. His client didn't even notice the brief glance sideways.

This is the promise of Glance Mode - the dashboard answers "Is everything okay?" without demanding attention, without requiring interaction, without needing a single click. The information hierarchy does its job: Tier 1 data is always visible, always current, always honest.

Three hours later, another glance. 🟡 DEGRADED catches his eye - the amber draws attention without panic. He makes a mental note to check it after his current task. The dashboard communicated a non-urgent issue in the same five-second window, trusting him to prioritize appropriately.

**This journey reveals requirements for:**
- Fixed header visible regardless of scroll position
- RAG status with visual hierarchy (green fades, yellow draws attention, red demands it)
- P&L with positive/negative color coding readable at a glance
- Active pair count showing running vs expected
- No loading spinners blocking header data

### Journey 4: Claudio the Investigator - When Something Seems Off

It's Tuesday afternoon and Claudio notices something unusual: his total P&L for the day is positive, but smaller than he expected given the market movement. The header shows +€12.45 but BTC is up 3% - shouldn't the grid have captured more profit?

He clicks the BTC/USDT row in the all-pairs table. The row expands smoothly, revealing the detail panel beneath it. He sees: 12 buy orders and 8 sell orders open, a position of 0.15 BTC, and only 3 completed trades today.

Only 3 trades? That's lower than usual. He hovers over the price chart and sees the trade markers - three small dots clustered in a narrow price range. The market moved up quickly, jumping past several grid levels without triggering sells.

Now he understands: the bot is working correctly, but the price gapped up overnight, skipping intermediate sell levels. The grid is repositioning. He could adjust grid spacing, but decides to wait - the strategy is sound, the bot is healthy, the day is still profitable.

The investigation took 90 seconds, not 10 minutes of hunting through multiple pages.

**This journey reveals requirements for:**
- Expandable row details with order counts
- Trade count visibility
- Trade markers on price chart
- Hover interaction for trade details
- Visual connection between chart events and P&L

### Journey Requirements Summary

| Journey | Primary Need | MVP Features | v1.5 Features |
|---------|-------------|--------------|---------------|
| Panic Mode (3am) | "Is everything okay?" | Fixed header, RAG status, P&L, no flickering | - |
| Coffee Mode (morning) | "Tell me the story" | Interactive chart | Timeframe summary, expandable details, trade markers |
| Glance Mode (5 sec) | "Up or down? Anything on fire?" | Header strip, color coding | - |
| Investigation | "Why is this happening?" | All-pairs table | Expandable details, chart-trade connection |

## Web Application Specific Requirements

### Architecture Model

**SPA-like Architecture:**
- NiceGUI runs as a single-page application with WebSocket-driven updates
- No full-page reloads after initial load
- State maintained in Python backend, pushed to browser via WebSocket
- Polling existing REST API (port 8080) for data updates

### Browser Support Matrix

| Browser | Version | Support Level |
|---------|---------|---------------|
| Chrome | Latest | Primary - fully tested |
| Firefox | Latest | Secondary - should work |
| Safari | Latest | Not supported |
| Edge | Latest | Not supported |

**Rationale:** Single user, single machine. Chrome is the development and runtime browser.

### Responsive Design

**Not Required for MVP:**
- Target: 13-15" laptop screen (1366x768 to 1920x1080)
- Fixed layout optimized for this viewport
- No mobile breakpoints
- No tablet support
- Horizontal scrolling acceptable for edge cases

### Performance Targets

Already defined in Technical Success criteria:

| Metric | Target |
|--------|--------|
| Initial render | <1 second |
| Chart population | <3 seconds |
| Tier 1 update latency | <1 second |
| Runtime stability | 24+ hours |
| Memory growth | <100MB from baseline |

### SEO Strategy

**Not Applicable:**
- Dashboard runs on localhost
- No public access
- No search engine indexing needed
- No meta tags, structured data, or sitemap required

### Accessibility Level

**Minimal (Personal Use):**
- No WCAG compliance required
- Color contrast: sufficient for readability in dark theme
- Keyboard navigation: not prioritized for MVP
- Screen reader support: not required

**Future consideration:** If remote access is added (v2+), reassess accessibility needs.

### Real-Time Update Strategy

**Hybrid Approach:**

| Component | Update Method | Frequency |
|-----------|---------------|-----------|
| Tier 1 (header) | REST poll → NiceGUI WS push | 1-2 seconds |
| Price chart | REST poll → Plotly update | 5-10 seconds |
| Pairs table | REST poll → Row update | 2-5 seconds |

NiceGUI's reactive binding ensures DOM updates are surgical (only changed elements), eliminating the Streamlit flicker problem.

## Project Scoping & Risk Mitigation

### Scope Classification

**Project Type:** Feature Migration (Streamlit → NiceGUI)
**Complexity:** Medium-High (new framework, real-time requirements)
**Resource Model:** Solo developer with AI assistance

### MVP Philosophy

**Chosen Approach:** Problem-Solving MVP

The MVP focuses on eliminating the core pain point (flickering) rather than adding features. Success is measured by:
- Zero flickering during data updates
- All current monitoring capabilities preserved
- No new features required - just better execution

This is a *replacement* project, not a *feature expansion* project.

### Scope Boundaries Summary

| Phase | Focus | User Journeys Supported |
|-------|-------|------------------------|
| MVP (v1) | Eliminate flickering, maintain feature parity | Panic Mode, Glance Mode |
| v1.5 | Enhanced monitoring depth | Coffee Mode, Investigation Mode |
| v2 | Feature expansion | All + new capabilities |

### Risk Mitigation Strategy

**Technical Risks:**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| NiceGUI learning curve | Medium | Medium | Start with simple components, iterate |
| Plotly integration issues | Low | High | Use existing Streamlit chart code as reference |
| WebSocket performance | Low | High | Test with sustained 24hr runs early |
| Memory leaks over time | Medium | Medium | Monitor baseline, set alerts |

**Implementation Risks:**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Feature creep | Medium | High | Strict MVP definition, defer all "nice-to-have" |
| API changes breaking dashboard | Low | Medium | Bot API frozen for MVP; no backend changes |
| Scope expansion | Medium | Medium | User journeys define boundaries |

**Contingency: Minimum Viable Fallback**

If blocked, the absolute minimum that delivers value:
1. Fixed header with RAG status
2. P&L display (total only)
3. Single static refresh button (no auto-update)

This fallback still solves the core problem (visibility) even if real-time updates prove difficult.

## Functional Requirements

### Dashboard Health & Status

- FR1: User can see system health status (HEALTHY/DEGRADED/ERROR) immediately upon page load
- FR2: User can see health status without scrolling regardless of current view position
- FR3: User can distinguish health states through both color and text indicators
- FR4: User can see when health status was last updated

### Profit & Loss Monitoring

- FR5: User can see total P&L for the current day
- FR6: User can see P&L per trading pair
- FR7: User can distinguish positive P&L from negative P&L through color coding
- FR8: User can see P&L values update in real-time without page refresh
- FR9: User can see P&L for multiple timeframes (1H/24H/7D/30D) [v1.5]

### Trading Pair Overview

- FR10: User can see all active trading pairs simultaneously (4-5 pairs)
- FR11: User can see key metrics for each pair (current price, P&L, position)
- FR12: User can see number of active pairs vs expected pairs
- FR13: User can expand a pair row to see detailed information [v1.5]
- FR14: User can see open order counts per pair [v1.5]
- FR15: User can see recent trades for a specific pair [v1.5]

### Price Chart Visualization

- FR16: User can see a price chart for the primary trading pair
- FR17: User can hover over the chart to see price details at specific points
- FR18: User can zoom into a specific time range on the chart
- FR19: User can pan across the chart timeline
- FR20: User can see trade execution markers on the chart [v1.5]
- FR21: User can switch between line and candlestick chart modes [v1.5]

### Real-Time Data Updates

- FR22: Dashboard can update displayed data automatically without user action
- FR23: Dashboard can update data without causing visible page flickering
- FR24: Dashboard can show Tier 1 data (health, P&L) updates within 2 seconds of API response
- FR25: Dashboard can continue updating data continuously for 24+ hours

### Visual Presentation

- FR26: User can view the dashboard in a dark color theme
- FR27: User can see the fixed header strip at all times regardless of scroll position
- FR28: User can read all critical information (Tier 1 data) without clicking or scrolling
- FR29: User can distinguish different information through consistent color coding

### Data Display

- FR30: Dashboard can display prices with appropriate decimal precision per pair
- FR31: Dashboard can display P&L values in the configured currency (EUR)
- FR32: Dashboard can display timestamps in local timezone
- FR33: Dashboard can show "last updated" timestamps for data freshness awareness

### Future Capabilities (v2+)

- FR34: User can view historical trade records with filtering [v2]
- FR35: User can view grid strategy visualization showing buy/sell levels [v2]
- FR36: User can view bot configuration settings (read-only) [v2]
- FR37: User can authenticate with a simple password if remote access enabled [v2]

## Non-Functional Requirements

### Performance

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| NFR1: Initial page load | <1 second | Time to first meaningful paint |
| NFR2: Chart render | <3 seconds | Time until chart displays data |
| NFR3: Tier 1 update latency | <1 second | API response to DOM update |
| NFR4: Visual stability | Zero flickering | No full-page redraws on data refresh |
| NFR5: Data polling overhead | <5% CPU idle | Measured during 24hr continuous run |

### Reliability

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| NFR6: Runtime stability | 24+ hours | Continuous operation without restart |
| NFR7: Memory growth | <100MB from baseline | Measured at 24hr mark |
| NFR8: Error recovery | Auto-retry on API failure | Dashboard continues operating if API temporarily unavailable |
| NFR9: Browser tab persistence | Survives background | Dashboard resumes updates when tab returns to foreground |

### Integration

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| NFR10: API compatibility | Existing endpoints unchanged | No modifications to bot REST API for MVP |
| NFR11: API port | Port 8080 | Standard configuration |
| NFR12: WebSocket transport | NiceGUI native | Use NiceGUI's built-in WebSocket for browser updates |
| NFR13: Charting library | Plotly | Consistent with existing Streamlit implementation |

### Maintainability

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| NFR14: Code organization | Modular components | Separate header, table, chart components |
| NFR15: Configuration | External config file | Update poll intervals without code changes |
| NFR16: Logging | Console output | Debug issues without attaching debugger |
| NFR17: Python version | 3.10+ | Match existing bot runtime environment |

