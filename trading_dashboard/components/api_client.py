"""API client for backend communication using httpx."""

import asyncio
import os
from typing import Any

import httpx
import streamlit as st

# Backend API base URL - configurable via environment variable
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")


@st.cache_resource
def get_http_client() -> httpx.Client:
    """Get cached HTTP client with connection pooling.

    Returns:
        httpx.Client: Configured HTTP client
    """
    return httpx.Client(
        base_url=API_BASE_URL,
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )


# =============================================================================
# Endpoint-Specific Fetch Functions
# =============================================================================


@st.cache_data(ttl=5)
def fetch_trades() -> dict[str, Any]:
    """Fetch recent trades (5s cache).

    Returns:
        dict: Trade data or error fallback
    """
    try:
        response = get_http_client().get("/api/trades")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"trades": [], "error": str(e)}


@st.cache_data(ttl=5)
def fetch_positions() -> dict[str, Any]:
    """Fetch open positions (5s cache).

    Returns:
        dict: Position data or error fallback
    """
    try:
        response = get_http_client().get("/api/positions")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"positions": [], "error": str(e)}


@st.cache_data(ttl=10)
def fetch_pnl() -> dict[str, Any]:
    """Fetch P&L summary (10s cache).

    Returns:
        dict: P&L data or error fallback
    """
    try:
        response = get_http_client().get("/api/pnl")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"total": 0, "unrealized": 0, "change_pct": 0, "cycles": 0, "error": str(e)}


@st.cache_data(ttl=10)
def fetch_equity() -> dict[str, Any]:
    """Fetch equity curve data (10s cache).

    Returns:
        dict: Equity data or error fallback
    """
    try:
        response = get_http_client().get("/api/equity")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"data": [], "error": str(e)}


@st.cache_data(ttl=30)
def fetch_status() -> dict[str, Any]:
    """Fetch bot status (30s cache).

    Returns:
        dict: Status data or error fallback
    """
    try:
        response = get_http_client().get("/api/status")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {
            "running": False,
            "trading_enabled": False,
            "ws_connected": False,
            "db_connected": False,
            "circuit_breaker_active": False,
            "current_drawdown": 0,
            "max_drawdown_limit": 10,
            "daily_loss": 0,
            "daily_loss_limit": 1000,
            "grid_config": {},
            "error": str(e),
        }


@st.cache_data(ttl=60)
def fetch_health() -> dict[str, Any]:
    """Fetch health check (60s cache).

    Returns:
        dict: Health data or error fallback
    """
    try:
        response = get_http_client().get("/health")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"healthy": False, "error": str(e)}


@st.cache_data(ttl=3)
def fetch_orders(symbol: str | None = None) -> dict[str, Any]:
    """Fetch pending orders from exchange (3s cache).

    Args:
        symbol: Optional symbol filter

    Returns:
        dict: Orders data or error fallback
    """
    try:
        params = {"symbol": symbol} if symbol else {}
        response = get_http_client().get("/api/orders", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"orders": [], "error": str(e)}


@st.cache_data(ttl=5)
def fetch_strategies() -> dict[str, Any]:
    """Fetch all strategies with statistics (5s cache).

    Returns:
        dict: Strategies data or error fallback
    """
    try:
        response = get_http_client().get("/api/strategies")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"strategies": [], "error": str(e)}


@st.cache_data(ttl=30)
def fetch_ohlcv(symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 100) -> dict[str, Any]:
    """Fetch OHLCV candlestick data (30s cache).

    Args:
        symbol: Trading pair symbol
        timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of candles to fetch

    Returns:
        dict: OHLCV data or error fallback
    """
    try:
        params = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        response = get_http_client().get("/api/ohlcv", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"ohlcv": [], "error": str(e)}


# =============================================================================
# Batch Fetching for Dashboard Initialization
# =============================================================================


async def _fetch_all_dashboard_data() -> dict[str, Any]:
    """Fetch all dashboard data concurrently.

    Returns:
        dict: Combined data from all endpoints
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as client:
        tasks = [
            client.get("/api/trades"),
            client.get("/api/positions"),
            client.get("/api/pnl"),
            client.get("/api/equity"),
            client.get("/api/status"),
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "trades": _parse_response(responses[0], {"trades": []}),
            "positions": _parse_response(responses[1], {"positions": []}),
            "pnl": _parse_response(responses[2], {"total": 0, "unrealized": 0}),
            "equity": _parse_response(responses[3], {"data": []}),
            "status": _parse_response(responses[4], {"running": False}),
        }


def _parse_response(response: httpx.Response | Exception, default: Any) -> Any:
    """Parse response or return default on error.

    Args:
        response: HTTP response or exception
        default: Default value on error

    Returns:
        Parsed JSON or default value
    """
    if isinstance(response, Exception):
        return default
    try:
        response.raise_for_status()
        return response.json()
    except Exception:
        return default


@st.cache_data(ttl=5)
def get_all_data() -> dict[str, Any]:
    """Cached wrapper for batch fetch.

    Returns:
        dict: Combined data from all endpoints
    """
    return asyncio.run(_fetch_all_dashboard_data())


# =============================================================================
# Cache Management
# =============================================================================


def clear_all_caches() -> None:
    """Clear all data caches. Called on refresh."""
    st.cache_data.clear()


def clear_trading_caches() -> None:
    """Clear only real-time trading data caches."""
    fetch_trades.clear()
    fetch_positions.clear()
    fetch_pnl.clear()
