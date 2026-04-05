"""CryptoTrader Dashboard - BTC Prediction View.

Hauptview fuer die BTC 1h Prediction-Strategie:
- Model-Status (Retraining-Info, aktuelle Prediction)
- BTC-Preis-Chart mit Confidence-Overlay und Trade-Markern
- Offene Positionen mit Live-P&L
- Prediction-Timeline (stuendliche History)
"""

import logging
from datetime import datetime, timezone

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from nicegui import ui

from dashboard.state import state

logger = logging.getLogger(__name__)


def create_predictions_view() -> None:
    """Erstellt den BTC Prediction Tab."""
    with ui.column().classes("predictions-view gap-4 w-full p-4"):
        # Sektion 1: Model-Status + aktuelle Prediction
        model_container = ui.column().classes("w-full")
        _create_model_status(model_container)

        ui.separator().classes("my-2")

        # Sektion 2: BTC-Preis-Chart mit Confidence
        chart_container = ui.column().classes("w-full")
        _create_price_chart(chart_container)

        ui.separator().classes("my-2")

        # Sektion 3: Offene Positionen
        positions_container = ui.column().classes("w-full")
        _create_positions_section(positions_container)

        ui.separator().classes("my-2")

        # Sektion 4: Prediction-Timeline
        timeline_container = ui.column().classes("w-full")
        _create_prediction_timeline(timeline_container)

    # Auto-Refresh alle 30s
    async def refresh_all() -> None:
        _create_model_status(model_container)
        _create_price_chart(chart_container)
        _create_positions_section(positions_container)
        _create_prediction_timeline(timeline_container)

    ui.timer(30.0, refresh_all)

    _add_predictions_css()


