"""CryptoTrader Dashboard - Performance View.

Zeigt Trading-Performance:
- Equity-Kurve (kumulativer P&L)
- Win/Loss Statistiken
- Geschlossene Positionen (History)
"""

import logging
from datetime import datetime, timezone

import plotly.graph_objects as go
from nicegui import ui

from dashboard.state import state

logger = logging.getLogger(__name__)


def create_performance_view() -> None:
    """Erstellt den Performance Tab."""
    with ui.column().classes("performance-view gap-4 w-full p-4"):
        # Sektion 1: Statistiken
        stats_container = ui.column().classes("w-full")
        _create_stats_section(stats_container)

        ui.separator().classes("my-2")

        # Sektion 2: Equity-Kurve
        equity_container = ui.column().classes("w-full")
        _create_equity_chart(equity_container)

        ui.separator().classes("my-2")

        # Sektion 3: Geschlossene Positionen
        closed_container = ui.column().classes("w-full")
        _create_closed_positions(closed_container)

    # Auto-Refresh alle 30s
    async def refresh_all() -> None:
        _create_stats_section(stats_container)
        _create_equity_chart(equity_container)
        _create_closed_positions(closed_container)

    ui.timer(30.0, refresh_all)

    _add_performance_css()


def _create_stats_section(container: ui.column) -> None:
    """Trading-Statistiken aus geschlossenen Positionen."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("analytics", size="24px").classes("text-primary")
            ui.label("Trading-Statistiken").classes("text-h6 text-primary")

        closed = state.closed_positions

        if not closed:
            ui.label("Noch keine geschlossenen Trades.").classes("text-secondary p-4")
            return

        # Berechne Stats
        total_trades = len(closed)
        wins = [p for p in closed if p.get("pnl") and float(p["pnl"]) > 0]
        losses = [p for p in closed if p.get("pnl") and float(p["pnl"]) <= 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / total_trades * 100 if total_trades > 0 else 0

        total_pnl = sum(float(p.get("pnl", 0)) for p in closed if p.get("pnl"))
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        avg_win = (
            sum(float(p["pnl"]) for p in wins) / win_count
            if win_count > 0 else 0
        )
        avg_loss = (
            sum(float(p["pnl"]) for p in losses) / loss_count
            if loss_count > 0 else 0
        )
        best_trade = max((float(p.get("pnl", 0)) for p in closed), default=0)
        worst_trade = min((float(p.get("pnl", 0)) for p in closed), default=0)

        # Reason-Breakdown
        by_reason = {}
        for p in closed:
            reason = p.get("close_reason", "unknown")
            by_reason.setdefault(reason, 0)
            by_reason[reason] += 1

        with ui.row().classes("w-full gap-4 mb-4 flex-wrap"):
            with ui.card().classes("perf-card"):
                ui.label(str(total_trades)).classes("text-h4 text-primary")
                ui.label("Total Trades").classes("text-caption text-secondary")

            pnl_color = "text-positive" if total_pnl >= 0 else "text-negative"
            with ui.card().classes("perf-card"):
                ui.label(f"${total_pnl:+.2f}").classes(f"text-h4 {pnl_color}")
                ui.label("Gesamt P&L").classes("text-caption text-secondary")

            wr_color = "text-positive" if win_rate >= 55 else "text-warning" if win_rate >= 50 else "text-negative"
            with ui.card().classes("perf-card"):
                ui.label(f"{win_rate:.1f}%").classes(f"text-h4 {wr_color}")
                ui.label(f"Win-Rate ({win_count}W / {loss_count}L)").classes("text-caption text-secondary")

            avg_color = "text-positive" if avg_pnl >= 0 else "text-negative"
            with ui.card().classes("perf-card"):
                ui.label(f"${avg_pnl:+.2f}").classes(f"text-h4 {avg_color}")
                ui.label("Avg P&L / Trade").classes("text-caption text-secondary")

        with ui.row().classes("w-full gap-4 mb-4 flex-wrap"):
            with ui.card().classes("perf-card"):
                ui.label(f"${avg_win:+.2f}").classes("text-h5 text-positive")
                ui.label("Avg Gewinn").classes("text-caption text-secondary")

            with ui.card().classes("perf-card"):
                ui.label(f"${avg_loss:+.2f}").classes("text-h5 text-negative")
                ui.label("Avg Verlust").classes("text-caption text-secondary")

            with ui.card().classes("perf-card"):
                ui.label(f"${best_trade:+.2f}").classes("text-h5 text-positive")
                ui.label("Bester Trade").classes("text-caption text-secondary")

            with ui.card().classes("perf-card"):
                ui.label(f"${worst_trade:+.2f}").classes("text-h5 text-negative")
                ui.label("Schlechtester Trade").classes("text-caption text-secondary")

        # Close-Reason Breakdown
        if by_reason:
            with ui.row().classes("gap-4 flex-wrap"):
                for reason, count in sorted(by_reason.items()):
                    reason_label = {
                        "time": "Zeitablauf",
                        "stop_loss": "Stop-Loss",
                        "take_profit": "Take-Profit",
                    }.get(reason, reason)
                    with ui.card().classes("perf-card-sm"):
                        ui.label(str(count)).classes("text-h5")
                        ui.label(reason_label).classes("text-caption text-secondary")


def _create_equity_chart(container: ui.column) -> None:
    """Equity-Kurve: kumulativer P&L ueber Zeit."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("show_chart", size="24px").classes("text-primary")
            ui.label("Equity-Kurve").classes("text-h6 text-primary")

        closed = state.closed_positions

        if not closed:
            ui.label("Noch keine geschlossenen Trades fuer Equity-Kurve.").classes(
                "text-secondary p-4"
            )
            return

        # Sortiere nach close_at (bzw. opened_at als Fallback)
        sorted_pos = sorted(
            closed,
            key=lambda p: p.get("close_at", p.get("opened_at", "")),
        )

        # Kumulative P&L berechnen
        timestamps = []
        cumulative_pnl = []
        running = 0.0

        for pos in sorted_pos:
            pnl = float(pos.get("pnl", 0)) if pos.get("pnl") else 0
            running += pnl
            ts = pos.get("close_at", pos.get("opened_at", ""))
            try:
                dt = datetime.fromisoformat(ts)
                timestamps.append(dt)
            except (ValueError, TypeError):
                timestamps.append(ts)
            cumulative_pnl.append(running)

        # Chart
        fig = go.Figure()

        # Farbverlauf: gruen wenn positiv, rot wenn negativ
        colors = ["#4caf50" if p >= 0 else "#f44336" for p in cumulative_pnl]

        fig.add_trace(go.Scatter(
            x=timestamps,
            y=cumulative_pnl,
            mode="lines+markers",
            name="Kumulativer P&L",
            line=dict(width=2),
            marker=dict(color=colors, size=6),
            fill="tozeroy",
            fillcolor="rgba(76, 175, 80, 0.1)",
        ))

        # Nulllinie
        fig.add_hline(y=0, line_dash="dash", line_color="#9e9e9e", line_width=1)

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
            height=350,
            margin=dict(l=50, r=20, t=10, b=30),
            yaxis=dict(title="Kumulativer P&L ($)", gridcolor="#0f3460"),
            xaxis=dict(gridcolor="#0f3460"),
            hovermode="x unified",
            showlegend=False,
        )

        plotly_chart = ui.plotly(fig).classes("w-full")
        plotly_chart._props["config"] = {
            "scrollZoom": True,
            "doubleClick": "reset",
            "displayModeBar": False,
            "responsive": True,
        }


