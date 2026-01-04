"""Unit tests for logging configuration."""

import json

import pytest
import structlog

from crypto_bot.config.logging_config import (
    configure_logging,
    get_logger,
    redact_secrets,
)


class TestRedactSecrets:
    """Tests for secret redaction in logs."""

    def test_redacts_api_key(self) -> None:
        """Test that api_key is redacted."""
        event_dict = {"api_key": "secret123", "message": "test"}
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["api_key"] == "***REDACTED***"
        assert result["message"] == "test"

    def test_redacts_api_secret(self) -> None:
        """Test that api_secret is redacted."""
        event_dict = {"api_secret": "secret123"}
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["api_secret"] == "***REDACTED***"

    def test_redacts_password(self) -> None:
        """Test that password is redacted."""
        event_dict = {"password": "secret123", "db_password": "secret456"}
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["password"] == "***REDACTED***"
        assert result["db_password"] == "***REDACTED***"

    def test_redacts_token(self) -> None:
        """Test that token is redacted."""
        event_dict = {"token": "abc123", "auth_token": "xyz789"}
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["token"] == "***REDACTED***"
        assert result["auth_token"] == "***REDACTED***"

    def test_preserves_non_sensitive_keys(self) -> None:
        """Test that non-sensitive keys are preserved."""
        event_dict = {
            "symbol": "BTC/USDT",
            "price": 50000,
            "amount": 0.1,
        }
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["symbol"] == "BTC/USDT"
        assert result["price"] == 50000
        assert result["amount"] == 0.1

    def test_case_insensitive_redaction(self) -> None:
        """Test that redaction is case-insensitive."""
        event_dict = {
            "API_KEY": "secret1",
            "Api_Secret": "secret2",
            "PASSWORD": "secret3",
        }
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["API_KEY"] == "***REDACTED***"
        assert result["Api_Secret"] == "***REDACTED***"
        assert result["PASSWORD"] == "***REDACTED***"

    def test_redacts_nested_dicts(self) -> None:
        """Test that nested dictionaries are also redacted."""
        event_dict = {
            "config": {
                "api_key": "secret123",
                "exchange": "binance",
            }
        }
        result = redact_secrets(None, None, event_dict)  # type: ignore

        assert result["config"]["api_key"] == "***REDACTED***"
        assert result["config"]["exchange"] == "binance"


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configure_json_output(self) -> None:
        """Test JSON logging configuration."""
        configure_logging(log_level="DEBUG", json_output=True)
        logger = get_logger("test")

        # Just verify configuration completes without error
        assert logger is not None

    def test_configure_console_output(self) -> None:
        """Test console logging configuration."""
        configure_logging(log_level="INFO", json_output=False)
        logger = get_logger("test")

        assert logger is not None

    def test_logger_with_component_name(self) -> None:
        """Test logger binding with component name."""
        configure_logging(log_level="INFO", json_output=True)
        logger = get_logger("my_component")

        # Logger should be bound with component context
        assert logger is not None


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_bound_logger(self) -> None:
        """Test that get_logger returns a bound logger."""
        configure_logging()
        logger = get_logger()

        assert logger is not None
        # Should be able to log without error
        logger.info("test_message", key="value")

    def test_logger_with_name(self) -> None:
        """Test logger with explicit name."""
        configure_logging()
        logger = get_logger("named_logger")

        assert logger is not None
