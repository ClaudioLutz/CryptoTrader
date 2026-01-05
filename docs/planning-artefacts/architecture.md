---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
workflowStatus: complete
completedAt: '2026-01-05'
inputDocuments:
  - 'docs/planning-artefacts/prd.md'
  - 'docs/planning-artefacts/ux-design-specification.md'
  - '_bmad-output/analysis/brainstorming-session-2026-01-05.md'
  - '_bmad-output/analysis/brainstorming-session-2026-01-05-dashboard-design.md'
workflowType: 'architecture'
project_name: 'CryptoTrader'
user_name: 'Claudio'
date: '2026-01-05'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
The PRD defines 37 functional requirements across 8 categories:
- Dashboard Health & Status (FR1-FR4): RAG status indicator with instant visibility
- Profit & Loss Monitoring (FR5-FR9): Real-time P&L with color-coded indicators
- Trading Pair Overview (FR10-FR15): All-pairs table with expandable details
- Price Chart Visualization (FR16-FR21): Interactive Plotly charts with hover/zoom
- Real-Time Data Updates (FR22-FR25): WebSocket-driven updates without flickering
- Visual Presentation (FR26-FR29): Dark theme, fixed header, consistent styling
- Data Display (FR30-FR33): Currency formatting, timestamps, precision handling
- Future Capabilities (FR34-FR37): Trade history, grid visualization, config view (v2+)

**Non-Functional Requirements:**
17 NFRs organized into 4 categories drive architectural decisions:
- Performance (NFR1-5): <1s render, <3s chart, <1s Tier 1 updates, zero flicker
- Reliability (NFR6-9): 24+ hour runtime, <100MB memory growth, auto-retry on API failure
- Integration (NFR10-13): Existing REST API unchanged, NiceGUI WebSocket, Plotly charts
- Maintainability (NFR14-17): Modular components, external config, console logging

**Scale & Complexity:**
- Primary domain: Web Application (SPA-like dashboard)
- Complexity level: Medium-High
- Estimated architectural components: 6-8 (header, table, chart, status, P&L display, data service, WebSocket handler, config)

### Technical Constraints & Dependencies

| Constraint | Details |
|------------|---------|
| Existing API | aiohttp REST API on port 8080 - must remain unchanged |
| Framework | NiceGUI (FastAPI + Vue/Quasar + WebSocket) |
| Charting | Plotly (matches existing Streamlit implementation) |
| Browser | Chrome latest only |
| Viewport | 1024-1440px laptop screens |
| Users | Single user, localhost |
| Runtime | Python 3.10+ |

### Cross-Cutting Concerns Identified

1. **Error Handling:** API failures should show warning in header, not crash dashboard
2. **Connection Recovery:** WebSocket reconnection after network interruption
3. **Memory Management:** Prevent leaks during 24+ hour continuous operation
4. **Data Freshness:** Timestamp display, staleness warning at >60s
5. **Styling Consistency:** Dark theme colors, RAG status patterns, monospace numbers
6. **Logging:** Console output for debugging without attaching debugger

## Starter Template Evaluation

### Primary Technology Domain

**Python Web Application** - Single-page dashboard with real-time updates

This is a **brownfield migration** (replacing existing Streamlit dashboard), not a greenfield project requiring starter template selection. The technology stack was determined through brainstorming analysis.

### Framework Selection: NiceGUI

**Version:** 3.4.1 (December 2025)
**Status:** Actively maintained by Zauberzeug

**Why NiceGUI was selected (from brainstorming):**
- WebSocket reactive bindings eliminate Streamlit's flickering
- Plotly integration matches existing charting code
- FastAPI under the hood (potential for API consolidation)
- Streamlit-like Python syntax = minimal learning curve
- Single-user, single-worker model fits requirements

### Initialization Command

```bash
pip install nicegui plotly
```

No scaffolding CLI required - NiceGUI projects are standard Python packages.

### Architectural Decisions Provided by NiceGUI

**Runtime Architecture:**
- FastAPI backend (ASGI, async-native)
- Vue 3 + Quasar frontend (auto-generated)
- Socket.io WebSocket for real-time UI updates
- Single uvicorn worker (no multi-process sync needed)

