# Epic: Phase 4A - Operational Monitoring & Alerting

**Epic Owner:** Development Team
**Priority:** High - Production readiness
**Dependencies:** Phase 2 (Bot Orchestrator), Phase 3 (Risk Management)

---

## Overview

Production monitoring ensures the trading bot operates reliably and issues are detected before they compound. This epic implements structured logging, multi-channel alerting (Telegram, Discord), health checks, and performance dashboards.

### Key Deliverables
- Production-ready structured logging with structlog
- Telegram and Discord alert integrations
- Alert manager with severity routing and rate limiting
- Health check endpoints for monitoring
- Performance data API for dashboards

### Research & Best Practices Applied

Based on current 2025 best practices:
- **Structured Logging:** [JSON output with structlog](https://www.structlog.org/en/stable/logging-best-practices.html) for log aggregation
- **Context Variables:** [Request-scoped context](https://betterstack.com/community/guides/logging/structlog/) for async operations
- **Alerting:** [Multi-channel delivery](https://github.com/freqtrade/freqtrade) (Telegram, Discord, webhooks)
- **Performance:** [Cache loggers](https://www.structlog.org/en/stable/performance.html), use orjson for speed

---

## Story 4.1: Configure Production Logging with structlog

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** operator
**I want** structured JSON logs with trade context
**So that** issues can be diagnosed quickly and logs integrate with aggregation tools

### Background
Per [structlog best practices](https://www.structlog.org/en/stable/logging-best-practices.html), production logs should be JSON for machine parsing, with context variables for request/trade tracking.

### Acceptance Criteria

- [ ] Update `src/crypto_bot/config/logging_config.py`
- [ ] Implement production-optimized configuration:
  ```python
  import logging
  import sys
  from typing import Optional
  import structlog
  from structlog.typing import Processor

  try:
      import orjson
      JSON_SERIALIZER = orjson.dumps
      LOGGER_FACTORY = structlog.BytesLoggerFactory()
  except ImportError:
      import json
      JSON_SERIALIZER = json.dumps
      LOGGER_FACTORY = structlog.PrintLoggerFactory()

  def configure_logging(
      log_level: str = "INFO",
      json_output: bool = True,
      log_file: Optional[str] = None,
  ) -> None:
      """Configure structured logging for production."""

      # Build processor chain
      processors: list[Processor] = [
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
          processors.append(
              structlog.processors.JSONRenderer(serializer=JSON_SERIALIZER)
          )
      else:
          processors.append(
              structlog.dev.ConsoleRenderer(colors=True, exception_formatter=structlog.dev.plain_traceback)
          )

      structlog.configure(
          processors=processors,
          wrapper_class=structlog.make_filtering_bound_logger(
              getattr(logging, log_level.upper())
          ),
          context_class=dict,
          logger_factory=LOGGER_FACTORY,
          cache_logger_on_first_use=True,
      )
  ```
- [ ] Implement secret redaction processor:
  ```python
  SENSITIVE_KEYS = frozenset({
      "api_key", "api_secret", "password", "token", "secret",
      "authorization", "credential", "private_key",
  })

  SENSITIVE_PATTERNS = frozenset({
      "key", "secret", "token", "password", "credential",
  })

  def redact_secrets(
      logger: structlog.types.WrappedLogger,
      method_name: str,
      event_dict: dict,
  ) -> dict:
      """Redact sensitive values from log output."""
      for key, value in list(event_dict.items()):
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
          if isinstance(value, dict):
              event_dict[key] = _redact_dict(value)

      return event_dict

  def _redact_dict(d: dict) -> dict:
      """Recursively redact sensitive values in nested dicts."""
      result = {}
      for key, value in d.items():
          if any(p in key.lower() for p in SENSITIVE_PATTERNS):
              result[key] = "***REDACTED***"
          elif isinstance(value, dict):
              result[key] = _redact_dict(value)
          else:
              result[key] = value
      return result
  ```
- [ ] Implement context binding for trades:
  ```python
  import structlog
  from contextvars import ContextVar

  # Context variables for request/trade tracking
  trade_context: ContextVar[dict] = ContextVar("trade_context", default={})

  def bind_trade_context(
      trade_id: Optional[str] = None,
      order_id: Optional[str] = None,
      symbol: Optional[str] = None,
      strategy: Optional[str] = None,
  ) -> None:
      """Bind trade context for all subsequent logs."""
      ctx = {}
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

  # Context manager for automatic cleanup
  from contextlib import contextmanager

  @contextmanager
  def trade_logging_context(**kwargs):
      """Context manager for trade-scoped logging."""
      bind_trade_context(**kwargs)
      try:
          yield
      finally:
          clear_trade_context()
  ```
- [ ] Add file logging with rotation:
  ```python
  import logging.handlers

  def add_file_handler(
      log_file: str,
      max_bytes: int = 10_000_000,  # 10MB
      backup_count: int = 5,
  ) -> None:
      """Add rotating file handler for persistent logs."""
      handler = logging.handlers.RotatingFileHandler(
          log_file,
          maxBytes=max_bytes,
          backupCount=backup_count,
      )
      handler.setFormatter(logging.Formatter("%(message)s"))
      logging.getLogger().addHandler(handler)
  ```
- [ ] Write tests verifying secret redaction

### Technical Notes
- orjson provides 10x faster JSON serialization
- `cache_logger_on_first_use=True` improves performance
- Context variables work correctly with asyncio
- Rotate log files to prevent disk filling

### Definition of Done
- Production logging configured with JSON output
- Secret redaction working for all sensitive keys
- Context binding works across async calls
- File rotation configured
- Tests verify redaction

---

## Story 4.2: Build Telegram Alert Integration

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** trader
**I want** real-time Telegram notifications
**So that** I'm informed of important events immediately

### Background
[Telegram bots](https://github.com/freqtrade/freqtrade) are the standard for trading bot notifications. The python-telegram-bot library provides async support.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/alerting.py`
- [ ] Implement TelegramAlerter:
  ```python
  import aiohttp
  from typing import Optional
  from decimal import Decimal
  import structlog

  logger = structlog.get_logger()

  class TelegramAlerter:
      """Send alerts via Telegram Bot API."""

      def __init__(self, bot_token: str, chat_id: str):
          self._bot_token = bot_token
          self._chat_id = chat_id
          self._base_url = f"https://api.telegram.org/bot{bot_token}"
          self._session: Optional[aiohttp.ClientSession] = None

      async def connect(self) -> None:
          """Initialize HTTP session."""
          self._session = aiohttp.ClientSession()
          # Verify bot is working
          async with self._session.get(f"{self._base_url}/getMe") as resp:
              if resp.status != 200:
                  raise ValueError("Invalid Telegram bot token")
              data = await resp.json()
              logger.info("telegram_connected", bot_username=data["result"]["username"])

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
          """Send a text message."""
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
          except Exception as e:
              logger.error("telegram_error", error=str(e))
              return False
  ```
- [ ] Implement formatted alert messages:
  ```python
  async def send_trade_alert(
      self,
      side: str,
      symbol: str,
      amount: Decimal,
      price: Decimal,
      order_id: str,
  ) -> bool:
      """Send trade execution alert."""
      emoji = "\U0001F7E2" if side.lower() == "buy" else "\U0001F534"  # Green/Red circle

      message = f"""
  {emoji} <b>{side.upper()}</b> {symbol}

  <b>Amount:</b> {amount}
  <b>Price:</b> ${price:,.2f}
  <b>Value:</b> ${amount * price:,.2f}
  <b>Order ID:</b> <code>{order_id}</code>
  """
      return await self.send_message(message.strip())

  async def send_profit_alert(
      self,
      symbol: str,
      profit: Decimal,
      profit_pct: Decimal,
      total_profit: Decimal,
  ) -> bool:
      """Send profit notification."""
      emoji = "\U0001F4B0" if profit > 0 else "\U0001F4C9"  # Money bag or chart down

      message = f"""
  {emoji} <b>Trade Closed</b> {symbol}

  <b>Profit:</b> ${profit:,.2f} ({profit_pct:+.2%})
  <b>Total Profit:</b> ${total_profit:,.2f}
  """
      return await self.send_message(message.strip())

  async def send_error_alert(
      self,
      error_type: str,
      error_message: str,
      context: Optional[dict] = None,
  ) -> bool:
      """Send error notification."""
      context_str = ""
      if context:
          context_str = "\n".join(f"<b>{k}:</b> {v}" for k, v in context.items())

      message = f"""
  \U0001F6A8 <b>ERROR</b>

  <b>Type:</b> {error_type}
  <b>Message:</b> {error_message}

  {context_str}
  """
      return await self.send_message(message.strip())

  async def send_circuit_breaker_alert(
      self,
      trigger: str,
      details: dict,
  ) -> bool:
      """Send circuit breaker trigger notification."""
      details_str = "\n".join(f"<b>{k}:</b> {v}" for k, v in details.items())

      message = f"""
  \U0001F6D1 <b>CIRCUIT BREAKER TRIGGERED</b>

  <b>Trigger:</b> {trigger}

  {details_str}

  Trading has been paused. Manual review required.
  """
      return await self.send_message(message.strip())

  async def send_daily_summary(
      self,
      date: str,
      trades: int,
      profit: Decimal,
      profit_pct: Decimal,
      win_rate: Decimal,
  ) -> bool:
      """Send daily performance summary."""
      emoji = "\U0001F4C8" if profit > 0 else "\U0001F4C9"

      message = f"""
  {emoji} <b>Daily Summary</b> - {date}

  <b>Trades:</b> {trades}
  <b>Profit:</b> ${profit:,.2f} ({profit_pct:+.2%})
  <b>Win Rate:</b> {win_rate:.1%}
  """
      return await self.send_message(message.strip())
  ```
- [ ] Add rate limiting to prevent spam:
  ```python
  from collections import deque
  from datetime import datetime, timedelta

  class RateLimitedTelegramAlerter(TelegramAlerter):
      """Telegram alerter with rate limiting."""

      def __init__(
          self,
          bot_token: str,
          chat_id: str,
          max_messages_per_minute: int = 20,
      ):
          super().__init__(bot_token, chat_id)
          self._max_per_minute = max_messages_per_minute
          self._message_times: deque[datetime] = deque(maxlen=max_messages_per_minute)

      async def send_message(self, text: str, **kwargs) -> bool:
          """Send message with rate limiting."""
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
  ```
- [ ] Write tests with mocked HTTP

### Technical Notes
- Use HTML parse mode for formatting
- Rate limit to avoid Telegram API bans (30 msg/sec)
- Async HTTP with aiohttp
- Handle network errors gracefully

### Definition of Done
- Telegram alerter sends formatted messages
- All alert types implemented (trade, profit, error, circuit breaker)
- Rate limiting prevents spam
- Connection verification on startup
- Tests pass with mocked API

---

## Story 4.3: Implement Discord Alert Integration

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** trader
**I want** Discord webhook notifications
**So that** I can receive alerts in my preferred platform

### Acceptance Criteria

- [ ] Implement DiscordAlerter:
  ```python
  class DiscordAlerter:
      """Send alerts via Discord webhooks."""

      def __init__(self, webhook_url: str):
          self._webhook_url = webhook_url
          self._session: Optional[aiohttp.ClientSession] = None

      async def connect(self) -> None:
          self._session = aiohttp.ClientSession()

      async def disconnect(self) -> None:
          if self._session:
              await self._session.close()

      async def send_embed(
          self,
          title: str,
          description: str,
          color: int = 0x00FF00,  # Green
          fields: Optional[list[dict]] = None,
      ) -> bool:
          """Send a Discord embed message."""
          embed = {
              "title": title,
              "description": description,
              "color": color,
              "timestamp": datetime.utcnow().isoformat(),
          }

          if fields:
              embed["fields"] = [
                  {"name": f["name"], "value": str(f["value"]), "inline": f.get("inline", True)}
                  for f in fields
              ]

          try:
              async with self._session.post(
                  self._webhook_url,
                  json={"embeds": [embed]},
              ) as resp:
                  return resp.status in (200, 204)
          except Exception as e:
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
          """Send trade execution alert."""
          color = 0x00FF00 if side.lower() == "buy" else 0xFF0000

          return await self.send_embed(
              title=f"{side.upper()} {symbol}",
              description=f"Order executed successfully",
              color=color,
              fields=[
                  {"name": "Amount", "value": str(amount)},
                  {"name": "Price", "value": f"${price:,.2f}"},
                  {"name": "Value", "value": f"${amount * price:,.2f}"},
                  {"name": "Order ID", "value": order_id, "inline": False},
              ],
          )

      async def send_error_alert(
          self,
          error_type: str,
          error_message: str,
          context: Optional[dict] = None,
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
  ```
- [ ] Match message types with Telegram alerts
- [ ] Write tests with mocked webhooks

### Definition of Done
- Discord webhook integration working
- All alert types match Telegram
- Tests pass with mocked API

---

## Story 4.4: Create Alert Manager

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** a central alert manager coordinating all channels
**So that** alerts are sent consistently with proper routing

### Acceptance Criteria

- [ ] Implement AlertManager:
  ```python
  from enum import Enum
  from typing import Protocol, Optional
  from dataclasses import dataclass

  class AlertSeverity(str, Enum):
      INFO = "info"
      WARNING = "warning"
      ERROR = "error"
      CRITICAL = "critical"

  class AlertChannel(Protocol):
      """Protocol for alert channels."""
      async def connect(self) -> None: ...
      async def disconnect(self) -> None: ...
      async def send_message(self, text: str, **kwargs) -> bool: ...

  @dataclass
  class AlertConfig:
      telegram_enabled: bool = True
      discord_enabled: bool = True
      min_severity: AlertSeverity = AlertSeverity.INFO
      rate_limit_per_minute: int = 30
      suppress_duplicates_seconds: int = 60

  class AlertManager:
      """Central manager for all alert channels."""

      def __init__(self, config: AlertConfig):
          self._config = config
          self._channels: dict[str, AlertChannel] = {}
          self._severity_channels: dict[AlertSeverity, list[str]] = {
              AlertSeverity.INFO: ["telegram"],
              AlertSeverity.WARNING: ["telegram", "discord"],
              AlertSeverity.ERROR: ["telegram", "discord"],
              AlertSeverity.CRITICAL: ["telegram", "discord"],
          }
          self._recent_alerts: dict[str, datetime] = {}

      def add_channel(self, name: str, channel: AlertChannel) -> None:
          """Add an alert channel."""
          self._channels[name] = channel

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
              await channel.disconnect()

      async def send(
          self,
          severity: AlertSeverity,
          title: str,
          message: str,
          context: Optional[dict] = None,
          dedupe_key: Optional[str] = None,
      ) -> bool:
          """Send alert to appropriate channels."""
          # Check severity threshold
          if self._severity_value(severity) < self._severity_value(self._config.min_severity):
              return True

          # Check duplicate suppression
          if dedupe_key:
              last_sent = self._recent_alerts.get(dedupe_key)
              if last_sent:
                  if (datetime.utcnow() - last_sent).seconds < self._config.suppress_duplicates_seconds:
                      logger.debug("alert_suppressed_duplicate", key=dedupe_key)
                      return True
              self._recent_alerts[dedupe_key] = datetime.utcnow()

          # Format message
          full_message = self._format_message(severity, title, message, context)

          # Send to appropriate channels
          channels = self._severity_channels.get(severity, [])
          success = True

          for channel_name in channels:
              if channel_name in self._channels:
                  try:
                      result = await self._channels[channel_name].send_message(full_message)
                      if not result:
                          success = False
                  except Exception as e:
                      logger.error("alert_send_failed",
                                  channel=channel_name,
                                  error=str(e))
                      success = False

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
          context: Optional[dict],
      ) -> str:
          """Format alert message."""
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
      async def send_info(self, title: str, message: str, **kwargs) -> bool:
          return await self.send(AlertSeverity.INFO, title, message, **kwargs)

      async def send_warning(self, title: str, message: str, **kwargs) -> bool:
          return await self.send(AlertSeverity.WARNING, title, message, **kwargs)

      async def send_error(self, title: str, message: str, **kwargs) -> bool:
          return await self.send(AlertSeverity.ERROR, title, message, **kwargs)

      async def send_critical(self, title: str, message: str, **kwargs) -> bool:
          return await self.send(AlertSeverity.CRITICAL, title, message, **kwargs)
  ```
- [ ] Implement duplicate suppression
- [ ] Add batch/aggregate alerts for high-frequency events
- [ ] Write integration tests

### Definition of Done
- AlertManager coordinates multiple channels
- Severity-based routing working
- Duplicate suppression prevents spam
- All convenience methods implemented

---

## Story 4.5: Build Health Check Endpoint

**Story Points:** 3
**Priority:** P1 - High

### Description
**As a** operator
**I want** a health check endpoint
**So that** monitoring systems can verify bot status

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/health.py`
- [ ] Implement health check server:
  ```python
  from aiohttp import web
  from datetime import datetime
  from typing import Optional
  import asyncio

  class HealthCheckServer:
      """Simple HTTP server for health checks."""

      def __init__(
          self,
          host: str = "0.0.0.0",
          port: int = 8080,
      ):
          self._host = host
          self._port = port
          self._app = web.Application()
          self._runner: Optional[web.AppRunner] = None
          self._bot = None
          self._last_heartbeat = datetime.utcnow()

          # Setup routes
          self._app.router.add_get("/health", self._health_handler)
          self._app.router.add_get("/ready", self._ready_handler)
          self._app.router.add_get("/metrics", self._metrics_handler)

      def set_bot(self, bot) -> None:
          """Set reference to trading bot for status checks."""
          self._bot = bot

      def update_heartbeat(self) -> None:
          """Update last heartbeat timestamp."""
          self._last_heartbeat = datetime.utcnow()

      async def start(self) -> None:
          """Start health check server."""
          self._runner = web.AppRunner(self._app)
          await self._runner.setup()
          site = web.TCPSite(self._runner, self._host, self._port)
          await site.start()
          logger.info("health_server_started", host=self._host, port=self._port)

      async def stop(self) -> None:
          """Stop health check server."""
          if self._runner:
              await self._runner.cleanup()

      async def _health_handler(self, request: web.Request) -> web.Response:
          """Basic health check - is the process alive?"""
          return web.json_response({
              "status": "healthy",
              "timestamp": datetime.utcnow().isoformat(),
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
          heartbeat_age = (datetime.utcnow() - self._last_heartbeat).seconds
          is_stale = heartbeat_age > 60

          if not is_running:
              return web.json_response(
                  {"status": "not_ready", "reason": "Bot not running"},
                  status=503,
              )

          if is_stale:
              return web.json_response(
                  {"status": "not_ready", "reason": f"Heartbeat stale ({heartbeat_age}s)"},
                  status=503,
              )

          return web.json_response({
              "status": "ready",
              "timestamp": datetime.utcnow().isoformat(),
              "heartbeat_age_seconds": heartbeat_age,
          })

      async def _metrics_handler(self, request: web.Request) -> web.Response:
          """Return current metrics for monitoring."""
          if not self._bot:
              return web.json_response({"error": "Bot not initialized"}, status=503)

          # Get risk metrics if available
          risk_metrics = {}
          if hasattr(self._bot, "_risk_manager"):
              risk_metrics = self._bot._risk_manager.get_risk_metrics()

          # Get strategy status
          strategy_status = {}
          if hasattr(self._bot, "_strategy"):
              strategy_status = {
                  "name": self._bot._strategy.name,
                  "symbol": self._bot._strategy.symbol,
              }

          return web.json_response({
              "timestamp": datetime.utcnow().isoformat(),
              "bot_running": getattr(self._bot, "_running", False),
              "strategy": strategy_status,
              "risk": risk_metrics,
              "heartbeat_age_seconds": (datetime.utcnow() - self._last_heartbeat).seconds,
          })
  ```
- [ ] Add Prometheus metrics export (optional):
  ```python
  async def _prometheus_handler(self, request: web.Request) -> web.Response:
      """Export metrics in Prometheus format."""
      metrics = []

      # Add bot status
      is_running = 1 if getattr(self._bot, "_running", False) else 0
      metrics.append(f"trading_bot_running {is_running}")

      # Add heartbeat age
      heartbeat_age = (datetime.utcnow() - self._last_heartbeat).seconds
      metrics.append(f"trading_bot_heartbeat_age_seconds {heartbeat_age}")

      # Add risk metrics
      if hasattr(self._bot, "_risk_manager"):
          risk = self._bot._risk_manager.get_risk_metrics()
          metrics.append(f'trading_bot_circuit_breaker_tripped {1 if risk.get("circuit_breaker_tripped") else 0}')
          metrics.append(f"trading_bot_consecutive_losses {risk.get('consecutive_losses', 0)}")

      return web.Response(
          text="\n".join(metrics),
          content_type="text/plain",
      )
  ```
- [ ] Write tests for health endpoints

### Definition of Done
- Health check endpoint returns bot status
- Readiness check verifies trading capability
- Metrics endpoint exposes key data
- Kubernetes/Docker probes compatible

---

## Story 4.6: Implement Performance Dashboard Data API

**Story Points:** 5
**Priority:** P2 - Medium

### Description
**As a** operator
**I want** an API exposing trading performance data
**So that** dashboards can visualize bot performance

### Acceptance Criteria

- [ ] Add dashboard routes to health server:
  ```python
  def _setup_dashboard_routes(self) -> None:
      """Setup dashboard data API routes."""
      self._app.router.add_get("/api/trades", self._trades_handler)
      self._app.router.add_get("/api/positions", self._positions_handler)
      self._app.router.add_get("/api/pnl", self._pnl_handler)
      self._app.router.add_get("/api/equity", self._equity_handler)

  async def _trades_handler(self, request: web.Request) -> web.Response:
      """Get recent trades."""
      limit = int(request.query.get("limit", 100))
      symbol = request.query.get("symbol")

      async with self._database.session() as session:
          repo = TradeRepository(session)
          trades = await repo.get_trade_history(
              symbol=symbol,
              limit=limit,
          )

      return web.json_response({
          "trades": [
              {
                  "id": t.id,
                  "symbol": t.symbol,
                  "side": t.side,
                  "amount": str(t.amount),
                  "open_rate": str(t.open_rate),
                  "close_rate": str(t.close_rate) if t.close_rate else None,
                  "profit": str(t.profit) if t.profit else None,
                  "open_date": t.open_date.isoformat(),
                  "close_date": t.close_date.isoformat() if t.close_date else None,
              }
              for t in trades
          ]
      })

  async def _positions_handler(self, request: web.Request) -> web.Response:
      """Get current open positions."""
      async with self._database.session() as session:
          repo = TradeRepository(session)
          positions = await repo.get_open_trades()

      return web.json_response({
          "positions": [
              {
                  "id": p.id,
                  "symbol": p.symbol,
                  "side": p.side,
                  "amount": str(p.amount),
                  "entry_price": str(p.open_rate),
                  "current_price": str(self._get_current_price(p.symbol)),
                  "unrealized_pnl": str(self._calculate_unrealized_pnl(p)),
                  "open_date": p.open_date.isoformat(),
              }
              for p in positions
          ]
      })

  async def _pnl_handler(self, request: web.Request) -> web.Response:
      """Get P&L summary."""
      period = request.query.get("period", "daily")  # daily, weekly, monthly, all

      async with self._database.session() as session:
          repo = TradeRepository(session)

          if period == "daily":
              start_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
          elif period == "weekly":
              start_date = datetime.utcnow() - timedelta(days=7)
          elif period == "monthly":
              start_date = datetime.utcnow() - timedelta(days=30)
          else:
              start_date = None

          trades = await repo.get_trade_history(start_date=start_date, limit=10000)

      total_pnl = sum(t.profit for t in trades if t.profit)
      winning = [t for t in trades if t.profit and t.profit > 0]
      losing = [t for t in trades if t.profit and t.profit < 0]

      return web.json_response({
          "period": period,
          "total_trades": len(trades),
          "winning_trades": len(winning),
          "losing_trades": len(losing),
          "win_rate": len(winning) / len(trades) if trades else 0,
          "total_pnl": str(total_pnl),
          "gross_profit": str(sum(t.profit for t in winning)),
          "gross_loss": str(sum(t.profit for t in losing)),
      })

  async def _equity_handler(self, request: web.Request) -> web.Response:
      """Get equity curve data."""
      days = int(request.query.get("days", 30))

      async with self._database.session() as session:
          # Query balance snapshots
          result = await session.execute(
              select(BalanceSnapshot)
              .where(BalanceSnapshot.timestamp >= datetime.utcnow() - timedelta(days=days))
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
  ```
- [ ] Add CORS support for web dashboards
- [ ] Document API endpoints
- [ ] Write tests for API responses

### Definition of Done
- Trade history API working
- Position API working
- P&L summary API working
- Equity curve API working
- API documented

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 4.1 Production Logging | 5 | P0 | Phase 2 |
| 4.2 Telegram Alerts | 5 | P0 | 4.1 |
| 4.3 Discord Alerts | 3 | P1 | 4.1 |
| 4.4 Alert Manager | 5 | P0 | 4.2, 4.3 |
| 4.5 Health Check Endpoint | 3 | P1 | Phase 2 |
| 4.6 Dashboard Data API | 5 | P2 | 4.5 |
| **Total** | **26** | | |

---

## Sources & References

- [structlog Best Practices](https://www.structlog.org/en/stable/logging-best-practices.html)
- [structlog Performance](https://www.structlog.org/en/stable/performance.html)
- [Python Logging with Structlog Guide](https://betterstack.com/community/guides/logging/structlog/)
- [Freqtrade - Open Source Trading Bot](https://github.com/freqtrade/freqtrade)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Discord Webhooks](https://discord.com/developers/docs/resources/webhook)
