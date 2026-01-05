"""CryptoTrader Dashboard - Configuration Module.

This module provides centralized configuration management using Pydantic Settings.
All settings can be overridden via environment variables with the DASHBOARD_ prefix.

Story 10.3: Adds optional password authentication settings.
"""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardConfig(BaseSettings):
    """Dashboard configuration with environment variable support.

    All settings can be overridden via environment variables with
    the DASHBOARD_ prefix. For example:
        DASHBOARD_API_BASE_URL=http://localhost:8080
        DASHBOARD_POLL_INTERVAL_TIER1=1.5

    Attributes:
        api_base_url: Base URL for the trading bot REST API.
        api_timeout: Timeout in seconds for API requests.
        dashboard_port: Port for the NiceGUI dashboard server.
        poll_interval_tier1: Polling interval for Tier 1 data (health, P&L).
        poll_interval_tier2: Polling interval for Tier 2 data (chart, table).
    """

    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore other env vars from bot config
    )

    # API Configuration
    api_base_url: str = Field(
        default="http://localhost:8080",
        description="Base URL for the trading bot REST API",
    )
    api_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Timeout in seconds for API requests",
    )

    # Dashboard Server
    dashboard_port: int = Field(
        default=8081,
        ge=1024,
        le=65535,
        description="Port for the NiceGUI dashboard server",
    )

    # Polling Intervals (Tiered refresh strategy from architecture)
    poll_interval_tier1: float = Field(
        default=2.0,
        ge=0.5,
        le=60.0,
        description="Polling interval for Tier 1 data (health, P&L) in seconds",
    )
    poll_interval_tier2: float = Field(
        default=5.0,
        ge=1.0,
        le=120.0,
        description="Polling interval for Tier 2 data (chart, table) in seconds",
    )

    # Authentication (Story 10.3 - optional)
    auth_enabled: bool = Field(
        default=False,
        description="Enable password authentication for dashboard access",
    )
    auth_password: SecretStr = Field(
        default=SecretStr(""),
        description="Dashboard access password (required if auth_enabled)",
    )
    auth_session_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Session duration in hours before re-authentication",
    )


# Singleton instance - import this in other modules
config = DashboardConfig()