**UI Update Model:**
- Python state changes → WebSocket → Surgical DOM updates
- No full-page refresh, no flicker
- `ui.timer()` for periodic polling of external APIs

**Built-in Components:**
- `ui.plotly()` - Interactive Plotly charts
- `ui.table()` / `ui.aggrid()` - Data tables
- `ui.card()`, `ui.row()`, `ui.column()` - Layout
- `ui.expansion()` - Collapsible panels
- Dark mode theming support

### Recommended Project Structure

```
dashboard/
├── main.py                 # Entry point, ui.run()
├── config.py               # Dashboard configuration
├── components/
│   ├── header.py           # Fixed header strip component
│   ├── status_indicator.py # RAG health indicator
│   ├── pnl_display.py      # P&L with color coding
│   ├── pairs_table.py      # All-pairs table
│   └── price_chart.py      # Plotly chart wrapper
├── services/
│   ├── api_client.py       # REST API client (polls bot API)
│   └── data_models.py      # Pydantic models for API responses
├── assets/
│   └── css/
│       └── theme.css       # Dark theme overrides
└── tests/
    └── test_components.py
```

### Integration with Existing Bot

```
CryptoTrader/
├── src/                    # Existing trading bot
│   ├── api/                # aiohttp REST API (port 8080)
│   └── ...
├── dashboard/              # NEW: NiceGUI dashboard
│   └── ...                 # Structure above
└── requirements.txt        # Add nicegui, plotly
```

**Note:** Dashboard is a separate Python package that consumes the existing bot API. No modifications to bot code required for MVP.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
1. Data Flow Architecture → Centralized DataService with timer polling
2. Port Strategy → Dashboard on 8081, Bot API on 8080
3. Error Handling → Graceful degradation with stale data indicators

**Important Decisions (Shape Architecture):**
4. Polling Intervals → 2s/5s/on-demand tiers
5. State Management → Python class with NiceGUI reactive bindings
6. Component Communication → Shared state reference

**Deferred Decisions (Post-MVP):**
- Caching strategy (not needed for single-user, low-latency)
- Authentication (v2 feature if remote access added)
- Logging aggregation (console logging sufficient for MVP)

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NiceGUI Dashboard                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐     ┌─────────────────────────────────┐   │
│  │  ui.timer() │────▶│     DataService (singleton)      │   │
│  │   (1-10s)   │     │  - polls bot API via httpx       │   │
│  └─────────────┘     │  - holds current state           │   │
│                      │  - notifies components on change │   │
│                      └──────────────┬──────────────────┘   │
│                                     │                       │
│         ┌───────────────────────────┼───────────────────┐   │
│         ▼                           ▼                   ▼   │
│  ┌────────────┐            ┌─────────────┐      ┌──────────┐│
│  │   Header   │            │ Pairs Table │      │  Chart   ││
│  │ (Tier 1)   │            │  (Tier 2)   │      │ (Tier 2) ││
│  └────────────┘            └─────────────┘      └──────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ REST (httpx async)
                    ┌─────────────────────┐
                    │  Bot API (aiohttp)  │
                    │     Port 8080       │
                    └─────────────────────┘
