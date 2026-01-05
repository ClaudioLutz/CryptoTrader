# Story 1.5: Implement Main Entry Point

Status: review

## Story

As a **developer**,
I want **a main.py entry point that launches the NiceGUI application**,
So that **the dashboard can be started with a simple command**.

## Acceptance Criteria

1. **AC1:** `dashboard/main.py` launches NiceGUI on configured port (default 8081)
2. **AC2:** Browser opens automatically to `http://localhost:8081`
3. **AC3:** Page displays a placeholder "CryptoTrader Dashboard" title
4. **AC4:** Dark theme is applied on startup
5. **AC5:** Console shows "Dashboard started on port {port}" using logger
6. **AC6:** Dashboard runs without errors

## Tasks / Subtasks

- [x] Task 1: Implement main() function (AC: 1, 2, 6)
  - [x] Import NiceGUI and config
  - [x] Configure ui.run() with port from config
  - [x] Set browser auto-open behavior

- [x] Task 2: Apply dark theme (AC: 4)
  - [x] Enable NiceGUI dark mode
  - [x] Import theme.css (from Story 1.3)

- [x] Task 3: Create placeholder UI (AC: 3)
  - [x] Add page title "CryptoTrader Dashboard"
  - [x] Add placeholder header element

- [x] Task 4: Configure logging (AC: 5)
  - [x] Use logging module (not print)
  - [x] Log startup message with port number

- [x] Task 5: Add entry point guard (AC: 6)
  - [x] Add `if __name__ == "__main__":` block

## Dev Notes

### Main Entry Point Implementation

[Source: docs/planning-artefacts/architecture.md - Development Workflow]

```python
"""CryptoTrader Dashboard - Main Entry Point.

This module serves as the main entry point for the NiceGUI dashboard.
Run with: python dashboard/main.py
"""

import logging

from nicegui import ui

from dashboard.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_ui() -> None:
    """Create the dashboard UI components."""
    # Enable dark mode
    ui.dark_mode(True)

    # Placeholder title - will be replaced by header component in Epic 3
    ui.label("CryptoTrader Dashboard").classes("text-h4 text-center q-pa-md")

    # Placeholder message
    ui.label("Dashboard initialized successfully. Components coming in Epic 3-6.")


def main() -> None:
    """Main entry point for the dashboard."""
    logger.info("Starting CryptoTrader Dashboard on port %d", config.dashboard_port)

    # Create UI
    create_ui()

    # Run NiceGUI server
    ui.run(
        port=config.dashboard_port,
        title="CryptoTrader Dashboard",
        dark=True,
        reload=False,  # Disable for production
    )


if __name__ == "__main__":
    main()
```

### Running the Dashboard

```bash
# Direct execution
python dashboard/main.py

# Or as module (if pyproject.toml configured)
python -m dashboard.main
```

### NiceGUI ui.run() Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `port` | `config.dashboard_port` | Server port (8081) |
| `title` | "CryptoTrader Dashboard" | Browser tab title |
| `dark` | `True` | Enable dark mode |
| `reload` | `False` | Disable auto-reload for stability |

### Logging Pattern

[Source: _bmad-output/project-context.md - Logging Rules]

```python
import logging
logger = logging.getLogger(__name__)

# Correct pattern
logger.info("Dashboard started", port=8081, version="1.0.0")

# NEVER use print()
# print("Dashboard started")  # Wrong!
```

### Integration with Theme (Story 1.3)

If theme.css exists, load it:
```python
from pathlib import Path

theme_path = Path(__file__).parent / "assets" / "css" / "theme.css"
if theme_path.exists():
    ui.add_css(theme_path.read_text())
```

### Project Structure Notes

- File location: `dashboard/main.py`
- Depends on: `dashboard/config.py` (Story 1.4)
- Optional dependency: `dashboard/assets/css/theme.css` (Story 1.3)

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#development-workflow)
- [Project Context](/_bmad-output/project-context.md#logging-rules)
- [NiceGUI Documentation](https://nicegui.io/documentation#ui_run)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Implemented main() function with config.dashboard_port integration
- ui.run() configured with dark=True, reload=False for stability
- create_ui() function created for dashboard UI setup
- load_theme() function loads CSS from assets/css/theme.css
- Proper logging configured with logger.info() for startup message
- Entry point guard (__name__ == "__main__") added
- @ui.page("/") decorator for main route

### File List

- dashboard/main.py (modified)

