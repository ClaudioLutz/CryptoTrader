# Story 1.1: Initialize Dashboard Project Structure

Status: review

## Story

As a **developer**,
I want **the dashboard project structure created with proper folder organization**,
So that **code is organized consistently and future development is streamlined**.

## Acceptance Criteria

1. **AC1:** The `dashboard/` directory is created at the project root level
2. **AC2:** The following directory structure is created:
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
3. **AC3:** Each `__init__.py` file is present for Python package recognition
4. **AC4:** `.gitkeep` files are added to empty directories (`assets/css/`)
5. **AC5:** All files follow the project's naming conventions (snake_case for Python files)

## Tasks / Subtasks

- [x] Task 1: Create dashboard directory structure (AC: 1, 2)
  - [x] Create `dashboard/` root directory
  - [x] Create `dashboard/components/` subdirectory
  - [x] Create `dashboard/services/` subdirectory
  - [x] Create `dashboard/assets/css/` subdirectory
  - [x] Create `dashboard/tests/` subdirectory

- [x] Task 2: Create Python package files (AC: 3, 5)
  - [x] Create `dashboard/components/__init__.py`
  - [x] Create `dashboard/services/__init__.py`
  - [x] Create `dashboard/tests/__init__.py`

- [x] Task 3: Create placeholder files (AC: 2, 4)
  - [x] Create `dashboard/main.py` with minimal placeholder
  - [x] Create `dashboard/config.py` with minimal placeholder
  - [x] Create `dashboard/state.py` with minimal placeholder
  - [x] Create `dashboard/assets/css/.gitkeep`

- [x] Task 4: Verify structure (AC: 1-5)
  - [x] Run `tree dashboard/` to verify structure
  - [x] Verify all `__init__.py` files exist
  - [x] Verify no linting errors in placeholder files

## Dev Notes

### Critical Architecture Context

**This story establishes the foundation for the NiceGUI dashboard that will replace the existing Streamlit dashboard.** The directory structure is defined in the Architecture Decision Document and must be followed exactly to ensure consistency with subsequent stories.

### Project Structure Reference

[Source: docs/planning-artefacts/architecture.md - Project Structure & Boundaries]

```
CryptoTrader/
├── src/                            # Existing trading bot (UNCHANGED)
│   ├── api/                        # aiohttp REST API (port 8080)
│   └── ...
├── dashboard/                      # NEW: NiceGUI dashboard
│   ├── main.py                     # Entry point
│   ├── config.py                   # DashboardConfig (Pydantic Settings)
│   ├── state.py                    # DashboardState class
│   ├── components/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   ├── assets/
│   │   └── css/
│   └── tests/
│       └── __init__.py
└── ...
```

**Important:** The dashboard is a **separate Python package** that consumes the existing bot API. No modifications to bot code (`src/`) are required.

### Project Structure Notes

- **Alignment:** This structure aligns with the unified project architecture defined in architecture.md
- **Integration Point:** Dashboard will communicate with Bot API on port 8080 via REST
- **Dashboard Port:** Will run on port 8081 (configured in Story 1.4)
- **No Conflicts:** Dashboard is isolated from bot code

### Technology Stack Reference

[Source: _bmad-output/project-context.md - Technology Stack]

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | >=3.11 | Runtime (match existing bot) |
| NiceGUI | 3.4.1 | Dashboard framework |
| httpx | async | REST API client (Story 2.2) |
| Pydantic | >=2.0.0 | Configuration & models |
| Plotly | >=5.24.0 | Charts |

### Placeholder File Contents

**dashboard/main.py:**
```python
"""CryptoTrader Dashboard - Entry Point.

This module serves as the main entry point for the NiceGUI dashboard.
Full implementation in Story 1.5.
"""
```

**dashboard/config.py:**
```python
"""CryptoTrader Dashboard - Configuration.

Pydantic Settings configuration module.
Full implementation in Story 1.4.
"""
```

**dashboard/state.py:**
```python
"""CryptoTrader Dashboard - State Management.

Dashboard state management using DashboardState class.
Full implementation in Story 2.3.
"""
```

**dashboard/components/__init__.py:**
```python
"""Dashboard UI components package."""
```

**dashboard/services/__init__.py:**
```python
"""Dashboard services package (API client, data models)."""
```

**dashboard/tests/__init__.py:**
```python
"""Dashboard test package."""
```

### Coding Standards

[Source: _bmad-output/project-context.md - Critical Implementation Rules]

- **File Naming:** snake_case.py (e.g., `api_client.py`, `data_models.py`)
- **Type Hints:** Required on all function signatures (mypy strict)
- **Docstrings:** Required for all modules
- **Line Length:** 100 characters max (ruff)
- **No print():** Use logger (though not needed for this story)

### References

- [Architecture Decision Document](docs/planning-artefacts/architecture.md#project-structure--boundaries)
- [Project Context](/_bmad-output/project-context.md)
- [UX Design Specification](docs/planning-artefacts/ux-design-specification.md) - Section on component organization

### Git Intelligence

Recent commits show:
- `feat: streamlit dashboard implementation` - Existing Streamlit dashboard in place
- Documentation updates for README and stories

**Note:** The new NiceGUI dashboard (`dashboard/`) will coexist with the existing Streamlit implementation during migration, eventually replacing it.

### Definition of Done

- [x] `dashboard/` directory exists with all subdirectories
- [x] All `__init__.py` files present
- [x] Placeholder files contain module docstrings
- [x] `ruff check dashboard/` passes with no errors
- [x] Structure matches architecture.md exactly

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None required - straightforward file creation

### Completion Notes List

- Created dashboard directory structure matching architecture.md exactly
- All Python package __init__.py files created with appropriate docstrings
- Placeholder files (main.py, config.py, state.py) created with module docstrings
- .gitkeep added to empty assets/css/ directory
- All files verified via py_compile (no syntax errors)
- All files follow snake_case naming convention

### File List

- dashboard/main.py (created)
- dashboard/config.py (created)
- dashboard/state.py (created)
- dashboard/components/__init__.py (created)
- dashboard/services/__init__.py (created)
- dashboard/tests/__init__.py (created)
- dashboard/assets/css/.gitkeep (created)

