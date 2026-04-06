"""Konfiguration fuer die Prediction-Strategie.

BTC-only mit 1h-Daten: Backtest zeigte 55.5% Win-Rate auf 22'000 Trades.
Taeglich-Daten mit Multi-Coin brachten nur ~50% Accuracy (Muenzwurf).
"""

from decimal import Decimal

from pydantic import Field

from crypto_bot.strategies.base_strategy import StrategyConfig

# BTC-only Strategie: 1h-Daten, 3d Horizont (72h)
# Walk-Forward Backtest (319 Folds, 22k Trades): 55.5% Win-Rate
DEFAULT_PREDICTION_COINS = ["BTC"]

# Alle Coins mit 1h-Daten im coin_prediction-Projekt (fuer spaeteren Ausbau)
ALL_PREDICTION_COINS = [
    "BTC", "ETH", "SOL", "XRP", "BNB", "TRX", "DOGE",
    "ADA", "DOT", "ETC", "EOS", "ATOM", "AVAX", "NEAR",
    "XLM", "MATIC", "LINK", "LTC",
]


class PredictionConfig(StrategyConfig):
    """Konfiguration fuer die Prediction-basierte Trading-Strategie.

    BTC-only mit 1h-Timeframe. Retraining alle 4 Stunden.
    Positionen werden nach prediction_horizon_hours geschlossen.
    """

    name: str = "prediction"
    symbol: str = "BTC/USDT"
    coins: list[str] = Field(default_factory=lambda: list(DEFAULT_PREDICTION_COINS))
    quote_currency: str = "USDT"
    total_capital: Decimal = Decimal("0")  # 0 = dynamisch aus USDT-Balance
    max_per_coin_pct: Decimal = Decimal("0.80")  # BTC-only: 80% pro Coin
    max_total_exposure_pct: Decimal = Decimal("0.80")  # BTC-only: hoehere Exposure ok
    min_confidence: float = Field(default=0.65, ge=0.50, le=1.0)
    retrain_interval_hours: int = Field(default=1, ge=1, le=24)
    prediction_horizon_hours: int = Field(default=72, ge=1, le=720)  # 3 Tage = 72h
    timeframe: str = Field(default="1h")
    train_window_hours: int = Field(default=720, ge=168, le=8760)  # 30 Tage = 720h
    coin_prediction_path: str = Field(
        default_factory=lambda: __import__("os").environ.get(
            "COIN_PREDICTION_PATH", "C:/Codes/coin_prediction"
        ),
    )

    # D1: Kelly Criterion — Position Sizing
    kelly_enabled: bool = Field(default=True)
    kelly_fraction: float = Field(default=0.25, ge=0.1, le=1.0)  # Quarter-Kelly
    kelly_min_trades: int = Field(default=20, ge=5)  # Min. Trades fuer stabile Schaetzung
    kelly_lookback_trades: int = Field(default=50, ge=10)  # Rolling-Window

    # D4: Drawdown Protection — Progressive Positionsreduktion
    drawdown_protection_enabled: bool = Field(default=True)
    drawdown_threshold_pct: float = Field(default=0.05, ge=0.01, le=0.50)  # Ab 5% Drawdown aktiv
    drawdown_max_reduction: float = Field(default=0.25, ge=0.10, le=0.90)  # Min. 25% der normalen Groesse

    # B8: Optuna Hyperparameter-Tuning
    optuna_enabled: bool = Field(default=True)
    optuna_n_trials: int = Field(default=30, ge=5, le=200)
    optuna_timeout_seconds: int = Field(default=300, ge=60, le=1800)  # 5 Min default
    optuna_retune_interval_hours: int = Field(default=24, ge=1)  # Nur 1x taeglich tunen

    # E1: Telegram Notifications
    telegram_enabled: bool = Field(default=False)
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # Abwaertskompatibilitaet
    @property
    def prediction_horizon_days(self) -> int:
        return max(1, self.prediction_horizon_hours // 24)

    @property
    def retrain_hour_utc(self) -> int:
        return 0

    @property
    def retrain_minute_utc(self) -> int:
        return 5
