"""CryptoTrader Dashboard - Data Models.

Pydantic models for API response parsing and validation.
These models represent the data structures returned by the trading bot API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Bot health status response from /health endpoint.

    Attributes:
        status: Current health status (healthy, degraded, or error).
        uptime_seconds: Bot uptime in seconds since start.
        message: Optional status message with additional context.
    """

    status: Literal["healthy", "degraded", "error"] = Field(
        description="Current health status",
    )
    uptime_seconds: int = Field(
        ge=0,
        description="Bot uptime in seconds",
    )
    message: str | None = Field(
        default=None,
        description="Optional status message",
    )


class PairData(BaseModel):
    """Trading pair data from /pairs endpoint.

    Attributes:
        symbol: Trading pair symbol (e.g., BTC/USDT).
        current_price: Current market price.
        pnl_today: Profit/loss for today in quote currency.
        pnl_percent: Profit/loss percentage for today.
        position_size: Current position size in base currency.
        order_count: Number of open orders for this pair.
        lower_price: Grid lower price bound.
        upper_price: Grid upper price bound.
        num_grids: Number of grid levels.
        total_investment: Total investment amount.
    """

    symbol: str = Field(
        description="Trading pair symbol (e.g., BTC/USDT)",
    )
    current_price: Decimal = Field(
        ge=0,
        description="Current market price",
    )
    pnl_today: Decimal = Field(
        default=Decimal("0"),
        description="Profit/loss for today in quote currency",
    )
    pnl_percent: Decimal = Field(
        default=Decimal("0"),
        description="Profit/loss percentage for today",
    )
    position_size: Decimal = Field(
        default=Decimal("0"),
        description="Current position size in base currency",
    )
    order_count: int = Field(
        ge=0,
        default=0,
        description="Number of open orders",
    )
    # Grid strategy config
    lower_price: Decimal = Field(
        default=Decimal("0"),
        description="Grid lower price bound",
    )
    upper_price: Decimal = Field(
        default=Decimal("0"),
        description="Grid upper price bound",
    )
    num_grids: int = Field(
        default=0,
        description="Number of grid levels",
    )
    total_investment: Decimal = Field(
        default=Decimal("0"),
        description="Total investment amount",
    )


class OrderData(BaseModel):
    """Individual order data for expanded row details.

    Attributes:
        order_id: Unique order identifier.
        symbol: Trading pair symbol.
        side: Order side (buy or sell).
        price: Order price.
        amount: Order amount.
        filled: Amount filled so far.
        status: Order status.
    """

    order_id: str = Field(description="Unique order identifier")
    symbol: str = Field(description="Trading pair symbol")
    side: Literal["buy", "sell"] = Field(description="Order side")
    price: Decimal = Field(ge=0, description="Order price")
    amount: Decimal = Field(ge=0, description="Order amount")
    filled: Decimal = Field(ge=0, default=Decimal("0"), description="Amount filled")
    status: str = Field(default="open", description="Order status")


class TradeData(BaseModel):
    """Individual trade data for history.

    Attributes:
        trade_id: Unique trade identifier.
        symbol: Trading pair symbol.
        side: Trade side (buy or sell).
        price: Execution price.
        amount: Trade amount.
        cost: Total cost (price * amount).
        fee: Trading fee.
        timestamp: Trade execution timestamp.
    """

    trade_id: str = Field(description="Unique trade identifier")
    symbol: str = Field(description="Trading pair symbol")
    side: Literal["buy", "sell"] = Field(description="Trade side")
    price: Decimal = Field(ge=0, description="Execution price")
    amount: Decimal = Field(ge=0, description="Trade amount")
    cost: Decimal = Field(ge=0, description="Total cost (price * amount)")
    fee: Decimal = Field(ge=0, default=Decimal("0"), description="Trading fee")
    timestamp: datetime = Field(description="Trade execution timestamp")


class DashboardData(BaseModel):
    """Aggregated dashboard data for main view.

    Attributes:
        health: Bot health status.
        pairs: List of all trading pair data.
        total_pnl: Total P&L across all pairs.
        total_pnl_percent: Total P&L percentage.
        last_update: Timestamp of last successful data fetch.
        is_stale: Whether data is stale (older than expected refresh).
    """

    health: HealthResponse | None = Field(
        default=None,
        description="Bot health status",
    )
    pairs: list[PairData] = Field(
        default_factory=list,
        description="All trading pair data",
    )
    total_pnl: Decimal = Field(
        default=Decimal("0"),
        description="Total P&L across all pairs",
    )
    total_pnl_percent: Decimal = Field(
        default=Decimal("0"),
        description="Total P&L percentage",
    )
    last_update: datetime | None = Field(
        default=None,
        description="Timestamp of last successful data fetch",
    )
    is_stale: bool = Field(
        default=False,
        description="Whether data is stale (older than expected refresh)",
    )

    @property
    def pair_count(self) -> int:
        """Return the number of trading pairs."""
        return len(self.pairs)

    @property
    def is_healthy(self) -> bool:
        """Return True if bot health status is healthy."""
        return self.health is not None and self.health.status == "healthy"


