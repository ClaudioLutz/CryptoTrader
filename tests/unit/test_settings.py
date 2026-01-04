"""Unit tests for configuration settings."""

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from crypto_bot.config.settings import (
    AppSettings,
    DatabaseSettings,
    ExchangeSettings,
    TradingSettings,
    clear_settings_cache,
    get_settings,
)


class TestExchangeSettings:
    """Tests for ExchangeSettings."""

    def test_default_values(self) -> None:
        """Test default exchange settings."""
        settings = ExchangeSettings()

        assert settings.name == "binance"
        assert settings.testnet is True
        assert settings.rate_limit_ms == 100
        assert settings.timeout_ms == 30000

    def test_api_key_is_secret_str(self) -> None:
        """Test that API keys use SecretStr."""
        settings = ExchangeSettings(
            api_key=SecretStr("test_key"),
            api_secret=SecretStr("test_secret"),
        )

        # SecretStr should not expose value in str()
        assert "test_key" not in str(settings.api_key)
        assert "test_secret" not in str(settings.api_secret)

        # But value should be accessible via get_secret_value()
        assert settings.api_key.get_secret_value() == "test_key"
        assert settings.api_secret.get_secret_value() == "test_secret"

    def test_rate_limit_validation(self) -> None:
        """Test rate limit bounds validation."""
        # Valid values
        settings = ExchangeSettings(rate_limit_ms=50)
        assert settings.rate_limit_ms == 50

        settings = ExchangeSettings(rate_limit_ms=1000)
        assert settings.rate_limit_ms == 1000

        # Invalid values
        with pytest.raises(ValidationError):
            ExchangeSettings(rate_limit_ms=49)

        with pytest.raises(ValidationError):
            ExchangeSettings(rate_limit_ms=1001)

    def test_timeout_validation(self) -> None:
        """Test timeout bounds validation."""
        with pytest.raises(ValidationError):
            ExchangeSettings(timeout_ms=4999)

        with pytest.raises(ValidationError):
            ExchangeSettings(timeout_ms=60001)


class TestDatabaseSettings:
    """Tests for DatabaseSettings."""

    def test_default_values(self) -> None:
        """Test default database settings."""
        settings = DatabaseSettings()

        assert settings.url == "sqlite+aiosqlite:///./trading.db"
        assert settings.echo is False
        assert settings.pool_size == 5

    def test_pool_size_validation(self) -> None:
        """Test pool size bounds validation."""
        with pytest.raises(ValidationError):
            DatabaseSettings(pool_size=0)

        with pytest.raises(ValidationError):
            DatabaseSettings(pool_size=21)


class TestTradingSettings:
    """Tests for TradingSettings."""

    def test_default_values(self) -> None:
        """Test default trading settings."""
        settings = TradingSettings()

        assert settings.symbol == "BTC/USDT"
        assert settings.dry_run is True
        assert settings.max_position_pct == 0.1

    def test_max_position_pct_validation(self) -> None:
        """Test position percentage bounds validation."""
        # Valid values
        settings = TradingSettings(max_position_pct=0.01)
        assert settings.max_position_pct == 0.01

        settings = TradingSettings(max_position_pct=1.0)
        assert settings.max_position_pct == 1.0

        # Invalid values
        with pytest.raises(ValidationError):
            TradingSettings(max_position_pct=0.009)

        with pytest.raises(ValidationError):
            TradingSettings(max_position_pct=1.1)


class TestAppSettings:
    """Tests for AppSettings."""

    def test_default_values(self) -> None:
        """Test default app settings with nested configs."""
        settings = AppSettings()

        assert settings.log_level == "INFO"
        assert settings.json_logs is True
        assert isinstance(settings.exchange, ExchangeSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.trading, TradingSettings)

    def test_env_override(self) -> None:
        """Test environment variable override."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            clear_settings_cache()
            settings = get_settings()
            assert settings.log_level == "DEBUG"

        clear_settings_cache()

    def test_nested_env_override(self) -> None:
        """Test nested environment variable override."""
        with patch.dict(os.environ, {"EXCHANGE__TESTNET": "false"}):
            clear_settings_cache()
            settings = get_settings()
            assert settings.exchange.testnet is False

        clear_settings_cache()


class TestGetSettings:
    """Tests for get_settings function."""

    def test_caching(self) -> None:
        """Test that settings are cached."""
        clear_settings_cache()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_cache_clear(self) -> None:
        """Test cache clearing."""
        settings1 = get_settings()
        clear_settings_cache()
        settings2 = get_settings()

        # Should be different objects after cache clear
        assert settings1 is not settings2
