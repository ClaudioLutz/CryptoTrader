"""Konfiguration fuer die Prediction-Strategie."""

from decimal import Decimal

from pydantic import Field

from crypto_bot.strategies.base_strategy import StrategyConfig

# Alle 20 Coins aus dem coin_prediction-Projekt
DEFAULT_PREDICTION_COINS = [
    "BTC", "ETH", "BNB", "LTC", "XRP", "ADA", "ETC", "XLM", "EOS", "TRX",
    "LINK", "ATOM", "MATIC", "DOGE", "DOT", "SOL", "AVAX", "UNI", "FIL", "NEAR",
]


class PredictionConfig(StrategyConfig):
    """Konfiguration fuer die Prediction-basierte Trading-Strategie.

    Attributes:
        coins: Liste der zu handelnden Coins.
        quote_currency: Quote-Waehrung (Standard: USDT).
        total_capital: Gesamtes USDT-Budget fuer die Strategie.
        max_per_coin_pct: Maximaler Anteil pro Coin am Gesamtkapital.
        max_total_exposure_pct: Maximale Gesamtexposure (Rest bleibt in USDT).
        min_confidence: Minimale Confidence fuer einen Trade (0.5-1.0).
        retrain_hour_utc: Stunde fuer taegliches Retraining (UTC).
        retrain_minute_utc: Minute fuer taegliches Retraining.
        prediction_horizon_days: Vorhersage-Horizont in Tagen.
        coin_prediction_path: Pfad zum coin_prediction-Projekt.
    """

    name: str = "prediction"
    symbol: str = "MULTI/USDT"
    coins: list[str] = Field(default_factory=lambda: list(DEFAULT_PREDICTION_COINS))
    quote_currency: str = "USDT"
    total_capital: Decimal = Decimal("1000")
    max_per_coin_pct: Decimal = Decimal("0.10")
    max_total_exposure_pct: Decimal = Decimal("0.60")
    min_confidence: float = Field(default=0.55, ge=0.50, le=1.0)
    retrain_hour_utc: int = Field(default=0, ge=0, le=23)
    retrain_minute_utc: int = Field(default=5, ge=0, le=59)
    prediction_horizon_days: int = Field(default=7, ge=1, le=30)
    coin_prediction_path: str = "C:/Codes/coin_prediction"
