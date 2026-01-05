# Story 1.4: Create Configuration Module

Status: ready-for-dev

## Story

As a **developer**,
I want **a centralized configuration module using Pydantic Settings**,
So that **settings like API URL and poll intervals can be changed without code modifications**.

## Acceptance Criteria

1. **AC1:** Configuration module `config.py` exists in dashboard directory
2. **AC2:** Settings are loaded with sensible defaults
3. **AC3:** Settings can be overridden via environment variables with prefix `DASHBOARD_`
4. **AC4:** Config is accessible as a singleton throughout the application
5. **AC5:** All configuration values are type-safe using Pydantic

## Tasks / Subtasks

- [ ] Task 1: Create DashboardConfig class (AC: 1, 2, 5)
  - [ ] Define `api_base_url` with default `http://localhost:8080`
  - [ ] Define `dashboard_port` with default `8081`
  - [ ] Define `poll_interval_tier1` with default `2.0` seconds
  - [ ] Define `poll_interval_tier2` with default `5.0` seconds
  - [ ] Define `api_timeout` with default `5.0` seconds

- [ ] Task 2: Configure environment variable support (AC: 3)
  - [ ] Set `env_prefix = "DASHBOARD_"` in model_config
  - [ ] Test override with `DASHBOARD_API_BASE_URL`

- [ ] Task 3: Implement singleton pattern (AC: 4)
  - [ ] Create module-level `config` instance
  - [ ] Export for import by other modules

- [ ] Task 4: Add validation and documentation (AC: 5)
  - [ ] Add Field constraints (ge, le) where appropriate
  - [ ] Add docstrings for each setting

## Dev Notes

### Configuration Implementation

[Source: docs/planning-artefacts/architecture.md - Process Patterns]

```python
"""CryptoTrader Dashboard - Configuration Module."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardConfig(BaseSettings):
    """Dashboard configuration with environment variable support.

    All settings can be overridden via environment variables with
    the DASHBOARD_ prefix. For example:
        DASHBOARD_API_BASE_URL=http://localhost:8080
        DASHBOARD_POLL_INTERVAL_TIER1=1.5
    """

    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API Configuration
    api_base_url: str = Field(
        default="http://localhost:8080",
        description="Base URL for the trading bot REST API"
    )
    api_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Timeout in seconds for API requests"
    )

    # Dashboard Server
    dashboard_port: int = Field(
        default=8081,
        ge=1024,
        le=65535,
        description="Port for the NiceGUI dashboard server"
    )

    # Polling Intervals
    poll_interval_tier1: float = Field(
        default=2.0,
        ge=0.5,
        le=60.0,
        description="Polling interval for Tier 1 data (health, P&L)"
    )
    poll_interval_tier2: float = Field(
        default=5.0,
        ge=1.0,
        le=120.0,
        description="Polling interval for Tier 2 data (chart, table)"
    )


# Singleton instance
config = DashboardConfig()
```

### Usage Pattern

```python
from dashboard.config import config

# Access settings
print(config.api_base_url)
print(config.poll_interval_tier1)
```

### Environment Variable Examples

```bash
# Override API URL
export DASHBOARD_API_BASE_URL="http://192.168.1.100:8080"

# Faster polling for testing
export DASHBOARD_POLL_INTERVAL_TIER1=1.0

# Change dashboard port
export DASHBOARD_PORT=3000
```

### Polling Interval Reference

[Source: docs/planning-artefacts/architecture.md - Polling Intervals]

| Data Tier | Default Interval | Rationale |
|-----------|-----------------|-----------|
| Tier 1 (Health, P&L) | 2 seconds | Critical, real-time feel |
| Tier 2 (Pairs table, Chart) | 5 seconds | Important but less urgent |
| Tier 3 (Expanded details) | On-demand | Only when user expands row |

### Project Structure Notes

- File location: `dashboard/config.py`
- Pydantic Settings v2 syntax (`model_config` not `class Config`)
- Match existing bot pattern using `SettingsConfigDict`

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#configuration-via-pydantic-settings)
- [Project Context](/_bmad-output/project-context.md#pydantic-rules)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

