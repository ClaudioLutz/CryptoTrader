"""Kontostand und P/L Bericht."""
import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from decimal import Decimal
from crypto_bot.config.settings import get_settings
from crypto_bot.exchange.binance_adapter import BinanceAdapter


async def check():
    settings = get_settings()
    exchange = BinanceAdapter(settings.exchange)
    await exchange.connect()

    balances = await exchange.fetch_balance()

    total_usd = Decimal(0)
    print("KONTOSTAND")
    print("=" * 70)
    header = f"  {'Asset':<8} {'Frei':>12} {'Gesperrt':>12} {'Total':>12} {'USD-Wert':>12}"
    print(header)
    print("  " + "-" * 66)

    for currency, bal in sorted(balances.items()):
        if bal.total > 0:
            if currency == "USDT":
                usd_value = bal.total
            else:
                try:
                    ticker = await exchange.fetch_ticker(f"{currency}/USDT")
                    usd_value = bal.total * ticker.last
                except Exception:
                    usd_value = Decimal(0)

            locked = bal.total - bal.free
            total_usd += usd_value
            print(
                f"  {currency:<8} {float(bal.free):>12.4f} {float(locked):>12.4f}"
                f" {float(bal.total):>12.4f} ${float(usd_value):>10.2f}"
            )

    print("  " + "-" * 66)
    print(f"  {'GESAMT':<8} {'':>12} {'':>12} {'':>12} ${float(total_usd):>10.2f}")

    # Trade-Historie
    print()
    print("P/L PRO ASSET")
    print("=" * 70)
    for symbol in ["SOL/USDT", "TRX/USDT"]:
        try:
            trades = await exchange.fetch_my_trades(symbol, limit=50)
            if not trades:
                continue

            total_buy_amt = Decimal(0)
            total_sell_amt = Decimal(0)
            total_buy_cost = Decimal(0)
            total_sell_cost = Decimal(0)
            total_fees = Decimal(0)

            for t in trades:
                fee = t.fee if t.fee else Decimal(0)
                total_fees += fee
                if t.side.value == "buy":
                    total_buy_amt += t.amount
                    total_buy_cost += t.cost
                else:
                    total_sell_amt += t.amount
                    total_sell_cost += t.cost

            ticker = await exchange.fetch_ticker(symbol)
            price = ticker.last
            holding = total_buy_amt - total_sell_amt
            holding_value = holding * price

            avg_buy = total_buy_cost / total_buy_amt if total_buy_amt > 0 else Decimal(0)

            if total_sell_amt > 0 and total_buy_amt > 0:
                cost_of_sold = avg_buy * total_sell_amt
                realized = total_sell_cost - cost_of_sold - total_fees
            else:
                realized = Decimal(0) - total_fees

            if holding > 0:
                cost_of_holding = avg_buy * holding
                unrealized = holding_value - cost_of_holding
            else:
                unrealized = Decimal(0)

            total_pl = realized + unrealized
            coin = symbol.split("/")[0]

            print(f"  {symbol}:")
            print(f"    Kaeufe:       {float(total_buy_amt):>10.4f} {coin} fuer ${float(total_buy_cost):>10.2f}  (Avg: ${float(avg_buy):.2f})")
            print(f"    Verkaeufe:    {float(total_sell_amt):>10.4f} {coin} fuer ${float(total_sell_cost):>10.2f}")
            print(f"    Holding:      {float(holding):>10.4f} {coin}       ${float(holding_value):>10.2f}  (Preis: ${float(price):.2f})")
            print(f"    Fees:                              ${float(total_fees):>10.4f}")
            print(f"    Realized P/L:                      ${float(realized):>10.2f}")
            print(f"    Unrealized P/L:                    ${float(unrealized):>10.2f}")
            print(f"    Total P/L:                         ${float(total_pl):>10.2f}")
            print()
        except Exception as e:
            print(f"  {symbol}: Fehler - {e}")

    await exchange.disconnect()


asyncio.run(check())
