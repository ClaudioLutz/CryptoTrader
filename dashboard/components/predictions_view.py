"""CryptoTrader Dashboard - Predictions View Component.

Zeigt ML-Vorhersagen aus dem coin_prediction-Projekt an und
ermoeglicht das Starten des Trainings direkt aus dem Dashboard.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from nicegui import ui

logger = logging.getLogger(__name__)

# Globaler State fuer Predictions
_prediction_state = {
    "results": {},  # coin -> PredictionResult
    "is_training": False,
    "last_train_time": None,  # datetime
    "last_train_duration": None,  # seconds
    "error": None,  # str
}


def _get_signal_label(confidence: float) -> tuple[str, str]:
    """Bestimmt Signal-Label und Farbe basierend auf Confidence.

    Returns:
        Tuple von (label, css_color).
    """
    if confidence >= 0.60:
        return "STARK", "#4caf50"
    elif confidence >= 0.55:
        return "MODERAT", "#ff9800"
    elif confidence >= 0.52:
        return "SCHWACH", "#f44336"
    else:
        return "NOISE", "#9e9e9e"


def _get_direction_display(direction: str) -> tuple[str, str, str]:
    """Bestimmt Anzeige fuer die Richtung.

    Returns:
        Tuple von (text, icon, css_color).
    """
    if direction == "up":
        return "Up", "trending_up", "#4caf50"
    else:
        return "Down", "trending_down", "#f44336"


async def _run_training(
    status_label: ui.label,
    train_button: ui.button,
    results_container: ui.column,
    spinner: ui.spinner,
) -> None:
    """Fuehrt die Prediction-Pipeline aus."""
    if _prediction_state["is_training"]:
        return

    _prediction_state["is_training"] = True
    _prediction_state["error"] = None
    train_button.disable()
    spinner.set_visibility(True)
    status_label.set_text("Training laeuft... (kann 5-15 Minuten dauern)")
    status_label.classes(replace="text-warning prediction-status")

    start_time = time.time()

    try:
        from crypto_bot.prediction.prediction_config import DEFAULT_PREDICTION_COINS
        from crypto_bot.prediction.prediction_pipeline import PredictionPipeline

        pipeline = PredictionPipeline(
            coin_prediction_path="C:/Codes/coin_prediction",
            coins=list(DEFAULT_PREDICTION_COINS),
            horizon_days=7,
        )

        results = await pipeline.run_full_pipeline()

        duration = time.time() - start_time
        _prediction_state["results"] = results
        _prediction_state["last_train_time"] = datetime.now(timezone.utc)
        _prediction_state["last_train_duration"] = duration

        status_label.set_text(
            f"Training abgeschlossen: {len(results)} Coins in {duration:.0f}s"
        )
        status_label.classes(replace="text-positive prediction-status")
        logger.info("Training completed: %d coins in %.0fs", len(results), duration)

        # Tabelle aktualisieren
        _refresh_results_table(results_container)

    except Exception as e:
        duration = time.time() - start_time
        _prediction_state["error"] = str(e)
        status_label.set_text(f"Training fehlgeschlagen: {e}")
        status_label.classes(replace="text-negative prediction-status")
        logger.exception("Training failed after %.0fs", duration)
    finally:
        _prediction_state["is_training"] = False
        train_button.enable()
        spinner.set_visibility(False)


def _refresh_results_table(container: ui.column) -> None:
    """Aktualisiert die Ergebnis-Tabelle mit den neuesten Predictions."""
    container.clear()
    results = _prediction_state["results"]

    if not results:
        with container:
            with ui.card().classes("w-full"):
                ui.label("Keine Predictions vorhanden. Training starten um Vorhersagen zu generieren.").classes(
                    "text-secondary p-4"
                )
        return

    # Sortiere nach Confidence absteigend
    sorted_results = sorted(results.values(), key=lambda r: r.confidence, reverse=True)

    # Zusammenfassung
    up_count = sum(1 for r in sorted_results if r.direction == "up")
    down_count = sum(1 for r in sorted_results if r.direction == "down")
    strong_count = sum(1 for r in sorted_results if r.confidence >= 0.55)

    with container:
        # Summary Cards
        with ui.row().classes("w-full gap-4 mb-4"):
            with ui.card().classes("prediction-summary-card"):
                ui.label(str(len(sorted_results))).classes("text-h4 text-primary")
                ui.label("Coins analysiert").classes("text-caption text-secondary")

            with ui.card().classes("prediction-summary-card"):
                ui.label(str(up_count)).classes("text-h4 text-positive")
                ui.label("Up-Signale").classes("text-caption text-secondary")

            with ui.card().classes("prediction-summary-card"):
                ui.label(str(down_count)).classes("text-h4 text-negative")
                ui.label("Down-Signale").classes("text-caption text-secondary")

            with ui.card().classes("prediction-summary-card"):
                ui.label(str(strong_count)).classes("text-h4 text-warning")
                ui.label("Handelbar (>55%)").classes("text-caption text-secondary")

        # Tabelle
        columns = [
            {"name": "coin", "label": "Coin", "field": "coin", "align": "left", "sortable": True},
            {"name": "direction", "label": "Richtung", "field": "direction", "align": "center", "sortable": True},
            {"name": "probability", "label": "Wahrsch.", "field": "probability", "align": "center", "sortable": True},
            {"name": "confidence", "label": "Confidence", "field": "confidence", "align": "center", "sortable": True},
            {"name": "signal", "label": "Signal", "field": "signal", "align": "center", "sortable": True},
            {"name": "date", "label": "Daten bis", "field": "date", "align": "center"},
        ]

        rows = []
        for r in sorted_results:
            signal_label, signal_color = _get_signal_label(r.confidence)
            dir_text, _, dir_color = _get_direction_display(r.direction)
            rows.append({
                "coin": r.coin,
                "direction": dir_text,
                "probability": f"{r.probability:.1%}",
                "confidence": f"{r.confidence:.1%}",
                "signal": signal_label,
                "date": r.features_date,
            })

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="coin",
        ).classes("predictions-table w-full")

        # Custom cell styling via slots
        table.add_slot(
            "body-cell-direction",
            """
            <q-td :props="props">
                <q-badge :color="props.value === 'Up' ? 'positive' : 'negative'">
                    {{ props.value }}
                </q-badge>
            </q-td>
            """,
        )

        table.add_slot(
            "body-cell-signal",
            """
            <q-td :props="props">
                <q-badge
                    :color="props.value === 'STARK' ? 'positive' :
                            props.value === 'MODERAT' ? 'warning' :
                            props.value === 'SCHWACH' ? 'negative' : 'grey'"
                >
                    {{ props.value }}
                </q-badge>
            </q-td>
            """,
        )


async def _fetch_open_positions() -> list[dict]:
    """Holt offene Positionen und aktuelle Preise vom Exchange."""
    positions = []
    try:
        from crypto_bot.config.settings import get_settings
        from crypto_bot.exchange.binance_adapter import BinanceAdapter

        settings = get_settings()
        exchange = BinanceAdapter(settings.exchange)
        await exchange.connect()

        balances = await exchange.fetch_balance()
        now = datetime.now(timezone.utc)

        # Alle Coins mit Guthaben > 0 (ausser USDT)
        for currency, bal in sorted(balances.items()):
            if currency == "USDT" or bal.total <= 0:
                continue
            try:
                ticker = await exchange.fetch_ticker(f"{currency}/USDT")
                price = float(ticker.last)
                amount = float(bal.total)
                value = price * amount

                if value < 1.0:  # Dust ignorieren
                    continue

                # Trade-Historie fuer Avg-Preis
                trades = await exchange.fetch_my_trades(f"{currency}/USDT", limit=50)
                total_buy_amt = 0.0
                total_buy_cost = 0.0
                for t in trades:
                    if t.side.value == "buy":
                        total_buy_amt += float(t.amount)
                        total_buy_cost += float(t.cost)

                avg_buy = total_buy_cost / total_buy_amt if total_buy_amt > 0 else price
                cost = avg_buy * amount
                pnl = value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0

                positions.append({
                    "coin": currency,
                    "amount": f"{amount:.4f}",
                    "avg_price": f"${avg_buy:.4f}",
                    "current_price": f"${price:.4f}",
                    "value": f"${value:.2f}",
                    "pnl": pnl,
                    "pnl_display": f"${pnl:+.2f} ({pnl_pct:+.1f}%)",
                    "pnl_color": "positive" if pnl >= 0 else "negative",
                })
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", currency, e)

        await exchange.disconnect()
    except Exception as e:
        logger.exception("Failed to fetch positions: %s", e)

    return positions


def _create_positions_section(container: ui.column) -> None:
    """Erstellt die Sektion fuer offene Positionen (initial leer)."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2"):
            ui.spinner("dots", size="sm")
            ui.label("Positionen werden geladen...").classes("text-secondary")


