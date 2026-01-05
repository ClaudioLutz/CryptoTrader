---
project_name: 'CryptoTrader'
user_name: 'Claudio'
date: '2026-01-05'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'workflow_rules', 'critical_rules']
existing_patterns_found: 12
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

### Bot Core (Existing - DO NOT MODIFY)

| Technology | Version | Notes |
|------------|---------|-------|
| Python | >=3.11 | Required for type union syntax `X | None` |
| Pydantic | >=2.0.0 | Use `model_config` not `class Config` |
| pydantic-settings | >=2.0.0 | For configuration management |
| SQLAlchemy | >=2.0.0 | Use `Mapped[]` columns, async sessions |
| ccxt | >=4.0.0 | Exchange integration |
| structlog | >=24.0.0 | Structured JSON logging |
| aiohttp | >=3.9.0 | REST API server (port 8080) |

### Dashboard (New)

| Technology | Version | Notes |
|------------|---------|-------|
| NiceGUI | 3.4.1 | Dashboard framework (port 8081) |
| httpx | async | For API client calls |
| Plotly | >=5.24.0 | Interactive charts |

### Dev Tools

| Tool | Configuration |
|------|--------------|
| ruff | line-length=100, target-version="py311" |
| mypy | strict=true, disallow_untyped_defs=true |
| pytest | asyncio_mode="auto" |

---

## Critical Implementation Rules

### Python-Specific Rules

- **Type Hints Required:** All functions MUST have type hints (mypy strict)
- **Union Syntax:** Use `X | None` not `Optional[X]` (Python 3.11+)
- **Async-First:** All I/O operations must be async (`async def`, `await`)
- **No print():** Use `structlog` logger, never `print()` statements
- **Decimal for Money:** Use `Decimal` not `float` for all financial calculations

```python
# ✅ Correct
from decimal import Decimal
async def calculate_pnl(entry: Decimal, exit: Decimal) -> Decimal:
    return exit - entry

# ❌ Wrong
def calculate_pnl(entry, exit):  # Missing types, not async
    return exit - entry
```

### Pydantic Rules

- **Settings Pattern:** Use `SettingsConfigDict` with `env_prefix`
- **Field Validation:** Use `Field()` with constraints (`ge`, `le`, etc.)
- **SecretStr:** Always use `SecretStr` for sensitive values

```python
# ✅ Correct pattern from codebase
class ExchangeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EXCHANGE__")
    api_key: SecretStr = Field(default=SecretStr(""))
    rate_limit_ms: int = Field(default=100, ge=50, le=1000)
```

### SQLAlchemy 2.0 Rules

- **Mapped Columns:** Use `Mapped[type]` with `mapped_column()`
- **Async Sessions:** Always use `async_session` context manager
- **TimestampMixin:** Include `created_at`/`updated_at` on all models

```python
# ✅ Correct pattern from codebase
class Trade(Base, TimestampMixin):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
```

### NiceGUI Dashboard Rules

- **Component Pattern:** Function-based with shared state reference
- **Timer for Polling:** Use `ui.timer()` for periodic API calls
- **No Full Refresh:** NiceGUI handles surgical DOM updates via WebSocket
- **State in Python:** Dashboard state lives in Python class, not browser

```python
# ✅ Correct pattern from architecture
def header(state: DashboardState) -> None:
    with ui.header().classes('fixed-header'):
        ui.label().bind_text_from(state, 'health_status')

ui.timer(2.0, state.refresh_tier1)  # Tier 1: 2 seconds
ui.timer(5.0, state.refresh_tier2)  # Tier 2: 5 seconds
```

### Testing Rules

- **Async Tests:** Use `pytest-asyncio` with `asyncio_mode="auto"`
- **Markers:** Use `@pytest.mark.integration` and `@pytest.mark.slow`
- **Test Naming:** `test_<module>_<behavior>.py`
- **Fixtures in conftest.py:** Shared fixtures go in `conftest.py`

```python
# ✅ Correct pattern
@pytest.mark.asyncio
async def test_api_client_fetches_health():
    client = ApiClient(config)
    result = await client.get_health()
    assert result.status in ["healthy", "degraded", "error"]
```

### Code Quality Rules

- **Line Length:** 100 characters max (ruff)
- **Import Order:** stdlib → third-party → local (isort via ruff)
- **Docstrings:** Required for all public functions/classes
- **No Unused Args:** Flagged by ruff (ARG rules)

### Logging Rules

- **Logger per Module:** `logger = logging.getLogger(__name__)`
- **Structured Fields:** Use `logger.info("msg", key=value)` pattern
- **No print():** NEVER use `print()` - always logger

```python
import logging
logger = logging.getLogger(__name__)

# ✅ Correct
logger.info("Dashboard started", port=8081, version="1.0.0")

# ❌ Wrong
print("Dashboard started on port 8081")
```

---

## Critical Don't-Miss Rules

### Anti-Patterns to Avoid

1. **Never modify bot code for dashboard MVP** - Dashboard consumes existing API
2. **Never use `float` for money** - Always `Decimal`
3. **Never block the event loop** - All I/O must be async
4. **Never hardcode secrets** - Use environment variables or SecretStr
5. **Never skip type hints** - mypy strict mode will fail

### Port Configuration

| Service | Port | Notes |
|---------|------|-------|
| Bot API (aiohttp) | 8080 | DO NOT CHANGE |
| Dashboard (NiceGUI) | 8081 | Configurable via `DASHBOARD_PORT` |

### Error Handling Pattern

```python
# Dashboard must gracefully degrade
async def fetch_health() -> HealthResponse | None:
    try:
        response = await client.get(f"{API_BASE}/health", timeout=5.0)
        return HealthResponse(**response.json())
    except Exception as e:
        logger.error("Health fetch failed", error=str(e))
        return None  # Show stale data, don't crash
```

### Configuration Pattern

```python
# Use Pydantic Settings with env prefix
class DashboardConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DASHBOARD_")

    api_base_url: str = "http://localhost:8080"
    port: int = 8081
    poll_interval_tier1: float = 2.0
```

---

## Architecture Reference

Full architecture decisions are documented in:
`docs/planning-artefacts/architecture.md`

Key architectural decisions:
- Centralized DataService with timer-based polling
- Tiered polling (2s/5s/on-demand)
- Graceful degradation with stale data indicators
- NiceGUI reactive bindings for flicker-free updates

---

**Last Updated:** 2026-01-05
**Source:** Generated from architecture.md and codebase analysis
