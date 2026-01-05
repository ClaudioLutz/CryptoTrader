---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - 'docs/planning-artefacts/prd.md'
  - '_bmad-output/analysis/brainstorming-session-2026-01-05-dashboard-design.md'
  - '_bmad-output/analysis/brainstorming-session-2026-01-05.md'
workflowType: 'ux-design'
lastStep: 14
workflowStatus: complete
completedAt: '2026-01-05'
documentCounts:
  prd: 1
  brainstorming: 2
  projectContext: 0
---

# UX Design Specification - CryptoTrader NiceGUI Dashboard

**Author:** Claudio
**Date:** 2026-01-05

---

## Executive Summary

### Project Vision

CryptoTrader's NiceGUI dashboard exists for one purpose: **instant, trustworthy answers**.

When you check your trading bot — whether at 3am in panic or during a coffee ritual — the dashboard should feel like a trusted colleague giving you a clear status report, not a flickering screen that makes you question what's real.

The migration from Streamlit to NiceGUI isn't about technology. It's about replacing anxiety with confidence.

### Target Users

**Primary User:** Single user (Claudio) operating a personal cryptocurrency trading bot.

**User Modes (Same Person, Different Contexts):**

| Mode | Trigger | Primary Question | Success State |
|------|---------|------------------|---------------|
| Panic Mode | 3am price alert | "Is everything okay?" | Close laptop in 4 minutes, not 45 |
| Coffee Mode | Weekend morning | "How did the bot perform?" | Satisfying 10-minute review |
| Glance Mode | Mid-task distraction | "Up or down today?" | 5-second answer, back to work |

