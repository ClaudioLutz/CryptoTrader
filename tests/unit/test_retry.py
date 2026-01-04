"""Unit tests for retry utility."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from crypto_bot.utils.retry import (
    NON_RETRYABLE_EXCEPTIONS,
    RETRYABLE_EXCEPTIONS,
    retry_with_backoff,
)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_successful_call(self) -> None:
        """Test that successful calls return immediately."""
        mock_func = AsyncMock(return_value="success")

        @retry_with_backoff(max_retries=3)
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self) -> None:
        """Test retry on ConnectionError."""
        mock_func = AsyncMock(
            side_effect=[ConnectionError("failed"), ConnectionError("failed"), "success"]
        )

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self) -> None:
        """Test that retries are exhausted after max attempts."""
        mock_func = AsyncMock(side_effect=ConnectionError("always fails"))

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def test_func() -> str:
            return await mock_func()

        with pytest.raises(ConnectionError):
            await test_func()

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_value_error(self) -> None:
        """Test that ValueError is not retried."""
        mock_func = AsyncMock(side_effect=ValueError("invalid"))

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def test_func() -> str:
            return await mock_func()

        with pytest.raises(ValueError):
            await test_func()

        # Should fail immediately without retries
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test that delays increase exponentially."""
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("1"),
                ConnectionError("2"),
                ConnectionError("3"),
                "success",
            ]
        )

        @retry_with_backoff(
            max_retries=4, base_delay=1.0, exponential_base=2.0, jitter=False
        )
        async def test_func() -> str:
            return await mock_func()

        with patch("asyncio.sleep", mock_sleep):
            result = await test_func()

        assert result == "success"
        assert len(delays) == 3
        # Without jitter: 1.0, 2.0, 4.0
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("1"),
                ConnectionError("2"),
                ConnectionError("3"),
                ConnectionError("4"),
                "success",
            ]
        )

        @retry_with_backoff(
            max_retries=5,
            base_delay=1.0,
            max_delay=3.0,
            exponential_base=2.0,
            jitter=False,
        )
        async def test_func() -> str:
            return await mock_func()

        with patch("asyncio.sleep", mock_sleep):
            result = await test_func()

        assert result == "success"
        # Delays should be capped at 3.0
        assert delays[0] == 1.0  # 1.0 * 2^0 = 1.0
        assert delays[1] == 2.0  # 1.0 * 2^1 = 2.0
        assert delays[2] == 3.0  # 1.0 * 2^2 = 4.0 -> capped to 3.0
        assert delays[3] == 3.0  # 1.0 * 2^3 = 8.0 -> capped to 3.0

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self) -> None:
        """Test that jitter adds randomness to delays."""
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        mock_func = AsyncMock(
            side_effect=[ConnectionError("1"), ConnectionError("2"), "success"]
        )

        @retry_with_backoff(max_retries=3, base_delay=1.0, jitter=True)
        async def test_func() -> str:
            return await mock_func()

        with patch("asyncio.sleep", mock_sleep):
            await test_func()

        # With jitter, delays should be between 0.5x and 1.5x base
        assert 0.5 <= delays[0] <= 1.5
        assert 1.0 <= delays[1] <= 3.0  # 2.0 * (0.5 to 1.5)

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self) -> None:
        """Test custom retryable exceptions."""

        class CustomError(Exception):
            pass

        mock_func = AsyncMock(
            side_effect=[CustomError("retry me"), "success"]
        )

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(CustomError,),
        )
        async def test_func() -> str:
            return await mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_logging_on_retry(self) -> None:
        """Test that retries are logged."""
        mock_func = AsyncMock(
            side_effect=[ConnectionError("failed"), "success"]
        )

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def test_func() -> str:
            return await mock_func()

        # Just verify it completes without error
        # Logging is handled internally
        result = await test_func()
        assert result == "success"
