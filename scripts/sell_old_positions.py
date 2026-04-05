"""Verkauft alte Positionen (AAVE, ANKR, FET) von der vorherigen Strategie."""

import asyncio
from decimal import Decimal

from crypto_bot.config.settings import get_settings
from crypto_bot.exchange.binance_adapter import BinanceAdapter
from crypto_bot.exchange.base_exchange import OrderType, OrderSide


async def sell_all():
    s = get_settings()
    ex = BinanceAdapter(s.exchange)
    await ex.connect()

    coins = ["AAVE", "ANKR", "FET"]
    for coin in coins:
        symbol = f"{coin}/USDT"
        bal = await ex.fetch_balance()
        amount = bal[coin].total if coin in bal else 0
        if amount <= 0:
            print(f"{coin}: keine Balance, uebersprungen")
            continue

        ticker = await ex.fetch_ticker(symbol)
        price = ticker.last
        value = float(amount) * float(price)
        print(f"{coin}: {amount} x ${float(price):.4f} = ${value:.2f}")

        if value < 1.0:
            print(f"  -> Dust (${value:.2f}), uebersprungen")
            continue

        try:
            order = await ex.create_order(symbol, OrderType.MARKET, OrderSide.SELL, Decimal(str(amount)))
            print(f"  -> VERKAUFT: Order {order.id}")
        except Exception as e:
            print(f"  -> FEHLER: {e}")

    bal = await ex.fetch_balance()
    usdt = bal.get("USDT")
    print(f"\nNeue USDT-Balance: {usdt.total if usdt else 'N/A'}")
    await ex.disconnect()


if __name__ == "__main__":
    asyncio.run(sell_all())
