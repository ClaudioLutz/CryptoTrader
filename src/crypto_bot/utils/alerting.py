"""Multi-channel alerting system for trading notifications.

This module provides:
- TelegramAlerter: Send alerts via Telegram Bot API
- DiscordAlerter: Send alerts via Discord webhooks
- AlertManager: Central coordinator with severity routing and rate limiting
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Protocol

import aiohttp
import structlog

logger = structlog.get_logger()


class AlertSeverity(str, Enum):
    """Alert severity levels for routing."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Protocol):
    """Protocol for alert channels."""

    async def connect(self) -> None:
        """Initialize the alert channel."""
        ...

    async def disconnect(self) -> None:
        """Close the alert channel."""
        ...

    async def send_message(self, text: str, **kwargs: Any) -> bool:
        """Send a text message."""
        ...


class TelegramAlerter:
    """Send alerts via Telegram Bot API.

    Usage:
        alerter = TelegramAlerter(bot_token="...", chat_id="...")
        await alerter.connect()
        await alerter.send_trade_alert("BUY", "BTC/USDT", Decimal("0.1"), Decimal("42000"), "ORD123")
        await alerter.disconnect()
    """

    def __init__(self, bot_token: str, chat_id: str):
        """Initialize Telegram alerter.

        Args:
            bot_token: Telegram bot token from @BotFather.
            chat_id: Chat ID to send messages to.
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        """Initialize HTTP session and verify bot token."""
        self._session = aiohttp.ClientSession()
        try:
            async with self._session.get(f"{self._base_url}/getMe") as resp:
                if resp.status != 200:
                    raise ValueError("Invalid Telegram bot token")
                data = await resp.json()
                if data.get("ok"):
                    logger.info(
                        "telegram_connected",
                        bot_username=data["result"]["username"],
                    )
                else:
                    raise ValueError(f"Telegram API error: {data}")
        except aiohttp.ClientError as e:
            logger.error("telegram_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> bool:
        """Send a text message.

        Args:
            text: Message text (supports HTML formatting).
            parse_mode: Parse mode ("HTML" or "Markdown").
            disable_notification: If True, send silently.

        Returns:
            True if message was sent successfully.
        """
        if not self._session:
            logger.error("telegram_not_connected")
            return False

        try:
            async with self._session.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                },
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error("telegram_send_failed", status=resp.status, error=error)
                    return False
                return True
        except aiohttp.ClientError as e:
            logger.error("telegram_error", error=str(e))
            return False

    async def send_trade_alert(
        self,
        side: str,
        symbol: str,
        amount: Decimal,
        price: Decimal,
        order_id: str,
    ) -> bool:
        """Send trade execution alert.

        Args:
            side: Trade side ("BUY" or "SELL").
            symbol: Trading pair symbol.
            amount: Trade amount.
            price: Execution price.
            order_id: Exchange order ID.

        Returns:
            True if alert was sent successfully.
        """
        emoji = "\U0001F7E2" if side.upper() == "BUY" else "\U0001F534"
        value = amount * price

        message = f"""{emoji} <b>{side.upper()}</b> {symbol}

<b>Amount:</b> {amount}
<b>Price:</b> ${price:,.2f}
<b>Value:</b> ${value:,.2f}
<b>Order ID:</b> <code>{order_id}</code>"""

        return await self.send_message(message)

    async def send_profit_alert(
        self,
        symbol: str,
        profit: Decimal,
        profit_pct: Decimal,
        total_profit: Decimal,
    ) -> bool:
        """Send profit notification.

        Args:
            symbol: Trading pair symbol.
            profit: Profit amount for this trade.
            profit_pct: Profit percentage.
            total_profit: Total accumulated profit.

        Returns:
            True if alert was sent successfully.
        """
        emoji = "\U0001F4B0" if profit > 0 else "\U0001F4C9"

        message = f"""{emoji} <b>Trade Closed</b> {symbol}

