---
stepsCompleted: [1, 2, 3, 4]
workflowStatus: complete
inputDocuments:
  - 'docs/planning-artefacts/prd.md'
  - 'docs/planning-artefacts/architecture.md'
  - 'docs/planning-artefacts/ux-design-specification.md'
---

# CryptoTrader - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the CryptoTrader NiceGUI Dashboard, decomposing the requirements from the PRD, Architecture, and UX Design Specification into implementable stories.

**Project Goal:** Replace the Streamlit dashboard with a NiceGUI-based dashboard that eliminates flickering through WebSocket reactive bindings, enabling sub-second updates for critical trading data.

**Phased Delivery:**
- **MVP (v1.0):** Core monitoring with zero flickering - Panic Mode & Glance Mode support
- **v1.5:** Enhanced monitoring depth - Coffee Mode & Investigation Mode support
- **v2.0:** Feature expansion - Trade history, grid visualization, configuration

---

## Requirements Inventory

### Functional Requirements

**Dashboard Health & Status**
- FR1: User can see system health status (HEALTHY/DEGRADED/ERROR) immediately upon page load
- FR2: User can see health status without scrolling regardless of current view position
- FR3: User can distinguish health states through both color and text indicators
- FR4: User can see when health status was last updated

**Profit & Loss Monitoring**
- FR5: User can see total P&L for the current day
- FR6: User can see P&L per trading pair
- FR7: User can distinguish positive P&L from negative P&L through color coding
- FR8: User can see P&L values update in real-time without page refresh
- FR9: User can see P&L for multiple timeframes (1H/24H/7D/30D) [v1.5]

**Trading Pair Overview**
- FR10: User can see all active trading pairs simultaneously (4-5 pairs)
- FR11: User can see key metrics for each pair (current price, P&L, position)
- FR12: User can see number of active pairs vs expected pairs
- FR13: User can expand a pair row to see detailed information [v1.5]
- FR14: User can see open order counts per pair [v1.5]
- FR15: User can see recent trades for a specific pair [v1.5]

**Price Chart Visualization**
- FR16: User can see a price chart for the primary trading pair
- FR17: User can hover over the chart to see price details at specific points
- FR18: User can zoom into a specific time range on the chart
- FR19: User can pan across the chart timeline
- FR20: User can see trade execution markers on the chart [v1.5]
- FR21: User can switch between line and candlestick chart modes [v1.5]

**Real-Time Data Updates**
- FR22: Dashboard can update displayed data automatically without user action
- FR23: Dashboard can update data without causing visible page flickering
- FR24: Dashboard can show Tier 1 data (health, P&L) updates within 2 seconds of API response
- FR25: Dashboard can continue updating data continuously for 24+ hours

**Visual Presentation**
- FR26: User can view the dashboard in a dark color theme
- FR27: User can see the fixed header strip at all times regardless of scroll position
- FR28: User can read all critical information (Tier 1 data) without clicking or scrolling
- FR29: User can distinguish different information through consistent color coding

**Data Display**
- FR30: Dashboard can display prices with appropriate decimal precision per pair
- FR31: Dashboard can display P&L values in the configured currency (EUR)
- FR32: Dashboard can display timestamps in local timezone
- FR33: Dashboard can show "last updated" timestamps for data freshness awareness

**Future Capabilities (v2+)**
- FR34: User can view historical trade records with filtering [v2]
- FR35: User can view grid strategy visualization showing buy/sell levels [v2]
- FR36: User can view bot configuration settings (read-only) [v2]
- FR37: User can authenticate with a simple password if remote access enabled [v2]

### Non-Functional Requirements

**Performance**
- NFR1: Initial page load <1 second (time to first meaningful paint)
- NFR2: Chart render <3 seconds (time until chart displays data)
- NFR3: Tier 1 update latency <1 second (API response to DOM update)
- NFR4: Visual stability - zero flickering (no full-page redraws on data refresh)
- NFR5: Data polling overhead <5% CPU idle (measured during 24hr continuous run)

**Reliability**
- NFR6: Runtime stability 24+ hours continuous operation without restart
- NFR7: Memory growth <100MB from baseline (measured at 24hr mark)
- NFR8: Error recovery - auto-retry on API failure; dashboard continues if API temporarily unavailable
- NFR9: Browser tab persistence - dashboard resumes updates when tab returns to foreground

**Integration**
- NFR10: API compatibility - existing endpoints unchanged; no modifications to bot REST API for MVP
- NFR11: API port - Bot API on port 8080
- NFR12: WebSocket transport - use NiceGUI's built-in WebSocket for browser updates
- NFR13: Charting library - Plotly (consistent with existing Streamlit implementation)