**User Characteristics:**
- Intermediate technical skill
- Laptop-first usage (13-15" screen)
- Single user, no sharing/collaboration needs
- Trades 4-5 cryptocurrency pairs simultaneously
- Prefers watching to controlling from dashboard

### Key Design Challenges

1. **Trust Through Stability** — Eliminate the uncertainty caused by flickering; every update must feel intentional, not broken
2. **Information Density vs. Glanceability** — Show all pairs and key metrics without overwhelming the 5-second scan
3. **Anxiety Reduction** — Design the 3am experience as a calming pipeline from alert → status check → reassurance
4. **Feature Parity Without Cruft** — Maintain all Streamlit capabilities while improving the experience, not just swapping frameworks

### Design Opportunities

1. **The 5-Second Header Strip** — A fixed, always-visible header that answers the core question for all three user modes
2. **Silent Confidence UI** — Updates happen without visual disruption; attention drawn only when warranted
3. **Progressive Disclosure Architecture** — Surface-level simplicity with available depth on demand
4. **Dark Theme as Trust Signal** — Professional trading aesthetic that signals "this is a serious tool"

## Core User Experience

### Defining Experience

**Primary Interaction Pattern:** Glance → Confirm → Close

The dashboard's core experience is a sub-5-second scan that answers "Is everything okay?" without requiring any user action beyond opening the page. The fixed header strip is the product's defining feature — it speaks first, answering the user's unspoken question before they consciously form it.

**Core Action Hierarchy:**
1. **Glance** (5 seconds) — Header strip confirms health, P&L direction, pair count
2. **Scan** (30 seconds) — All-pairs table provides per-pair context
3. **Explore** (minutes) — Chart interaction, expandable details for investigation

### Platform Strategy

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Platform | Web (NiceGUI SPA) | Real-time WebSocket updates, single deployment |
| Primary Device | Laptop (13-15") | User's actual usage pattern |
| Input Method | Mouse/keyboard | Hover interactions, click-to-expand |
| Browser Target | Chrome (latest) | Single-user, consistent environment |
| Responsive Design | Not required | Fixed viewport, no mobile support needed |
| Offline Support | Not applicable | Real-time trading data is inherently online |

### Effortless Interactions

**Zero-Thought Interactions:**
- **Status comprehension** — RAG colors + P&L indicators communicate without reading
- **All-pairs visibility** — Every trading pair visible simultaneously without filtering
- **Update awareness** — "Last updated" timestamp present but non-intrusive
- **Data freshness** — Updates happen silently; no visual disruption indicates refresh

**Friction Points Eliminated:**
- Streamlit's full-page flicker replaced with surgical DOM updates
- No uncertainty about data staleness
- No mental load differentiating "refresh in progress" from "something broke"

### Critical Success Moments

| Moment | User Context | Success Criteria |
|--------|--------------|------------------|
| First Glance | Eyes reach header strip | Health status understood in <1 second |
| Panic Resolution | 3am alert, anxious | "Go back to sleep" answer within 30 seconds |
| Anomaly Awareness | Normal check finds issue | Yellow/Red naturally draws attention |
| Investigation Entry | Curiosity about specific pair | Row expansion feels instant |
| Chart Exploration | Understanding price action | Hover/zoom responds lag-free |

**Trust Inflection Point:** The first update the user witnesses. If it flickers or creates uncertainty, trust is damaged. If it happens invisibly, confidence builds.

### Experience Principles

1. **Answer First** — The dashboard answers the user's question before they consciously ask it
2. **Silent Confidence** — Updates occur invisibly; the user sees current data, never a "refreshing" state
3. **Progressive Depth** — Surface simplicity with available complexity; Glance Mode by default, Coffee Mode on demand
4. **Earned Attention** — Visual elements compete for attention appropriately; green recedes, yellow draws, red demands
5. **Trust Through Stability** — Visual consistency signals data reliability; solid appearance creates confidence

## Desired Emotional Response

### Primary Emotional Goals

**Core Emotion: Relief**

The dashboard's primary emotional job is to deliver relief as quickly as possible. When Claudio opens the dashboard at 3am with his heart racing, the goal is not just information delivery — it's emotional transformation from anxiety to calm.

**Supporting Emotions:**
- **Trust** — "The data I'm seeing is real and current"
- **Confidence** — "The bot is doing what it should"
- **Calm** — "Nothing requires my immediate attention"
- **Control** — "I can see everything I need without hunting"

### Emotional Journey Mapping

| Journey | Start State | Trigger | End State | Success Metric |
|---------|-------------|---------|-----------|----------------|
| Panic Check (3am) | Anxious, racing heart | Price alert | Relieved, ready to sleep | 30 seconds to "go back to sleep" |
| Morning Review | Curious, reflective | Weekend ritual | Satisfied, confident | 10-minute enjoyable review |
| Quick Glance | Distracted, multi-tasking | Random check | Confirmed, back to task | 5-second answer |
| Issue Investigation | Alerted, focused | Yellow/Red status | Understanding, informed | Root cause found in 90 seconds |

### Micro-Emotions

**Trust vs. Suspicion**
- Trust is built through visual stability and consistent behavior
- Every flicker or unexplained state change creates micro-suspicion
- Design response: Silent updates, visible timestamps, smooth transitions

**Calm vs. Anxiety**
- Anxiety is the default state when checking a trading dashboard
- Design must actively de-escalate, not add to cognitive load
- Design response: Green recedes, dark theme, no unnecessary movement

**Confidence vs. Doubt**
- Confidence comes from complete information visibility
- Doubt emerges from hidden states or unclear indicators
- Design response: All pairs visible, clear status indicators, no mystery

**Control vs. Helplessness**
- Control means having the information needed to make decisions
- Helplessness means hunting for data or not understanding the display
- Design response: Information hierarchy, progressive disclosure, self-explanatory layout

### Design Implications

| Emotional Goal | Design Decision |
|----------------|-----------------|
| Relief in <1 second | Fixed header strip with RAG status as first visual element |
| Trust through stability | WebSocket updates that modify only changed DOM elements |
| Calm through restraint | Green status fades into background; attention only when earned |
| Confidence through completeness | All 4-5 trading pairs visible without scrolling or filtering |
| Control through depth | Expandable rows provide detail on demand, never forced |

### Emotional Design Principles

1. **Relief is the Product** — The dashboard sells peace of mind, not data visualization
2. **Anxiety is the Enemy** — Every design choice should reduce, not add to, cognitive load
3. **Trust is Earned in Milliseconds** — The first update the user sees determines their confidence level
4. **Attention is a Resource** — Green should fade; only yellow/red should draw the eye
5. **Calm is an Active Choice** — Dark theme, muted colors, no unnecessary animation

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

**Binance Trading Interface**
- Compact multi-symbol rows with expandable details
- WebSocket real-time updates without page refresh
- Dark theme as professional trading default
- Key insight: Information density without clutter through progressive disclosure

**TradingView**
- Compact timeframe performance summaries
- Instant-feeling chart interactions
- Clean visual hierarchy
- Key insight: Power users expect depth; the interface should reward exploration

**Carbon Design System**
- RAG (Red/Amber/Green) status patterns with icon + color + text
- Semantic communication through visual hierarchy
- Key insight: Status should be understood without reading; color does the work

**Dashboard UI Best Practices 2025**
- "5-Second Rule" fixed headers
- Critical information never scrolls away
- Key insight: The header strip is the product; everything else is supporting detail

### Transferable UX Patterns

| Pattern | Application |
|---------|-------------|
| Fixed Header Strip | Tier 1 data (health, P&L, counts) always visible regardless of scroll |
| RAG Status System | Health indicator using green/yellow/red with semantic meaning |
| Compact Multi-Row Table | All-pairs visible in horizontal rows with expandable details |
| Timeframe Summary Row | 1H/24H/7D/30D P&L in single scannable line |
| Silent Real-Time Updates | WebSocket DOM patching for flicker-free data refresh |
| Dark Theme Default | Professional trading aesthetic, 3am eye comfort |
| Hover-to-Reveal | Chart tooltips show detail without cluttering view |
| Click-to-Expand | Row expansion for pair-specific deep dive |

### Anti-Patterns to Avoid

| Anti-Pattern | Risk | Mitigation |
|--------------|------|------------|
| Full-Page Refresh | Destroys trust, creates anxiety | NiceGUI WebSocket updates |
| Loading Spinners on Tier 1 | Blocks critical information during refresh | Silent updates, no blocking |
| Filtering Required to See Data | Hides information, adds friction | All pairs always visible |
| Information Overload | Overwhelms 5-second glance | Three-tier hierarchy |
| Attention-Grabbing Animation | Creates anxiety, not calm | Static UI, motion only for state changes |
| Color Without Meaning | Decorative color distracts | Every color communicates status |
| Hidden System Status | User hunts for health info | Header strip speaks first |

### Design Inspiration Strategy

**Adopt Directly:**
- Fixed header strip pattern (Dashboard best practices)
- RAG status with icon+color+text (Carbon Design)
- Dark theme as default (trading platform standard)

**Adapt for Context:**
- Binance's multi-symbol table → simplified for 4-5 pairs only
- TradingView's timeframe summary → positioned below header strip
- Hover interactions → chart tooltips, not row previews

**Avoid Explicitly:**
- Streamlit's full-page refresh architecture
- Loading states that block Tier 1 information
- Any animation that draws attention without communicating status change

## Design System Foundation

### Design System Choice

**Selected Approach:** Themed NiceGUI (Quasar/Material Design base with trading customizations)

NiceGUI provides a Quasar/Material Design foundation out of the box. Rather than building custom components or adopting an external design system, we'll leverage NiceGUI's built-in component library and customize the theme for a professional trading aesthetic.

### Rationale for Selection

| Factor | Decision Driver |
|--------|-----------------|
| Speed | NiceGUI components ready immediately; no custom building |
| Consistency | Quasar provides cohesive, tested component library |
| Dark Theme | Quasar has excellent native dark mode support |
| Charting | Plotly integration matches existing Streamlit implementation |
| Maintenance | Single-developer project benefits from framework defaults |
| Learning Curve | Minimal; NiceGUI is designed for Python developers |

### Implementation Approach

**Use NiceGUI Defaults For:**
- Layout components (rows, columns, cards)
- Typography and spacing
- Form elements (if needed in future)
- Expansion panels for row details

**Customize:**
- Color theme (dark trading palette)
- Status indicator styling (RAG pattern)
- Table styling (compact rows, trading density)
- Chart theming (dark mode, semantic colors)

**External Libraries:**
- Plotly for interactive charts (existing familiarity)
- NiceGUI's built-in table (or AG Grid for v1.5+ if needed)

### Customization Strategy

**Color Palette:**

| Role | Value | Usage |
|------|-------|-------|
| Background Primary | `#1a1a2e` | Dashboard background |
| Background Secondary | `#16213e` | Header, cards, panels |
| Surface | `#0f3460` | Table rows, interactive elements |
| Text Primary | `#e8e8e8` | Main content |
| Text Secondary | `#a0a0a0` | Labels, timestamps |
| Accent | `#4a9eff` | Interactive highlights |
| Success | `#00c853` | Healthy status, positive P&L |
| Warning | `#ffc107` | Degraded status, attention |
| Error | `#ff5252` | Critical status, negative P&L |

**Status Indicator Pattern:**
- Green (Healthy): Muted, recedes into background — "all is well"
- Amber (Warning): Brighter, draws attention — "look at this"
- Red (Error): High contrast, demands attention — "action needed"

**Typography:**
- Use Quasar/Material defaults (Roboto)
- Monospace for numbers and prices (data clarity)
- Slightly reduced font sizes for information density

**Component Density:**
- Tighter padding than Material defaults
- Compact table rows optimized for 4-5 pairs
- Header strip designed for maximum information in minimal vertical space

## Defining Core Experience

### The Defining Interaction

**Core Experience Statement:** "Glance at the header — know everything is okay — close the laptop."

This is the CryptoTrader dashboard's equivalent of Tinder's swipe. The entire product exists to deliver this 5-second moment where anxiety transforms into relief. Every design decision serves this atomic unit of value.

**Why This Matters:**
- Panic Mode (3am): The header answers "Is everything okay?" in under 5 seconds
- Glance Mode (mid-task): Eyes scan the header, confirm "up, green, done"
- Coffee Mode (morning): Starts with the header, then optionally explores deeper

### User Mental Model

**Current Experience (Streamlit):**
The user opens the dashboard, watches it flicker, questions whether data is current, scans multiple areas looking for confirmation, and eventually closes the laptop still uncertain. Total time: 10-45 minutes. Emotional outcome: lingering anxiety.

**Expected Experience (Mental Model):**
Like glancing at a watch. The information is simply *there* — no loading, no waiting, no interaction required. The user's expectation is passive comprehension, not active investigation.

**Mental Model Alignment:**
- Users expect status to be immediately visible (aligned: header strip)
- Users expect green=good, red=bad (aligned: RAG pattern)
- Users expect data to be current without manual refresh (aligned: WebSocket updates)
- Users expect all key info without scrolling (aligned: fixed header)

### Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Time to Status Comprehension | <1 second | Eyes hit header → status understood |
| Required User Actions | Zero | No clicks, scrolls, or waits for status |
| Data Freshness Confidence | 100% | No "is this current?" uncertainty |
| Visual Disruption | Zero | No full-page refreshes or flicker |
| Emotional Outcome | Relief | Anxiety transforms to calm |

**"This Just Works" Indicators:**
- Header is visible immediately on page load
- RAG status comprehensible without reading
- P&L direction (up/down) clear from color
- Updates happen invisibly in the background
- User can close laptop feeling informed

### Novel UX Patterns

**Classification: Established Patterns, Exceptional Execution**

This product doesn't require novel interaction design. The patterns are well-established:
- Fixed headers (dashboard best practices)
- RAG status indicators (Carbon Design System)
- Multi-symbol tables (Binance, TradingView)
- Real-time WebSocket updates (trading platform standard)
- Dark theme (financial interface convention)

**The Innovation is Subtraction:**
The defining experience is achieved not through new patterns but through the *absence* of friction. We remove:
- Flickering that creates uncertainty
- Loading states that block information
- Filtering requirements that hide data
- Manual refresh buttons that add cognitive load

**No User Education Required:**
Users already know how to glance at a header. They already understand green=good, red=bad. The dashboard leverages existing mental models rather than requiring learned behavior.

### Experience Mechanics

**The "Glance → Confirm → Close" Flow:**

**Stage 1: Initiation**
- Trigger: Price alert, curiosity, or routine check
- User Action: Opens dashboard URL
- System Response: Page renders in <1 second with header visible first
- User State: Anxious or curious

**Stage 2: Comprehension**
- User Action: Eyes involuntarily scan header left-to-right
- Visual Pattern: `🟢 HEALTHY │ +€47.32 ▲ │ 4/4 pairs │ 7 ord │ 16:42`
- Duration: <5 seconds
- Required Controls: None — passive visual processing
- User State: Information absorbed

**Stage 3: Feedback Loop**
- Green + Positive P&L → Relief, confidence
- Yellow status → Attention drawn, curiosity (not panic)
- Red status → Alert, focus, investigation mode
- Timestamp confirms data freshness
- User State: Emotionally resolved

**Stage 4: Completion**
- Success Outcome: User feels informed and reassured
- Primary Exit: Close laptop / switch tabs (Panic/Glance modes)
- Secondary Path: Scroll down to explore (Coffee mode)
- Duration: 5-30 seconds for typical check
- User State: Calm, confident, done

## Visual Design Foundation

### Color System

**Background Palette:**
| Layer | Hex | Usage |
|-------|-----|-------|
| Base | `#1a1a2e` | Page background |
| Elevated | `#16213e` | Header, cards, panels |
| Surface | `#0f3460` | Table rows, interactive elements |

**Text Colors:**
| Level | Hex | Usage |
|-------|-----|-------|
| Primary | `#e8e8e8` | Main content |
| Secondary | `#a0a0a0` | Labels, timestamps |
| Tertiary | `#6b7280` | Disabled states |

**Semantic Colors (RAG Status):**
| Status | Hex | Behavior |
|--------|-----|----------|
| Healthy/Success | `#00c853` | Recedes — calm, doesn't demand attention |
| Warning/Degraded | `#ffc107` | Draws eye — requires awareness |
| Error/Critical | `#ff5252` | Demands attention — impossible to miss |

**P&L Indicators:**
- Positive: `#00c853` (green)
- Negative: `#ff5252` (red)
- Neutral: `#a0a0a0` (gray)

**Interactive Elements:**
- Accent: `#4a9eff`
- Hover: `#6bb3ff`

### Typography System

**Font Stack:**
- Primary: Roboto (system fallbacks)
- Monospace: Roboto Mono (for numerical data)

**Type Scale:**
| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| H2 | 18px | 500 | Section headers |
| H3 | 16px | 500 | Card titles |
| Body | 14px | 400 | Standard content |
| Small | 12px | 400 | Labels, timestamps |

**Data Typography:**
All prices, P&L values, and numerical data use monospace font for vertical alignment and professional appearance.

### Spacing & Layout Foundation

**Base Unit:** 4px spacing scale

**Spacing Tokens:**
- xs: 4px (inline spacing)
- sm: 8px (component padding)
- md: 16px (standard gaps)
- lg: 24px (section separation)

**Layout Zones:**
1. Header Strip: Fixed 48-56px, never scrolls
2. Timeframe Row: Optional 32-40px (v1.5)
3. Pairs Table: 4-5 rows × ~40px each
4. Chart Area: Flexible ~300-400px
5. Tabs: Future expansion (v2)

**Density Strategy:**
- Header: Maximum density (every pixel counts)
- Table: Compact (fit all pairs without scrolling)
- Chart: Standard (room for exploration)

### Accessibility Considerations

**Contrast Compliance:**
All text-background combinations meet or exceed WCAG AA 4.5:1 contrast ratio.

**Status Indication:**
RAG status uses icon + color + text — never color alone.

**Target Sizes:**
Interactive elements maintain minimum 32px touch/click targets.

**Rationale:**
While formal WCAG compliance isn't required for a single-user tool, good contrast and semantic indicators improve usability during late-night monitoring sessions.

## Design Direction Decision

### Design Directions Explored

**Approach:** Single canonical direction based on comprehensive brainstorming analysis.

The design direction was established through detailed brainstorming sessions that analyzed:
- User personas (Panic/Coffee/Glance modes)
- Information hierarchy requirements
- Trading dashboard best practices
- NiceGUI technical capabilities

Multiple layout variations were not required because the core requirements (header strip, all-pairs table, interactive chart) emerged clearly from user needs analysis.

### Chosen Direction

**Layout:** Vertical single-page dashboard with fixed header

**Component Stack:**
1. **Header Strip** (48-56px) — Fixed position, Tier 1 data
2. **Timeframe Performance Row** (32-40px) — Scrolls, v1.5 feature
3. **All-Pairs Table** (~180px) — 4-5 compact rows with expansion
4. **Interactive Chart** (~300px) — Plotly with dark theme
5. **Future Tabs Area** — Trade history, grid details (v2.0)

**Visual Treatment:**
- Dark theme with navy/blue gradient backgrounds
- Muted green for healthy status (recedes)
- Bright amber/red for attention states (draws eye)
- Monospace typography for all numerical data
- Compact density optimized for 13-15" laptop

### Design Rationale

| Decision | Rationale |
|----------|-----------|
| Fixed header strip | Answers "Is everything okay?" without scrolling |
| Single page layout | All critical info visible; no navigation overhead |
| Vertical flow | Natural top-to-bottom scan pattern |
| Compact table rows | Fit 4-5 pairs without scrolling |
| Expandable details | Progressive disclosure; depth on demand |
| Dark theme | Trading convention; 3am eye comfort |

### Implementation Approach

**MVP (v1.0):**
- Header strip with RAG + P&L + counts
- All-pairs table with basic expansion
- Plotly chart with dark theme
- WebSocket real-time updates

**Enhancement (v1.5):**
- Timeframe performance row
- Enhanced chart interactions
- Row expansion with order details

**Future (v2.0):**
- Tabbed interface for history/details
- Trade history views
- Grid visualization

## User Journey Flows

### Journey 1: Panic Check (3am Alert)

**Trigger:** Price alert notification during sleep
**Goal:** Determine "Is everything okay?" in under 30 seconds
**Success State:** Return to sleep with confidence

**Flow:**
1. Price alert → Open dashboard
2. Eyes hit header strip immediately
3. RAG status provides instant answer:
   - Green → Relief → Close laptop (10 seconds)
   - Yellow → Read warning → Scan table → Assess severity
   - Red → Alert mode → Expand problem pair → Evaluate options
4. Timestamp confirms data freshness
5. Close laptop or escalate to Binance if action needed

**Critical Design Requirements:**
- Header visible in <1 second
- RAG status comprehensible without reading
- Escalation path clear but not forced

### Journey 2: Morning Review (Coffee Mode)

**Trigger:** Weekend morning, reflective mood
**Goal:** Understand "How did the bot perform this week?"
**Success State:** Satisfying 10-minute review with insights

**Flow:**
1. Open dashboard in relaxed state
2. Header confirms all systems healthy
3. Timeframe row shows 1H/24H/7D/30D performance
4. Scan all-pairs table for individual performance
5. Expand interesting pairs for order details
6. Scroll to chart for price exploration
7. Hover for detailed data points
8. Repeat for other pairs as curiosity drives
9. Close dashboard feeling informed

**Critical Design Requirements:**
- Clear visual hierarchy for leisurely scanning
- Expandable rows for depth on demand
- Interactive chart rewards exploration

### Journey 3: Quick Glance (Mid-Task Check)

**Trigger:** Random curiosity or routine check during other work
**Goal:** Answer "Up or down today?" in 5 seconds
**Success State:** Return to primary task without disruption

**Flow:**
1. Switch to dashboard tab
2. Eyes immediately hit header strip
3. See: Green status + Positive P&L
4. Confirm "good" in <5 seconds
5. Tab back to primary task

**Critical Design Requirements:**
- Header answers question without any interaction
- No cognitive load required
- Clean escalation path if something needs attention

### Journey Patterns

**Header-First Principle:**
All journeys begin with the header strip. It serves as the universal routing mechanism:
- Green → Confidence path (minimal investigation)
- Yellow → Attention path (moderate investigation)
- Red → Alert path (deep investigation)

**Progressive Disclosure Cascade:**
Information depth increases on demand:
Header Strip → All-Pairs Table → Expanded Row → Chart → External (Binance)

**Silent Confidence Pattern:**
Updates occur without visual disruption. Users trust the data because they never see it "refreshing" — they only see current data.

**Escalation Ladder:**
Users naturally move from quick check to deep investigation as needed:
5-second glance → 30-second panic check → 10-minute review → External action

### Flow Optimization Principles

1. **Minimize Steps to Answer** — Header answers primary question without clicks
2. **Support Natural Scanning** — Top-to-bottom, left-to-right visual flow
3. **Enable Depth on Demand** — Expansion is invitation, not requirement
4. **Preserve Context During Exploration** — Header remains visible during scroll
5. **Clean Escalation Paths** — Easy transition from calm to investigation mode

## Component Strategy

### Design System Components

**NiceGUI/Quasar Foundation Components:**
| Component | Usage |
|-----------|-------|
| `ui.row()` / `ui.column()` | Page layout structure |
| `ui.card()` | Section containers |
| `ui.table()` | All-pairs table foundation |
| `ui.expansion()` | Row expansion behavior |
| `ui.label()` | Text and data display |
| `plotly` integration | Interactive price charts |
| Dark theme | Built-in theming support |

### Custom Components

**1. Header Strip**
- Purpose: Fixed component answering "Is everything okay?" instantly
- Elements: RAG status + P&L + Pair count + Order count + Timestamp
- Behavior: Fixed position, WebSocket updates without full refresh
- States: Healthy (green, recedes), Warning (amber, draws attention), Error (red, demands attention)

**2. RAG Status Indicator**
- Purpose: Instant health comprehension via color + icon + text
- Elements: Status icon (●/◆/▲) + Colored shape + Short text
- Accessibility: Shape differentiates state (not just color)

**3. P&L Display**
- Purpose: Profit/loss with instant positive/negative recognition
- Elements: Sign + Currency + Value + Direction arrow
- Typography: Monospace, always show sign, color-coded

**4. Pair Row**
- Purpose: Compact single-pair display in all-pairs table
- Elements: Symbol + P&L + Price + Order count + Expand toggle
- Behavior: Full row clickable, hover highlight, expandable
- Height: ~40px for compact density

**5. Expanded Pair Details**
- Purpose: Deep dive into single pair during Coffee Mode
- Elements: Orders table + Timeframe P&L breakdown
- Behavior: Appears below row on expansion, closes on collapse

**6. Timeframe Performance Row (v1.5)**
- Purpose: Quick multi-timeframe performance comparison
- Elements: 1H + 24H + 7D + 30D percentage changes
- Placement: Below header strip, scrolls with content

### Component Implementation Strategy

**Build with NiceGUI Primitives:**
All custom components will be built using NiceGUI's basic elements (`ui.row()`, `ui.label()`, `ui.card()`) styled with the design system color tokens.

**Reactive Data Binding:**
Components will use NiceGUI's reactive binding to update individual values without full component refresh.

**Consistency Patterns:**
- All monetary values use P&L Display component
- All status indicators use RAG pattern
- All expandable elements use consistent toggle behavior

### Implementation Roadmap

**Phase 1 - MVP Core:**
1. Header Strip (critical for Glance Mode)
2. RAG Status Indicator (critical for Panic Mode)
3. P&L Display (used in header and table)
4. Pair Row (basic version)
5. Plotly chart integration

**Phase 2 - Enhancement (v1.5):**
1. Expanded Pair Details
2. Timeframe Performance Row
3. Enhanced Pair Row with hover states

**Phase 3 - Future (v2.0):**
1. Tabs component for history/details
2. Trade history table
3. Grid visualization component

## UX Consistency Patterns

### Status & Feedback Patterns

**RAG Status System:**
| Level | Color | Icon | Behavior |
|-------|-------|------|----------|
| Healthy | `#00c853` | ● | Recedes — calm, doesn't demand attention |
| Warning | `#ffc107` | ◆ | Draws attention — awareness needed |
| Error | `#ff5252` | ▲ | Demands attention — action may be needed |

**Application Rules:**
- Never use color alone; always combine icon + color + text
- Green is the "quiet" default state
- Yellow interrupts but doesn't alarm
- Red is impossible to miss

### Data Update Patterns

**Silent Confidence Principle:**
Users never see "refreshing" — they only see current data.

**Update Behavior:**
- WebSocket pushes new data; UI updates in place
- No spinners on Tier 1 data (header)
- No full-page refresh; individual element updates
- No manual refresh button required

**Staleness Indication:**
- Normal: Timestamp displays last update time
- Warning (>60s): Timestamp turns amber
- Critical (>120s): Consider connection warning

### Interaction Patterns

**Hover States:**
| Element | Hover Effect |
|---------|--------------|
| Pair Row | Background lightens (+10%) |
| Expand Toggle | Subtle scale (1.1x) |
| Chart | Crosshair cursor, data tooltip |
| Header | No hover change (not interactive) |

**Click/Expand Behavior:**
- Pair row click toggles expansion (200ms animation)
- Expanded panel appears below row
- Only one row expanded at a time (optional: allow multiple)

**Focus States:**
- Focus ring: 2px `#4a9eff` outline
- Tab order: Header → Table rows → Chart

### Loading & Empty States

**Initial Load Priority:**
1. Header strip loads first (answers primary question)
2. Table rows populate
3. Chart renders last

**Empty States:**
| Scenario | Display |
|----------|---------|
| No pairs | "No active pairs configured" |
| No orders | "No open orders" (gray text) |
| API unavailable | Warning in header strip |

### Navigation Patterns

**Single Page Structure:**
- No navigation menu (single-purpose tool)
- Vertical scroll only
- Header fixed; content scrolls beneath
- Information accessible via scroll + expansion (no pages/tabs in v1.0)

**Scroll Behavior:**
- Header Strip: Fixed, never scrolls
- All other content: Scrolls naturally
- Expanded details: Push content down (don't overlay)

## Responsive Design & Accessibility

### Responsive Strategy

**Approach: Desktop-Only, Fixed-Width Optimization**

CryptoTrader is a single-user monitoring tool designed for laptop usage. Mobile and tablet support is explicitly out of scope for v1.0-v2.0.

**Desktop Strategy:**
| Viewport | Layout Behavior |
|----------|-----------------|
| 1200px+ | Full layout with comfortable spacing |
| 1024-1199px | Primary target (13-15" laptop) — compact density |
| <1024px | Graceful degradation, no optimization required |

**Design Rationale:**
- No responsive complexity = faster development
- Optimized for the actual use case, not hypothetical ones
- NiceGUI's Quasar foundation provides sensible defaults

### Breakpoint Strategy

**Approach: Single Target, No Breakpoints**

Rather than implementing breakpoints, the dashboard is designed for a single optimal viewport.

**Target Viewport:**
- **Width:** 1024-1440px (typical 13-15" laptop)
- **Height:** 700-900px (accounting for browser chrome)

**Layout Constants:**
| Element | Size | Rationale |
|---------|------|-----------|
| Header Strip | 48-56px fixed | Always visible, answers primary question |
| Pair Row | ~40px each | Fit 4-5 pairs without scrolling |
| Chart Area | ~300-400px | Flexible, fills remaining space |

**Overflow Handling:**
- Horizontal: Content stays within viewport; no horizontal scroll
- Vertical: Natural scroll for future content (tabs, history in v2.0)

### Accessibility Strategy

**Compliance Level: WCAG AA-Informed (Pragmatic)**

While formal WCAG compliance isn't required for a single-user tool, accessibility principles improve usability during late-night monitoring sessions.

**Implemented Accessibility Features:**

| Feature | Implementation | Rationale |
|---------|---------------|-----------|
| Color Contrast | 4.5:1+ for all text | Readable during 3am checks |
| Status Indication | Icon + Color + Text | Never color alone (RAG pattern) |
| Focus Visibility | 2px `#4a9eff` outline | Clear keyboard navigation |
| Font Size | Minimum 12px | Comfortable reading |
| Monospace Numbers | Roboto Mono | Data alignment and clarity |

**Not Required (Out of Scope):**
- Screen reader optimization (single sighted user)
- Touch target sizing (mouse/keyboard only)
- Complex ARIA implementations
- High contrast mode toggle

**3am Accessibility Considerations:**
- Dark theme reduces eye strain
- High contrast status colors (green/amber/red) remain distinguishable at low alertness
- No bright flashing or animation that could startle

### Testing Strategy

**Pragmatic Single-User Testing:**

**Device Testing:**
- Primary: Your actual laptop (13-15" screen)
- Browser: Chrome (latest) — primary target
- Secondary: Firefox, Edge (sanity check)

**Visual Testing:**
- [ ] Header strip visible without scroll
- [ ] All 4-5 pairs visible in table
- [ ] Chart renders at comfortable size
- [ ] RAG colors distinguishable
- [ ] Update timestamps readable

**3am Simulation Testing:**
- [ ] Dashboard readable in dim room
- [ ] Status comprehensible in 5-second glance
- [ ] No jarring animations or flashes

**Real-World Validation:**
- Use dashboard during actual trading periods
- Note any friction during panic/coffee/glance modes
- Iterate based on lived experience

### Implementation Guidelines

**Development Principles:**

**Layout:**
- Use NiceGUI's layout primitives (`ui.row()`, `ui.column()`)
- Fixed header using CSS `position: sticky`
- Avoid absolute positioning except for header
- Let content flow naturally in single column

**Typography:**
- Use relative units (`rem`) for font sizes
- Base size: 14px (0.875rem)
- Monospace for all numerical data

**Color Implementation:**
- Define CSS variables for theme colors
- Use semantic naming (e.g., `--status-healthy`, `--status-warning`)
- Apply opacity variations rather than additional colors

**Focus Management:**
- Ensure tab order follows visual order
- Visible focus rings on all interactive elements
- Skip link not required (simple page structure)

**Dark Theme:**
- NiceGUI/Quasar dark mode as foundation
- Override with custom color palette
- Test contrast ratios with WebAIM checker
