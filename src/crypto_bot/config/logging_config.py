"""Structured logging configuration with structlog."""

import logging
from typing import Any

import structlog
from structlog.typing import Processor

SENSITIVE_KEYS = frozenset({
    "api_key",
    "api_secret",
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
})


def redact_secrets(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Redact sensitive values from log output.

    Args:
        _logger: The logger instance (unused, required by structlog signature).
        _method_name: The logging method name (unused, required by structlog signature).
        event_dict: The event dictionary to process.

    Returns:
        The processed event dictionary with secrets redacted.
    """
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            event_dict[key] = "***REDACTED***"
        elif isinstance(event_dict[key], dict):
            event_dict[key] = _redact_nested(event_dict[key])
    return event_dict


def _redact_nested(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive values in nested dictionaries."""
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = _redact_nested(value)
        else:
            result[key] = value
    return result


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog for the application.

    Args:
        log_level: The minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, output JSON logs. If False, use colored console output.
    """
    # Shared processors for both JSON and console output
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # Production: JSON output for log aggregation
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance.

    Args:
        name: Optional logger name for context.

    Returns:
        A bound logger instance.
    """
    log = structlog.get_logger()
    if name:
        log = log.bind(component=name)
    return log