class PnLBreakdown(BaseModel):
    """Separated P&L for professional display.

    Attributes:
        realized_pnl: Locked-in grid profits from completed cycles.
        unrealized_pnl: Mark-to-market floating P&L on open positions.
        total_pnl: Sum of realized + unrealized P&L.
    """

    realized_pnl: Decimal = Field(
        default=Decimal("0"),
        description="Locked-in grid profits",
    )
    unrealized_pnl: Decimal = Field(
        default=Decimal("0"),
        description="Mark-to-market floating P&L",
    )
    total_pnl: Decimal = Field(
        default=Decimal("0"),
        description="Sum of realized + unrealized",
    )


# Grid Visualization Models (Story 10.1)


class GridLevel(BaseModel):
    """Single grid level for grid trading visualization.

    Attributes:
        price: Grid level price.
        side: Buy or sell level.
        status: Current status of the order at this level.
        order_id: Associated order ID if any.
    """

    price: Decimal = Field(ge=0, description="Grid level price")
    side: Literal["buy", "sell"] = Field(description="Grid level side")
    status: Literal["open", "filled", "canceled"] = Field(
        default="open", description="Level status"
    )
    order_id: str | None = Field(default=None, description="Associated order ID")


class GridConfig(BaseModel):
    """Grid configuration for a trading pair.

    Attributes:
        symbol: Trading pair symbol.
        levels: List of grid levels.
        current_price: Current market price.
        grid_spacing: Spacing between grid levels.
        total_levels: Total number of grid levels.
    """

    symbol: str = Field(description="Trading pair symbol")
    levels: list[GridLevel] = Field(default_factory=list, description="Grid levels")
    current_price: Decimal = Field(ge=0, description="Current market price")
    grid_spacing: Decimal = Field(ge=0, description="Grid level spacing")
    total_levels: int = Field(ge=0, description="Total number of levels")


# Bot Configuration Models (Story 10.2)


class PairConfig(BaseModel):
    """Configuration for a single trading pair.

    Attributes:
        symbol: Trading pair symbol.
        enabled: Whether trading is enabled for this pair.
        grid_levels: Number of grid levels.
        grid_spacing_pct: Grid spacing as percentage.
        order_size: Size of each order.
        max_position: Maximum position size.
    """

    symbol: str = Field(description="Trading pair symbol")
    enabled: bool = Field(default=True, description="Is trading enabled")
    grid_levels: int = Field(ge=1, description="Number of grid levels")
    grid_spacing_pct: Decimal = Field(ge=0, description="Grid spacing percentage")
    order_size: Decimal = Field(ge=0, description="Order size")
    max_position: Decimal = Field(ge=0, description="Maximum position size")


class RiskConfig(BaseModel):
    """Risk management configuration.

    Attributes:
        max_open_orders: Maximum number of open orders.
        max_daily_loss: Maximum daily loss limit.
        stop_loss_pct: Stop loss percentage (optional).
        take_profit_pct: Take profit percentage (optional).
    """

    max_open_orders: int = Field(ge=0, default=50, description="Max open orders")
    max_daily_loss: Decimal = Field(ge=0, default=Decimal("1000"), description="Max daily loss")
    stop_loss_pct: Decimal | None = Field(default=None, description="Stop loss percentage")
    take_profit_pct: Decimal | None = Field(default=None, description="Take profit percentage")


class BotConfig(BaseModel):
    """Complete bot configuration (read-only display).

    Attributes:
        bot_name: Name of the trading bot.
        version: Bot software version.
        exchange: Exchange being traded on.
        pairs: Configuration for each trading pair.
        risk: Risk management settings.
        api_timeout_ms: API timeout in milliseconds.
        poll_interval_ms: Polling interval in milliseconds.
    """

    bot_name: str = Field(default="CryptoTrader", description="Bot name")
    version: str = Field(default="1.0.0", description="Bot version")
    exchange: str = Field(default="Binance", description="Exchange name")
    pairs: list[PairConfig] = Field(default_factory=list, description="Pair configurations")
    risk: RiskConfig = Field(default_factory=RiskConfig, description="Risk settings")
    api_timeout_ms: int = Field(default=5000, description="API timeout (ms)")
    poll_interval_ms: int = Field(default=1000, description="Poll interval (ms)")
