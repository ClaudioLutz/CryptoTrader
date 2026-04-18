"""Zeitgesteuerter Verkauf von Position #2.

Pos #2: BUY 0.00177 BTC @ 75'806.01 am 18.04.2026 18:12 UTC.
Schliesst automatisch nach 72h am 21.04.2026 18:12 UTC.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, "/app/src")

from crypto_bot.config.settings import get_settings
from crypto_bot.exchange.base_exchange import OrderSide, OrderType
from crypto_bot.exchange.binance_adapter import BinanceAdapter

TARGET_TIME_UTC = datetime(2026, 4, 21, 18, 12, 8, tzinfo=timezone.utc)
SYMBOL = "BTC/USDT"
AMOUNT = Decimal("0.00177")
ENTRY_PRICE = Decimal("75806.01")
POSITION_INFO = "Pos #2 (BUY @ 75'806 vom 18.04. 18:12)"


async def main() -> int:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Scheduled Sell Pos #2 gestartet")
    print(f"  Target: {TARGET_TIME_UTC.isoformat()}")
    print(f"  Info:   {POSITION_INFO}")

    while True:
        now = datetime.now(timezone.utc)
        if now >= TARGET_TIME_UTC:
            break
        remaining = TARGET_TIME_UTC - now
        hours_left = remaining.total_seconds() / 3600
        print(f"[{now.isoformat()}] Warte noch {hours_left:.2f}h...", flush=True)
        if remaining > timedelta(hours=1):
            await asyncio.sleep(600)
        elif remaining > timedelta(minutes=5):
            await asyncio.sleep(60)
        else:
            await asyncio.sleep(5)

    print(f"[{datetime.now(timezone.utc).isoformat()}] ZEIT ERREICHT — verkaufe Pos #2")

    settings = get_settings()
    ex = BinanceAdapter(settings.exchange)
    await ex.connect()

    try:
        bal = await ex.fetch_balance()
        btc = bal.get("BTC")
        if not btc or btc.free < AMOUNT:
            print(f"FEHLER: Nicht genug BTC frei (free={btc.free if btc else 0})")
            return 1
        print(f"BTC-Balance vor Sell: {btc.total} (frei: {btc.free})")

        ticker = await ex.fetch_ticker(SYMBOL)
        print(f"Aktueller BTC-Preis: {ticker.last}")

        order = await ex.create_order(
            symbol=SYMBOL,
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            amount=AMOUNT,
        )
        print(f"SELL ORDER: id={order.id} status={order.status.value}")

        entry_cost = ENTRY_PRICE * AMOUNT
        pnl = (order.cost or Decimal(0)) - entry_cost
        pnl_pct = pnl / entry_cost * 100 if entry_cost > 0 else 0
        print(f"  P&L: {pnl:+.2f} USDT ({pnl_pct:+.2f}%)")

        token = os.environ.get("TELEGRAM__BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM__CHAT_ID", "")
        if token and chat_id:
            import json
            import urllib.request

            msg = (
                f"🔔 *Pos #2 geschlossen (72h-Zeitbarriere)*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Entry: 75'806 USDT (18.04. 18:12)\n"
                f"Exit:  {order.price:,.2f} USDT (21.04. 18:12)\n"
                f"Menge: {AMOUNT} BTC\n"
                f"{'📈' if pnl >= 0 else '📉'} P&L: {pnl:+.2f} USDT ({pnl_pct:+.2f}%)"
            )
            data = json.dumps(
                {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
            ).encode("utf-8")
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(req).read()
                print("Telegram-Nachricht gesendet.")
            except Exception as e:
                print(f"Telegram-Fehler: {e}")

        return 0

    except Exception as e:
        print(f"FEHLER: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await ex.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
