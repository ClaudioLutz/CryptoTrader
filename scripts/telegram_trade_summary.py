"""Sendet vollstaendige Trade-Zusammenfassung via Telegram.

Holt alle BTC-Trades seit 17.04.2026 von Binance, berechnet aktuelle P&L
basierend auf dem Live-Preis und sendet eine formatierte Markdown-Nachricht.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/src")

from crypto_bot.config.settings import get_settings
from crypto_bot.exchange.binance_adapter import BinanceAdapter


async def main() -> int:
    settings = get_settings()
    ex = BinanceAdapter(settings.exchange)
    await ex.connect()

    try:
        bal = await ex.fetch_balance()
        btc_bal = bal.get("BTC")
        usdt_bal = bal.get("USDT")
        btc_total = float(btc_bal.total) if btc_bal else 0
        usdt_total = float(usdt_bal.total) if usdt_bal else 0

        ticker = await ex.fetch_ticker("BTC/USDT")
        price = float(ticker.last)

        trades = await ex.fetch_my_trades("BTC/USDT", limit=30)
        cutoff = datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc)
        trades = [t for t in trades if t.timestamp >= cutoff]

        positions = []
        for t in trades:
            if t.side.value != "buy":
                continue
            entry = float(t.price)
            amt = float(t.amount)
            cost = float(t.cost)
            cur_val = amt * price
            pnl = cur_val - cost
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
            close_at = t.timestamp + timedelta(hours=72)
            positions.append({
                "time": t.timestamp,
                "amount": amt,
                "entry": entry,
                "cost": cost,
                "cur_val": cur_val,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "close_at": close_at,
            })
    finally:
        await ex.disconnect()

    total_cost = sum(p["cost"] for p in positions)
    total_val = sum(p["cur_val"] for p in positions)
    total_pnl = total_val - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost > 0 else 0

    mgmt_map = {
        0: "Scheduled Sell",
        1: "Scheduled Sell",
        2: "Bot (72h-Zeitbarriere)",
    }

    lines = [
        "📋 *Trade-Zusammenfassung*",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 BTC aktuell: *{price:,.0f} USDT*",
        "",
    ]
    for i, p in enumerate(positions):
        emoji = "📈" if p["pnl"] >= 0 else "📉"
        mgmt = mgmt_map.get(i, "Bot (72h-Zeitbarriere)")
        lines += [
            f"*Pos #{i+1}*  {emoji}",
            f"  Entry: {p['entry']:,.0f} USDT",
            f"  Menge: {p['amount']:.6f} BTC",
            f"  Cost: {p['cost']:.2f} USDT",
            f"  P&L: {p['pnl']:+.2f} USDT ({p['pnl_pct']:+.2f}%)",
            f"  Open: {p['time'].strftime('%d.%m. %H:%M')} UTC",
            f"  Close: {p['close_at'].strftime('%d.%m. %H:%M')} UTC",
            f"  via: {mgmt}",
            "",
        ]
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    lines += [
        "━━━━━━━━━━━━━━━━━━",
        f"📊 *Gesamt ({len(positions)} Positionen)*",
        f"Cost: {total_cost:.2f} USDT",
        f"Value: {total_val:.2f} USDT",
        f"{pnl_emoji} P&L: {total_pnl:+.2f} USDT ({total_pnl_pct:+.2f}%)",
        "",
        f"💵 Cash: {usdt_total:.2f} USDT",
        f"📦 Portfolio: {total_val + usdt_total:.2f} USDT",
    ]
    msg = "\n".join(lines)

    token = os.environ["TELEGRAM__BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM__CHAT_ID"]
    body = json.dumps(
        {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    print("Gesendet:", result.get("ok"))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