```

**Rationale:** Single data source prevents duplicate API calls and ensures consistent state across components.

### Polling Intervals

| Data Tier | Interval | Rationale |
|-----------|----------|-----------|
| Tier 1 (Health, P&L) | 2 seconds | Critical, real-time feel |
| Tier 2 (Pairs table, Chart) | 5 seconds | Important but less urgent |
| Tier 3 (Expanded details) | On-demand | Only when user expands row |

**Configurable:** Intervals stored in `config.py`, adjustable without code changes.

### Error Handling Strategy

| Scenario | Response | UI Feedback |
|----------|----------|-------------|
| API timeout (>5s) | Retry once, then show stale | Header shows "⚠️ Stale data" |
| API unavailable | Show last known data | Header shows "🔴 API Offline" |
| Partial API failure | Show available data | Affected section shows error |
| Network restored | Resume normal polling | Header returns to healthy |

**Implementation:** `httpx` with timeouts + exception handling in DataService.

### Data Architecture

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Database | None | Dashboard has no persistence; consumes bot API |
| Data Models | Pydantic | Type safety, validation, API response parsing |
| HTTP Client | httpx (async) | Modern async client, timeout support |
| Caching | None for MVP | Real-time data, single user, low latency |

### Authentication & Security

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Authentication | None | Single user, localhost only (PRD) |
| HTTPS | None | Localhost traffic, no external exposure |
| API Keys | None | Dashboard to bot communication is internal |
| CORS | Not needed | Single origin (same machine) |

### API & Communication Patterns

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Data Source | Existing bot REST API | No modifications required |
| Protocol | HTTP polling + NiceGUI WebSocket | Hybrid approach per requirements |
| Error Format | Graceful degradation | Show stale data, indicate status |
| Timeouts | 5 second API timeout | Prevents hung requests |

### Frontend Architecture

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| State Management | Python DashboardState class | NiceGUI's reactive model |
| Component Pattern | Function-based with shared state | Simple, Pythonic |
| Styling | Quasar dark theme + CSS overrides | Minimal custom CSS |
| Layout | Fixed header + scrollable content | UX specification |

### Infrastructure & Deployment

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Hosting | localhost (uvicorn) | Single user, personal tool |
| Port | 8081 | Separate from bot API (8080) |
| Process Management | Manual or systemd | Personal project, simple deployment |
| Logging | Console (stdout) | Debug visibility, simple |
| Monitoring | None for MVP | Browser DevTools sufficient |

### Decision Impact Analysis

**Implementation Sequence:**
1. DataService with httpx client → Foundation for all components
2. DashboardState class → Shared state container
3. Timer-based polling → Data refresh mechanism
4. Error handling middleware → Resilience layer
5. UI components → Consume state, display data

**Cross-Component Dependencies:**
- All UI components depend on DataService for data
- Timer coordinates refresh for all components
- Error state propagates to header for visibility

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Python File Naming:** `snake_case.py`
- Examples: `header.py`, `status_indicator.py`, `api_client.py`

**Python Class Naming:** `PascalCase`
- Examples: `DashboardState`, `HealthStatus`, `PairData`

**Python Function/Variable Naming:** `snake_case`
- Examples: `get_health_status()`, `total_pnl`, `last_update`

**Constants:** `UPPER_SNAKE_CASE`
- Examples: `POLL_INTERVAL_TIER1 = 2.0`, `API_TIMEOUT = 5.0`

**CSS Class Naming:** `kebab-case`
- Examples: `.header-strip`, `.status-healthy`, `.pnl-positive`

### Structure Patterns

**Component File Structure:**
```python
"""Component description."""
from nicegui import ui
from state import DashboardState

def component_name(state: DashboardState) -> None:
    """Create the component."""
    # Implementation
```

**Test Naming:** `test_<module>_<behavior>.py`
- Match component names: `test_header.py`, `test_api_client.py`

### Format Patterns

**Pydantic Models for API Responses:**
```python
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "error"
    uptime_seconds: int
```

**Number Formatting:**
- P&L: `+€123.45` (sign + currency + 2 decimals)
- Prices: `$97,234.12` (currency + thousands separator)

**Date/Time:**
- Internal: `datetime` objects with UTC timezone
- Display: Local time, format `HH:MM:SS`
- Freshness: Relative time (`5s ago`)

### Communication Patterns

**State Update Pattern:**
```python
class DashboardState:
    def __init__(self):
        self.health: HealthResponse | None = None
        self.pairs: list[PairData] = []
        self.last_update: datetime | None = None

    async def refresh(self) -> None:
        # NiceGUI automatically pushes changes to browser
```

**Logging:** Module-level logger, never `print()`
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Dashboard started on port %d", port)
```

### Process Patterns

**Error States:**
- `healthy` - Normal operation
- `stale` - Data older than 60s
- `api_error` - API call failed
- `offline` - API unreachable

**Timer Setup:**
```python
ui.timer(2.0, state.refresh_tier1)   # Health, P&L
ui.timer(5.0, state.refresh_tier2)   # Chart, table
```

