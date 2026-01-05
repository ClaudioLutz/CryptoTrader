# Story 1.2: Install and Configure Dependencies

Status: ready-for-dev

## Story

As a **developer**,
I want **all required Python packages installed and configured**,
So that **NiceGUI, httpx, Pydantic, and Plotly are available for development**.

## Acceptance Criteria

1. **AC1:** `requirements.txt` includes all required dashboard dependencies
2. **AC2:** Running `pip install -r requirements.txt` succeeds without errors
3. **AC3:** `pyproject.toml` includes dashboard as a runnable module
4. **AC4:** All package versions are pinned to specific versions for reproducibility
5. **AC5:** Dependencies are compatible with existing bot requirements (Python 3.11+)

## Tasks / Subtasks

- [ ] Task 1: Update requirements.txt (AC: 1, 4)
  - [ ] Add `nicegui>=3.4.0`
  - [ ] Add `httpx>=0.27.0`
  - [ ] Add `pydantic>=2.0.0` (if not already present)
  - [ ] Add `pydantic-settings>=2.0.0`
  - [ ] Add `plotly>=5.0.0` (if not already present)

- [ ] Task 2: Update pyproject.toml (AC: 3)
  - [ ] Add dashboard entry point configuration
  - [ ] Ensure dashboard can be run as module

- [ ] Task 3: Verify installation (AC: 2, 5)
  - [ ] Run `pip install -r requirements.txt`
  - [ ] Verify no version conflicts with existing bot dependencies
  - [ ] Test imports: `import nicegui`, `import httpx`, `import plotly`

## Dev Notes

### Required Dependencies

[Source: docs/planning-artefacts/architecture.md - Starter Template Evaluation]

| Package | Version | Purpose |
|---------|---------|---------|
| nicegui | >=3.4.0 | Dashboard framework (FastAPI + Vue/Quasar + WebSocket) |
| httpx | >=0.27.0 | Async HTTP client for bot API calls |
| pydantic | >=2.0.0 | Data validation and settings management |
| pydantic-settings | >=2.0.0 | Configuration management with env vars |
| plotly | >=5.0.0 | Interactive charting library |

### Existing Bot Dependencies

[Source: _bmad-output/project-context.md - Technology Stack]

The bot already uses:
- Python >=3.11
- Pydantic >=2.0.0
- SQLAlchemy >=2.0.0
- ccxt >=4.0.0
- structlog >=24.0.0
- aiohttp >=3.9.0

**Compatibility Notes:**
- NiceGUI uses FastAPI internally (compatible with aiohttp)
- httpx is async-native, works alongside aiohttp
- Plotly has no conflicts with existing stack

### pyproject.toml Entry Point

Add to `[project.scripts]` or `[tool.poetry.scripts]`:
```toml
[project.scripts]
dashboard = "dashboard.main:main"
```

Or for direct module execution:
```toml
[tool.setuptools.packages.find]
include = ["dashboard*"]
```

### Project Structure Notes

- Dependencies should be added to existing `requirements.txt` at project root
- Do NOT create a separate `dashboard/requirements.txt`
- Maintain single source of truth for dependencies

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#initialization-command)
- [Project Context](/_bmad-output/project-context.md#technology-stack--versions)
- [NiceGUI Documentation](https://nicegui.io)

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Completion Notes List

### File List

