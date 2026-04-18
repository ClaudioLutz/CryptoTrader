"""Sendet Predictions-Summary mit Chart an Telegram.

Liest die letzten N Stunden Predictions aus den Log-Files,
generiert einen Chart mit BTC-Preis + Predictions + Trade-Markers
und sendet ihn zusammen mit einer Text-Summary an den Telegram-Bot.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

sys.path.insert(0, "/app/src")

from crypto_bot.config.settings import get_settings
from crypto_bot.exchange.binance_adapter import BinanceAdapter

WINDOW_HOURS = 72
LOG_DIR = Path("/app/logs")
CHART_PATH = "/tmp/chart.png"

TELEGRAM_TOKEN = os.environ["TELEGRAM__BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM__CHAT_ID"]


def load_predictions(hours: int) -> list[dict]:
    """Laedt Predictions aus Log-Files der letzten N Stunden."""
    preds = []
    for path in sorted(LOG_DIR.glob("crypto_bot.log*")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
                    if d.get("event") == "coin_predicted_1h":
                        preds.append(d)
        except FileNotFoundError:
            continue

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = [
        p for p in preds
        if datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")) >= cutoff
    ]
    recent.sort(key=lambda p: p["timestamp"])
    return recent


def load_trades() -> list[dict]:
    """Liest Trade-Events (Position opened) aus Log-Files."""
    trades = []
    for path in sorted(LOG_DIR.glob("crypto_bot.log*")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
                    if d.get("event") == "prediction_position_opened":
                        trades.append(d)
        except FileNotFoundError:
            continue
    return trades


async def fetch_btc_ohlcv(limit: int):
    """Holt BTC/USDT 1h-Kerzen von Binance."""
    settings = get_settings()
    ex = BinanceAdapter(settings.exchange)
    await ex.connect()
    try:
        return await ex.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=limit)
    finally:
        await ex.disconnect()


def generate_chart(
    ohlcv: list,
    predictions: list[dict],
    trades: list[dict],
    current_price: float,
) -> None:
    """Generiert den Chart und speichert ihn nach CHART_PATH."""
    fig, ax1 = plt.subplots(figsize=(14, 7), facecolor="white")

    # === BTC Price (linke Achse) ===
    times = [c.timestamp for c in ohlcv]
    closes = [float(c.close) for c in ohlcv]
    ax1.plot(
        times, closes,
        color="#F7931A", linewidth=2.8, label="BTC/USDT Preis",
        zorder=2,
    )
    ax1.set_ylabel("BTC Preis (USDT)", color="#F7931A", fontsize=12, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor="#F7931A")
    ax1.grid(True, alpha=0.25, zorder=1)

    # Entry-Preis-Linie (falls Trade existiert)
    now = datetime.now(timezone.utc)
    entry_times = []
    for t in trades:
        t_time = datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00"))
        # Nur Trades im Chart-Zeitraum markieren
        if t_time >= times[0] and t_time <= times[-1]:
            entry_times.append(t_time)
            entry_price = float(t.get("price", 0))
            # Horizontale Linie: Entry-Preis
            ax1.axhline(
                y=entry_price, color="#2563eb", linestyle=":",
                linewidth=1.8, alpha=0.7, zorder=1,
                label=f"Entry-Preis ({entry_price:,.0f} USDT)",
            )
            # Vertikale Linie: Entry-Zeitpunkt
            ax1.axvline(
                x=t_time, color="#2563eb", linestyle="-",
                linewidth=2.5, alpha=0.9, zorder=3,
            )
            # Trade-Marker Dreieck
            ax1.scatter(
                t_time, entry_price,
                marker="^", s=300, c="#2563eb", edgecolors="white",
                linewidths=2, zorder=5, label="BUY",
            )

    # Aktueller Preis als Horizontal-Linie
    ax1.axhline(
        y=current_price, color="#10b981", linestyle="--",
        linewidth=1.2, alpha=0.5, zorder=1,
    )

    # === Predictions (rechte Achse) ===
    ax2 = ax1.twinx()
    ups_t, ups_c = [], []
    downs_t, downs_c = [], []
    for p in predictions:
        t = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
        c = p["confidence"]
        if p["direction"] == "up":
            ups_t.append(t)
            ups_c.append(c)
        else:
            downs_t.append(t)
            downs_c.append(c)

    # Grössere Punkte: 0.50 -> 20, 1.00 -> 400
    def size(c):
        return 20 + (c - 0.5) * 760

    if ups_t:
        ax2.scatter(
            ups_t, ups_c,
            c="#22c55e", s=[size(c) for c in ups_c],
            alpha=0.75, edgecolors="#14532d", linewidths=1.2,
            zorder=4, label="UP Prediction",
        )
    if downs_t:
        ax2.scatter(
            downs_t, downs_c,
            c="#ef4444", s=[size(c) for c in downs_c],
            alpha=0.75, edgecolors="#7f1d1d", linewidths=1.2,
            zorder=4, label="DOWN Prediction",
        )

    # Threshold-Linie
    ax2.axhline(
        y=0.65, color="#6b7280", linestyle="--",
        linewidth=1.5, alpha=0.7, zorder=1,
        label="Trade-Schwelle (0.65)",
    )
    ax2.set_ylabel("Prediction Confidence", color="#374151", fontsize=12, fontweight="bold")
    ax2.set_ylim(0.48, 1.02)
    ax2.tick_params(axis="y", labelcolor="#374151")

    # === Jetzt-Linie ===
    ax1.axvline(
        x=now, color="#9ca3af", linestyle="-",
        linewidth=1.2, alpha=0.6, zorder=1,
    )

    # === Formatierung ===
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M", tz=timezone.utc))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=8))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Titel
    pnl_str = ""
    if entry_times:
        entry_price = float(trades[-1].get("price", 0))
        if entry_price > 0:
            pnl_pct = (current_price - entry_price) / entry_price * 100
            pnl_str = f"  |  P&L: {pnl_pct:+.2f}%"

    title = (
        f"BTC/USDT {WINDOW_HOURS}h  -  {len(predictions)} Predictions"
        f"  |  Now: {current_price:,.0f} USDT{pnl_str}"
    )
    plt.title(title, fontsize=13, fontweight="bold", pad=12)

    # Legende kombiniert
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2, labels1 + labels2,
        loc="upper left", fontsize=9, framealpha=0.92,
    )

    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close()


def send_photo_with_caption(chart_path: str, caption: str) -> None:
    """Sendet Chart + Caption via sendPhoto. Caption wird als UTF-8 multipart gesendet."""
    import mimetypes
    import uuid

    boundary = uuid.uuid4().hex
    body_parts = []

    def add_field(name: str, value: str) -> None:
        body_parts.append(f"--{boundary}".encode("utf-8"))
        body_parts.append(
            f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
        )
        body_parts.append(b"Content-Type: text/plain; charset=utf-8")
        body_parts.append(b"")
        body_parts.append(value.encode("utf-8"))

    def add_file(name: str, filename: str, data: bytes, content_type: str) -> None:
        body_parts.append(f"--{boundary}".encode("utf-8"))
        body_parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode(
                "utf-8"
            )
        )
        body_parts.append(f"Content-Type: {content_type}".encode("utf-8"))
        body_parts.append(b"")
        body_parts.append(data)

    add_field("chat_id", TELEGRAM_CHAT_ID)
    add_field("caption", caption)
    add_field("parse_mode", "Markdown")

    with open(chart_path, "rb") as f:
        photo_bytes = f.read()
    add_file("photo", "chart.png", photo_bytes, "image/png")

    body_parts.append(f"--{boundary}--".encode("utf-8"))
    body_parts.append(b"")
    body = b"\r\n".join(body_parts)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        print(f"Fehler: {result}")
    else:
        print("Chart+Caption gesendet.")


def main() -> int:
    predictions = load_predictions(WINDOW_HOURS)
    if not predictions:
        print("Keine Predictions gefunden.")
        return 1

    ups = [p for p in predictions if p["direction"] == "up"]
    downs = [p for p in predictions if p["direction"] == "down"]
    confs = [p["confidence"] for p in predictions]
    strong = [p for p in predictions if p["confidence"] >= 0.65]
    last = predictions[-1]

    trades = load_trades()

    # BTC-Daten (72h + 1 zur Sicherheit)
    ohlcv = asyncio.run(fetch_btc_ohlcv(limit=WINDOW_HOURS + 1))
    current_price = float(ohlcv[-1].close)

    # Nur OHLCV im Zeitraum behalten
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    ohlcv = [c for c in ohlcv if c.timestamp >= cutoff_time]

    generate_chart(ohlcv, predictions, trades, current_price)

    # Text-Summary
    up_pct = len(ups) / len(predictions) * 100 if predictions else 0
    caption = (
        f"📊 *BTC {WINDOW_HOURS}h Predictions Summary*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Total: {len(predictions)} Predictions\n"
        f"🟢 UP: {len(ups)} ({up_pct:.0f}%)\n"
        f"🔴 DOWN: {len(downs)} ({100-up_pct:.0f}%)\n"
        f"🎯 Avg Confidence: {sum(confs)/len(confs):.1%}\n"
        f"🔥 Max: {max(confs):.1%}\n"
        f"💪 Strong (≥65%): {len(strong)} von {len(predictions)}\n"
        f"\n"
        f"📍 Letzte: *{last['direction'].upper()}* @ {last['confidence']:.1%}\n"
        f"💰 BTC jetzt: *{current_price:,.0f} USDT*"
    )

    # Trade-Info anhaengen falls vorhanden
    if trades:
        last_trade = trades[-1]
        entry_price = float(last_trade.get("price", 0))
        entry_time = datetime.fromisoformat(
            last_trade["timestamp"].replace("Z", "+00:00")
        )
        pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price else 0
        pnl_emoji = "📈" if pnl_pct >= 0 else "📉"
        caption += (
            f"\n\n"
            f"🎲 *Offene Position*\n"
            f"BUY @ {entry_price:,.0f} USDT\n"
            f"Eröffnet: {entry_time.strftime('%d.%m. %H:%M UTC')}\n"
            f"{pnl_emoji} P&L: {pnl_pct:+.2f}%"
        )

    send_photo_with_caption(CHART_PATH, caption)
    return 0


if __name__ == "__main__":
    sys.exit(main())