<b>Profit:</b> ${profit:,.2f} ({profit_pct:+.2%})
<b>Total Profit:</b> ${total_profit:,.2f}"""

        return await self.send_message(message)

    async def send_error_alert(
        self,
        error_type: str,
        error_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send error notification.

        Args:
            error_type: Type/category of error.
            error_message: Error description.
            context: Optional additional context.

        Returns:
            True if alert was sent successfully.
        """
        context_str = ""
        if context:
            context_str = "\n".join(f"<b>{k}:</b> {v}" for k, v in context.items())

        message = f"""\U0001F6A8 <b>ERROR</b>

<b>Type:</b> {error_type}
<b>Message:</b> {error_message}

{context_str}"""

        return await self.send_message(message.strip())

    async def send_circuit_breaker_alert(
        self,
        trigger: str,
        details: dict[str, Any],
    ) -> bool:
        """Send circuit breaker trigger notification.

        Args:
            trigger: What triggered the circuit breaker.
            details: Additional details about the trigger.

        Returns:
            True if alert was sent successfully.
        """
        details_str = "\n".join(f"<b>{k}:</b> {v}" for k, v in details.items())

        message = f"""\U0001F6D1 <b>CIRCUIT BREAKER TRIGGERED</b>

<b>Trigger:</b> {trigger}

{details_str}

Trading has been paused. Manual review required."""

        return await self.send_message(message)

    async def send_daily_summary(
        self,
        date: str,
        trades: int,
        profit: Decimal,
        profit_pct: Decimal,
        win_rate: Decimal,
    ) -> bool:
        """Send daily performance summary.

        Args:
            date: Date of the summary.
            trades: Number of trades.
            profit: Total profit for the day.
            profit_pct: Profit percentage.
            win_rate: Win rate (0-1).

        Returns:
            True if alert was sent successfully.
        """
        emoji = "\U0001F4C8" if profit > 0 else "\U0001F4C9"

        message = f"""{emoji} <b>Daily Summary</b> - {date}

<b>Trades:</b> {trades}
<b>Profit:</b> ${profit:,.2f} ({profit_pct:+.2%})
<b>Win Rate:</b> {win_rate:.1%}"""

        return await self.send_message(message)