**Maintainability**
- NFR14: Code organization - modular components (separate header, table, chart components)
- NFR15: Configuration - external config file; update poll intervals without code changes
- NFR16: Logging - console output for debug visibility
- NFR17: Python version - 3.10+ (match existing bot runtime environment)

### Additional Requirements

**From Architecture Document:**
- Dashboard runs on port 8081 (separate from Bot API on 8080)
- Use httpx async client for REST API calls with 5-second timeout
- Use Pydantic models for API response parsing
- Implement DataService singleton pattern for centralized data management
- Timer-based polling: 2s for Tier 1 (health, P&L), 5s for Tier 2 (chart, table)
- Error handling: graceful degradation with stale data indicators
- Project structure: dashboard/ folder with components/, services/, assets/ subdirectories

**From UX Design Specification:**
- Fixed header strip (48-56px) answering "Is everything okay?" instantly
- RAG status with icon + color + text (never color alone)
- Dark theme color palette: Background `#1a1a2e`, Surface `#0f3460`, Success `#00c853`, Warning `#ffc107`, Error `#ff5252`
- Monospace typography (Roboto Mono) for all numerical data
- Compact table rows (~40px) to fit 4-5 pairs without scrolling
- Silent Confidence UI - updates happen without visual disruption
- Header-first principle: all user journeys begin with the header strip

---

## FR Coverage Map

| FR | Epic | Story | Status |
|----|------|-------|--------|
| FR1 | Epic 3 | Story 3.1, 3.2 | MVP |
| FR2 | Epic 3 | Story 3.1 | MVP |
| FR3 | Epic 3 | Story 3.2 | MVP |
| FR4 | Epic 3 | Story 3.3 | MVP |
| FR5 | Epic 3 | Story 3.4 | MVP |
| FR6 | Epic 4 | Story 4.2 | MVP |
| FR7 | Epic 3 | Story 3.4 | MVP |
| FR8 | Epic 6 | Story 6.1 | MVP |
| FR9 | Epic 8 | Story 8.1 | v1.5 |
| FR10 | Epic 4 | Story 4.1 | MVP |
| FR11 | Epic 4 | Story 4.2 | MVP |
| FR12 | Epic 3 | Story 3.5 | MVP |
| FR13 | Epic 7 | Story 7.1 | v1.5 |
| FR14 | Epic 7 | Story 7.2 | v1.5 |
| FR15 | Epic 7 | Story 7.3 | v1.5 |
| FR16 | Epic 5 | Story 5.1 | MVP |
| FR17 | Epic 5 | Story 5.2 | MVP |
| FR18 | Epic 5 | Story 5.3 | MVP |
| FR19 | Epic 5 | Story 5.3 | MVP |
| FR20 | Epic 8 | Story 8.2 | v1.5 |
| FR21 | Epic 8 | Story 8.3 | v1.5 |
| FR22 | Epic 6 | Story 6.1 | MVP |
| FR23 | Epic 6 | Story 6.1 | MVP |
| FR24 | Epic 6 | Story 6.2 | MVP |
| FR25 | Epic 6 | Story 6.3 | MVP |
| FR26 | Epic 1 | Story 1.3 | MVP |
| FR27 | Epic 3 | Story 3.1 | MVP |
| FR28 | Epic 3 | Story 3.1 | MVP |
| FR29 | Epic 1 | Story 1.3 | MVP |
| FR30 | Epic 4 | Story 4.2 | MVP |
| FR31 | Epic 3 | Story 3.4 | MVP |
| FR32 | Epic 2 | Story 2.3 | MVP |
| FR33 | Epic 3 | Story 3.3 | MVP |
| FR34 | Epic 9 | Story 9.1-9.3 | v2.0 |
| FR35 | Epic 10 | Story 10.1 | v2.0 |
| FR36 | Epic 10 | Story 10.2 | v2.0 |
| FR37 | Epic 10 | Story 10.3 | v2.0 |

---

## Epic List

### MVP (v1.0) - Core Monitoring

| Epic | Title | Goal |
|------|-------|------|
| Epic 1 | Project Foundation & Setup | Establish dashboard project structure and dependencies |
| Epic 2 | Data Infrastructure | Implement API client and data service layer |
| Epic 3 | Header Strip & Status | Build the fixed header with health, P&L, and counts |
| Epic 4 | All-Pairs Table | Display all trading pairs with key metrics |
| Epic 5 | Price Chart | Interactive Plotly chart with hover and zoom |
| Epic 6 | Real-Time Updates & Stability | Timer-based polling with flicker-free updates |

