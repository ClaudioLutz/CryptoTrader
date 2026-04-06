"""Telegram-Notifications fuer Trade-Events und Daily Summary.

Nutzt direkt die Telegram Bot API via aiohttp (keine extra Dependency).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    """Sendet Trade-Notifications und Summaries via Telegram."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        if not bot_token or not chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID muessen gesetzt sein")
        self._token = bot_token
        self._chat_id = chat_id
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Sendet eine Nachricht an den konfigurierten Chat."""
        session = await self._get_session()
        url = TELEGRAM_API.format(token=self._token, method="sendMessage")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                logger.warning("telegram_send_failed", status=resp.status, body=body[:200])
                return False
        except Exception:
            logger.warning("telegram_send_error", exc_info=True)
            return False

    async def send_trade(
        self,
        side: str,
        coin: str,
        amount: Decimal,
        price: Decimal,
        cost: Decimal,
        confidence: float = 0.0,
        pnl: Decimal | None = None,
        reason: str = "",
    ) -> bool:
        """Sendet eine Trade-Notification."""
        emoji = "🟢" if side == "BUY" else ("🔴" if pnl and pnl < 0 else "🟡")
        pnl_str = ""
        if pnl is not None:
            pnl_pct = float(pnl / cost) * 100 if cost > 0 else 0
            pnl_emoji = "✅" if pnl > 0 else "❌"
            pnl_str = f"\n{pnl_emoji} P&L: {float(pnl):+.2f} USDT ({pnl_pct:+.1f}%)"

        reason_str = f"\n📋 Grund: {reason}" if reason else ""
        conf_str = f"\n🎯 Confidence: {confidence:.1%}" if confidence > 0 else ""

        msg = (
            f"{emoji} *{side} {coin}*\n"
            f"💰 Preis: {float(price):,.2f} USDT\n"
            f"📊 Menge: {float(amount):.6f}\n"
            f"💵 Wert: {float(cost):.2f} USDT"
            f"{conf_str}{pnl_str}{reason_str}"
        )
        return await self._send_message(msg)

    async def send_daily_summary(
        self,
        total_capital: Decimal,
        open_positions: int,
        total_pnl: Decimal,
        drawdown_pct: float,
        win_rate: float | None = None,
        kelly_pct: float | None = None,
    ) -> bool:
        """Sendet eine taegliche Zusammenfassung."""
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        wr_str = f"\n🎯 Win-Rate: {win_rate:.1%}" if win_rate else ""
        kelly_str = f"\n📐 Kelly: {kelly_pct:.1%}" if kelly_pct else ""
        dd_str = f"\n🛡️ Drawdown: {drawdown_pct:.1%}" if drawdown_pct > 0 else ""

        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        msg = (
            f"📊 *Daily Summary* — {now}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Kapital: {float(total_capital):,.2f} USDT\n"
            f"📂 Offene Positionen: {open_positions}\n"
            f"{pnl_emoji} Realisierter P&L: {float(total_pnl):+.2f} USDT"
            f"{dd_str}{wr_str}{kelly_str}"
        )
        return await self._send_message(msg)

    async def send_alert(self, title: str, message: str) -> bool:
        """Sendet eine Warnung/Alert-Nachricht."""
        msg = f"⚠️ *{title}*\n{message}"
        return await self._send_message(msg)

    async def close(self) -> None:
        """Schliesst die aiohttp-Session."""
        if self._session and not self._session.closed:
            await self._session.close()
