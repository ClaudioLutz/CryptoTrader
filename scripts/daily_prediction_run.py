"""Taeglicher Prediction-Run (ohne dauerhaft laufenden Bot).

Kann per Task Scheduler / Cron 1x taeglich ausgefuehrt werden.
1. Ueberfaellige Positionen schliessen (Market Sell)
2. Pipeline trainieren (38 Coins, ~3 Min)
3. Neue Positionen oeffnen (Up + Confidence >= 55%)

Usage:
    python scripts/daily_prediction_run.py
    python scripts/daily_prediction_run.py --dry-run
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# State-Datei fuer Positionen (persistiert zwischen Runs)
STATE_FILE = Path(__file__).parent.parent / "data" / "prediction_positions.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"positions": [], "closed": []}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


async def main() -> int:
    dry_run = "--dry-run" in sys.argv
    now = datetime.now(timezone.utc)

    print(f"{'=' * 60}")
    print(f"  Prediction Daily Run — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print(f"{'=' * 60}")

    # Exchange verbinden
    from crypto_bot.config.settings import get_settings
    from crypto_bot.exchange.binance_adapter import BinanceAdapter

    settings = get_settings()
    exchange = BinanceAdapter(settings.exchange)
    await exchange.connect()

    state = _load_state()

    # ================================================================
    # Schritt 1: Ueberfaellige Positionen schliessen
    # ================================================================
    print("\n[1/3] Positionen pruefen...")

    open_positions = [p for p in state["positions"] if p["status"] == "open"]
    closed_today = 0

    for pos in open_positions:
        close_at = datetime.fromisoformat(pos["close_at"])
        if now >= close_at:
            coin = pos["coin"]
            amount = Decimal(pos["amount"])
            symbol = f"{coin}/USDT"

            print(f"  UEBERFAELLIG: {coin} — {amount} seit {pos['opened_at'][:10]}")
            print(f"    Faellig seit: {close_at.strftime('%Y-%m-%d %H:%M UTC')}")

            if not dry_run:
                try:
                    order = await exchange.create_order(
                        symbol=symbol,
                        order_type="market",
                        side="sell",
                        amount=amount,
                    )
                    close_price = float(order.price or order.cost / order.filled)
                    revenue = float(order.filled) * close_price
                    cost = float(pos["cost"])
                    pnl = revenue - cost

                    pos["status"] = "closed"
                    pos["close_price"] = str(close_price)
                    pos["pnl"] = str(round(pnl, 4))
                    pos["closed_at"] = now.isoformat()
                    state["closed"].append(pos)

                    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                    print(f"    GESCHLOSSEN @ ${close_price:.4f} — P/L: {pnl_str}")
                    closed_today += 1
                except Exception as e:
                    print(f"    FEHLER beim Schliessen: {e}")
            else:
                ticker = await exchange.fetch_ticker(symbol)
                price = float(ticker.last)
                pnl = float(amount) * price - float(pos["cost"])
                print(f"    DRY-RUN: Wuerde schliessen @ ${price:.4f} — P/L: ${pnl:+.2f}")
                closed_today += 1
        else:
            days_left = (close_at - now).days
            hours_left = int((close_at - now).total_seconds() / 3600) % 24
            print(f"  {pos['coin']}: offen — schliesst in {days_left}d {hours_left}h")

    # Geschlossene aus open-Liste entfernen
    state["positions"] = [p for p in state["positions"] if p["status"] == "open"]

    if closed_today == 0 and open_positions:
        print("  Keine ueberfaelligen Positionen.")
    elif not open_positions:
        print("  Keine offenen Positionen.")

    # ================================================================
    # Schritt 2: Pipeline trainieren
    # ================================================================
    print("\n[2/3] ML-Pipeline trainieren...")

    from crypto_bot.prediction.prediction_config import DEFAULT_PREDICTION_COINS
    from crypto_bot.prediction.prediction_pipeline import PredictionPipeline

    pipeline = PredictionPipeline(
        coin_prediction_path="C:/Codes/coin_prediction",
        coins=list(DEFAULT_PREDICTION_COINS),
        horizon_days=7,
    )

    results = await pipeline.run_full_pipeline()

    # Sortiert nach Confidence
    sorted_results = sorted(results.values(), key=lambda r: r.confidence, reverse=True)

    up_count = sum(1 for r in sorted_results if r.direction == "up")
    tradeable = [r for r in sorted_results if r.direction == "up" and r.confidence >= 0.55]

    print(f"  {len(results)} Coins analysiert — {up_count} Up, {len(results) - up_count} Down")
    print(f"  Handelbar (Up + >=55%): {len(tradeable)}")

    for r in sorted_results[:10]:
        signal = "STARK" if r.confidence >= 0.60 else "MODERAT" if r.confidence >= 0.55 else "SCHWACH"
        mark = "*" if r.direction == "up" and r.confidence >= 0.55 else " "
        print(f"    {mark}{r.coin:<8} {r.direction:<6} {r.probability:.1%}  conf={r.confidence:.1%}  [{signal}]")
    if len(sorted_results) > 10:
        print(f"    ... und {len(sorted_results) - 10} weitere")

    # ================================================================
    # Schritt 3: Neue Positionen oeffnen
    # ================================================================
    print("\n[3/3] Positionen oeffnen...")

    # Bereits offene Coins
    open_coins = {p["coin"] for p in state["positions"]}

    # Budget
    balances = await exchange.fetch_balance()
    usdt_balance = float(balances.get("USDT", type("", (), {"free": Decimal(0)})()).free) if "USDT" in balances else 0.0
    total_capital = usdt_balance
    max_per_coin = total_capital * 0.10  # 10% pro Coin
    max_exposure = total_capital * 0.60  # 60% max deployed
    current_exposure = sum(float(p["cost"]) for p in state["positions"])
    available = min(usdt_balance, max_exposure - current_exposure)

    print(f"  USDT Balance: ${usdt_balance:.2f}")
    print(f"  Aktuelle Exposure: ${current_exposure:.2f}")
    print(f"  Verfuegbar: ${available:.2f}")

    opened_today = 0
    for pred in tradeable:
        if pred.coin in open_coins:
            print(f"  {pred.coin}: bereits offen — uebersprungen")
            continue
        if available < 1:
            print(f"  Kein Budget mehr.")
            break

        # Confidence-basierte Groesse
        conf_range = 1.0 - 0.55
        conf_above = pred.confidence - 0.55
        scale = 0.25 + 0.75 * (conf_above / conf_range) if conf_range > 0 else 1.0
        size = min(max_per_coin * scale, available)

        if size < 1:
            continue

        symbol = f"{pred.coin}/USDT"
        ticker = await exchange.fetch_ticker(symbol)
        price = float(ticker.last)
        amount = size / price

        if not dry_run:
            try:
                order = await exchange.create_order(
                    symbol=symbol,
                    order_type="market",
                    side="buy",
                    amount=Decimal(str(amount)).quantize(Decimal("0.00000001")),
                )
                actual_cost = float(order.cost)
                actual_amount = float(order.filled)
                actual_price = float(order.price or (order.cost / order.filled))

                close_at = now + __import__("datetime").timedelta(days=7)
                position = {
                    "coin": pred.coin,
                    "symbol": symbol,
                    "direction": "up",
                    "confidence": pred.confidence,
                    "entry_price": str(actual_price),
                    "amount": str(actual_amount),
                    "cost": str(actual_cost),
                    "opened_at": now.isoformat(),
                    "close_at": close_at.isoformat(),
                    "status": "open",
                }
                state["positions"].append(position)
                available -= actual_cost
                opened_today += 1

                print(f"  GEKAUFT: {pred.coin} — {actual_amount:.4f} @ ${actual_price:.4f} = ${actual_cost:.2f} (conf={pred.confidence:.1%})")
                print(f"    Schliesst: {close_at.strftime('%Y-%m-%d %H:%M UTC')}")
            except Exception as e:
                print(f"  FEHLER {pred.coin}: {e}")
        else:
            print(f"  DRY-RUN: {pred.coin} — {amount:.4f} @ ${price:.4f} = ${size:.2f} (conf={pred.confidence:.1%})")
            opened_today += 1

    if opened_today == 0 and tradeable:
        print("  Keine neuen Positionen (bereits offen oder kein Budget).")
    elif not tradeable:
        print("  Keine handelbaren Signale heute.")

    # State speichern
    _save_state(state)

    # ================================================================
    # Zusammenfassung
    # ================================================================
    print(f"\n{'=' * 60}")
    print(f"  ZUSAMMENFASSUNG")
    print(f"  Geschlossen: {closed_today}")
    print(f"  Geoeffnet:   {opened_today}")
    print(f"  Offen total: {len(state['positions'])}")
    print(f"  State:       {STATE_FILE}")
    print(f"{'=' * 60}")

    await exchange.disconnect()
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0
    sys.exit(exit_code)
