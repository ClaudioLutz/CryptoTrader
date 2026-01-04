"""Retry utility with exponential backoff and jitter."""

import asyncio
import random
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import structlog

# Import ccxt exceptions if available, otherwise define fallbacks
try:
    import ccxt

    RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        ccxt.NetworkError,
        ccxt.RateLimitExceeded,
        ccxt.ExchangeNotAvailable,
        ccxt.RequestTimeout,
        ccxt.DDoSProtection,
        ConnectionError,
        TimeoutError,
        OSError,
    )

    NON_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        ccxt.AuthenticationError,
        ccxt.InvalidOrder,
        ccxt.InsufficientFunds,
        ccxt.BadSymbol,
        ccxt.BadRequest,
        ValueError,
        TypeError,
    )
except ImportError:
    RETRYABLE_EXCEPTIONS = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    NON_RETRYABLE_EXCEPTIONS = (
        ValueError,
        TypeError,
    )

logger = structlog.get_logger()

P = ParamSpec("P")
T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    non_retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay in seconds between retries.
        exponential_base: Base for exponential backoff calculation.
        jitter: If True, add randomization to delay to prevent thundering herd.
        retryable_exceptions: Tuple of exceptions to retry on.
        non_retryable_exceptions: Tuple of exceptions that should fail immediately.

    Returns:
        Decorated async function with retry logic.

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def fetch_data():
            return await api.get_data()
    """
    retry_on = retryable_exceptions or RETRYABLE_EXCEPTIONS
    dont_retry_on = non_retryable_exceptions or NON_RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except dont_retry_on:
                    # Don't retry auth/validation errors - fail fast
                    raise
                except retry_on as e:
                    last_exception = e

                    if attempt == max_retries - 1:
                        # Last attempt failed, re-raise
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_retries,
                            error_type=type(e).__name__,
                            error_msg=str(e),
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base**attempt),
                        max_delay,
                    )

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay *= 0.5 + random.random()

                    logger.warning(
                        "retry_scheduled",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=round(delay, 2),
                        error_type=type(e).__name__,
                        error_msg=str(e),
                    )

                    await asyncio.sleep(delay)

            # This should never be reached, but satisfies type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop exited unexpectedly")

        return wrapper  # type: ignore[return-value]

    return decorator


class RetryableError(Exception):
    """Exception that signals the operation should be retried."""

    pass


class NonRetryableError(Exception):
    """Exception that signals the operation should not be retried."""

    pass
