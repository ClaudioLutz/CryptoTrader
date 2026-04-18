"""Einmaliger zeitgesteuerter Verkauf einer verwaisten Position.

Wartet bis zur Zielzeit und fuehrt dann einen Market Sell aus.
Laeuft in einem separaten Docker-Container, unabhaengig vom Bot.
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

# === KONFIGURATION ===
TARGET_TIME_UTC = datetime(2026, 4, 20, 19, 29, 10, tzinfo=timezone.utc)
SYMBOL = "BTC/USDT"
AMOUNT = Decimal("0.00106")  # Genau die Menge von Position #1
POSITION_INFO = "Pos #1 (BUY @ 77'250 vom 17.04. 19:29)"


async def main() -> int:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Scheduled Sell gestartet")
    print(f"  Target: {TARGET_TIME_UTC.isoformat()}")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Amount: {AMOUNT} BTC")
    print(f"  Info:   {POSITION_INFO}")

    # Sleep bis Ziel-Zeit
    while True:
        now = datetime.now(timezone.utc)
        if now >= TARGET_TIME_UTC:
            break
        remaining = TARGET_TIME_UTC - now
        hours_left = remaining.total_seconds() / 3600
        print(f"[{now.isoformat()}] Warte noch {hours_left:.2f}h...", flush=True)
        # Alle 10 Minuten status loggen, naeher zur Zielzeit genauer
        if remaining > timedelta(hours=1):
            await asyncio.sleep(600)  # 10 Min
        elif remaining > timedelta(minutes=5):
            await asyncio.sleep(60)  # 1 Min
        else:
            await asyncio.sleep(5)  # 5 Sek

    print(f"[{datetime.now(timezone.utc).isoformat()}] ZEIT ERREICHT — verkaufe jetzt")

    settings = get_settings()
    ex = BinanceAdapter(settings.exchange)
    await ex.connect()

    try:
        # Balance-Check vor dem Verkauf
        bal = await ex.fetch_balance()
        btc = bal.get("BTC")
        if not btc or btc.free < AMOUNT:
            print(
                f"FEHLER: Nicht genug BTC frei "
                f"(free={btc.free if btc else 0}, benoetigt={AMOUNT})"
            )
            return 1
        print(f"BTC-Balance vor Sell: {btc.total} (frei: {btc.free})")

        # Current price
        ticker = await ex.fetch_ticker(SYMBOL)
        print(f"Aktueller BTC-Preis: {ticker.last}")

        # Market Sell
        order = await ex.create_order(
            symbol=SYMBOL,
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            amount=AMOUNT,
        )
        print(f"SELL ORDER: id={order.id} status={order.status.value}")
        print(f"  Filled: {order.filled} @ avg {order.price}")
        print(f"  Cost:   {order.cost} USDT")

        # Entry war 77'250 * 0.00106 = 81.89 USDT
        entry_cost = Decimal("77250.01") * AMOUNT
        pnl = (order.cost or Decimal(0)) - entry_cost
        pnl_pct = pnl / entry_cost * 100 if entry_cost > 0 else 0
        print(f"  P&L:    {pnl:+.2f} USDT ({pnl_pct:+.2f}%)")

        # Telegram-Notification falls konfiguriert
        token = os.environ.get("TELEGRAM__BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM__CHAT_ID", "")
        if token and chat_id:
            import json
            import urllib.request

            msg = (
                f"🔔 *Pos #1 geschlossen (72h-Zeitbarriere)*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Entry: 77'250 USDT (17.04. 19:29)\n"
                f"Exit:  {order.price:,.2f} USDT (20.04. 19:29)\n"
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
        print(f"FEHLER beim Verkauf: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await ex.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