async def _refresh_positions(container: ui.column) -> None:
    """Aktualisiert die offene-Positionen-Anzeige."""
    positions = await _fetch_open_positions()
    container.clear()

    with container:
        if not positions:
            ui.label("Keine offenen Positionen").classes("text-secondary")
            return

        # P/L Zusammenfassung
        total_value = sum(float(p["value"].replace("$", "")) for p in positions)
        total_pnl = sum(p["pnl"] for p in positions)

        with ui.row().classes("w-full gap-4 mb-4"):
            with ui.card().classes("prediction-summary-card"):
                ui.label(f"${total_value:.2f}").classes("text-h4 text-primary")
                ui.label("Gesamtwert").classes("text-caption text-secondary")

            pnl_color = "text-positive" if total_pnl >= 0 else "text-negative"
            with ui.card().classes("prediction-summary-card"):
                ui.label(f"${total_pnl:+.2f}").classes(f"text-h4 {pnl_color}")
                ui.label("Unrealized P/L").classes("text-caption text-secondary")

            with ui.card().classes("prediction-summary-card"):
                ui.label(str(len(positions))).classes("text-h4 text-primary")
                ui.label("Offene Positionen").classes("text-caption text-secondary")

        # Positions-Tabelle
        columns = [
            {"name": "coin", "label": "Coin", "field": "coin", "align": "left", "sortable": True},
            {"name": "amount", "label": "Menge", "field": "amount", "align": "right"},
            {"name": "avg_price", "label": "Avg. Einkauf", "field": "avg_price", "align": "right"},
            {"name": "current_price", "label": "Aktuell", "field": "current_price", "align": "right"},
            {"name": "value", "label": "Wert", "field": "value", "align": "right"},
            {"name": "pnl_display", "label": "P/L", "field": "pnl_display", "align": "right", "sortable": True},
        ]

        rows = [{k: v for k, v in p.items() if k != "pnl" and k != "pnl_color"} for p in positions]

        table = ui.table(columns=columns, rows=rows, row_key="coin").classes(
            "positions-table w-full"
        )

        table.add_slot(
            "body-cell-pnl_display",
            """
            <q-td :props="props">
                <span :style="props.value.startsWith('+') ? 'color: #4caf50' : 'color: #f44336'">
                    {{ props.value }}
                </span>
            </q-td>
            """,
        )


