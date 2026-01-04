"""Type-safe configuration management with Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExchangeSettings(BaseSettings):
    """Exchange connection settings."""

    model_config = SettingsConfigDict(env_prefix="EXCHANGE__")

    name: str = "binance"
    api_key: SecretStr = Field(default=SecretStr(""))
    api_secret: SecretStr = Field(default=SecretStr(""))
    testnet: bool = True
    rate_limit_ms: int = Field(default=100, ge=50, le=1000)
    timeout_ms: int = Field(default=30000, ge=5000, le=60000)


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="DB__")

    url: str = "sqlite+aiosqlite:///./trading.db"
    echo: bool = False
    pool_size: int = Field(default=5, ge=1, le=20)


class TradingSettings(BaseSettings):
    """Trading behavior settings."""

    model_config = SettingsConfigDict(env_prefix="TRADING__")

    symbol: str = "BTC/USDT"
    dry_run: bool = True
    max_position_pct: float = Field(default=0.1, ge=0.01, le=1.0)


class AlertSettings(BaseSettings):
    """Alert and notification settings."""

    model_config = SettingsConfigDict(env_prefix="ALERT__")

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    discord_webhook_url: SecretStr | None = None
    enabled: bool = True


class AppSettings(BaseSettings):
    """Root application settings with nested configurations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    exchange: ExchangeSettings = Field(default_factory=ExchangeSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    trading: TradingSettings = Field(default_factory=TradingSettings)
    alert: AlertSettings = Field(default_factory=AlertSettings)
    log_level: str = "INFO"
    json_logs: bool = True


@lru_cache
def get_settings() -> AppSettings:
    """Get cached application settings.

    Returns:
        AppSettings: The application configuration loaded from environment.
    """
    return AppSettings()


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing."""
    get_settings.cache_clear()
