"""Startet den Prediction-Bot mit manuellen Positionen.

Registriert bestehende manuelle Trades und startet dann den Bot,
der sie nach Ablauf automatisch schliesst.

Usage:
    python scripts/start_prediction_bot.py
    python scripts/start_prediction_bot.py --dry-run
"""

import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal

from crypto_bot.config.logging_config import configure_logging, get_logger
from crypto_bot.config.settings import get_settings
from crypto_bot.data.persistence import Database
from crypto_bot.exchange.binance_adapter import BinanceAdapter
from crypto_bot.main import create_bot, display_banner, MultiBotTracker
from crypto_bot.prediction.prediction_config import PredictionConfig, DEFAULT_PREDICTION_COINS
from crypto_bot.prediction.prediction_strategy import PredictionStrategy
from crypto_bot.utils.health import HealthCheckServer


# ============================================================================
# Manuelle Positionen registrieren
# ============================================================================

MANUAL_POSITIONS = []


async def main() -> int:
    dry_run = "--dry-run" in sys.argv

    settings = get_settings()
    if dry_run:
        settings.trading.dry_run = True

    configure_logging(log_level=settings.log_level, json_output=True, log_file="logs/crypto_bot.log")
    logger = get_logger("prediction_bot")

    api_port = 8082

    display_banner(settings, settings.trading.dry_run, api_port)

    health_server = None

    try:
        exchange = BinanceAdapter(settings.exchange)
        database = Database(settings.database)

        # Prediction-Strategie erstellen
        config = PredictionConfig(
            name="prediction",
            symbol="MULTI/USDT",
            coins=list(DEFAULT_PREDICTION_COINS),
            total_capital=Decimal("0"),  # Dynamisch aus USDT-Balance
            dry_run=settings.trading.dry_run,
        )
        strategy = PredictionStrategy(config)

        # Manuelle Positionen registrieren
        for pos in MANUAL_POSITIONS:
            strategy.register_manual_position(**pos)
            logger.info(
                "manual_position_added",
                coin=pos["coin"],
                amount=str(pos["amount"]),
                close_after_days=pos["close_after_days"],
            )

        logger.info(
            "starting_prediction_bot",
            manual_positions=len(MANUAL_POSITIONS),
            total_capital=str(config.total_capital),
            dry_run=settings.trading.dry_run,
        )

        await exchange.connect()
        await database.connect()

        bot = create_bot(settings, strategy, exchange, database)
        bot_tracker = MultiBotTracker()
        bot_tracker.add_bot(bot)

        # API-Server starten
        cors_origins = (
            [o.strip() for o in settings.health.cors_origins.split(",") if o.strip()]
            if settings.health.cors_origins
            else []
        )
        health_server = HealthCheckServer(
            host=settings.health.host,
            port=api_port,
            api_key=settings.health.api_key.get_secret_value(),
            cors_origins=cors_origins,
            rate_limit_requests=settings.health.rate_limit_requests,
            rate_limit_window=settings.health.rate_limit_window,
        )
        health_server.set_database(database)
        health_server.set_bot(bot_tracker)
        await health_server.start()

        logger.info("prediction_bot_starting", strategy=strategy.name)
        await bot.start()
        return 0

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        return 0
    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        return 1
    finally:
        if health_server:
            await health_server.stop()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 0
    sys.exit(exit_code)
