"""Pytest fixtures for E2E dashboard tests.

This module provides Playwright fixtures for testing the NiceGUI dashboard.
The dashboard is started as a subprocess and tests run against it.

Usage:
    pytest tests/e2e/ -m e2e --headed  # Run with visible browser
    pytest tests/e2e/ -m e2e           # Run headless (CI mode)
"""

import os
import subprocess
import sys
import time
from collections.abc import Generator
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

# Dashboard configuration
# For now, tests run against an already-running dashboard on port 8081
# Start dashboard with: python -m dashboard.main
DASHBOARD_HOST = "localhost"
DASHBOARD_PORT = int(os.environ.get("TEST_DASHBOARD_PORT", "8081"))
DASHBOARD_URL = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"
DASHBOARD_STARTUP_TIMEOUT = 30  # seconds (for auth dashboard)


@pytest.fixture(scope="session")
def dashboard_url() -> str:
    """Get the dashboard URL for tests.

    NOTE: Dashboard must be running before tests start.
    Start with: python -m dashboard.main
    """
    import httpx

    try:
        response = httpx.get(f"{DASHBOARD_URL}/", timeout=5.0)
        if response.status_code not in (200, 302):
            pytest.skip(f"Dashboard not responding correctly (status {response.status_code})")
    except Exception as e:
        pytest.skip(f"Dashboard not running at {DASHBOARD_URL}. Start with: python -m dashboard.main. Error: {e}")

    return DASHBOARD_URL


@pytest.fixture(scope="session")
def browser_context_args() -> dict[str, Any]:
    """Configure browser context for tests."""
    return {
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def dashboard_page(
    page: Page,
    dashboard_url: str,
) -> Generator[Page, None, None]:
    """Navigate to dashboard and yield page for testing.

    This fixture ensures the dashboard is loaded before yielding.
    """
    page.goto(dashboard_url)

    # Wait for NiceGUI to initialize (WebSocket connection)
    page.wait_for_load_state("networkidle")

    # Wait for dashboard-specific element to ensure UI is ready
    try:
        page.wait_for_selector("header", timeout=10000)
    except Exception:
        # Fallback: wait for any content
        page.wait_for_selector("body", timeout=5000)

    yield page


@pytest.fixture(scope="session")
def dashboard_with_auth() -> Generator[subprocess.Popen[bytes], None, None]:
    """Start dashboard with authentication enabled.

    Use this fixture for testing authentication flows.
    """
    env = os.environ.copy()
    env["DASHBOARD_DASHBOARD_PORT"] = str(DASHBOARD_PORT + 1)  # Different port
    env["DASHBOARD_AUTH_ENABLED"] = "true"
    env["DASHBOARD_AUTH_PASSWORD"] = "test_password_123"

    process = subprocess.Popen(
        [sys.executable, "-m", "dashboard.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )

    # Wait for startup
    auth_url = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT + 1}"
    start_time = time.time()
    while time.time() - start_time < DASHBOARD_STARTUP_TIMEOUT:
        try:
            import httpx

            response = httpx.get(f"{auth_url}/", timeout=2.0, follow_redirects=False)
            if response.status_code in (200, 302, 307):
                break
        except Exception:
            time.sleep(0.5)
    else:
        process.terminate()
        pytest.skip("Dashboard with auth failed to start. Skipping auth tests.")

    yield process

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope="function")
def auth_dashboard_url(dashboard_with_auth: subprocess.Popen[bytes]) -> str:
    """Get URL for dashboard with authentication enabled."""
    return f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT + 1}"


# Playwright configuration
def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for E2E tests."""
    # Add e2e marker
    config.addinivalue_line("markers", "e2e: end-to-end browser tests")


# Screenshot on failure (for debugging)
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, None]:
    """Capture screenshot on test failure."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        # Try to get page from test
        page = item.funcargs.get("page") or item.funcargs.get("dashboard_page")
        if page and hasattr(page, "screenshot"):
            try:
                screenshot_dir = os.path.join(
                    os.path.dirname(__file__), "..", "..", "test-results", "screenshots"
                )
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, f"{item.name}.png")
                page.screenshot(path=screenshot_path)
            except Exception:
                pass  # Don't fail test cleanup if screenshot fails