### v1.5 - Enhanced Monitoring

| Epic | Title | Goal |
|------|-------|------|
| Epic 7 | Expandable Row Details | Per-pair deep dive with orders and trades |
| Epic 8 | Timeframe Performance & Chart Enhancements | Multi-timeframe P&L and chart improvements |

### v2.0 - Feature Expansion

| Epic | Title | Goal |
|------|-------|------|
| Epic 9 | Trade History | Historical trade records with filtering |
| Epic 10 | Grid Visualization & Configuration | Visual grid levels and settings view |

---

## Epic 1: Project Foundation & Setup

**Goal:** Establish the NiceGUI dashboard project structure, install dependencies, and configure the development environment with dark theme styling.

**User Value:** Provides the foundation that enables all subsequent dashboard features to be built consistently.

**NFRs Addressed:** NFR14 (modular components), NFR15 (external config), NFR17 (Python 3.10+)

---

### Story 1.1: Initialize Dashboard Project Structure

As a **developer**,
I want **the dashboard project structure created with proper folder organization**,
So that **code is organized consistently and future development is streamlined**.

**Acceptance Criteria:**

**Given** the CryptoTrader repository exists
**When** the dashboard project is initialized
**Then** the following directory structure is created:
```
dashboard/
├── main.py
├── config.py
├── state.py
├── components/
│   └── __init__.py
├── services/
│   └── __init__.py
├── assets/
│   └── css/
└── tests/
    └── __init__.py
```
**And** each `__init__.py` file is present for Python package recognition
**And** `.gitkeep` files are added to empty directories if needed

---

### Story 1.2: Install and Configure Dependencies

As a **developer**,
I want **all required Python packages installed and configured**,
So that **NiceGUI, httpx, Pydantic, and Plotly are available for development**.

**Acceptance Criteria:**

**Given** the dashboard project structure exists
**When** dependencies are configured
**Then** `requirements.txt` includes:
- `nicegui>=3.4.0`
- `httpx>=0.27.0`
- `pydantic>=2.0.0`
- `pydantic-settings>=2.0.0`
- `plotly>=5.0.0`
**And** running `pip install -r requirements.txt` succeeds
**And** `pyproject.toml` includes dashboard as a runnable module

---

### Story 1.3: Implement Dark Theme Configuration

As a **trader (Claudio)**,
I want **the dashboard to display in a professional dark theme**,
So that **it's comfortable for 3am monitoring and looks like a serious trading tool**.

**Acceptance Criteria:**

**Given** the dashboard application starts
**When** the page renders
**Then** the background color is `#1a1a2e` (dark navy)
**And** text primary color is `#e8e8e8` (light gray)
**And** all color tokens from UX spec are applied:
- Background Secondary: `#16213e`
- Surface: `#0f3460`
- Success: `#00c853`
- Warning: `#ffc107`
- Error: `#ff5252`
**And** Quasar dark mode is enabled by default
**And** `assets/css/theme.css` contains custom color overrides

---

### Story 1.4: Create Configuration Module

As a **developer**,
I want **a centralized configuration module using Pydantic Settings**,
So that **settings like API URL and poll intervals can be changed without code modifications**.

**Acceptance Criteria:**

**Given** the configuration module `config.py` exists
**When** the dashboard starts
**Then** the following settings are loaded with defaults:
- `api_base_url`: `http://localhost:8080`
- `dashboard_port`: `8081`
- `poll_interval_tier1`: `2.0` seconds
- `poll_interval_tier2`: `5.0` seconds
- `api_timeout`: `5.0` seconds
**And** settings can be overridden via environment variables with prefix `DASHBOARD_`
**And** the config is accessible as a singleton throughout the application

---

### Story 1.5: Implement Main Entry Point

As a **developer**,
I want **a main.py entry point that launches the NiceGUI application**,
So that **the dashboard can be started with a simple command**.

**Acceptance Criteria:**

**Given** `dashboard/main.py` exists
**When** running `python dashboard/main.py`
**Then** NiceGUI starts on port 8081
**And** the browser opens to `http://localhost:8081`
**And** the page displays a placeholder "CryptoTrader Dashboard" title
**And** dark theme is applied
**And** console shows "Dashboard started on port 8081"

---

## Epic 2: Data Infrastructure

**Goal:** Build the API client and data service layer that fetches data from the existing bot API and provides it to UI components.

**User Value:** Enables all dashboard components to display current trading data without duplicating API calls.

