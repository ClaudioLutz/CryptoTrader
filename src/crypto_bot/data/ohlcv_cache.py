"""OHLCV data caching with multi-layer storage.

Provides efficient caching of historical price data to:
- Reduce API calls and avoid rate limits
- Speed up backtesting with local data
- Support offline analysis

Cache layers:
1. Memory cache (LRU) - fastest, limited size
2. Disk cache (Parquet) - persistent, compressed
3. Exchange API - fallback source
"""

from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import structlog

from crypto_bot.exchange.base_exchange import BaseExchange, OHLCV

logger = structlog.get_logger()


class OHLCVCache:
    """Multi-layer OHLCV data cache.

    Implements a two-tier caching strategy:
    1. In-memory LRU cache for hot data
    2. Disk storage using Parquet files for persistence

    Example:
        >>> cache = OHLCVCache()
        >>> data = await cache.get("BTC/USDT", "1h", start, end)
        >>> if data is None:
        ...     data = await exchange.fetch_ohlcv(...)
        ...     await cache.put("BTC/USDT", "1h", start, end, data)
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        memory_cache_size: int = 100,
    ) -> None:
        """Initialize OHLCV cache.

        Args:
            cache_dir: Directory for disk cache files.
            memory_cache_size: Maximum entries in memory cache.
        """
        self._cache_dir = cache_dir or Path("./data/ohlcv_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: OrderedDict[str, list[OHLCV]] = OrderedDict()
        self._memory_cache_size = memory_cache_size
        self._logger = logger.bind(component="ohlcv_cache")

    def _cache_key(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> str:
        """Generate cache key from parameters.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            Unique cache key string.
        """
        # Normalize symbol for filesystem
        safe_symbol = symbol.replace("/", "_")
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")
        return f"{safe_symbol}_{timeframe}_{start_str}_{end_str}"

    async def get(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> Optional[list[OHLCV]]:
        """Get cached OHLCV data.

        Checks memory cache first, then disk cache.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            List of OHLCV candles if cached, None otherwise.
        """
        key = self._cache_key(symbol, timeframe, start, end)

        # Check memory cache first (and move to end for LRU)
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
            self._logger.debug("cache_hit", layer="memory", key=key)
            return self._memory_cache[key]

        # Check disk cache
        cache_file = self._cache_dir / f"{key}.parquet"
        if cache_file.exists():
            try:
                data = self._load_from_parquet(cache_file)
                self._add_to_memory_cache(key, data)
                self._logger.debug("cache_hit", layer="disk", key=key)
                return data
            except Exception as e:
                self._logger.warning(
                    "disk_cache_load_failed",
                    key=key,
                    error=str(e),
                )

        self._logger.debug("cache_miss", key=key)
        return None

    async def put(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        data: list[OHLCV],
    ) -> None:
        """Cache OHLCV data.

        Stores in both memory and disk cache.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.
            start: Start timestamp.
            end: End timestamp.
            data: OHLCV candles to cache.
        """
        if not data:
            return

        key = self._cache_key(symbol, timeframe, start, end)

        # Save to disk
        cache_file = self._cache_dir / f"{key}.parquet"
        try:
            self._save_to_parquet(data, cache_file)
        except Exception as e:
            self._logger.warning(
                "disk_cache_save_failed",
                key=key,
                error=str(e),
            )

        # Add to memory cache
        self._add_to_memory_cache(key, data)

        self._logger.debug("cached", key=key, candles=len(data))

    def _add_to_memory_cache(self, key: str, data: list[OHLCV]) -> None:
        """Add data to memory cache with LRU eviction.

        Args:
            key: Cache key.
            data: OHLCV data to cache.
        """
        # Evict oldest if at capacity
        while len(self._memory_cache) >= self._memory_cache_size:
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]

        self._memory_cache[key] = data

    def _save_to_parquet(self, data: list[OHLCV], filepath: Path) -> None:
        """Save OHLCV data to Parquet file.

        Args:
            data: OHLCV candles.
            filepath: Output file path.
        """
        try:
            import pandas as pd

            rows = [
                {
                    "timestamp": candle.timestamp,
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": float(candle.volume),
                }
                for candle in data
            ]
            df = pd.DataFrame(rows)
            df.to_parquet(filepath, index=False)
        except ImportError:
            # Fallback to JSON if pandas not available
            import json

            json_path = filepath.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump(
                    [
                        {
                            "timestamp": c.timestamp.isoformat(),
                            "open": str(c.open),
                            "high": str(c.high),
                            "low": str(c.low),
                            "close": str(c.close),
                            "volume": str(c.volume),
                        }
                        for c in data
                    ],
                    f,
                )

    def _load_from_parquet(self, filepath: Path) -> list[OHLCV]:
        """Load OHLCV data from Parquet file.

        Args:
            filepath: Input file path.

        Returns:
            List of OHLCV candles.
        """
        try:
            import pandas as pd

            df = pd.read_parquet(filepath)
            return [
                OHLCV(
                    timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                )
                for _, row in df.iterrows()
            ]
        except ImportError:
            # Fallback to JSON
            import json

            json_path = filepath.with_suffix(".json")
            if json_path.exists():
                with open(json_path) as f:
                    data = json.load(f)
                return [
                    OHLCV(
                        timestamp=datetime.fromisoformat(c["timestamp"]),
                        open=Decimal(c["open"]),
                        high=Decimal(c["high"]),
                        low=Decimal(c["low"]),
                        close=Decimal(c["close"]),
                        volume=Decimal(c["volume"]),
                    )
                    for c in data
                ]
            raise FileNotFoundError(f"No cache file found: {filepath}")

    def clear_memory(self) -> None:
        """Clear in-memory cache."""
        self._memory_cache.clear()
        self._logger.info("memory_cache_cleared")

    def clear_disk(self) -> None:
        """Clear disk cache."""
        for f in self._cache_dir.glob("*.parquet"):
            f.unlink()
        for f in self._cache_dir.glob("*.json"):
            f.unlink()
        self._logger.info("disk_cache_cleared")

    def clear(self) -> None:
        """Clear all caches."""
        self.clear_memory()
        self.clear_disk()

    def get_cache_info(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        disk_files = list(self._cache_dir.glob("*.parquet"))
        disk_files.extend(self._cache_dir.glob("*.json"))

        return {
            "memory_entries": len(self._memory_cache),
            "memory_capacity": self._memory_cache_size,
            "disk_files": len(disk_files),
            "cache_dir": str(self._cache_dir),
        }


class OHLCVFetcher:
    """Cache-aware OHLCV data fetcher.

    Combines cache lookup with exchange API calls,
    automatically caching fetched data.

    Example:
        >>> fetcher = OHLCVFetcher(exchange, cache)
        >>> candles = await fetcher.fetch("BTC/USDT", "1h", start, end)
    """

    def __init__(
        self,
        exchange: BaseExchange,
        cache: Optional[OHLCVCache] = None,
    ) -> None:
        """Initialize OHLCV fetcher.

        Args:
            exchange: Exchange adapter for API calls.
            cache: Optional cache instance.
        """
        self._exchange = exchange
        self._cache = cache or OHLCVCache()
        self._logger = logger.bind(component="ohlcv_fetcher")

    async def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        use_cache: bool = True,
    ) -> list[OHLCV]:
        """Fetch OHLCV data with caching.

        Checks cache first, falls back to exchange API.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe (1m, 5m, 1h, etc.).
            start: Start timestamp.
            end: End timestamp.
            use_cache: Whether to use cache (default True).

        Returns:
            List of OHLCV candles.
        """
        # Try cache first
        if use_cache:
            cached = await self._cache.get(symbol, timeframe, start, end)
            if cached is not None:
                return cached

        # Fetch from exchange
        self._logger.info(
            "fetching_ohlcv",
            symbol=symbol,
            timeframe=timeframe,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        # Calculate limit based on timeframe
        limit = self._calculate_limit(timeframe, start, end)

        ohlcv = await self._exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        # Filter to requested range
        filtered = [
            c for c in ohlcv
            if start <= c.timestamp <= end
        ]

        # Cache the result
        if use_cache and filtered:
            await self._cache.put(symbol, timeframe, start, end, filtered)

        return filtered

    def _calculate_limit(
        self,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """Calculate number of candles needed for time range.

        Args:
            timeframe: Candle timeframe.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            Number of candles to request.
        """
        # Parse timeframe to seconds
        timeframe_seconds = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "8h": 28800,
            "12h": 43200,
            "1d": 86400,
            "3d": 259200,
            "1w": 604800,
        }

        seconds = timeframe_seconds.get(timeframe, 3600)
        duration = (end - start).total_seconds()
        candles = int(duration / seconds) + 1

        # Clamp to reasonable limit
        return min(max(candles, 100), 1000)

    async def fetch_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[OHLCV]:
        """Fetch latest candles without caching.

        For real-time data that shouldn't be cached.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.
            limit: Number of candles.

        Returns:
            List of latest OHLCV candles.
        """
        return await self._exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )


class OHLCVDataManager:
    """High-level manager for OHLCV data operations.

    Provides utilities for bulk data loading, gap detection,
    and data maintenance.
    """

    def __init__(
        self,
        fetcher: OHLCVFetcher,
        cache: OHLCVCache,
    ) -> None:
        """Initialize data manager.

        Args:
            fetcher: OHLCV fetcher instance.
            cache: OHLCV cache instance.
        """
        self._fetcher = fetcher
        self._cache = cache
        self._logger = logger.bind(component="ohlcv_manager")

    async def ensure_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> bool:
        """Ensure data is available for the given range.

        Fetches missing data if not in cache.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle timeframe.
            start: Start timestamp.
            end: End timestamp.

        Returns:
            True if data is available, False on error.
        """
        try:
            data = await self._fetcher.fetch(symbol, timeframe, start, end)
            return len(data) > 0
        except Exception as e:
            self._logger.error(
                "ensure_data_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e),
            )
            return False

    def detect_gaps(
        self,
        data: list[OHLCV],
        timeframe: str,
    ) -> list[tuple[datetime, datetime]]:
        """Detect gaps in OHLCV data.

        Args:
            data: OHLCV candles to check.
            timeframe: Expected timeframe.

        Returns:
            List of (gap_start, gap_end) tuples.
        """
        if len(data) < 2:
            return []

        # Parse timeframe to seconds
        timeframe_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }
        expected_interval = timeframe_seconds.get(timeframe, 3600)

        gaps = []
        for i in range(1, len(data)):
            actual_interval = (
                data[i].timestamp - data[i - 1].timestamp
            ).total_seconds()

            if actual_interval > expected_interval * 1.5:
                gaps.append((data[i - 1].timestamp, data[i].timestamp))

        return gaps

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Cache info dictionary.
        """
        return self._cache.get_cache_info()
