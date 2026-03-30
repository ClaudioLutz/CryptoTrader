"""Konfiguration fuer die Prediction-Strategie."""

from decimal import Decimal

from pydantic import Field

from crypto_bot.strategies.base_strategy import StrategyConfig

# Coins mit historischer Accuracy > 54% im Backtest (80/20 Split, 7d Horizont)
# Ausgeschlossen: BTC (50.2%), ETH (46.1%), BNB (48.7%), XRP (50.1%),
#                 FIL (49.8%), UNI (50.8%), LINK (51.6%), LTC (52.4%)
# Diese Coins sind zu effizient fuer ML-basiertes Trading.
PROFITABLE_COINS = [
    # >58% Accuracy (stark)
    "MATIC", "DOT", "ETC", "ADA", "XLM",
    # 55-58% Accuracy (solide)
    "EOS", "ATOM", "TRX", "DOGE",
    # 53-55% Accuracy (knapp profitabel)
    "AVAX", "SOL", "NEAR",
]

# Alle Coins fuer Training/Analyse (inkl. unprofitable fuer Completeness)
ALL_PREDICTION_COINS = [
    # Tier 1: >$30M Volumen
    "BTC", "ETH", "SOL", "XRP", "BCH", "BNB", "TAO", "TRX", "DOGE", "SUI",
    # Tier 2: $5M-$30M Volumen
    "ADA", "ZEC", "FET", "LINK", "WLD", "NEAR", "LTC", "CHZ", "AVAX", "FIL",
    "ANKR", "ENA",
    # Tier 3: $2M-$5M Volumen
    "ONT", "ENJ", "DOT", "XLM", "AAVE", "UNI", "HBAR", "ICP", "ARB", "RENDER",
    "APT", "CFX", "SEI", "CRV",
    # Legacy (bestehende Features im coin_prediction-Projekt)
    "ETC", "EOS", "ATOM", "MATIC",
]

# Default: Nur profitable Coins handeln
DEFAULT_PREDICTION_COINS = PROFITABLE_COINS


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
    total_capital: Decimal = Decimal("0")  # 0 = dynamisch aus USDT-Balance
    max_per_coin_pct: Decimal = Decimal("0.20")
    max_total_exposure_pct: Decimal = Decimal("0.60")
    min_confidence: float = Field(default=0.65, ge=0.50, le=1.0)
    retrain_hour_utc: int = Field(default=0, ge=0, le=23)
    retrain_minute_utc: int = Field(default=5, ge=0, le=59)
    prediction_horizon_days: int = Field(default=7, ge=1, le=30)
    coin_prediction_path: str = "C:/Codes/coin_prediction"
