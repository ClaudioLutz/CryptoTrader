---
stepsCompleted: [1, 2, 3]
inputDocuments: []
session_topic: 'Dashboard technology migration - replacing Streamlit for CryptoTrader'
session_goals: 'Find a dashboard solution with smooth, partial/incremental updates without flickering'
selected_approach: 'AI-Recommended Techniques'
techniques_used: ['Constraint Mapping', 'Cross-Pollination', 'Solution Matrix']
ideas_generated: ['NiceGUI', 'Panel', 'Flask + HTMX']
context_file: '_bmad/bmm/data/project-context-template.md'
---

# Brainstorming Session Results

**Facilitator:** Claudio
**Date:** 2026-01-05

## Session Overview

**Topic:** Dashboard technology migration - replacing Streamlit for CryptoTrader

**Goals:** Find a dashboard solution with smooth, partial/incremental updates without flickering

### Context Guidance

Focus areas for this session:
- **User Problems and Pain Points** - Streamlit's full-page refresh causing flickering on data updates
- **Technical Approaches** - Alternative frameworks/tools for real-time trading dashboards
- **User Experience** - Smooth, professional dashboard interactions
- **Technical Risks and Challenges** - Migration complexity, learning curve, feature parity

### Session Setup

**Core Problem Identified:** Streamlit's re-run-the-entire-script architecture causes full page re-renders on every data refresh, resulting in distracting flickering for a trading dashboard that requires frequent updates.

**Implicit Requirements:**
- Real-time or near-real-time data display
- Professional, non-flickery user experience
- Charts, metrics, order/trade history display

---

## Phase 1: Constraint Mapping Results

### Hard Constraints (Must Have)
| Constraint | Details |
|------------|---------|
| No flickering | Partial/incremental DOM updates only |
| ~1 second refresh | Current 10-15s is compromise, not preference |
| Full feature parity | Candlesticks, metrics, equity curves, tables, auth, config, dark theme |
| Large table support | Could grow to 1000s of rows |

### Soft Constraints (Strong Preference)
| Constraint | Details |
|------------|---------|
| Simple to implement | Avoid overengineering |
| Claude-friendly | Python preferred, but open to best solution |
| Maintainable | Single developer (Claudio) will maintain |

### Non-Constraints (Simplifies Scope)
| Factor | Value |
|--------|-------|
| Mobile support | Not needed |
| Multi-user | Single user only |
| JS expertise required | Flexible - whatever works |

### Key Insight
Flask familiarity + Python backend preference + "simplest effective option" points toward **Python frameworks with reactive/websocket-based updates** rather than full JS frontend rewrites.

---

## Phase 2: Cross-Pollination Results

### How Professional Trading Dashboards Avoid Flicker

| Technique | How It Works | Who Uses It |
|-----------|--------------|-------------|
| WebSocket push | Server pushes only changed data, client updates specific DOM elements | TradingView, Binance, Coinbase |
| Virtual DOM diffing | Framework calculates minimal changes, updates only what changed | React, Vue dashboards |
| Reactive bindings | UI elements bound to data - when data changes, only that element re-renders | Modern SPA frameworks |

### Python Frameworks Evaluated

| Framework | Update Mechanism | Charting | Tables | Complexity |
|-----------|------------------|----------|--------|------------|
| **NiceGUI** | WebSocket reactive bindings | Plotly, ECharts | AG Grid built-in | Low |
| **Panel** | Bokeh server / WebSocket | HoloViews, Plotly | Tabulator | Medium |
| **Flask + HTMX** | Partial HTML swaps | Plotly (static) | Custom | Low-Med |

### NiceGUI Deep Dive

- **Architecture:** FastAPI backend + Vue/Quasar frontend + WebSocket connection
- **Version:** 3.4.1 (v3.0 released September 2025)
- **Key Feature:** Updates only changed DOM elements via WebSocket - no page refresh
- **Production Use:** Zauberzeug (German robotics company) uses in production
- **Streamlit Comparison:** Built specifically as a reactive alternative to Streamlit

---

## Phase 3: Solution Matrix Results

### Scoring Matrix

| Criteria | **NiceGUI** | **Panel** | **Flask + HTMX** |
|----------|-------------|-----------|------------------|
| No Flickering | ✅ Excellent | ✅ Good | ⚠️ Good (manual) |
| 1s Refresh | ✅ Built-in timer | ✅ Periodic callback | ⚠️ JS setInterval |
| Candlestick Charts | ✅ Plotly native | ✅ Plotly/HoloViews | ⚠️ Static render |
| AG Grid Tables | ✅ Built-in | ⚠️ Tabulator | ❌ Manual |
| Simplicity | ✅ Streamlit-like | ⚠️ Steeper curve | ⚠️ More boilerplate |
| Migration Effort | ✅ Low-Medium | ⚠️ Medium | ⚠️ Medium-High |

### Final Scores

| Solution | Score | Verdict |
|----------|-------|---------|
| **NiceGUI** | ⭐⭐⭐⭐⭐ | Best fit - checks all boxes, lowest friction |
| **Panel** | ⭐⭐⭐⭐ | Solid alternative for heavy data science |
| **Flask + HTMX** | ⭐⭐⭐ | More control but more work |

---

## Final Recommendation

### Winner: NiceGUI

**Why NiceGUI wins for CryptoTrader:**

1. **Solves the core problem** - WebSocket reactivity eliminates flickering by design
2. **Feature parity is easy** - AG Grid, Plotly, auth all built-in
3. **Familiar syntax** - Streamlit-like patterns, minimal learning curve
4. **Existing code transfers** - Same Plotly charting library
5. **FastAPI under the hood** - Could integrate existing backend API

### Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Smaller community | Medium | Active development, good docs, Discord |
| Learning new patterns | Low | Very similar to Streamlit mental model |
| Performance at scale | Low | AG Grid + WebSocket handle large data well |

---

## Next Steps

1. **Install NiceGUI:** `pip install nicegui`
2. **Create proof-of-concept:** Single page with 1s-updating metrics + Plotly chart
3. **Validate no-flicker:** Confirm WebSocket updates work as expected
4. **Incremental migration:** Port one page at a time from Streamlit
5. **Full migration:** Complete dashboard rebuild with feature parity

### Resources

- [NiceGUI Official Site](https://nicegui.io/)
- [NiceGUI GitHub](https://github.com/zauberzeug/nicegui)
- [NiceGUI Documentation](https://nicegui.io/documentation)
- [Talk Python Podcast: NiceGUI 3.0](https://talkpython.fm/episodes/show/525/nicegui-goes-3.0)

---

*Session completed: 2026-01-05*