**Configuration via Pydantic Settings:**
```python
class DashboardConfig(BaseSettings):
    api_base_url: str = "http://localhost:8080"
    dashboard_port: int = 8081
    poll_interval_tier1: float = 2.0

    class Config:
        env_prefix = "DASHBOARD_"
```

### Enforcement Guidelines

**All AI Agents MUST:**
1. Follow PEP 8 naming conventions
2. Use type hints on all function signatures
3. Include docstrings for public functions/classes
4. Use `logger` instead of `print()`
5. Handle API errors with fallback to last known state
6. Use Pydantic models for API response parsing

**Pattern Verification:**
- `ruff check` for linting
- `mypy` for type checking
- `pytest` for tests

## Project Structure & Boundaries

### Complete Project Directory Structure

```
CryptoTrader/
├── src/                            # Existing trading bot (UNCHANGED)
│   ├── api/                        # aiohttp REST API (port 8080)
│   ├── strategies/
│   ├── risk/
│   └── ...
├── dashboard/                      # NEW: NiceGUI dashboard
│   ├── main.py                     # Entry point
│   ├── config.py                   # DashboardConfig (Pydantic Settings)
│   ├── state.py                    # DashboardState class
│   ├── components/
│   │   ├── __init__.py
│   │   ├── header.py               # Fixed header strip (FR1-FR4, FR26-FR27)
│   │   ├── status_indicator.py     # RAG health indicator (FR1-FR3)
│   │   ├── pnl_display.py          # P&L with color coding (FR5-FR8)
│   │   ├── pairs_table.py          # All-pairs table (FR10-FR12)
│   │   ├── pair_row.py             # Expandable row component (FR13-FR15)
│   │   └── price_chart.py          # Plotly chart wrapper (FR16-FR19)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── api_client.py           # httpx async client
│   │   └── data_models.py          # Pydantic models
│   ├── assets/
│   │   └── css/
│   │       └── theme.css           # Dark theme overrides
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py             # Shared fixtures
│       ├── test_api_client.py
│       ├── test_state.py
│       └── test_components.py
├── docs/
│   ├── planning-artefacts/
│   │   ├── prd.md
│   │   ├── ux-design-specification.md
│   │   └── architecture.md         # This document
│   └── stories/
├── requirements.txt                # Add: nicegui, httpx, pydantic-settings
├── pyproject.toml                  # Project configuration
└── README.md
```

### Architectural Boundaries

**API Boundaries:**

```
┌───────────────┐     HTTP      ┌─────────────────┐    WebSocket    ┌─────────┐
│   Bot API     │◄─────────────►│    Dashboard    │◄───────────────►│ Browser │
│  (aiohttp)    │   Port 8080   │    (NiceGUI)    │    Port 8081    │ (Chrome)│
└───────────────┘               └─────────────────┘                 └─────────┘
```

| Boundary | Description |
|----------|-------------|
| Bot API → Dashboard | REST over HTTP (localhost:8080) |
| Dashboard → Browser | NiceGUI WebSocket (localhost:8081) |

**Component Boundaries:**

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `state.py` | Holds all dashboard state | api_client, all components |
| `api_client.py` | Fetches data from bot API | Bot REST API |
| `header.py` | Fixed header strip | state (reads) |
| `pairs_table.py` | All-pairs display | state (reads) |
| `price_chart.py` | Plotly chart | state (reads) |

### Requirements to Structure Mapping

| FR Category | Component(s) | File(s) |
|-------------|--------------|---------|
| FR1-FR4: Health & Status | Header, StatusIndicator | `header.py`, `status_indicator.py` |
| FR5-FR9: P&L Monitoring | PnlDisplay | `pnl_display.py` |
| FR10-FR15: Pair Overview | PairsTable, PairRow | `pairs_table.py`, `pair_row.py` |
| FR16-FR21: Charts | PriceChart | `price_chart.py` |
| FR22-FR25: Real-Time | State, Timer | `state.py`, `main.py` |
| FR26-FR29: Visual | All components | `theme.css` |
| FR30-FR33: Data Display | Data models | `data_models.py` |

### Data Flow