def _create_model_status(container: ui.column) -> None:
    """Model-Status Cards: Aktuelle Prediction, Retraining-Info, Config."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("psychology", size="24px").classes("text-primary")
            ui.label("BTC Prediction — Model-Status").classes("text-h6 text-primary")

        pred = state.current_prediction
        info = state.model_info

        with ui.row().classes("w-full gap-4 mb-4 flex-wrap"):
            # Card 1: Aktuelle Prediction
            with ui.card().classes("pred-card"):
                ui.label("Aktuelle Prediction").classes("text-caption text-secondary")
                if pred:
                    direction = pred.get("direction", "?")
                    confidence = pred.get("confidence", 0)
                    min_conf = info.get("min_confidence", 0.65) if info else 0.65

                    if direction == "up":
                        arrow = "\u25b2 UP"
                        color = "#4caf50" if confidence >= min_conf else "#9e9e9e"
                    else:
                        arrow = "\u25bc DOWN"
                        color = "#f44336"

                    ui.label(arrow).style(
                        f"color: {color}; font-weight: 700; font-size: 1.4em"
                    )
                    ui.label(f"Confidence: {confidence:.1%}").classes("text-body2")

                    tradeable = confidence >= min_conf and direction == "up"
                    badge_color = "positive" if tradeable else "grey"
                    badge_text = "HANDELBAR" if tradeable else f"< {min_conf:.0%} Schwelle"
                    ui.badge(badge_text, color=badge_color).classes("mt-1")
                else:
                    ui.label("--").classes("text-h5 text-secondary")
                    ui.label("Kein Modell geladen").classes("text-caption")

            # Card 2: Letztes Retraining
            with ui.card().classes("pred-card"):
                ui.label("Letztes Retraining").classes("text-caption text-secondary")
                if info and info.get("last_retrain_time"):
                    try:
                        rt = datetime.fromisoformat(info["last_retrain_time"])
                        elapsed = (datetime.now(timezone.utc) - rt).total_seconds()
                        elapsed_min = int(elapsed / 60)
                        ui.label(rt.strftime("%H:%M UTC")).classes("text-h5")
                        ui.label(f"vor {elapsed_min} Min.").classes("text-caption")
                    except (ValueError, TypeError):
                        ui.label("--").classes("text-h5 text-secondary")

                    duration = info.get("last_retrain_duration")
                    if duration:
                        ui.label(f"Dauer: {duration:.0f}s").classes("text-caption text-secondary")

                    if info.get("is_retraining"):
                        ui.badge("TRAINING LAEUFT", color="warning").classes("mt-1")
                else:
                    ui.label("--").classes("text-h5 text-secondary")
                    ui.label("Noch kein Training").classes("text-caption")

            # Card 3: Naechstes Retraining
            with ui.card().classes("pred-card"):
                ui.label("Naechstes Retraining").classes("text-caption text-secondary")
                if info and info.get("last_retrain_time") and info.get("retrain_interval_hours"):
                    try:
                        rt = datetime.fromisoformat(info["last_retrain_time"])
                        interval_h = info["retrain_interval_hours"]
                        from datetime import timedelta
                        next_rt = rt + timedelta(hours=interval_h)
                        remaining = (next_rt - datetime.now(timezone.utc)).total_seconds()
                        remaining_min = max(0, int(remaining / 60))
                        ui.label(f"in {remaining_min} Min.").classes("text-h5")
                        ui.label(f"Intervall: {interval_h}h").classes("text-caption text-secondary")
                    except (ValueError, TypeError):
                        ui.label("--").classes("text-h5 text-secondary")
                else:
                    ui.label("--").classes("text-h5 text-secondary")

            # Card 4: Config
            with ui.card().classes("pred-card"):
                ui.label("Strategie").classes("text-caption text-secondary")
                if info:
                    coins = ", ".join(info.get("coins", []))
                    tf = info.get("timeframe", "?")
                    horizon = info.get("prediction_horizon_hours", "?")
                    window = info.get("train_window_hours", "?")
                    ui.label(f"{coins} — {tf}").classes("text-body1 font-bold")
                    ui.label(f"Horizont: {horizon}h").classes("text-caption")
                    ui.label(f"Trainings-Fenster: {window}h").classes("text-caption text-secondary")
                else:
                    ui.label("--").classes("text-h5 text-secondary")


def _create_price_chart(container: ui.column) -> None:
    """BTC-Preis-Chart mit Confidence-Overlay und Trade-Markern."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("candlestick_chart", size="24px").classes("text-primary")
            ui.label("BTC/USDT — Preis & Confidence").classes("text-h6 text-primary")

        history = state.prediction_history
        ohlcv = state.ohlcv_by_symbol.get("BTC/USDT", [])

        if not history and not ohlcv:
            ui.label("Keine Daten vorhanden. Warte auf erstes Retraining...").classes(
                "text-secondary p-4"
            )
            # Trigger OHLCV laden
            async def load_ohlcv() -> None:
                await state.refresh_ohlcv("BTC/USDT", "1h", 168)
                _create_price_chart(container)
            ui.timer(0.5, load_ohlcv, once=True)
            return

        # Chart bauen mit Plotly (2 Y-Achsen: Preis + Confidence)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=("BTC/USDT (1h)", "Confidence"),
        )

        # OHLCV als Candlestick
        if ohlcv:
            timestamps = [c.get("timestamp", "") for c in ohlcv]
            fig.add_trace(
                go.Candlestick(
                    x=timestamps,
                    open=[c["open"] for c in ohlcv],
                    high=[c["high"] for c in ohlcv],
                    low=[c["low"] for c in ohlcv],
                    close=[c["close"] for c in ohlcv],
                    name="BTC/USDT",
                    increasing=dict(line=dict(color="#00c853"), fillcolor="#00c853"),
                    decreasing=dict(line=dict(color="#ff5252"), fillcolor="#ff5252"),
                ),
                row=1, col=1,
            )

        # Confidence als Linie (aus Prediction History)
        if history:
            hist_ts = [h["timestamp"] for h in history]
            hist_conf = [h["confidence"] for h in history]
            hist_dir = [h["direction"] for h in history]

            # Farbe pro Punkt: gruen wenn up, rot wenn down
            colors = ["#4caf50" if d == "up" else "#f44336" for d in hist_dir]

            fig.add_trace(
                go.Scatter(
                    x=hist_ts,
                    y=hist_conf,
                    mode="lines+markers",
                    name="Confidence",
                    line=dict(color="#2196f3", width=2),
                    marker=dict(color=colors, size=5),
                ),
                row=2, col=1,
            )

            # Min-Confidence Schwelle als horizontale Linie
            min_conf = 0.65
            if state.model_info:
                min_conf = state.model_info.get("min_confidence", 0.65)

            fig.add_hline(
                y=min_conf, line_dash="dash", line_color="#ff9800",
                annotation_text=f"Min. {min_conf:.0%}",
                annotation_position="bottom right",
                row=2, col=1,
            )

        # Trade-Marker auf dem Preischart (nur BTC-Positionen)
        open_positions = [p for p in state.open_positions if p.get("coin") == "BTC"]
        closed_positions = [p for p in state.closed_positions if p.get("coin") == "BTC"]

        # Entries (gruen)
        entry_ts = []
        entry_prices = []
        entry_texts = []
        for pos in open_positions + closed_positions:
            entry_ts.append(pos.get("opened_at", ""))
            entry_prices.append(float(pos.get("entry_price", 0)))
            conf = pos.get("confidence", 0)
            entry_texts.append(f"BUY {conf:.0%}")

        if entry_ts:
            fig.add_trace(
                go.Scatter(
                    x=entry_ts, y=entry_prices,
                    mode="markers",
                    name="Entry",
                    marker=dict(
                        symbol="triangle-up", size=12, color="#4caf50",
                        line=dict(width=1, color="white"),
                    ),
                    text=entry_texts, hoverinfo="text+x+y",
                ),
                row=1, col=1,
            )

        # Exits (rot)
        exit_ts = []
        exit_prices = []
        exit_texts = []
        for pos in closed_positions:
            if pos.get("close_price"):
                # close_at als Exit-Zeitpunkt
                exit_ts.append(pos.get("close_at", pos.get("opened_at", "")))
                exit_prices.append(float(pos["close_price"]))
                pnl = float(pos.get("pnl", 0))
                reason = pos.get("close_reason", "?")
                exit_texts.append(f"SELL ({reason}) P&L: ${pnl:+.2f}")

        if exit_ts:
            fig.add_trace(
                go.Scatter(
                    x=exit_ts, y=exit_prices,
                    mode="markers",
                    name="Exit",
                    marker=dict(
                        symbol="triangle-down", size=12, color="#f44336",
                        line=dict(width=1, color="white"),
                    ),
                    text=exit_texts, hoverinfo="text+x+y",
                ),
                row=1, col=1,
            )

        # SL/TP Linien fuer offene Positionen
        for pos in open_positions:
            sl = pos.get("stop_loss_price")
            tp = pos.get("take_profit_price")
            opened = pos.get("opened_at", "")
            close_at = pos.get("close_at", "")

            if sl and opened and close_at:
                fig.add_shape(
                    type="line", x0=opened, x1=close_at,
                    y0=float(sl), y1=float(sl),
                    line=dict(color="#f44336", width=1, dash="dot"),
                    row=1, col=1,
                )
            if tp and opened and close_at:
                fig.add_shape(
                    type="line", x0=opened, x1=close_at,
                    y0=float(tp), y1=float(tp),
                    line=dict(color="#4caf50", width=1, dash="dot"),
                    row=1, col=1,
                )

        # Y-Achse auf tatsaechlichen Preisbereich skalieren (mit 2% Padding)
        y_range = None
        if ohlcv:
            all_lows = [c["low"] for c in ohlcv]
            all_highs = [c["high"] for c in ohlcv]
            price_min = min(all_lows)
            price_max = max(all_highs)
            padding = (price_max - price_min) * 0.15  # 15% Padding
            if padding < price_max * 0.01:  # Mindestens 1% des Preises
                padding = price_max * 0.01
            y_range = [price_min - padding, price_max + padding]

        # Layout
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
            height=600,
            margin=dict(l=60, r=20, t=40, b=30),
            hovermode="x unified",
            showlegend=True,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1, font=dict(size=10),
            ),
            xaxis2=dict(gridcolor="#0f3460"),
            yaxis=dict(
                title="Preis ($)", gridcolor="#0f3460",
                range=y_range,
                tickformat=",.0f",
            ),
            yaxis2=dict(title="Confidence", gridcolor="#0f3460", range=[0.4, 1.0]),
        )
        fig.update_xaxes(rangeslider_visible=False)

        plotly_chart = ui.plotly(fig).classes("w-full")
        plotly_chart._props["config"] = {
            "scrollZoom": True,
            "doubleClick": "reset",
            "displayModeBar": False,
            "responsive": True,
        }

        # Refresh-Button
        async def refresh_chart() -> None:
            await state.refresh_ohlcv("BTC/USDT", "1h", 168)
            _create_price_chart(container)

        ui.button("Chart aktualisieren", icon="refresh", color="secondary").props(
            "flat dense"
        ).classes("mt-2").on_click(refresh_chart)