def create_predictions_view() -> None:
    """Erstellt den Predictions-Tab mit Positionen, Training und Ergebnissen."""
    with ui.column().classes("predictions-view gap-4 w-full p-4"):
        # =====================================================================
        # Sektion 1: Offene Positionen
        # =====================================================================
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("account_balance_wallet", size="24px").classes("text-secondary")
            ui.label("Offene Positionen").classes("text-h6 text-primary")

        positions_container = ui.column().classes("w-full mb-6 open-positions")
        _create_positions_section(positions_container)

        # Refresh-Button
        refresh_btn = ui.button("Aktualisieren", icon="refresh", color="secondary").classes(
            "mb-6"
        )
        refresh_btn.on_click(lambda: _refresh_positions(positions_container))

        # Auto-Refresh beim Laden
        ui.timer(0.5, lambda: _refresh_positions(positions_container), once=True)

        ui.separator().classes("mb-4")

        # =====================================================================
        # Sektion 2: Predictions Training
        # =====================================================================
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("psychology", size="24px").classes("text-secondary")
            ui.label("7-Tage Predictions").classes("text-h6 text-primary")

        # Info-Card
        with ui.card().classes("w-full mb-4"):
            with ui.column().classes("gap-2 p-2"):
                ui.label(
                    "Trainiert ein LightGBM-Modell auf historischen Daten und erstellt "
                    "7-Tage-Vorhersagen (Up/Down) fuer 20 Kryptowaehrungen."
                ).classes("text-secondary")

        # Training Controls
        with ui.row().classes("items-center gap-4 mb-4"):
            train_button = ui.button(
                "Training starten",
                icon="play_arrow",
                color="primary",
            ).classes("prediction-train-btn")

            spinner = ui.spinner("dots", size="lg", color="primary")
            spinner.set_visibility(False)

            status_label = ui.label("Bereit").classes("text-secondary prediction-status")

        # Last training info
        if _prediction_state["last_train_time"]:
            t = _prediction_state["last_train_time"]
            d = _prediction_state["last_train_duration"]
            ui.label(
                f"Letztes Training: {t.strftime('%Y-%m-%d %H:%M UTC')} ({d:.0f}s)"
            ).classes("text-caption text-secondary")

        # Results container
        results_container = ui.column().classes("w-full prediction-results")

        # Bestehende Ergebnisse anzeigen
        _refresh_results_table(results_container)

        # Button-Handler
        train_button.on_click(
            lambda: _run_training(status_label, train_button, results_container, spinner)
        )

    # CSS fuer Predictions
    ui.add_css("""
        .predictions-view {
            max-width: 1200px;
            margin: 0 auto;
        }
        .prediction-summary-card {
            flex: 1;
            min-width: 120px;
            text-align: center;
            padding: 16px;
        }
        .predictions-table {
            background: var(--bg-secondary, #1e1e1e) !important;
        }
        .predictions-table .q-table__top,
        .predictions-table .q-table__bottom,
        .predictions-table thead tr th {
            color: var(--text-secondary, #aaa);
        }
        .predictions-table tbody tr td {
            color: var(--text-primary, #fff);
        }
        .positions-table {
            background: var(--bg-secondary, #1e1e1e) !important;
        }
        .positions-table thead tr th {
            color: var(--text-secondary, #aaa);
        }
        .positions-table tbody tr td {
            color: var(--text-primary, #fff);
        }
    """)