```
Bot API ──► api_client.py ──► DashboardState ──► Components ──► Browser
              (httpx)         (Python objects)   (NiceGUI WS)
```

### Development Workflow

**Run Dashboard:**
```bash
python dashboard/main.py
# Opens http://localhost:8081
```

**Run with Bot:**
```bash
# Terminal 1: Bot
python -m src.main

# Terminal 2: Dashboard
python dashboard/main.py
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
- NiceGUI 3.4.1 + httpx + Pydantic + Plotly - all Python async-compatible
- FastAPI (under NiceGUI) works seamlessly with httpx async client
- No version conflicts identified

**Pattern Consistency:**
- PEP 8 naming conventions apply uniformly
- Component pattern aligns with NiceGUI design
- Configuration pattern (Pydantic Settings) matches ecosystem

**Structure Alignment:**
- Project structure separates concerns (components, services, tests)
- Boundaries are clear (state.py mediates all data)
- Integration points well-defined

### Requirements Coverage ✅

| FR Range | Status | Component(s) |
|----------|--------|--------------|
| FR1-FR4 (Health) | ✅ | header.py, status_indicator.py |
| FR5-FR9 (P&L) | ✅ | pnl_display.py |
| FR10-FR15 (Pairs) | ✅ | pairs_table.py, pair_row.py |
| FR16-FR21 (Charts) | ✅ | price_chart.py |
| FR22-FR25 (Real-time) | ✅ | state.py, main.py |
| FR26-FR33 (Visual/Data) | ✅ | theme.css, data_models.py |
| FR34-FR37 (Future) | ⏳ | Deferred to v2 |

**NFR Coverage:**
- Performance: NiceGUI WebSocket (surgical updates) ✅
- Reliability: Error handling, graceful degradation ✅
- Integration: api_client.py consumes existing REST API ✅
- Maintainability: Modular structure, external config ✅

### Implementation Readiness ✅

**Completeness Checklist:**
- [x] All critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Naming conventions established
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Requirements to structure mapping complete

**Gap Analysis:**
- Critical Gaps: None
- Future Enhancements: v1.5 (expandable rows), v2 (trade history)

### Architecture Readiness Assessment

**Overall Status:** ✅ READY FOR IMPLEMENTATION

**Confidence Level:** HIGH

**Key Strengths:**
- Dashboard is independent package consuming existing API
- Zero bot modifications required for MVP
- Technology aligned with existing skills (Python, Plotly)
- Patterns follow NiceGUI framework conventions

**First Implementation Steps:**
1. Create dashboard directory structure
2. Install dependencies: `pip install nicegui httpx pydantic-settings plotly`
3. Implement main.py, config.py, state.py
4. Build header component (enables Glance Mode)
5. Add pairs_table and price_chart
6. Integrate with existing bot API

---

## Architecture Completion Summary

### Workflow Completion

**Architecture Decision Workflow:** COMPLETED ✅
**Total Steps Completed:** 8
**Date Completed:** 2026-01-05
**Document Location:** docs/planning-artefacts/architecture.md

### Final Architecture Deliverables

**Complete Architecture Document:**
- All architectural decisions documented with specific versions
- Implementation patterns ensuring AI agent consistency
- Complete project structure with all files and directories
- Requirements to architecture mapping
- Validation confirming coherence and completeness

**Implementation Ready Foundation:**
- 6 major architectural decisions made
- 5 implementation pattern categories defined
- 7 dashboard components specified
- 37 functional requirements fully supported

**AI Agent Implementation Guide:**
- Technology stack: NiceGUI 3.4.1, httpx, Pydantic, Plotly
- Consistency rules that prevent implementation conflicts
- Project structure with clear boundaries
- Integration patterns and communication standards

### Quality Assurance Summary

✅ Architecture Coherence - All decisions work together
✅ Requirements Coverage - All FRs and NFRs supported
✅ Implementation Readiness - Patterns prevent conflicts
✅ Structure Complete - All files and directories defined

---

**Architecture Status:** READY FOR IMPLEMENTATION ✅

**Next Phase:** Begin implementation using the architectural decisions and patterns documented herein.

