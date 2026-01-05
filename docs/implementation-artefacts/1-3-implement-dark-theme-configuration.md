# Story 1.3: Implement Dark Theme Configuration

Status: review

## Story

As a **trader (Claudio)**,
I want **the dashboard to display in a professional dark theme**,
So that **it's comfortable for 3am monitoring and looks like a serious trading tool**.

## Acceptance Criteria

1. **AC1:** Dashboard background color is `#1a1a2e` (dark navy)
2. **AC2:** Text primary color is `#e8e8e8` (light gray)
3. **AC3:** All color tokens from UX spec are applied via CSS variables
4. **AC4:** Quasar dark mode is enabled by default
5. **AC5:** `assets/css/theme.css` contains custom color overrides
6. **AC6:** Theme loads correctly when dashboard starts

## Tasks / Subtasks

- [x] Task 1: Create theme.css file (AC: 3, 5)
  - [x] Define CSS variables for all color tokens
  - [x] Set background colors (primary, secondary, surface)
  - [x] Set text colors (primary, secondary, tertiary)
  - [x] Set semantic colors (success, warning, error)
  - [x] Set accent color for interactive elements

- [x] Task 2: Configure Quasar dark mode (AC: 4)
  - [x] Enable dark mode in NiceGUI configuration
  - [x] Apply dark theme on application startup

- [x] Task 3: Apply theme to dashboard (AC: 1, 2, 6)
  - [x] Import theme.css in main.py
  - [x] Verify background renders as `#1a1a2e`
  - [x] Verify text renders as `#e8e8e8`

## Dev Notes

### Color Palette Reference

[Source: docs/planning-artefacts/ux-design-specification.md - Color System]

**Background Palette:**
| Role | Hex | CSS Variable |
|------|-----|--------------|
| Base | `#1a1a2e` | `--bg-primary` |
| Elevated | `#16213e` | `--bg-secondary` |
| Surface | `#0f3460` | `--surface` |

**Text Colors:**
| Level | Hex | CSS Variable |
|-------|-----|--------------|
| Primary | `#e8e8e8` | `--text-primary` |
| Secondary | `#a0a0a0` | `--text-secondary` |
| Tertiary | `#6b7280` | `--text-tertiary` |

**Semantic Colors (RAG Status):**
| Status | Hex | CSS Variable |
|--------|-----|--------------|
| Success/Healthy | `#00c853` | `--status-success` |
| Warning/Degraded | `#ffc107` | `--status-warning` |
| Error/Critical | `#ff5252` | `--status-error` |

**Interactive Elements:**
| Role | Hex | CSS Variable |
|------|-----|--------------|
| Accent | `#4a9eff` | `--accent` |
| Hover | `#6bb3ff` | `--accent-hover` |

### theme.css Template

```css
:root {
  /* Background colors */
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --surface: #0f3460;

  /* Text colors */
  --text-primary: #e8e8e8;
  --text-secondary: #a0a0a0;
  --text-tertiary: #6b7280;

  /* Semantic colors */
  --status-success: #00c853;
  --status-warning: #ffc107;
  --status-error: #ff5252;

  /* Interactive */
  --accent: #4a9eff;
  --accent-hover: #6bb3ff;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

/* Quasar dark mode overrides */
.q-dark {
  --q-primary: var(--accent);
  --q-dark: var(--bg-primary);
  --q-dark-page: var(--bg-primary);
}
```

### NiceGUI Dark Mode Configuration

```python
from nicegui import ui

# Enable dark mode
ui.dark_mode(True)

# Or use auto detection
# ui.dark_mode().auto()
```

### CSS Import in NiceGUI

```python
from nicegui import ui

# Add custom CSS
ui.add_css('''
    :root { ... }
''')

# Or load from file
# app.add_static_files('/assets', 'assets')
```

### Project Structure Notes

- Theme file location: `dashboard/assets/css/theme.css`
- Import in `main.py` before UI components render
- Quasar's dark mode must be enabled for consistent styling

### References

- [UX Design Specification](docs/planning-artefacts/ux-design-specification.md#color-system)
- [Architecture Document](docs/planning-artefacts/architecture.md#customization-strategy)
- [NiceGUI Dark Mode Docs](https://nicegui.io/documentation#dark_mode)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created theme.css with all color tokens from UX spec
- CSS variables include: bg-primary (#1a1a2e), bg-secondary, surface, text colors, semantic colors, accent
- Added PnL-specific colors (positive/negative/neutral) for trading context
- Quasar dark mode overrides included
- main.py updated with load_theme() function and ui.dark_mode(True)
- Theme loads automatically on dashboard startup

### File List

- dashboard/assets/css/theme.css (created)
- dashboard/main.py (modified)