def _create_closed_positions(container: ui.column) -> None:
    """Tabelle der geschlossenen Positionen."""
    container.clear()
    with container:
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("history", size="24px").classes("text-primary")
            ui.label("Geschlossene Positionen").classes("text-h6 text-primary")

        closed = state.closed_positions

        if not closed:
            ui.label("Noch keine geschlossenen Positionen.").classes("text-secondary p-4")
            return

        columns = [
            {"name": "coin", "label": "Coin", "field": "coin", "align": "left"},
            {"name": "opened", "label": "Geoeffnet", "field": "opened", "align": "center", "sortable": True},
            {"name": "closed", "label": "Geschlossen", "field": "closed", "align": "center", "sortable": True},
            {"name": "entry_price", "label": "Entry", "field": "entry_price", "align": "right"},
            {"name": "close_price", "label": "Exit", "field": "close_price", "align": "right"},
            {"name": "cost", "label": "Kosten", "field": "cost", "align": "right"},
            {"name": "pnl", "label": "P&L", "field": "pnl", "align": "right", "sortable": True},
            {"name": "reason", "label": "Grund", "field": "reason", "align": "center"},
        ]

        rows = []
        # Neueste zuerst
        for pos in reversed(closed):
            opened = pos.get("opened_at", "")
            close_at = pos.get("close_at", "")
            try:
                opened_str = datetime.fromisoformat(opened).strftime("%d.%m. %H:%M")
            except (ValueError, TypeError):
                opened_str = opened[:16]
            try:
                closed_str = datetime.fromisoformat(close_at).strftime("%d.%m. %H:%M")
            except (ValueError, TypeError):
                closed_str = close_at[:16]

            pnl = float(pos.get("pnl", 0)) if pos.get("pnl") else 0
            reason = pos.get("close_reason", "?")
            reason_label = {
                "time": "Zeit",
                "stop_loss": "SL",
                "take_profit": "TP",
            }.get(reason, reason)

            rows.append({
                "coin": pos.get("coin", "?"),
                "opened": opened_str,
                "closed": closed_str,
                "entry_price": f"${float(pos.get('entry_price', 0)):,.2f}",
                "close_price": f"${float(pos.get('close_price', 0)):,.2f}" if pos.get("close_price") else "-",
                "cost": f"${float(pos.get('cost', 0)):.2f}",
                "pnl": f"${pnl:+.2f}",
                "reason": reason_label,
            })

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="opened",
            pagination=20,
        ).classes("perf-table w-full")
        table.props("flat bordered dense dark")

        # P&L Farbe
        table.add_slot(
            "body-cell-pnl",
            """
            <q-td :props="props">
                <span :style="props.value.includes('-') ? 'color: #f44336; font-weight: 600' : 'color: #4caf50; font-weight: 600'">
                    {{ props.value }}
                </span>
            </q-td>
            """,
        )

        # Reason Badge
        table.add_slot(
            "body-cell-reason",
            """
            <q-td :props="props">
                <q-badge
                    :color="props.value === 'TP' ? 'positive' :
                            props.value === 'SL' ? 'negative' : 'grey'"
                >
                    {{ props.value }}
                </q-badge>
            </q-td>
            """,
        )


def _add_performance_css() -> None:
    ui.add_css("""
        .performance-view {
            max-width: 1400px;
            margin: 0 auto;
        }
        .perf-card {
            flex: 1;
            min-width: 140px;
            text-align: center;
            padding: 12px 16px;
            background: rgba(26, 26, 46, 0.6) !important;
            border: 1px solid #0f3460;
        }
        .perf-card-sm {
            min-width: 100px;
            text-align: center;
            padding: 8px 12px;
            background: rgba(26, 26, 46, 0.6) !important;
            border: 1px solid #0f3460;
        }
        .perf-table {
            background: var(--bg-secondary, #1e1e1e) !important;
        }
        .perf-table thead tr th {
            color: var(--text-secondary, #aaa);
        }
        .perf-table tbody tr td {
            color: var(--text-primary, #fff);
        }
    """)