class RateLimitedTelegramAlerter(TelegramAlerter):
    """Telegram alerter with rate limiting to prevent API bans."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        max_messages_per_minute: int = 20,
    ):
        """Initialize rate-limited Telegram alerter.

        Args:
            bot_token: Telegram bot token.
            chat_id: Chat ID to send messages to.
            max_messages_per_minute: Maximum messages allowed per minute.
        """
        super().__init__(bot_token, chat_id)
        self._max_per_minute = max_messages_per_minute
        self._message_times: deque[datetime] = deque(maxlen=max_messages_per_minute)

    async def send_message(self, text: str, **kwargs: Any) -> bool:
        """Send message with rate limiting.

        Args:
            text: Message text.
            **kwargs: Additional arguments passed to parent.

        Returns:
            True if message was sent, False if rate limited.
        """
        now = datetime.utcnow()

        # Remove old timestamps
        while self._message_times and (now - self._message_times[0]) > timedelta(minutes=1):
            self._message_times.popleft()

        # Check rate limit
        if len(self._message_times) >= self._max_per_minute:
            logger.warning("telegram_rate_limited", queued=len(self._message_times))
            return False

        self._message_times.append(now)
        return await super().send_message(text, **kwargs)


class DiscordAlerter:
    """Send alerts via Discord webhooks.

    Usage:
        alerter = DiscordAlerter(webhook_url="...")
        await alerter.connect()
        await alerter.send_trade_alert("BUY", "BTC/USDT", Decimal("0.1"), Decimal("42000"), "ORD123")
        await alerter.disconnect()
    """

    def __init__(self, webhook_url: str):
        """Initialize Discord alerter.

        Args:
            webhook_url: Discord webhook URL.
        """
        self._webhook_url = webhook_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        """Initialize HTTP session."""
        self._session = aiohttp.ClientSession()
        logger.info("discord_connected")

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def send_message(self, text: str, **kwargs: Any) -> bool:
        """Send a simple text message.

        Args:
            text: Message text.
            **kwargs: Ignored (for protocol compatibility).

        Returns:
            True if message was sent successfully.
        """
        if not self._session:
            logger.error("discord_not_connected")
            return False

        try:
            async with self._session.post(
                self._webhook_url,
                json={"content": text},
            ) as resp:
                return resp.status in (200, 204)
        except aiohttp.ClientError as e:
            logger.error("discord_error", error=str(e))
            return False

    async def send_embed(
        self,
        title: str,
        description: str,
        color: int = 0x00FF00,
        fields: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        """Send a Discord embed message.

        Args:
            title: Embed title.
            description: Embed description.
            color: Embed color (hex).
            fields: Optional list of field dicts with name, value, inline.

        Returns:
            True if message was sent successfully.
        """
        if not self._session:
            logger.error("discord_not_connected")
            return False

        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if fields:
            embed["fields"] = [
                {
                    "name": f["name"],
                    "value": str(f["value"]),
                    "inline": f.get("inline", True),
                }
                for f in fields
            ]

        try:
            async with self._session.post(
                self._webhook_url,
                json={"embeds": [embed]},
            ) as resp:
                if resp.status not in (200, 204):
                    error = await resp.text()
                    logger.error("discord_send_failed", status=resp.status, error=error)
                    return False
                return True
        except aiohttp.ClientError as e:
            logger.error("discord_error", error=str(e))
            return False

    async def send_trade_alert(
        self,
        side: str,
        symbol: str,
        amount: Decimal,
        price: Decimal,
        order_id: str,
    ) -> bool:
        """Send trade execution alert.

        Args:
            side: Trade side ("BUY" or "SELL").
            symbol: Trading pair symbol.
            amount: Trade amount.
            price: Execution price.
            order_id: Exchange order ID.

        Returns:
            True if alert was sent successfully.
        """
        color = 0x00FF00 if side.upper() == "BUY" else 0xFF0000
        value = amount * price

        return await self.send_embed(
            title=f"{side.upper()} {symbol}",
            description="Order executed successfully",
            color=color,
            fields=[
                {"name": "Amount", "value": str(amount)},
                {"name": "Price", "value": f"${price:,.2f}"},
                {"name": "Value", "value": f"${value:,.2f}"},
                {"name": "Order ID", "value": order_id, "inline": False},
            ],
        )

    async def send_profit_alert(
        self,
        symbol: str,
        profit: Decimal,
        profit_pct: Decimal,
        total_profit: Decimal,
    ) -> bool:
        """Send profit notification."""
        color = 0x00FF00 if profit > 0 else 0xFF0000

        return await self.send_embed(
            title=f"Trade Closed - {symbol}",
            description="Position closed",
            color=color,
            fields=[
                {"name": "Profit", "value": f"${profit:,.2f}"},
                {"name": "Profit %", "value": f"{profit_pct:+.2%}"},
                {"name": "Total Profit", "value": f"${total_profit:,.2f}"},
            ],
        )

    async def send_error_alert(
        self,
        error_type: str,
        error_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send error notification."""
        fields = [
            {"name": "Type", "value": error_type},
            {"name": "Message", "value": error_message, "inline": False},
        ]

        if context:
            for key, value in context.items():
                fields.append({"name": key, "value": str(value)})

        return await self.send_embed(
            title="\U0001F6A8 Error",
            description="An error occurred in the trading bot",
            color=0xFF0000,
            fields=fields,
        )

    async def send_circuit_breaker_alert(
        self,
        trigger: str,
        details: dict[str, Any],
    ) -> bool:
        """Send circuit breaker trigger notification."""
        fields = [{"name": "Trigger", "value": trigger}]
        for key, value in details.items():
            fields.append({"name": key, "value": str(value)})

        return await self.send_embed(
            title="\U0001F6D1 CIRCUIT BREAKER TRIGGERED",
            description="Trading has been paused. Manual review required.",
            color=0xFF0000,
            fields=fields,
        )

    async def send_daily_summary(
        self,
        date: str,
        trades: int,
        profit: Decimal,
        profit_pct: Decimal,
        win_rate: Decimal,
    ) -> bool:
        """Send daily performance summary."""
        color = 0x00FF00 if profit > 0 else 0xFF0000

        return await self.send_embed(
            title=f"Daily Summary - {date}",
            description="End of day trading report",
            color=color,
            fields=[
                {"name": "Trades", "value": str(trades)},
                {"name": "Profit", "value": f"${profit:,.2f}"},
                {"name": "Profit %", "value": f"{profit_pct:+.2%}"},
                {"name": "Win Rate", "value": f"{win_rate:.1%}"},
            ],
        )