def _create_positions_section(container: ui.column) -> None:
    """Zeigt offene Positionen mit Live-P&L."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("account_balance_wallet", size="24px").classes("text-primary")
            ui.label("Offene Positionen").classes("text-h6 text-primary")

        positions = state.open_positions

        if not positions:
            ui.label("Keine offenen Positionen").classes("text-secondary p-4")
            return

        # Summary
        total_cost = sum(float(p.get("cost", 0)) for p in positions)

        with ui.row().classes("gap-4 mb-3"):
            with ui.card().classes("pred-card"):
                ui.label(str(len(positions))).classes("text-h4 text-primary")
                ui.label("Positionen").classes("text-caption text-secondary")

            with ui.card().classes("pred-card"):
                ui.label(f"${total_cost:.2f}").classes("text-h4 text-primary")
                ui.label("Exposure").classes("text-caption text-secondary")

        # Tabelle
        columns = [
            {"name": "coin", "label": "Coin", "field": "coin", "align": "left"},
            {"name": "entry_price", "label": "Entry", "field": "entry_price", "align": "right"},
            {"name": "amount", "label": "Menge", "field": "amount", "align": "right"},
            {"name": "cost", "label": "Kosten", "field": "cost", "align": "right"},
            {"name": "sl_tp", "label": "SL / TP", "field": "sl_tp", "align": "center"},
            {"name": "close_at", "label": "Schliesst", "field": "close_at", "align": "center"},
            {"name": "status", "label": "Status", "field": "status", "align": "center"},
        ]

        rows = []
        for pos in positions:
            sl = pos.get("stop_loss_price")
            tp = pos.get("take_profit_price")
            sl_str = f"${float(sl):,.0f}" if sl else "-"
            tp_str = f"${float(tp):,.0f}" if tp else "-"

            close_at = pos.get("close_at", "")
            if close_at:
                try:
                    close_dt = datetime.fromisoformat(close_at)
                    remaining = (close_dt - datetime.now(timezone.utc)).total_seconds()
                    remaining_h = max(0, remaining / 3600)
                    close_str = f"{remaining_h:.0f}h"
                except (ValueError, TypeError):
                    close_str = close_at[:16]
            else:
                close_str = "-"

            rows.append({
                "coin": pos.get("coin", "?"),
                "entry_price": f"${float(pos.get('entry_price', 0)):,.2f}",
                "amount": f"{float(pos.get('amount', 0)):.6f}",
                "cost": f"${float(pos.get('cost', 0)):.2f}",
                "sl_tp": f"{sl_str} / {tp_str}",
                "close_at": close_str,
                "status": pos.get("status", "?").upper(),
            })

        table = ui.table(columns=columns, rows=rows, row_key="coin").classes(
            "pred-table w-full"
        )
        table.props("flat bordered dense dark")


def _create_prediction_timeline(container: ui.column) -> None:
    """Prediction-Timeline: stuendliche History aller Predictions."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("timeline", size="24px").classes("text-primary")
            ui.label("Prediction-Timeline").classes("text-h6 text-primary")

        history = state.prediction_history

        if not history:
            ui.label("Keine Prediction-History vorhanden. Warte auf Retraining...").classes(
                "text-secondary p-4"
            )
            return

        # Nur die letzten 48 Eintraege anzeigen (2 Tage)
        recent = history[-48:]
        recent.reverse()  # Neueste zuerst

        # Summary
        up_count = sum(1 for h in recent if h.get("direction") == "up")
        down_count = len(recent) - up_count
        avg_conf = sum(h.get("confidence", 0) for h in recent) / len(recent) if recent else 0
        min_conf = state.model_info.get("min_confidence", 0.65) if state.model_info else 0.65
        tradeable_count = sum(
            1 for h in recent
            if h.get("direction") == "up" and h.get("confidence", 0) >= min_conf
        )

        with ui.row().classes("gap-4 mb-3 flex-wrap"):
            with ui.card().classes("pred-card"):
                ui.label(str(len(recent))).classes("text-h5 text-primary")
                ui.label("Predictions (48h)").classes("text-caption text-secondary")

            with ui.card().classes("pred-card"):
                ui.label(f"{up_count} / {down_count}").classes("text-h5")
                ui.label("Up / Down").classes("text-caption text-secondary")

            with ui.card().classes("pred-card"):
                ui.label(f"{avg_conf:.1%}").classes("text-h5")
                ui.label("Avg Confidence").classes("text-caption text-secondary")

            with ui.card().classes("pred-card"):
                ui.label(str(tradeable_count)).classes("text-h5 text-positive")
                ui.label(f"Handelbar (>={min_conf:.0%})").classes("text-caption text-secondary")

        # Timeline-Tabelle
        columns = [
            {"name": "time", "label": "Zeitpunkt", "field": "time", "align": "left", "sortable": True},
            {"name": "direction", "label": "Richtung", "field": "direction", "align": "center"},
            {"name": "probability", "label": "Wahrsch.", "field": "probability", "align": "center"},
            {"name": "confidence", "label": "Confidence", "field": "confidence", "align": "center", "sortable": True},
            {"name": "tradeable", "label": "Handelbar", "field": "tradeable", "align": "center"},
        ]

        rows = []
        for h in recent:
            ts = h.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                time_str = dt.strftime("%d.%m. %H:%M")
            except (ValueError, TypeError):
                time_str = ts[:16]

            direction = h.get("direction", "?")
            confidence = h.get("confidence", 0)
            probability = h.get("probability", 0)
            is_tradeable = direction == "up" and confidence >= min_conf

            rows.append({
                "time": time_str,
                "direction": "\u25b2 Up" if direction == "up" else "\u25bc Down",
                "probability": f"{probability:.1%}",
                "confidence": f"{confidence:.1%}",
                "tradeable": "\u2713" if is_tradeable else "-",
            })

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="time",
            pagination=24,
        ).classes("pred-table w-full")
        table.props("flat bordered dense dark")

        # Styling fuer Richtung und Handelbar
        table.add_slot(
            "body-cell-direction",
            """
            <q-td :props="props">
                <span :style="props.value.includes('Up') ? 'color: #4caf50; font-weight: 600' : 'color: #f44336; font-weight: 600'">
                    {{ props.value }}
                </span>
            </q-td>
            """,
        )

        table.add_slot(
            "body-cell-tradeable",
            """
            <q-td :props="props">
                <span :style="props.value === '\u2713' ? 'color: #4caf50; font-weight: 700; font-size: 1.2em' : 'color: #9e9e9e'">
                    {{ props.value }}
                </span>
            </q-td>
            """,
        )

        table.add_slot(
            "body-cell-confidence",
            """
            <q-td :props="props">
                <span :style="parseFloat(props.value) >= 65 ? 'color: #4caf50; font-weight: 600' : 'color: #9e9e9e'">
                    {{ props.value }}
                </span>
            </q-td>
            """,
        )


def _add_predictions_css() -> None:
    """CSS fuer die Predictions-View."""
    ui.add_css("""
        .predictions-view {
            max-width: 1400px;
            margin: 0 auto;
        }
        .pred-card {
            flex: 1;
            min-width: 140px;
            text-align: center;
            padding: 12px 16px;
            background: rgba(26, 26, 46, 0.6) !important;
            border: 1px solid #0f3460;
        }
        .pred-table {
            background: var(--bg-secondary, #1e1e1e) !important;
        }
        .pred-table thead tr th {
            color: var(--text-secondary, #aaa);
        }
        .pred-table tbody tr td {
            color: var(--text-primary, #fff);
        }
    """)