**NFRs Addressed:** NFR10 (API compatibility), NFR8 (error recovery), NFR3 (update latency)

---

### Story 2.1: Create Pydantic Data Models

As a **developer**,
I want **Pydantic models that represent API response data**,
So that **data is validated, typed, and easy to work with in components**.

**Acceptance Criteria:**

**Given** the services folder exists
**When** `data_models.py` is created
**Then** the following models are defined:
- `HealthResponse`: status (str), uptime_seconds (int), message (Optional[str])
- `PairData`: symbol (str), current_price (float), pnl_today (float), position_size (float), order_count (int)
- `DashboardData`: health (HealthResponse), pairs (list[PairData]), total_pnl (float), last_update (datetime)
**And** all models include field validation
**And** models can be instantiated from dict (API JSON response)

---

### Story 2.2: Implement API Client

As a **developer**,
I want **an async HTTP client that fetches data from the bot API**,
So that **the dashboard can retrieve health, P&L, and pair data**.

**Acceptance Criteria:**

**Given** the config module provides `api_base_url`
**When** `api_client.py` is implemented
**Then** it includes async methods:
- `get_health() -> HealthResponse`
- `get_pairs() -> list[PairData]`
- `get_total_pnl() -> float`
- `get_dashboard_data() -> DashboardData` (aggregates all)
**And** httpx is used with configured timeout (5 seconds)
**And** HTTP errors are caught and logged (not raised)
**And** on error, methods return `None` or last known value
**And** all API calls use the existing bot endpoints (no new endpoints)

---

### Story 2.3: Implement Dashboard State Manager

As a **developer**,
I want **a centralized state class that holds current dashboard data**,
So that **all components can access the same data without redundant API calls**.

**Acceptance Criteria:**

**Given** `state.py` is created
**When** `DashboardState` class is implemented
**Then** it holds:
- `health: HealthResponse | None`
- `pairs: list[PairData]`
- `total_pnl: float`
- `last_update: datetime | None`
- `connection_status: str` ("connected", "stale", "offline")
**And** it includes async method `refresh()` that calls APIClient
**And** `refresh()` updates `connection_status` based on API availability
**And** timestamps are converted to local timezone
**And** state is accessible as singleton throughout application

---

### Story 2.4: Implement Error State Handling

As a **trader (Claudio)**,
I want **the dashboard to gracefully handle API errors**,
So that **I see the last known data with a warning rather than a broken dashboard**.

**Acceptance Criteria:**

**Given** the API client encounters an error
**When** `refresh()` is called
**Then** existing state data is preserved (not cleared)
**And** `connection_status` changes to "stale" after 60 seconds without successful update
**And** `connection_status` changes to "offline" if API is unreachable
**And** `last_update` shows the timestamp of last successful fetch
**And** a warning is logged but no exception is raised

---

## Epic 3: Header Strip & Status

**Goal:** Build the fixed header component that answers "Is everything okay?" with health status, P&L, pair count, and order count.

**User Value:** Enables Panic Mode and Glance Mode by providing instant status comprehension in under 5 seconds.

**FRs Addressed:** FR1-FR5, FR7, FR12, FR27-FR28, FR31, FR33

---

### Story 3.1: Create Fixed Header Strip Layout

As a **trader (Claudio)**,
I want **a fixed header strip that stays visible at all times**,
So that **I can see critical status information without scrolling**.

**Acceptance Criteria:**

**Given** the dashboard page loads
**When** the header component renders
**Then** a header strip of 48-56px height is displayed at the top
**And** the header has position `sticky` with `top: 0`
**And** the header uses background color `#16213e`
**And** the header contains placeholder slots for: status, P&L, pair count, order count, timestamp
**And** scrolling the page keeps the header fixed at the top
**And** the header is the first element to render (before table and chart)

---

### Story 3.2: Implement RAG Status Indicator

As a **trader (Claudio)**,
I want **a Red/Amber/Green status indicator showing bot health**,
So that **I instantly know if the trading bot is healthy, degraded, or in error state**.

**Acceptance Criteria:**

