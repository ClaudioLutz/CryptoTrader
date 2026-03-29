"""E2E-Tests fuer den Predictions-Tab im Dashboard.

Testet alle Features: Tab-Navigation, Training-Button, Ergebnis-Tabelle,
Signal-Badges, Summary-Cards.

Run: pytest tests/e2e/test_predictions_tab.py -v
"""

import pytest
from playwright.sync_api import Page, expect


DASHBOARD_URL = "http://localhost:8081"


@pytest.fixture(scope="function")
def page(browser):
    """Create a fresh page for each test."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
    )
    page = context.new_page()
    page.goto(DASHBOARD_URL)
    page.wait_for_load_state("networkidle")
    # Warten bis NiceGUI geladen ist
    page.wait_for_selector("header", timeout=15000)
    yield page
    context.close()


class TestDashboardBasics:
    """Grundlegende Dashboard-Tests."""

    def test_dashboard_loads(self, page: Page) -> None:
        """Dashboard laed erfolgreich."""
        expect(page).to_have_title("CryptoTrader Dashboard")

    def test_header_visible(self, page: Page) -> None:
        """Header-Strip ist sichtbar."""
        header = page.locator("header")
        expect(header).to_be_visible()

    def test_all_tabs_present(self, page: Page) -> None:
        """Alle 4 Tabs sind vorhanden."""
        for tab_name in ["Dashboard", "Predictions", "Trade History", "Configuration"]:
            tab = page.locator(".q-tab__label").filter(has_text=tab_name)
            expect(tab).to_be_visible()


class TestPredictionsTab:
    """Tests fuer den Predictions-Tab."""

    def _navigate_to_predictions(self, page: Page) -> None:
        """Navigiert zum Predictions-Tab."""
        page.locator(".q-tab__label").filter(has_text="Predictions").click()
        page.wait_for_timeout(1000)

    def test_predictions_tab_navigation(self, page: Page) -> None:
        """Predictions-Tab kann angeklickt werden."""
        self._navigate_to_predictions(page)
        predictions_view = page.locator(".predictions-view")
        expect(predictions_view).to_be_visible()

    def test_predictions_header_visible(self, page: Page) -> None:
        """Header '7-Tage Predictions' ist sichtbar."""
        self._navigate_to_predictions(page)
        header = page.locator("text=7-Tage Predictions")
        expect(header).to_be_visible()

    def test_info_card_visible(self, page: Page) -> None:
        """Info-Card mit Beschreibung ist sichtbar."""
        self._navigate_to_predictions(page)
        info = page.locator("text=LightGBM")
        expect(info).to_be_visible()

    def test_train_button_visible(self, page: Page) -> None:
        """Training-Button ist sichtbar und klickbar."""
        self._navigate_to_predictions(page)
        button = page.locator(".prediction-train-btn")
        expect(button).to_be_visible()
        expect(button).to_be_enabled()

    def test_initial_status_bereit(self, page: Page) -> None:
        """Status zeigt 'Bereit' vor dem Training."""
        self._navigate_to_predictions(page)
        status = page.locator(".prediction-status")
        expect(status).to_contain_text("Bereit")

    def test_no_results_message(self, page: Page) -> None:
        """Ohne Training wird eine Info-Meldung angezeigt."""
        self._navigate_to_predictions(page)
        msg = page.locator("text=Keine Predictions vorhanden")
        expect(msg).to_be_visible()

    def test_train_button_clickable(self, page: Page) -> None:
        """Training-Button ist klickbar und loest eine Aktion aus."""
        self._navigate_to_predictions(page)
        button = page.locator(".prediction-train-btn")
        expect(button).to_be_enabled()

        # Status vor Klick merken
        status = page.locator(".prediction-status")
        initial_text = status.inner_text()

        button.click()
        page.wait_for_timeout(5000)

        # Nach Klick: entweder Status hat sich geaendert ODER
        # es laeuft schon ein Training (Button deaktiviert) ODER
        # es gibt Ergebnisse
        final_text = page.locator(".prediction-status").inner_text()
        has_results = page.locator(".predictions-table").count() > 0
        button_disabled = not button.is_enabled()

        assert (
            final_text != initial_text or has_results or button_disabled
        ), "Training-Button sollte eine sichtbare Aenderung ausloesen"


class TestTabNavigation:
    """Tests fuer Tab-Wechsel."""

    def test_switch_between_all_tabs(self, page: Page) -> None:
        """Alle Tabs koennen gewechselt werden."""
        for tab_name in ["Predictions", "Trade History", "Configuration", "Dashboard"]:
            page.locator(".q-tab__label").filter(has_text=tab_name).click()
            page.wait_for_timeout(500)

    def test_predictions_tab_persists_after_switch(self, page: Page) -> None:
        """Predictions-Tab behalt Zustand nach Tab-Wechsel."""
        # Zu Predictions
        page.locator(".q-tab__label").filter(has_text="Predictions").click()
        page.wait_for_timeout(500)
        expect(page.locator(".predictions-view")).to_be_visible()

        # Zu Dashboard und zurueck
        page.locator(".q-tab__label").filter(has_text="Dashboard").click()
        page.wait_for_timeout(500)
        page.locator(".q-tab__label").filter(has_text="Predictions").click()
        page.wait_for_timeout(500)

        # Predictions-View sollte noch da sein
        expect(page.locator(".predictions-view")).to_be_visible()
