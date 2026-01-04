"""Health check server and performance dashboard API.

This module provides:
- HealthCheckServer: HTTP server for health/readiness probes
- Metrics endpoint for monitoring systems
- Dashboard data API for trading performance visualization
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from aiohttp import web
import structlog

logger = structlog.get_logger()


class HealthCheckServer:
    """HTTP server providing health check endpoints and dashboard API.

    Endpoints:
    - GET /health - Basic liveness probe (is the process running?)
    - GET /ready - Readiness probe (is the bot ready to trade?)
    - GET /metrics - JSON metrics for monitoring
    - GET /metrics/prometheus - Prometheus-format metrics
    - GET /api/trades - Recent trade history
    - GET /api/positions - Current open positions
    - GET /api/pnl - P&L summary
    - GET /api/equity - Equity curve data

    Usage:
        server = HealthCheckServer(host="0.0.0.0", port=8080)
        server.set_bot(trading_bot)
        await server.start()
        # ... bot runs ...
        await server.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        """Initialize health check server.

        Args:
            host: Host to bind to.
            port: Port to listen on.
        """
        self._host = host
        self._port = port
        self._app = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._bot: Any = None
        self._database: Any = None
        self._last_heartbeat = datetime.utcnow()
        self._start_time = datetime.utcnow()

        # Setup routes
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Configure HTTP routes."""
        # Health check endpoints
        self._app.router.add_get("/health", self._health_handler)
        self._app.router.add_get("/ready", self._ready_handler)
        self._app.router.add_get("/metrics", self._metrics_handler)
        self._app.router.add_get("/metrics/prometheus", self._prometheus_handler)

        # Dashboard API endpoints
        self._app.router.add_get("/api/trades", self._trades_handler)
        self._app.router.add_get("/api/positions", self._positions_handler)
        self._app.router.add_get("/api/pnl", self._pnl_handler)
        self._app.router.add_get("/api/equity", self._equity_handler)
        self._app.router.add_get("/api/status", self._status_handler)

    def set_bot(self, bot: Any) -> None:
        """Set reference to trading bot for status checks.

        Args:
            bot: Trading bot instance.
        """
        self._bot = bot

    def set_database(self, database: Any) -> None:
        """Set database for querying trade data.

        Args:
            database: Database instance.
        """
        self._database = database

    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp.

        Should be called periodically from the main trading loop.
        """
        self._last_heartbeat = datetime.utcnow()

    async def start(self) -> None:
        """Start health check server."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info(
            "health_server_started",
            host=self._host,
            port=self._port,
        )

    async def stop(self) -> None:
        """Stop health check server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("health_server_stopped")

    # Health check handlers
    async def _health_handler(self, request: web.Request) -> web.Response:
        """Basic health check - is the process alive?"""
        return web.json_response({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
        })

    async def _ready_handler(self, request: web.Request) -> web.Response:
        """Readiness check - is the bot ready to trade?"""
        if not self._bot:
            return web.json_response(
                {"status": "not_ready", "reason": "Bot not initialized"},
                status=503,
            )

        # Check if bot is running
        is_running = getattr(self._bot, "_running", False)

        # Check heartbeat (stale if > 60 seconds)
        heartbeat_age = (datetime.utcnow() - self._last_heartbeat).total_seconds()
        is_stale = heartbeat_age > 60

        if not is_running:
            return web.json_response(
                {"status": "not_ready", "reason": "Bot not running"},
                status=503,
            )

        if is_stale:
            return web.json_response(
                {
                    "status": "not_ready",
                    "reason": f"Heartbeat stale ({heartbeat_age:.0f}s)",
                },
                status=503,
            )

        return web.json_response({
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "heartbeat_age_seconds": heartbeat_age,
        })

    async def _metrics_handler(self, request: web.Request) -> web.Response:
        """Return current metrics for monitoring."""
        metrics: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "heartbeat_age_seconds": (
                datetime.utcnow() - self._last_heartbeat
            ).total_seconds(),
        }

        if self._bot:
            metrics["bot_running"] = getattr(self._bot, "_running", False)

            # Get strategy info
            if hasattr(self._bot, "_strategy") and self._bot._strategy:
                strategy = self._bot._strategy
                metrics["strategy"] = {
                    "name": getattr(strategy, "name", "unknown"),
                    "symbol": getattr(strategy, "symbol", "unknown"),
                }

                # Get strategy-specific metrics if available
                if hasattr(strategy, "get_statistics"):
                    stats = strategy.get_statistics()
                    metrics["strategy_stats"] = {
                        "total_profit": str(stats.total_profit),
                        "total_fees": str(stats.total_fees),
                        "completed_cycles": stats.completed_cycles,
                        "active_buy_orders": stats.active_buy_orders,
                        "active_sell_orders": stats.active_sell_orders,
                    }

            # Get risk metrics
            if hasattr(self._bot, "_risk_manager") and self._bot._risk_manager:
                risk = self._bot._risk_manager
                if hasattr(risk, "get_risk_metrics"):
                    metrics["risk"] = risk.get_risk_metrics()
        else:
            metrics["bot_running"] = False

        return web.json_response(metrics)

    async def _prometheus_handler(self, request: web.Request) -> web.Response:
        """Export metrics in Prometheus format."""
        lines = []

        # Uptime
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        lines.append(f"trading_bot_uptime_seconds {uptime}")

        # Heartbeat age
        heartbeat_age = (datetime.utcnow() - self._last_heartbeat).total_seconds()
        lines.append(f"trading_bot_heartbeat_age_seconds {heartbeat_age}")

        # Bot status
        is_running = 1 if self._bot and getattr(self._bot, "_running", False) else 0
        lines.append(f"trading_bot_running {is_running}")

        if self._bot:
            # Risk metrics
            if hasattr(self._bot, "_risk_manager") and self._bot._risk_manager:
                risk = self._bot._risk_manager

                if hasattr(risk, "_circuit_breaker"):
                    cb = risk._circuit_breaker
                    tripped = 1 if not cb.is_trading_allowed else 0
                    lines.append(f"trading_bot_circuit_breaker_tripped {tripped}")

                    if hasattr(cb, "_state"):
                        lines.append(
                            f"trading_bot_consecutive_losses {cb._state.consecutive_losses}"
                        )

            # Strategy metrics
            if hasattr(self._bot, "_strategy") and self._bot._strategy:
                strategy = self._bot._strategy
                if hasattr(strategy, "get_statistics"):
                    stats = strategy.get_statistics()
                    lines.append(
                        f"trading_bot_completed_cycles {stats.completed_cycles}"
                    )
                    lines.append(
                        f"trading_bot_active_orders {stats.active_buy_orders + stats.active_sell_orders}"
                    )

        return web.Response(
            text="\n".join(lines),
            content_type="text/plain",
        )

    # Dashboard API handlers
    async def _trades_handler(self, request: web.Request) -> web.Response:
        """Get recent trades."""
        if not self._database:
            return web.json_response(
                {"error": "Database not configured"},
                status=503,
            )

        limit = int(request.query.get("limit", "100"))
        symbol = request.query.get("symbol")

        try:
            from crypto_bot.data.persistence import TradeRepository

            async with self._database.session() as session:
                repo = TradeRepository(session)
                trades = await repo.get_trade_history(
                    symbol=symbol,
                    limit=limit,
                )

            return web.json_response({
                "trades": [
                    {
                        "id": str(t.id),
                        "symbol": t.symbol,
                        "side": t.side,
                        "amount": str(t.amount),
                        "open_rate": str(t.open_rate),
                        "close_rate": str(t.close_rate) if t.close_rate else None,
                        "profit": str(t.profit) if t.profit else None,
                        "profit_pct": str(t.profit_pct) if t.profit_pct else None,
                        "open_date": t.open_date.isoformat() if t.open_date else None,
                        "close_date": t.close_date.isoformat() if t.close_date else None,
                        "status": t.status,
                    }
                    for t in trades
                ]
            })
        except Exception as e:
            logger.error("trades_api_error", error=str(e))
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _positions_handler(self, request: web.Request) -> web.Response:
        """Get current open positions."""
        if not self._database:
            return web.json_response(
                {"error": "Database not configured"},
                status=503,
            )

        try:
            from crypto_bot.data.persistence import TradeRepository

            async with self._database.session() as session:
                repo = TradeRepository(session)
                positions = await repo.get_open_trades()

            # Try to get current prices for unrealized P&L
            current_prices: dict[str, Decimal] = {}
            if self._bot and hasattr(self._bot, "_exchange"):
                for p in positions:
                    if p.symbol not in current_prices:
                        try:
                            ticker = await self._bot._exchange.fetch_ticker(p.symbol)
                            current_prices[p.symbol] = ticker.last
                        except Exception:
                            pass

            return web.json_response({
                "positions": [
                    {
                        "id": str(p.id),
                        "symbol": p.symbol,
                        "side": p.side,
                        "amount": str(p.amount),
                        "entry_price": str(p.open_rate),
                        "current_price": str(current_prices.get(p.symbol, p.open_rate)),
                        "unrealized_pnl": str(
                            self._calculate_unrealized_pnl(
                                p, current_prices.get(p.symbol)
                            )
                        ),
                        "open_date": p.open_date.isoformat() if p.open_date else None,
                    }
                    for p in positions
                ]
            })
        except Exception as e:
            logger.error("positions_api_error", error=str(e))
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    def _calculate_unrealized_pnl(
        self,
        position: Any,
        current_price: Optional[Decimal],
    ) -> Decimal:
        """Calculate unrealized P&L for a position."""
        if not current_price:
            return Decimal("0")

        if position.side == "buy":
            return (current_price - position.open_rate) * position.amount
        else:
            return (position.open_rate - current_price) * position.amount

    async def _pnl_handler(self, request: web.Request) -> web.Response:
        """Get P&L summary."""
        if not self._database:
            return web.json_response(
                {"error": "Database not configured"},
                status=503,
            )

        period = request.query.get("period", "daily")

        try:
            from crypto_bot.data.persistence import TradeRepository

            # Determine start date based on period
            now = datetime.utcnow()
            if period == "daily":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "weekly":
                start_date = now - timedelta(days=7)
            elif period == "monthly":
                start_date = now - timedelta(days=30)
            else:
                start_date = None

            async with self._database.session() as session:
                repo = TradeRepository(session)
                trades = await repo.get_trade_history(
                    start_date=start_date,
                    limit=10000,
                )

            # Calculate metrics
            closed_trades = [t for t in trades if t.close_date and t.profit is not None]
            total_pnl = sum(t.profit for t in closed_trades)
            winning = [t for t in closed_trades if t.profit > 0]
            losing = [t for t in closed_trades if t.profit < 0]

            return web.json_response({
                "period": period,
                "start_date": start_date.isoformat() if start_date else None,
                "total_trades": len(closed_trades),
                "winning_trades": len(winning),
                "losing_trades": len(losing),
                "win_rate": len(winning) / len(closed_trades) if closed_trades else 0,
                "total_pnl": str(total_pnl),
                "gross_profit": str(sum(t.profit for t in winning)),
                "gross_loss": str(sum(t.profit for t in losing)),
                "average_win": str(
                    sum(t.profit for t in winning) / len(winning) if winning else 0
                ),
                "average_loss": str(
                    sum(t.profit for t in losing) / len(losing) if losing else 0
                ),
            })
        except Exception as e:
            logger.error("pnl_api_error", error=str(e))
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _equity_handler(self, request: web.Request) -> web.Response:
        """Get equity curve data."""
        if not self._database:
            return web.json_response(
                {"error": "Database not configured"},
                status=503,
            )

        days = int(request.query.get("days", "30"))

        try:
            from sqlalchemy import select
            from crypto_bot.data.models import BalanceSnapshot

            start_date = datetime.utcnow() - timedelta(days=days)

            async with self._database.session() as session:
                result = await session.execute(
                    select(BalanceSnapshot)
                    .where(BalanceSnapshot.timestamp >= start_date)
                    .order_by(BalanceSnapshot.timestamp)
                )
                snapshots = result.scalars().all()

            return web.json_response({
                "equity_curve": [
                    {
                        "timestamp": s.timestamp.isoformat(),
                        "equity": str(s.total),
                    }
                    for s in snapshots
                ]
            })
        except Exception as e:
            logger.error("equity_api_error", error=str(e))
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def _status_handler(self, request: web.Request) -> web.Response:
        """Get comprehensive bot status."""
        status: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "server": {
                "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
                "heartbeat_age_seconds": (
                    datetime.utcnow() - self._last_heartbeat
                ).total_seconds(),
            },
        }

        if self._bot:
            status["bot"] = {
                "running": getattr(self._bot, "_running", False),
                "dry_run": getattr(self._bot, "_dry_run", True),
            }

            # Strategy info
            if hasattr(self._bot, "_strategy") and self._bot._strategy:
                strategy = self._bot._strategy
                status["strategy"] = {
                    "name": getattr(strategy, "name", "unknown"),
                    "symbol": getattr(strategy, "symbol", "unknown"),
                }

                if hasattr(strategy, "get_statistics"):
                    stats = strategy.get_statistics()
                    status["strategy"]["statistics"] = {
                        "total_profit": str(stats.total_profit),
                        "completed_cycles": stats.completed_cycles,
                    }

            # Exchange info
            if hasattr(self._bot, "_exchange"):
                status["exchange"] = {
                    "connected": True,
                    "name": getattr(self._bot._exchange, "name", "unknown"),
                }

            # Risk info
            if hasattr(self._bot, "_risk_manager") and self._bot._risk_manager:
                risk = self._bot._risk_manager
                status["risk"] = {
                    "trading_allowed": getattr(risk, "is_trading_allowed", True),
                }
                if hasattr(risk, "get_risk_metrics"):
                    status["risk"]["metrics"] = risk.get_risk_metrics()
        else:
            status["bot"] = {"running": False}

        return web.json_response(status)


def create_health_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    bot: Any = None,
    database: Any = None,
) -> HealthCheckServer:
    """Factory function to create a configured HealthCheckServer.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        bot: Optional trading bot reference.
        database: Optional database reference.

    Returns:
        Configured HealthCheckServer instance.
    """
    server = HealthCheckServer(host=host, port=port)

    if bot:
        server.set_bot(bot)

    if database:
        server.set_database(database)

    return server