@dataclass
class AlertConfig:
    """Configuration for AlertManager."""

    telegram_enabled: bool = True
    discord_enabled: bool = True
    min_severity: AlertSeverity = AlertSeverity.INFO
    rate_limit_per_minute: int = 30
    suppress_duplicates_seconds: int = 60


class AlertManager:
    """Central manager for coordinating all alert channels.

    Features:
    - Multiple channel support (Telegram, Discord)
    - Severity-based routing
    - Rate limiting
    - Duplicate suppression

    Usage:
        manager = AlertManager(config)
        manager.add_channel("telegram", telegram_alerter)
        manager.add_channel("discord", discord_alerter)
        await manager.connect_all()
        await manager.send_error("API Error", "Connection timeout", context={"endpoint": "/orders"})
    """

    def __init__(self, config: Optional[AlertConfig] = None):
        """Initialize alert manager.

        Args:
            config: Alert configuration. Uses defaults if not provided.
        """
        self._config = config or AlertConfig()
        self._channels: dict[str, AlertChannel] = {}
        self._severity_channels: dict[AlertSeverity, list[str]] = {
            AlertSeverity.INFO: ["telegram"],
            AlertSeverity.WARNING: ["telegram", "discord"],
            AlertSeverity.ERROR: ["telegram", "discord"],
            AlertSeverity.CRITICAL: ["telegram", "discord"],
        }
        self._recent_alerts: dict[str, datetime] = {}
        self._message_times: deque[datetime] = deque(maxlen=self._config.rate_limit_per_minute)

    def add_channel(self, name: str, channel: AlertChannel) -> None:
        """Add an alert channel.

        Args:
            name: Channel identifier (e.g., "telegram", "discord").
            channel: Alert channel instance.
        """
        self._channels[name] = channel

    def configure_severity_routing(
        self,
        severity: AlertSeverity,
        channels: list[str],
    ) -> None:
        """Configure which channels receive alerts for a severity level.

        Args:
            severity: Alert severity level.
            channels: List of channel names to route to.
        """
        self._severity_channels[severity] = channels

    async def connect_all(self) -> None:
        """Connect all configured channels."""
        for name, channel in self._channels.items():
            try:
                await channel.connect()
                logger.info("alert_channel_connected", channel=name)
            except Exception as e:
                logger.error("alert_channel_failed", channel=name, error=str(e))

    async def disconnect_all(self) -> None:
        """Disconnect all channels."""
        for name, channel in self._channels.items():
            try:
                await channel.disconnect()
            except Exception as e:
                logger.error("alert_channel_disconnect_error", channel=name, error=str(e))

    async def send(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        context: Optional[dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
    ) -> bool:
        """Send alert to appropriate channels based on severity.

        Args:
            severity: Alert severity level.
            title: Alert title.
            message: Alert message body.
            context: Optional additional context.
            dedupe_key: Optional key for duplicate suppression.

        Returns:
            True if alert was sent to at least one channel.
        """
        # Check severity threshold
        if self._severity_value(severity) < self._severity_value(self._config.min_severity):
            return True

        # Check rate limit
        now = datetime.utcnow()
        while self._message_times and (now - self._message_times[0]) > timedelta(minutes=1):
            self._message_times.popleft()

        if len(self._message_times) >= self._config.rate_limit_per_minute:
            logger.warning("alert_rate_limited")
            return False

        # Check duplicate suppression
        if dedupe_key:
            last_sent = self._recent_alerts.get(dedupe_key)
            if last_sent:
                if (now - last_sent).total_seconds() < self._config.suppress_duplicates_seconds:
                    logger.debug("alert_suppressed_duplicate", key=dedupe_key)
                    return True
            self._recent_alerts[dedupe_key] = now

        # Format message
        full_message = self._format_message(severity, title, message, context)

        # Send to appropriate channels
        channels = self._severity_channels.get(severity, [])
        success = False

        for channel_name in channels:
            if channel_name not in self._channels:
                continue

            # Check if channel is enabled
            if channel_name == "telegram" and not self._config.telegram_enabled:
                continue
            if channel_name == "discord" and not self._config.discord_enabled:
                continue

            try:
                result = await self._channels[channel_name].send_message(full_message)
                if result:
                    success = True
                    self._message_times.append(now)
            except Exception as e:
                logger.error(
                    "alert_send_failed",
                    channel=channel_name,
                    error=str(e),
                )

        return success

    def _severity_value(self, severity: AlertSeverity) -> int:
        """Get numeric value for severity comparison."""
        return {
            AlertSeverity.INFO: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.ERROR: 2,
            AlertSeverity.CRITICAL: 3,
        }[severity]

    def _format_message(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        context: Optional[dict[str, Any]],
    ) -> str:
        """Format alert message with severity indicator."""
        severity_emoji = {
            AlertSeverity.INFO: "\u2139\ufe0f",
            AlertSeverity.WARNING: "\u26a0\ufe0f",
            AlertSeverity.ERROR: "\u274c",
            AlertSeverity.CRITICAL: "\U0001F6A8",
        }

        parts = [f"{severity_emoji[severity]} <b>{title}</b>", "", message]

        if context:
            parts.append("")
            for key, value in context.items():
                parts.append(f"<b>{key}:</b> {value}")

        return "\n".join(parts)

    # Convenience methods
    async def send_info(
        self,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send info-level alert."""
        return await self.send(AlertSeverity.INFO, title, message, **kwargs)

    async def send_warning(
        self,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send warning-level alert."""
        return await self.send(AlertSeverity.WARNING, title, message, **kwargs)

    async def send_error(
        self,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send error-level alert."""
        return await self.send(AlertSeverity.ERROR, title, message, **kwargs)

    async def send_critical(
        self,
        title: str,
        message: str,
        **kwargs: Any,
    ) -> bool:
        """Send critical-level alert."""
        return await self.send(AlertSeverity.CRITICAL, title, message, **kwargs)

    async def send_trade_alert(
        self,
        side: str,
        symbol: str,
        amount: Decimal,
        price: Decimal,
        order_id: str,
    ) -> bool:
        """Send trade execution alert to all channels."""
        success = True
        for name, channel in self._channels.items():
            if hasattr(channel, "send_trade_alert"):
                try:
                    result = await channel.send_trade_alert(side, symbol, amount, price, order_id)
                    if not result:
                        success = False
                except Exception as e:
                    logger.error("trade_alert_failed", channel=name, error=str(e))
                    success = False
        return success

    async def send_circuit_breaker_alert(
        self,
        trigger: str,
        details: dict[str, Any],
    ) -> bool:
        """Send circuit breaker alert to all channels."""
        success = True
        for name, channel in self._channels.items():
            if hasattr(channel, "send_circuit_breaker_alert"):
                try:
                    result = await channel.send_circuit_breaker_alert(trigger, details)
                    if not result:
                        success = False
                except Exception as e:
                    logger.error("circuit_breaker_alert_failed", channel=name, error=str(e))
                    success = False
        return success


def create_alert_manager(
    telegram_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    discord_webhook: Optional[str] = None,
    config: Optional[AlertConfig] = None,
) -> AlertManager:
    """Factory function to create a configured AlertManager.

    Args:
        telegram_token: Telegram bot token.
        telegram_chat_id: Telegram chat ID.
        discord_webhook: Discord webhook URL.
        config: Optional alert configuration.

    Returns:
        Configured AlertManager instance.
    """
    manager = AlertManager(config)

    if telegram_token and telegram_chat_id:
        telegram = RateLimitedTelegramAlerter(telegram_token, telegram_chat_id)
        manager.add_channel("telegram", telegram)

    if discord_webhook:
        discord = DiscordAlerter(discord_webhook)
        manager.add_channel("discord", discord)

    return manager