**Given** the header strip exists
**When** the RAG status indicator is rendered
**Then** it displays icon + colored badge + text label:
- Healthy: `#00c853` green, circle icon `●`, text "HEALTHY"
- Degraded: `#ffc107` amber, diamond icon `◆`, text "DEGRADED"
- Error: `#ff5252` red, triangle icon `▲`, text "ERROR"
**And** healthy status is visually muted (doesn't demand attention)
**And** warning status draws attention with brighter color
**And** error status demands attention and is impossible to miss
**And** the indicator updates when `DashboardState.health` changes

---

### Story 3.3: Implement Last Updated Timestamp

As a **trader (Claudio)**,
I want **to see when data was last updated**,
So that **I can trust the data is current and not stale**.

**Acceptance Criteria:**

**Given** the header strip exists
**When** the timestamp component is rendered
**Then** it displays the last update time in format `HH:MM:SS`
**And** the time is shown in local timezone
**And** normal state shows secondary text color `#a0a0a0`
**And** if data is >60 seconds old, timestamp turns amber `#ffc107`
**And** the timestamp updates each time `DashboardState.refresh()` succeeds
**And** relative time option available (e.g., "5s ago")

---

### Story 3.4: Implement Total P&L Display

As a **trader (Claudio)**,
I want **to see my total profit/loss for today prominently displayed**,
So that **I immediately know if I'm up or down**.

**Acceptance Criteria:**

**Given** the header strip exists
**When** the P&L display component is rendered
**Then** it shows the total P&L with format: sign + currency + value (e.g., `+€47.32`)
**And** positive P&L uses green color `#00c853` with `+` sign
**And** negative P&L uses red color `#ff5252` with `-` sign
**And** zero P&L uses gray color `#a0a0a0`
**And** typography is monospace (Roboto Mono) for data clarity
**And** an upward arrow `▲` accompanies positive, downward `▼` for negative
**And** the value updates when `DashboardState.total_pnl` changes

---

### Story 3.5: Implement Pair Count Display

As a **trader (Claudio)**,
I want **to see how many trading pairs are active**,
So that **I know all my pairs are running as expected**.

**Acceptance Criteria:**

**Given** the header strip exists
**When** the pair count component is rendered
**Then** it displays active/expected pairs (e.g., "4/4 pairs")
**And** if all pairs active, text is secondary color `#a0a0a0`
**And** if fewer pairs active than expected, text turns amber `#ffc107`
**And** the component also shows total open order count (e.g., "7 ord")
**And** values update when `DashboardState.pairs` changes

---

## Epic 4: All-Pairs Table

**Goal:** Display all trading pairs in a compact table showing key metrics per pair.

**User Value:** Enables scanning all pairs at once without filtering, supporting the "all info visible" success criterion.

**FRs Addressed:** FR6, FR10-FR11, FR30

---

### Story 4.1: Create Pairs Table Component

As a **trader (Claudio)**,
I want **to see all my trading pairs in a single table**,
So that **I can compare performance across pairs at a glance**.

**Acceptance Criteria:**

**Given** the dashboard has pair data loaded
**When** the pairs table component renders
**Then** a table displays all 4-5 trading pairs
**And** each row is approximately 40px tall (compact density)
**And** all rows are visible without scrolling the table itself
**And** the table has dark theme styling matching `#0f3460` surface color
**And** the table is positioned below the header strip
**And** column headers are: Symbol, Price, P&L, Position, Orders

---

### Story 4.2: Implement Pair Row Data Display

As a **trader (Claudio)**,
I want **each pair row to show key metrics**,
So that **I can quickly assess each pair's status**.

**Acceptance Criteria:**

**Given** the pairs table exists
**When** a pair row is rendered
**Then** it displays:
- **Symbol**: Trading pair name (e.g., "BTC/USDT") in primary text color
- **Price**: Current price with appropriate decimal precision (e.g., $97,234.12)
- **P&L**: Per-pair P&L with color coding (green/red) and sign
- **Position**: Current position size (e.g., "0.15 BTC")
- **Orders**: Open order count (e.g., "15")
**And** all numerical values use monospace font
**And** prices include thousands separator for readability
**And** P&L shows currency symbol (EUR)

---

### Story 4.3: Implement Pair Row Hover State

As a **trader (Claudio)**,
I want **pair rows to highlight when I hover over them**,
So that **it's clear which row I'm looking at**.

**Acceptance Criteria:**

**Given** a pair row exists
**When** the mouse hovers over the row
**Then** the row background lightens by 10%
**And** the cursor changes to pointer (indicating clickability for v1.5)
**And** the hover transition is smooth (150ms)
**And** hover state is removed when mouse leaves

---

## Epic 5: Price Chart

**Goal:** Display an interactive Plotly price chart for the selected trading pair with hover tooltips and zoom/pan capabilities.

**User Value:** Enables Coffee Mode investigation by showing price action and supporting chart exploration.

**FRs Addressed:** FR16-FR19

---

### Story 5.1: Implement Basic Price Chart

As a **trader (Claudio)**,
I want **to see a price chart for my primary trading pair**,
So that **I can understand recent price movements**.

**Acceptance Criteria:**

**Given** price data is available from the API
**When** the chart component renders
**Then** a Plotly line chart displays price over time
**And** the chart height is approximately 300-400px
**And** the chart uses dark theme colors:
- Background: `#1a1a2e`
- Grid lines: `#0f3460`
- Price line: `#4a9eff` (accent)
**And** X-axis shows time, Y-axis shows price
**And** the chart renders within 3 seconds of page load
**And** the default timeframe shows the last 24 hours

---

### Story 5.2: Implement Chart Hover Tooltips

As a **trader (Claudio)**,
I want **to see price details when hovering over the chart**,
So that **I can investigate specific price points**.

**Acceptance Criteria:**

**Given** the price chart is displayed
**When** hovering over a data point
**Then** a tooltip appears showing:
- Exact price (with precision)
- Exact timestamp (local time)
**And** a crosshair cursor appears at the hover position
**And** the tooltip follows the mouse smoothly
**And** the tooltip uses dark theme styling

---

### Story 5.3: Implement Chart Zoom and Pan

As a **trader (Claudio)**,
I want **to zoom and pan the price chart**,
So that **I can investigate specific time periods in detail**.

**Acceptance Criteria:**

**Given** the price chart is displayed
**When** using mouse scroll wheel
**Then** the chart zooms in/out centered on cursor position
**When** clicking and dragging
**Then** the chart pans horizontally across time
**And** double-click resets to default view (24 hours)
**And** zoom/pan interactions feel responsive (<100ms)
**And** chart toolbar is hidden (interactions via mouse only)

---

### Story 5.4: Implement Chart Pair Selection

As a **trader (Claudio)**,
I want **to select which trading pair the chart displays**,
So that **I can investigate any pair's price action**.

**Acceptance Criteria:**

**Given** multiple trading pairs exist
**When** clicking on a pair row in the table
**Then** the chart updates to show that pair's price data
**And** a visual indicator shows which pair is selected (highlighted row)
**And** the chart title updates to show the selected pair symbol
**And** the chart transition is smooth (no flicker)

---

## Epic 6: Real-Time Updates & Stability

**Goal:** Implement timer-based polling that updates all components without flickering, supporting 24+ hour continuous operation.

**User Value:** Eliminates the core pain point (Streamlit flickering) and builds trust through stable, silent updates.

**FRs Addressed:** FR8, FR22-FR25
**NFRs Addressed:** NFR1-NFR9

---

### Story 6.1: Implement Timer-Based Polling

As a **trader (Claudio)**,
I want **the dashboard to automatically update data**,
So that **I always see current information without manual refresh**.

**Acceptance Criteria:**

**Given** the dashboard is running
**When** timer intervals elapse
**Then** Tier 1 data (health, total P&L) refreshes every 2 seconds
**And** Tier 2 data (pairs table, chart) refreshes every 5 seconds
**And** updates are triggered by `ui.timer()` NiceGUI mechanism
**And** updates happen silently without full page refresh
**And** only changed DOM elements update (surgical updates via WebSocket)
**And** there is zero visible flickering during updates

---

### Story 6.2: Verify Sub-Second Update Latency

As a **trader (Claudio)**,
I want **Tier 1 data to update within 1 second of API response**,
So that **I trust the data I'm seeing is current**.

**Acceptance Criteria:**

**Given** the API returns new data
**When** `DashboardState.refresh()` completes
**Then** the header strip updates within 1 second
**And** the timestamp updates to reflect the new fetch time
**And** P&L changes are reflected immediately
**And** health status changes are reflected immediately
**And** latency can be measured via console logging

---

### Story 6.3: Implement 24-Hour Runtime Stability

As a **trader (Claudio)**,
I want **the dashboard to run continuously for 24+ hours**,
So that **I can rely on it for overnight monitoring**.

**Acceptance Criteria:**

**Given** the dashboard is started
**When** running for 24 hours continuously
**Then** memory usage stays within 100MB of startup baseline
**And** no memory leaks occur in timers or state objects
**And** WebSocket connection remains stable
**And** all components continue updating correctly
**And** browser tab can be backgrounded and foregrounded without issues

---

### Story 6.4: Implement Connection Recovery

As a **trader (Claudio)**,
I want **the dashboard to recover from network interruptions**,
So that **temporary connectivity issues don't require manual intervention**.

**Acceptance Criteria:**

**Given** the API becomes temporarily unavailable
**When** the network is restored
**Then** the dashboard automatically resumes updates
**And** no manual refresh is required
**And** the header shows "Reconnecting..." during recovery attempts
**And** successful reconnection shows normal status
**And** multiple retry attempts occur with backoff (1s, 2s, 4s)

---

## Epic 7: Expandable Row Details (v1.5)

**Goal:** Enable per-pair deep dive by expanding table rows to show order details and recent trades.

**User Value:** Supports Coffee Mode and Investigation Mode by providing depth on demand.

**FRs Addressed:** FR13-FR15

---

### Story 7.1: Implement Row Expansion Toggle

As a **trader (Claudio)**,
I want **to click a pair row to expand it**,
So that **I can see more details about that specific pair**.

**Acceptance Criteria:**

**Given** a pair row exists in the table
**When** clicking the row
**Then** an expansion panel opens below the row
**And** the expansion animation takes ~200ms
**And** only one row can be expanded at a time (previous collapses)
**And** clicking again collapses the row
**And** an expand/collapse icon indicates the state

---

### Story 7.2: Display Order Details in Expansion

As a **trader (Claudio)**,
I want **to see open orders for a pair in the expanded view**,
So that **I can understand the grid setup for that pair**.

**Acceptance Criteria:**

**Given** a pair row is expanded
**When** the expansion panel renders
**Then** it shows:
- Buy order count
- Sell order count
- Order price range (lowest buy to highest sell)
**And** orders are fetched on-demand (only when expanded)
**And** the data uses the same formatting as the main table

---

### Story 7.3: Display Recent Trades in Expansion

As a **trader (Claudio)**,
I want **to see recent trades for a pair**,
So that **I can understand recent trading activity**.

**Acceptance Criteria:**

**Given** a pair row is expanded
**When** the expansion panel renders
**Then** it shows the last 5 trades with:
- Trade direction (buy/sell)
- Price
- Amount
- Timestamp
**And** buys are shown in green, sells in red
**And** trade data is fetched on-demand

---

## Epic 8: Timeframe Performance & Chart Enhancements (v1.5)

**Goal:** Add multi-timeframe P&L summary and enhance chart with trade markers and candlestick mode.

**User Value:** Deepens Coffee Mode experience with performance trends and execution visibility.

**FRs Addressed:** FR9, FR20-FR21

---

### Story 8.1: Implement Timeframe Performance Row

As a **trader (Claudio)**,
I want **to see P&L across multiple timeframes**,
So that **I can understand performance trends**.

**Acceptance Criteria:**

**Given** the header strip exists
**When** the timeframe row renders (below header)
**Then** it displays P&L for: 1H, 24H, 7D, 30D
**And** each timeframe shows percentage change and absolute value
**And** positive values are green, negative are red
**And** the row is 32-40px tall
**And** the row scrolls with content (not fixed like header)

---

### Story 8.2: Add Trade Markers to Chart

As a **trader (Claudio)**,
I want **to see where trades executed on the price chart**,
So that **I can correlate price action with bot activity**.

**Acceptance Criteria:**

**Given** the price chart is displayed
**When** trade data is available
**Then** trade markers appear on the chart:
- Buy trades: green upward triangle
- Sell trades: red downward triangle
**And** hovering a marker shows trade details (price, amount, time)
**And** markers scale appropriately when zooming

---

### Story 8.3: Implement Candlestick Chart Toggle

As a **trader (Claudio)**,
I want **to switch between line and candlestick chart**,
So that **I can see OHLC data when investigating**.

**Acceptance Criteria:**

**Given** the price chart is displayed
**When** a toggle control is clicked
**Then** the chart switches between line mode and candlestick mode
**And** candlestick colors: green for up candles, red for down
**And** the toggle remembers preference during session
**And** chart data is preserved during toggle (no refetch)

---

## Epic 9: Trade History (v2.0)

**Goal:** Display historical trade records with filtering capabilities.

**User Value:** Provides full trade audit capability for detailed analysis.

**FRs Addressed:** FR34

---

### Story 9.1: Create Trade History Tab

As a **trader (Claudio)**,
I want **a dedicated area for viewing trade history**,
So that **I can review past trades without cluttering the main view**.

**Acceptance Criteria:**

**Given** the dashboard is in v2.0
**When** implementing trade history
**Then** a tab or collapsible section is added for "Trade History"
**And** the main dashboard view remains unchanged when history is hidden
**And** tab navigation uses NiceGUI's built-in tab components

---

### Story 9.2: Implement Trade History Table

As a **trader (Claudio)**,
I want **to see a table of historical trades**,
So that **I can review execution details**.

**Acceptance Criteria:**

**Given** the trade history tab is open
**When** the table renders
**Then** it displays columns: Time, Pair, Side, Price, Amount, Fee, P&L
**And** trades are sorted newest first by default
**And** pagination is available for large datasets
**And** trade data comes from existing bot API endpoints

---

### Story 9.3: Implement Trade History Filtering

As a **trader (Claudio)**,
I want **to filter trade history by pair and date range**,
So that **I can find specific trades**.

**Acceptance Criteria:**

**Given** the trade history table exists
**When** filters are applied
**Then** trades can be filtered by:
- Trading pair (dropdown)
- Date range (start/end date pickers)
- Side (buy/sell/all)
**And** filters update the table without page refresh
**And** filter state is preserved during session

---

## Epic 10: Grid Visualization & Configuration (v2.0)

**Goal:** Display grid strategy visualization and read-only configuration view.

**User Value:** Provides visibility into grid setup and bot configuration without risking accidental changes.

**FRs Addressed:** FR35-FR37

---

### Story 10.1: Implement Grid Visualization

As a **trader (Claudio)**,
I want **to see a visual representation of my grid levels**,
So that **I can understand the buy/sell grid structure**.

**Acceptance Criteria:**

**Given** grid configuration data is available
**When** the grid visualization renders
**Then** it shows buy levels as green horizontal lines
**And** sell levels as red horizontal lines
**And** current price is highlighted
**And** filled orders are indicated differently from open orders
**And** the visualization is overlaid on or adjacent to the price chart

---

### Story 10.2: Implement Configuration View

As a **trader (Claudio)**,
I want **to see bot configuration settings**,
So that **I can verify the bot is configured as expected**.

**Acceptance Criteria:**

**Given** configuration data is available from the API
**When** the configuration view renders
**Then** it displays key settings:
- Trading pairs
- Grid spacing
- Order sizes
- Risk parameters
**And** all settings are read-only (no edit capability)
**And** values are formatted for readability
**And** the view is accessed via a tab or collapsible section

---

### Story 10.3: Implement Simple Authentication (Optional)

As a **trader (Claudio)**,
I want **to add password protection if accessing remotely**,
So that **the dashboard isn't openly accessible on the network**.

**Acceptance Criteria:**

**Given** remote access is enabled
**When** authentication is configured
**Then** a simple password prompt appears on page load
**And** successful authentication grants access to dashboard
**And** session persists across page refreshes (cookie/token)
**And** failed attempts show error message
**And** authentication can be disabled for localhost-only use

---

## Implementation Notes

### Development Sequence Recommendation

**Phase 1: Foundation (Epics 1-2)**
1. Story 1.1 → Project structure
2. Story 1.2 → Dependencies
3. Story 1.3 → Dark theme
4. Story 1.4 → Config module
5. Story 1.5 → Main entry point
6. Story 2.1 → Data models
7. Story 2.2 → API client
8. Story 2.3 → State manager
9. Story 2.4 → Error handling

**Phase 2: Core UI (Epics 3-5)**
10. Story 3.1 → Header layout
11. Story 3.2 → RAG status
12. Story 3.3 → Timestamp
13. Story 3.4 → P&L display
14. Story 3.5 → Pair count
15. Story 4.1-4.3 → Pairs table
16. Story 5.1-5.4 → Price chart

**Phase 3: Real-Time (Epic 6)**
17. Story 6.1 → Timer polling
18. Story 6.2 → Latency verification
19. Story 6.3 → 24hr stability
20. Story 6.4 → Connection recovery

**Phase 4: Enhancements (Epics 7-8) - v1.5**
21. Stories 7.1-7.3 → Expandable rows
22. Stories 8.1-8.3 → Timeframe & chart enhancements

**Phase 5: Expansion (Epics 9-10) - v2.0**
23. Stories 9.1-9.3 → Trade history
24. Stories 10.1-10.3 → Grid & config

### Testing Strategy

- **Unit Tests:** API client, data models, state manager
- **Component Tests:** Individual UI component rendering
- **Integration Tests:** Full data flow from API to UI
- **Manual Tests:** Visual verification of dark theme, flickering absence
- **Stability Tests:** 24-hour runtime monitoring

### Definition of Done (per Story)

- [ ] Code implemented following architecture patterns
- [ ] Unit tests passing (where applicable)
- [ ] Manual verification completed
- [ ] No console errors
- [ ] Dark theme styling consistent
- [ ] Documented in code (docstrings)
