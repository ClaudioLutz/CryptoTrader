"""Position-Lifecycle fuer die Prediction-Strategie.

Verwaltet offene Positionen mit 7-Tage-Ablauf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PredictionPosition:
    """Eine einzelne Prediction-basierte Position."""

    coin: str
    symbol: str
    direction: str  # "up" (nur Spot-Markt)
    confidence: float
    entry_price: Decimal
    amount: Decimal  # Menge in Base-Currency
    cost: Decimal  # Ausgaben in USDT
    buy_order_id: str
    opened_at: datetime
    close_at: datetime
    status: str = "open"  # "open", "closing", "closed"
    sell_order_id: Optional[str] = None
    close_price: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    # SL/TP (ATR-basiert, berechnet bei Eroeffnung)
    stop_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    close_reason: Optional[str] = None  # "time", "stop_loss", "take_profit"

    def check_sl_tp(self, current_price: Decimal) -> Optional[str]:
        """Prueft ob SL oder TP getriggert wurde.

        Returns:
            'stop_loss', 'take_profit' oder None.
        """
        if self.stop_loss_price and current_price <= self.stop_loss_price:
            return "stop_loss"
        if self.take_profit_price and current_price >= self.take_profit_price:
            return "take_profit"
        return None

    def to_dict(self) -> dict:
        return {
            "coin": self.coin,
            "symbol": self.symbol,
            "direction": self.direction,
            "confidence": self.confidence,
            "entry_price": str(self.entry_price),
            "amount": str(self.amount),
            "cost": str(self.cost),
            "buy_order_id": self.buy_order_id,
            "opened_at": self.opened_at.isoformat(),
            "close_at": self.close_at.isoformat(),
            "status": self.status,
            "sell_order_id": self.sell_order_id,
            "close_price": str(self.close_price) if self.close_price else None,
            "pnl": str(self.pnl) if self.pnl else None,
            "stop_loss_price": str(self.stop_loss_price) if self.stop_loss_price else None,
            "take_profit_price": str(self.take_profit_price) if self.take_profit_price else None,
            "close_reason": self.close_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PredictionPosition:
        return cls(
            coin=data["coin"],
            symbol=data["symbol"],
            direction=data["direction"],
            confidence=data["confidence"],
            entry_price=Decimal(data["entry_price"]),
            amount=Decimal(data["amount"]),
            cost=Decimal(data["cost"]),
            buy_order_id=data["buy_order_id"],
            opened_at=datetime.fromisoformat(data["opened_at"]),
            close_at=datetime.fromisoformat(data["close_at"]),
            status=data["status"],
            sell_order_id=data.get("sell_order_id"),
            close_price=Decimal(data["close_price"]) if data.get("close_price") else None,
            pnl=Decimal(data["pnl"]) if data.get("pnl") else None,
            stop_loss_price=Decimal(data["stop_loss_price"]) if data.get("stop_loss_price") else None,
            take_profit_price=Decimal(data["take_profit_price"]) if data.get("take_profit_price") else None,
            close_reason=data.get("close_reason"),
        )


class PositionTracker:
    """Verwaltet den Lifecycle von Prediction-Positionen."""

    def __init__(self) -> None:
        self._positions: dict[str, PredictionPosition] = {}  # coin -> Position
        self._closed_positions: list[PredictionPosition] = []

    def add_position(self, position: PredictionPosition) -> None:
        if position.coin in self._positions:
            logger.warning("position_already_exists", coin=position.coin)
            return
        self._positions[position.coin] = position
        logger.info(
            "position_opened",
            coin=position.coin,
            confidence=round(position.confidence, 3),
            cost=str(position.cost),
            close_at=position.close_at.isoformat(),
        )

    def get_positions_to_close(self, now: datetime) -> list[PredictionPosition]:
        return [
            pos for pos in self._positions.values()
            if pos.status == "open" and now >= pos.close_at
        ]

    def mark_closing(self, coin: str, sell_order_id: str) -> None:
        if coin in self._positions:
            self._positions[coin].status = "closing"
            self._positions[coin].sell_order_id = sell_order_id
            logger.info("position_closing", coin=coin, sell_order_id=sell_order_id)

    def mark_closed(self, coin: str, close_price: Decimal, reason: str = "time") -> None:
        if coin not in self._positions:
            return
        pos = self._positions[coin]
        pos.status = "closed"
        pos.close_price = close_price
        pos.close_reason = reason
        revenue = pos.amount * close_price
        pos.pnl = revenue - pos.cost
        logger.info(
            "position_closed",
            coin=coin,
            reason=reason,
            entry_price=str(pos.entry_price),
            close_price=str(close_price),
            pnl=str(pos.pnl),
        )
        self._closed_positions.append(pos)
        del self._positions[coin]

    def get_open_positions(self) -> list[PredictionPosition]:
        return [p for p in self._positions.values() if p.status in ("open", "closing")]

    def get_total_exposure(self) -> Decimal:
        return sum(
            (p.cost for p in self._positions.values() if p.status in ("open", "closing")),
            Decimal(0),
        )

    def has_position(self, coin: str) -> bool:
        return coin in self._positions

    def get_total_pnl(self) -> Decimal:
        return sum((p.pnl for p in self._closed_positions if p.pnl), Decimal(0))

    def to_dict(self) -> dict:
        return {
            "positions": {coin: pos.to_dict() for coin, pos in self._positions.items()},
            "closed_positions": [pos.to_dict() for pos in self._closed_positions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> PositionTracker:
        tracker = cls()
        for coin, pos_data in data.get("positions", {}).items():
            tracker._positions[coin] = PredictionPosition.from_dict(pos_data)
        for pos_data in data.get("closed_positions", []):
            tracker._closed_positions.append(PredictionPosition.from_dict(pos_data))
        return tracker
