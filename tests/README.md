# CryptoTrader Test Suite

This directory contains the test suite for the CryptoTrader project, including unit tests, integration tests, and end-to-end (E2E) browser tests for the dashboard.

## Test Structure

```
tests/
├── unit/                    # Unit tests for crypto_bot core
│   ├── test_settings.py     # Configuration validation
│   ├── test_retry.py        # Retry logic
│   └── test_logging.py      # Logging utilities
├── integration/             # Integration tests
│   └── test_binance_testnet.py  # Exchange connectivity
├── e2e/                     # End-to-end dashboard tests (Playwright)
│   ├── conftest.py          # Playwright fixtures
│   ├── test_dashboard_load.py   # Dashboard loading tests
│   └── test_auth.py         # Authentication flow tests
├── fixtures/                # Shared test fixtures
│   └── __init__.py
└── support/                 # Test support utilities
    └── page_objects/        # Page object models
        ├── dashboard_page.py
        └── login_page.py
```

## Quick Start

### Install Dependencies

```bash
# Install dev dependencies (includes pytest, pytest-playwright)
pip install -e ".[dev,dashboard]"

# Install Playwright browsers (first time only)
playwright install chromium
```

### Run Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run E2E tests
pytest tests/e2e/ -m e2e

# Run E2E tests with visible browser
pytest tests/e2e/ -m e2e --headed

# Run specific test file
pytest tests/e2e/test_auth.py -m e2e

# Run with coverage
pytest --cov=dashboard --cov-report=html
```

## E2E Testing with Playwright

E2E tests use [Playwright for Python](https://playwright.dev/python/) to test the NiceGUI dashboard in a real browser.

### How It Works

1. **Dashboard Startup**: The `dashboard_process` fixture starts the dashboard on port 8082 (separate from dev port 8081)
2. **Browser Automation**: Playwright controls a Chromium browser to interact with the dashboard
3. **Page Objects**: `DashboardPage` and `LoginPage` provide high-level APIs for interactions
4. **Cleanup**: Dashboard process is terminated after tests complete

### Running E2E Tests

```bash
# Headless (CI mode)
pytest tests/e2e/ -m e2e

# With visible browser (debugging)
pytest tests/e2e/ -m e2e --headed

# Slow motion for debugging
pytest tests/e2e/ -m e2e --headed --slowmo=500

# Single test
pytest tests/e2e/test_auth.py::TestAuthenticationEnabled::test_successful_login_grants_access -m e2e --headed
```

### Test Markers

- `@pytest.mark.e2e` - End-to-end browser tests
- `@pytest.mark.integration` - Integration tests (external services)
- `@pytest.mark.slow` - Long-running tests

Exclude markers:
```bash
pytest -m "not e2e"        # Skip E2E tests
pytest -m "not slow"       # Skip slow tests
pytest -m "not integration" # Skip integration tests
```

## Page Object Pattern

Tests use the Page Object Model for maintainability:

```python
from tests.support.page_objects import DashboardPage

def test_example(dashboard_page):
    dashboard = DashboardPage(dashboard_page)
    dashboard.select_tab("Configuration")
    assert dashboard.is_config_readonly()
```

### Available Page Objects

**DashboardPage** - Main dashboard interactions:
- `goto()` - Navigate to dashboard
- `is_loaded()` - Check if dashboard loaded
- `select_tab(name)` - Switch tabs
- `get_pair_count()` - Count trading pairs
- `toggle_grid_overlay()` - Toggle chart grid
- `is_config_readonly()` - Check config read-only

**LoginPage** - Authentication flows:
- `goto()` - Navigate to login
- `login(password)` - Perform login
- `is_error_visible()` - Check error state
- `is_redirected_to_dashboard()` - Check login success

## Writing New E2E Tests

### Basic Test Structure

```python
import pytest
from playwright.sync_api import Page, expect
from tests.support.page_objects import DashboardPage

@pytest.mark.e2e
class TestMyFeature:
    def test_feature_works(self, dashboard_page: Page) -> None:
        """Test description mapping to story/AC."""
        dashboard = DashboardPage(dashboard_page)

        # Arrange
        dashboard.select_tab("Trade History")

        # Act
        # ... perform action

        # Assert
        expect(dashboard.trade_history).to_be_visible()
```

### Using Fixtures

```python
@pytest.mark.e2e
def test_with_auth(self, page: Page, auth_dashboard_url: str, dashboard_with_auth):
    """Test requiring auth-enabled dashboard."""
    # dashboard_with_auth ensures auth server is running
    page.goto(auth_dashboard_url)
    # ...
```

## CI Integration

E2E tests are designed to run in CI:

```yaml
# Example GitHub Actions
- name: Install Playwright
  run: playwright install chromium

- name: Run E2E Tests
  run: pytest tests/e2e/ -m e2e --junit-xml=test-results/e2e.xml

- name: Upload Screenshots
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: test-screenshots
    path: test-results/screenshots/
```

### Failure Artifacts

On test failure, screenshots are automatically saved to `test-results/screenshots/`.

## Test Coverage by Story

| Epic | Story | Test File | Status |
|------|-------|-----------|--------|
| 1 | 1.5 Main Entry Point | test_dashboard_load.py | ✅ |
| 3 | 3.1 Header Strip | test_dashboard_load.py | ✅ |
| 3 | 3.2 RAG Status | test_dashboard_load.py | ✅ |
| 5 | 5.1 Price Chart | test_dashboard_load.py | ✅ |
| 6 | 6.3 Stability | test_dashboard_load.py | ✅ |
| 8 | 8.3 Chart Toggle | test_dashboard_load.py | ✅ |
| 9 | 9.1 Trade History Tab | test_dashboard_load.py | ✅ |
| 10 | 10.1 Grid Overlay | test_dashboard_load.py | ✅ |
| 10 | 10.2 Configuration | test_dashboard_load.py | ✅ |
| 10 | 10.3 Authentication | test_auth.py | ✅ |

## Troubleshooting

### Dashboard Won't Start

```bash
# Check if port is in use
netstat -ano | findstr :8082

# Kill process if needed
taskkill /F /PID <pid>
```

### Tests Timeout

Increase timeout in conftest.py:
```python
DASHBOARD_STARTUP_TIMEOUT = 60  # seconds
```

### Can't Find Elements

1. Run with `--headed` to see what's happening
2. Check NiceGUI element classes in browser DevTools
3. Update page object selectors if UI changed

## References

- [Playwright Python Docs](https://playwright.dev/python/)
- [pytest-playwright](https://github.com/nicegui/pytest-playwright)
- [NiceGUI Testing](https://nicegui.io/documentation/testing)
- [Page Object Pattern](https://martinfowler.com/bliki/PageObject.html)
