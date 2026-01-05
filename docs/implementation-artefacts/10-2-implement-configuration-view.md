# Story 10.2: Implement Configuration View

Status: review

**Version:** v2.0

## Story

As a **trader (Claudio)**,
I want **to see bot configuration settings**,
So that **I can verify the bot is configured as expected**.

## Acceptance Criteria

1. **AC1:** Display key settings: trading pairs, grid spacing, order sizes, risk parameters
2. **AC2:** All settings are read-only (no edit capability)
3. **AC3:** Values are formatted for readability
4. **AC4:** View is accessed via a tab or collapsible section

## Tasks / Subtasks

- [x] Task 1: Fetch configuration from API
  - [x] Add API method for bot config
  - [x] Define BotConfig data model

- [x] Task 2: Create configuration display (AC: 1, 3)
  - [x] Display trading pairs
  - [x] Display grid spacing
  - [x] Display order sizes
  - [x] Display risk parameters

- [x] Task 3: Ensure read-only (AC: 2)
  - [x] No edit controls
  - [x] Visual indication of read-only

- [x] Task 4: Add to tab navigation (AC: 4)
  - [x] Create "Configuration" tab
  - [x] Or collapsible section

## Dev Notes

### Bot Configuration Data Model

```python
"""Bot configuration data models."""

from decimal import Decimal

from pydantic import BaseModel


class PairConfig(BaseModel):
    """Configuration for a single trading pair."""
    symbol: str
    enabled: bool
    grid_levels: int
    grid_spacing_pct: Decimal
    order_size: Decimal
    max_position: Decimal


class RiskConfig(BaseModel):
    """Risk management configuration."""
    max_open_orders: int
    max_daily_loss: Decimal
    stop_loss_pct: Decimal | None
    take_profit_pct: Decimal | None


class BotConfig(BaseModel):
    """Complete bot configuration."""
    bot_name: str
    version: str
    exchange: str
    pairs: list[PairConfig]
    risk: RiskConfig
    api_timeout_ms: int
    poll_interval_ms: int
```

### Configuration View Component

```python
"""Bot configuration display component."""

from nicegui import ui

from dashboard.state import state


def configuration_view() -> None:
    """Display bot configuration (read-only)."""
    config = state.bot_config

    if config is None:
        ui.label("Configuration not available").classes("error-text")
        return

    with ui.column().classes("config-view gap-4"):
        # General info
        config_section("General", [
            ("Bot Name", config.bot_name),
            ("Version", config.version),
            ("Exchange", config.exchange),
        ])

        # Trading pairs
        ui.label("Trading Pairs").classes("section-header")
        for pair in config.pairs:
            pair_config_card(pair)

        # Risk settings
        config_section("Risk Management", [
            ("Max Open Orders", str(config.risk.max_open_orders)),
            ("Max Daily Loss", f"€{config.risk.max_daily_loss:,.2f}"),
            ("Stop Loss", f"{config.risk.stop_loss_pct}%" if config.risk.stop_loss_pct else "Disabled"),
            ("Take Profit", f"{config.risk.take_profit_pct}%" if config.risk.take_profit_pct else "Disabled"),
        ])


def config_section(title: str, items: list[tuple[str, str]]) -> None:
    """Display configuration section."""
    with ui.card().classes("config-section"):
        ui.label(title).classes("section-header")
        with ui.column().classes("config-items"):
            for label, value in items:
                config_item(label, value)


def config_item(label: str, value: str) -> None:
    """Single configuration item."""
    with ui.row().classes("config-item"):
        ui.label(label).classes("config-label")
        ui.label(value).classes("config-value")


def pair_config_card(pair: PairConfig) -> None:
    """Configuration card for a trading pair."""
    with ui.card().classes("pair-config-card"):
        with ui.row().classes("justify-between items-center"):
            ui.label(pair.symbol).classes("pair-symbol")
            status = "Enabled" if pair.enabled else "Disabled"
            status_class = "status-enabled" if pair.enabled else "status-disabled"
            ui.badge(status).classes(status_class)

        with ui.grid(columns=2).classes("pair-settings"):
            config_item("Grid Levels", str(pair.grid_levels))
            config_item("Grid Spacing", f"{pair.grid_spacing_pct}%")
            config_item("Order Size", str(pair.order_size))
            config_item("Max Position", str(pair.max_position))
```

### CSS Styling

```css
.config-view {
  padding: 16px;
  max-width: 800px;
}

.config-section {
  background-color: var(--bg-secondary);
  padding: 16px;
}

.section-header {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.config-item {
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--surface);
}

.config-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.config-value {
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
  color: var(--text-primary);
}

.pair-config-card {
  background-color: var(--surface);
  padding: 12px;
  margin-bottom: 8px;
}

.pair-symbol {
  font-weight: 600;
}

.status-enabled {
  background-color: var(--status-success);
}

.status-disabled {
  background-color: var(--text-tertiary);
}
```

### Tab Integration

```python
# In main.py tabs
with ui.tab("Configuration", icon="settings"):
    pass

with ui.tab_panel(...):
    configuration_view()
```

### Read-Only Indication

All values displayed as labels, not inputs. Visual cues:
- Monospace font for values
- No hover states on items
- Optional "Read-only" badge at top

### Project Structure Notes

- Creates: `dashboard/components/configuration_view.py`
- Modifies: `dashboard/main.py` (add to tabs)
- Modifies: `dashboard/services/api_client.py` (add config endpoint)

### References

- [Epics Document](docs/planning-artefacts/epics.md#story-102-implement-configuration-view)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created BotConfig, PairConfig, RiskConfig models in data_models.py
- Added get_bot_config API method in api_client.py
- Added bot_config field to state.py
- Created configuration_view.py component with:
  - General section (bot name, version, exchange)
  - Trading pairs section with per-pair cards
  - Risk management section
  - Timing section (API timeout, poll interval)
- All values displayed as labels (read-only)
- "Read-only" badge in header indicates no edit capability
- Enabled/Disabled badges for trading pairs
- Added Configuration tab to main.py navigation
- Monospace font for configuration values

### File List

- dashboard/services/data_models.py (modified)
- dashboard/services/api_client.py (modified)
- dashboard/state.py (modified)
- dashboard/components/configuration_view.py (created)
- dashboard/main.py (modified)
- dashboard/assets/css/theme.css (modified)

