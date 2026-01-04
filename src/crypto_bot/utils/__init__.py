"""Utility functions and helpers."""

from crypto_bot.utils.retry import retry_with_backoff
from crypto_bot.utils.alerting import (
    AlertConfig,
    AlertManager,
    AlertSeverity,
    DiscordAlerter,
    TelegramAlerter,
    RateLimitedTelegramAlerter,
    create_alert_manager,
)
from crypto_bot.utils.health import HealthCheckServer, create_health_server
from crypto_bot.utils.secrets import SecretManager
from crypto_bot.utils.validators import (
    ValidationError,
    validate_symbol,
    validate_positive_decimal,
    validate_percentage,
    validate_price_range,
    validate_grid_count,
    ValidatedGridConfig,
    ValidatedRiskConfig,
)
from crypto_bot.utils.api_validator import APIKeyValidator, APIPermissions
from crypto_bot.utils.security_check import SecurityChecker, SecurityReport
from crypto_bot.utils.audit import AuditLogger, AuditEvent

__all__ = [
    # Retry
    "retry_with_backoff",
    # Alerting
    "AlertConfig",
    "AlertManager",
    "AlertSeverity",
    "DiscordAlerter",
    "TelegramAlerter",
    "RateLimitedTelegramAlerter",
    "create_alert_manager",
    # Health
    "HealthCheckServer",
    "create_health_server",
    # Secrets
    "SecretManager",
    # Validators
    "ValidationError",
    "validate_symbol",
    "validate_positive_decimal",
    "validate_percentage",
    "validate_price_range",
    "validate_grid_count",
    "ValidatedGridConfig",
    "ValidatedRiskConfig",
    # API Validation
    "APIKeyValidator",
    "APIPermissions",
    # Security
    "SecurityChecker",
    "SecurityReport",
    # Audit
    "AuditLogger",
    "AuditEvent",
]
