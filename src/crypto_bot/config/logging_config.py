"""Production-ready structured logging configuration with structlog.

Features:
- JSON output with orjson for performance (falls back to stdlib json)
- Secret redaction for sensitive values
- Context binding for trade/request tracking
- File logging with rotation
- Callsite information for debugging
"""

import logging
import logging.handlers
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Generator, Optional

import structlog
from structlog.typing import Processor

# Try to use orjson for faster JSON serialization
try:
    import orjson

    def _orjson_dumps(obj: Any, **kwargs: Any) -> str:
        """Serialize using orjson, returning string."""
        return orjson.dumps(obj).decode("utf-8")

    JSON_SERIALIZER = _orjson_dumps
except ImportError:
    import json

    JSON_SERIALIZER = json.dumps

# Sensitive keys that should be redacted from logs
SENSITIVE_KEYS = frozenset({
    "api_key",
    "api_secret",
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
    "private_key",
})

# Patterns that indicate sensitive data
SENSITIVE_PATTERNS = frozenset({
    "key",
    "secret",
    "token",
    "password",
    "credential",
})

# Context variable for trade tracking
trade_context: ContextVar[dict[str, Any]] = ContextVar("trade_context", default={})


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

        # Check exact matches
        if key_lower in SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
            continue

        # Check pattern matches
        if any(pattern in key_lower for pattern in SENSITIVE_PATTERNS):
            event_dict[key] = "***REDACTED***"
            continue

        # Redact nested dicts
        if isinstance(event_dict[key], dict):
            event_dict[key] = _redact_nested(event_dict[key])

    return event_dict


def _redact_nested(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive values in nested dictionaries."""
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(pattern in key_lower for pattern in SENSITIVE_PATTERNS):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = _redact_nested(value)
        else:
            result[key] = value
    return result


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = True,
    log_file: Optional[str] = None,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5,
) -> None:
    """Configure structlog for production use.

    Args:
        log_level: The minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, output JSON logs. If False, use colored console output.
        log_file: Optional path to log file for persistent logging.
        max_bytes: Maximum size of log file before rotation (default 10MB).
        backup_count: Number of backup files to keep (default 5).
    """
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Build processor chain
    shared_processors: list[Processor] = [
        # Add context from contextvars
        structlog.contextvars.merge_contextvars,
        # Add log level
        structlog.processors.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Add caller info for debugging
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        # Redact secrets
        redact_secrets,
        # Format exceptions
        structlog.processors.format_exc_info,
        # Stack info for errors
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        # Production: JSON output for log aggregation
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.JSONRenderer(serializer=JSON_SERIALIZER),
        ]
    else:
        # Development: Colored console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # File handler with rotation (if specified)
    if log_file:
        add_file_handler(log_file, max_bytes, backup_count, numeric_level)

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def add_file_handler(
    log_file: str,
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    level: int = logging.INFO,
) -> None:
    """Add rotating file handler for persistent logs.

    Args:
        log_file: Path to the log file.
        max_bytes: Maximum size before rotation (default 10MB).
        backup_count: Number of backup files to keep.
        level: Minimum log level for file handler.
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)


def get_logger(name: Optional[str] = None) -> Any:
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


def bind_trade_context(
    trade_id: Optional[str] = None,
    order_id: Optional[str] = None,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
) -> None:
    """Bind trade context for all subsequent logs in this context.

    Args:
        trade_id: Optional trade identifier.
        order_id: Optional order identifier.
        symbol: Optional trading symbol.
        strategy: Optional strategy name.
    """
    ctx: dict[str, str] = {}
    if trade_id:
        ctx["trade_id"] = trade_id
    if order_id:
        ctx["order_id"] = order_id
    if symbol:
        ctx["symbol"] = symbol
    if strategy:
        ctx["strategy"] = strategy

    structlog.contextvars.bind_contextvars(**ctx)


def clear_trade_context() -> None:
    """Clear trade context after operation completes."""
    structlog.contextvars.clear_contextvars()


@contextmanager
def trade_logging_context(
    trade_id: Optional[str] = None,
    order_id: Optional[str] = None,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
) -> Generator[None, None, None]:
    """Context manager for trade-scoped logging.

    All logs within this context will include the trade information.

    Args:
        trade_id: Optional trade identifier.
        order_id: Optional order identifier.
        symbol: Optional trading symbol.
        strategy: Optional strategy name.

    Yields:
        None - context is managed via contextvars.

    Example:
        with trade_logging_context(trade_id="T123", symbol="BTC/USDT"):
            logger.info("Processing trade")  # Will include trade_id and symbol
    """
    bind_trade_context(
        trade_id=trade_id,
        order_id=order_id,
        symbol=symbol,
        strategy=strategy,
    )
    try:
        yield
    finally:
        clear_trade_context()
