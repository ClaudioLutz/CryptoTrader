"""Prediction-basierte Trading-Strategie.

Oeffnet Positionen basierend auf 7-Tage ML-Vorhersagen
und schliesst sie nach exakt 7 Tagen via Market Sell.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import structlog

from crypto_bot.exchange.base_exchange import Order, OrderSide, Ticker
from crypto_bot.prediction.position_tracker import PositionTracker, PredictionPosition
from crypto_bot.prediction.prediction_config import PredictionConfig
from crypto_bot.prediction.prediction_pipeline import PredictionPipeline, PredictionResult
from crypto_bot.strategies.base_strategy import ExecutionContext

logger = structlog.get_logger(__name__)

STATE_VERSION = 1


class PredictionStrategy:
    """Trading-Strategie basierend auf ML-Vorhersagen.

    Handelt alle 20 Coins aus dem coin_prediction-Projekt.
    Trainiert taeglich neu und oeffnet/schliesst Positionen
    basierend auf Confidence-gewichteten Signalen.
    """

    def __init__(
        self,
        config: PredictionConfig,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        self._config = config
        self._context = context
        self._tracker = PositionTracker()
        self._pipeline = PredictionPipeline(
            config.coin_prediction_path,
            config.coins,
            config.prediction_horizon_days,
            timeframe=getattr(config, "timeframe", "1d"),
            horizon_hours=getattr(config, "prediction_horizon_hours", 0),
            train_window_hours=getattr(config, "train_window_hours", 720),
        )
        self._latest_predictions: dict[str, PredictionResult] = {}
        self._prediction_history: list[dict] = []  # Chronologische Prediction-History
        self._max_history_entries: int = 168 * 2  # 2 Wochen bei stuendl. Predictions
        self._last_retrain_date: Optional[date] = None
        self._last_retrain_time: Optional[datetime] = None
        self._last_retrain_duration: Optional[float] = None  # Sekunden
        self._active_orders: dict[str, str] = {}  # order_id -> coin
        self._symbols = [f"{coin}/{config.quote_currency}" for coin in config.coins]
        self._initialized = False
        self._retrain_lock = asyncio.Lock()
        self._retraining = False

    @property
    def name(self) -> str:
        return "prediction_multi"

    @property
    def symbol(self) -> str:
        return "MULTI/USDT"

    @property
    def symbols(self) -> list[str]:
        """Alle gehandelten Symbole."""
        return self._symbols

    @property
    def tick_interval(self) -> float:
        """60 Sekunden statt 1 Sekunde — taegl. Strategie braucht keine Sekunden-Ticks."""
        return 60.0

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialisiert die Strategie: erstes Retraining und Positions-Oeffnung."""
        self._context = context

        # Kapital dynamisch setzen falls nicht manuell konfiguriert
        if self._config.total_capital <= Decimal(0):
            await self._update_capital_from_balance()

        if not self._initialized:
            logger.info("prediction_strategy_initializing", coins=len(self._config.coins))
            await self._run_retrain()
            await self._process_predictions()
            self._initialized = True
            logger.info(
                "prediction_strategy_initialized",
                predictions=len(self._latest_predictions),
                open_positions=len(self._tracker.get_open_positions()),
            )
        else:
            # Aus State wiederhergestellt — nur abgelaufene Positionen pruefen
            logger.info("prediction_strategy_restored_from_state")

        # Migration: bestehende Positionen ohne Binance-Level SL/TP nachrüsten
        await self._migrate_positions_to_binance_sl_tp()

    async def _update_capital_from_balance(self) -> None:
        """Setzt total_capital dynamisch auf den aktuellen USDT-Bestand."""
        if not self._context:
            return
        balance = await self._context.get_balance(self._config.quote_currency)
        self._config.total_capital = balance
        logger.info("capital_set_from_balance", total_capital=str(balance))

    async def on_tick(self, ticker: Ticker) -> None:
        """Wird alle 60 Sekunden aufgerufen.

        1. SL/TP pruefen (Fallback fuer Positionen ohne Binance-Orders)
        2. Abgelaufene Positionen schliessen (Zeitbarriere)
        3. Taegl. Retrain pruefen und ausfuehren
        """
        if not self._initialized or not self._context:
            return

        now = datetime.now(timezone.utc)

        # 1. TP pruefen (Bot-Level) + SL-Fallback fuer Positionen ohne Binance-SL
        #    SL wird auf Binance-Ebene geprueft (via SL-Order), TP bleibt Bot-Level
        for pos in self._tracker.get_open_positions():
            if pos.status != "open":
                continue
            try:
                current_price = await self._context.get_current_price(pos.symbol)

                # TP immer Bot-Level pruefen (keine Binance-TP-Order)
                if pos.take_profit_price and current_price >= pos.take_profit_price:
                    logger.warning(
                        "tp_triggered",
                        coin=pos.coin,
                        entry_price=str(pos.entry_price),
                        current_price=str(current_price),
                        tp=str(pos.take_profit_price),
                    )
                    await self._close_position(pos, reason="take_profit")
                    continue

                # SL nur als Fallback wenn keine Binance-SL-Order existiert
                if not pos.sl_order_id and pos.stop_loss_price and current_price <= pos.stop_loss_price:
                    logger.warning(
                        "sl_triggered_fallback",
                        coin=pos.coin,
                        entry_price=str(pos.entry_price),
                        current_price=str(current_price),
                        sl=str(pos.stop_loss_price),
                    )
                    await self._close_position(pos, reason="stop_loss")
            except Exception:
                logger.exception("sl_tp_check_failed", coin=pos.coin)

        # 2. Abgelaufene Positionen schliessen (Zeitbarriere)
        positions_to_close = self._tracker.get_positions_to_close(now)
        for pos in positions_to_close:
            await self._close_position(pos, reason="time")

        # 3. Taegl. Retrain
        if self._should_retrain(now) and not self._retraining:
            self._retraining = True
            try:
                await self._run_retrain()
                await self._process_predictions()
            finally:
                self._retraining = False

    async def on_order_filled(self, order: Order) -> None:
        """Verarbeitet gefuellte Orders (Buy = Position offen, Sell = Position geschlossen)."""
        if order.id not in self._active_orders:
            return

        coin = self._active_orders.pop(order.id)

        if order.side == OrderSide.SELL:
            close_price = order.price if order.price else (
                order.cost / order.filled if order.filled > 0 else Decimal(0)
            )
            pos = self._tracker._positions.get(coin)
            if not pos:
                return

            # Bestimme Reason: war es die Binance-SL-Order?
            if order.id == pos.sl_order_id:
                reason = "stop_loss"
            else:
                reason = pos.close_reason if pos.close_reason else "time"

            self._tracker.mark_closed(coin, close_price, reason=reason)
            logger.info(
                "prediction_position_closed_by_fill",
                coin=coin,
                reason=reason,
                close_price=str(close_price),
                filled=str(order.filled),
            )
        elif order.side == OrderSide.BUY:
            logger.info(
                "prediction_buy_filled",
                coin=coin,
                price=str(order.price),
                filled=str(order.filled),
            )

    async def on_order_cancelled(self, order: Order) -> None:
        """Verarbeitet stornierte Orders."""
        if order.id in self._active_orders:
            coin = self._active_orders.pop(order.id)
            logger.warning("prediction_order_cancelled", coin=coin, order_id=order.id)

    def get_state(self) -> dict[str, Any]:
        """Serialisiert den Strategie-State fuer Persistence."""
        return {
            "version": STATE_VERSION,
            "config": self._config.model_dump(mode="json"),
            "positions": self._tracker.to_dict(),
            "active_orders": dict(self._active_orders),
            "last_retrain_date": (
                self._last_retrain_date.isoformat() if self._last_retrain_date else None
            ),
            "last_retrain_time": (
                self._last_retrain_time.isoformat() if self._last_retrain_time else None
            ),
            "last_retrain_duration": self._last_retrain_duration,
            "latest_predictions": {
                coin: {
                    "coin": p.coin,
                    "direction": p.direction,
                    "probability": p.probability,
                    "confidence": p.confidence,
                    "features_date": p.features_date,
                }
                for coin, p in self._latest_predictions.items()
            },
            "prediction_history": self._prediction_history,
            "initialized": self._initialized,
        }

    @classmethod
    def from_state(
        cls, state: dict[str, Any], context: ExecutionContext
    ) -> PredictionStrategy:
        """Stellt die Strategie aus gespeichertem State wieder her."""
        config = PredictionConfig(**state["config"])
        strategy = cls(config, context)
        strategy._tracker = PositionTracker.from_dict(state["positions"])
        strategy._active_orders = state.get("active_orders", {})

        if state.get("last_retrain_date"):
            strategy._last_retrain_date = date.fromisoformat(state["last_retrain_date"])
        if state.get("last_retrain_time"):
            strategy._last_retrain_time = datetime.fromisoformat(state["last_retrain_time"])
        strategy._last_retrain_duration = state.get("last_retrain_duration")

        for coin, pdata in state.get("latest_predictions", {}).items():
            strategy._latest_predictions[coin] = PredictionResult(**pdata)

        strategy._prediction_history = state.get("prediction_history", [])
        strategy._initialized = state.get("initialized", False)
        return strategy

    async def shutdown(self) -> None:
        """Graceful Shutdown — loggt offene Positionen."""
        open_positions = self._tracker.get_open_positions()
        total_pnl = self._tracker.get_total_pnl()
        logger.info(
            "prediction_strategy_shutdown",
            open_positions=len(open_positions),
            total_exposure=str(self._tracker.get_total_exposure()),
            realized_pnl=str(total_pnl),
        )

    def register_manual_position(
        self,
        coin: str,
        entry_price: Decimal,
        amount: Decimal,
        cost: Decimal,
        opened_at: datetime,
        close_after_days: int = 7,
    ) -> None:
        """Registriert eine manuell geoeffnete Position fuer automatisches Closing."""
        symbol = f"{coin}/{self._config.quote_currency}"
        position = PredictionPosition(
            coin=coin,
            symbol=symbol,
            direction="up",
            confidence=1.0,
            entry_price=entry_price,
            amount=amount,
            cost=cost,
            buy_order_id="MANUAL",
            opened_at=opened_at,
            close_at=opened_at + timedelta(days=close_after_days),
        )
        self._tracker.add_position(position)
        logger.info(
            "manual_position_registered",
            coin=coin,
            amount=str(amount),
            close_at=position.close_at.isoformat(),
        )

    # =========================================================================
    # Interne Methoden
    # =========================================================================

    async def _migrate_positions_to_binance_sl_tp(self) -> None:
        """Migriert bestehende Positionen ohne Binance-Level SL/TP.

        Wird beim Start aufgerufen um sicherzustellen, dass alle offenen
        Positionen durch Binance-Orders geschuetzt sind.
        """
        for pos in self._tracker.get_open_positions():
            if pos.sl_order_id or pos.tp_order_id:
                continue  # Bereits mit Binance-Orders
            if not pos.stop_loss_price or not pos.take_profit_price:
                continue  # Keine SL/TP-Preise definiert
            try:
                current_price = await self._context.get_current_price(pos.symbol)
                # Preisregel: TP > current > SL
                if pos.take_profit_price > current_price > pos.stop_loss_price:
                    await self._place_sl_tp_orders(pos)
                    logger.info("position_migrated_to_binance_sl_tp", coin=pos.coin)
                else:
                    logger.warning(
                        "position_migration_skipped_price_rule",
                        coin=pos.coin,
                        current=str(current_price),
                        sl=str(pos.stop_loss_price),
                        tp=str(pos.take_profit_price),
                    )
            except Exception:
                logger.warning("position_migration_failed", coin=pos.coin, exc_info=True)

    def _should_retrain(self, now: datetime) -> bool:
        """Prueft ob ein Retrain faellig ist.

        Bei 1h-Timeframe: alle retrain_interval_hours (z.B. 4h).
        Bei 1d-Timeframe: 1x taeglich zur konfigurierten Zeit.
        """
        retrain_interval = getattr(self._config, "retrain_interval_hours", 0)

        if retrain_interval > 0:
            # Stundl. Intervall-basiert (fuer 1h-Timeframe)
            if self._last_retrain_time is None:
                return True
            elapsed = (now - self._last_retrain_time).total_seconds() / 3600
            return elapsed >= retrain_interval
        else:
            # Taeglich (Legacy fuer 1d-Timeframe)
            if self._last_retrain_date == now.date():
                return False
            if now.hour > self._config.retrain_hour_utc:
                return True
            if (
                now.hour == self._config.retrain_hour_utc
                and now.minute >= self._config.retrain_minute_utc
            ):
                return True
            return False

    async def _run_retrain(self) -> None:
        """Fuehrt die Prediction-Pipeline in einem Background-Thread aus."""
        import time as _time

        async with self._retrain_lock:
            logger.info("prediction_retrain_start",
                        timeframe=getattr(self._config, "timeframe", "1d"))
            start = _time.monotonic()
            try:
                self._latest_predictions = await self._pipeline.run_full_pipeline()
                self._last_retrain_date = date.today()
                self._last_retrain_time = datetime.now(timezone.utc)
                self._last_retrain_duration = _time.monotonic() - start

                # Prediction-History speichern
                self._append_prediction_history()

                logger.info(
                    "prediction_retrain_complete",
                    n_predictions=len(self._latest_predictions),
                    duration_s=round(self._last_retrain_duration, 1),
                )
            except Exception:
                self._last_retrain_duration = _time.monotonic() - start
                logger.exception("prediction_retrain_failed")
                # Vorherige Predictions behalten

    def _append_prediction_history(self) -> None:
        """Speichert aktuelle Predictions in der History-Liste."""
        now = datetime.now(timezone.utc)
        for coin, pred in self._latest_predictions.items():
            self._prediction_history.append({
                "timestamp": now.isoformat(),
                "coin": pred.coin,
                "direction": pred.direction,
                "probability": round(pred.probability, 4),
                "confidence": round(pred.confidence, 4),
                "features_date": pred.features_date,
                "sl_pct": round(getattr(pred, "sl_pct", 0), 4),
                "tp_pct": round(getattr(pred, "tp_pct", 0), 4),
            })

        # History beschraenken
        if len(self._prediction_history) > self._max_history_entries:
            self._prediction_history = self._prediction_history[-self._max_history_entries:]

    async def _process_predictions(self) -> None:
        """Oeffnet Positionen fuer hochkonfidente 'Up'-Predictions."""
        if not self._context or not self._latest_predictions:
            return

        usdt_balance = await self._context.get_balance(self._config.quote_currency)
        current_exposure = self._tracker.get_total_exposure()
        max_total = self._config.total_capital * self._config.max_total_exposure_pct
        available = min(usdt_balance, max_total - current_exposure)

        if available <= Decimal(0):
            logger.info("no_budget_available", balance=str(usdt_balance), exposure=str(current_exposure))
            return

        # Nur "Up"-Predictions ueber Confidence-Schwelle, sortiert nach Confidence
        candidates = [
            p for p in self._latest_predictions.values()
            if p.direction == "up"
            and p.confidence >= self._config.min_confidence
            and not self._tracker.has_position(p.coin)
        ]
        candidates.sort(key=lambda p: p.confidence, reverse=True)

        if not candidates:
            logger.info("no_trade_candidates")
            return

        logger.info(
            "processing_predictions",
            candidates=len(candidates),
            available_budget=str(available),
        )

        for pred in candidates:
            if available <= Decimal("1"):  # Min. 1 USDT
                break

            position_size = self._calculate_position_size(pred, available)
            if position_size < Decimal("1"):
                continue

            symbol = f"{pred.coin}/{self._config.quote_currency}"
            try:
                price = await self._context.get_current_price(symbol)
                if price <= Decimal(0):
                    continue

                amount = (position_size / price).quantize(Decimal("0.00000001"))
                if amount <= Decimal(0):
                    continue

                # Market Buy
                order_id = await self._context.place_order(
                    symbol=symbol,
                    side="buy",
                    amount=amount,
                )

                now = datetime.now(timezone.utc)
                # SL/TP nur setzen wenn Pipeline Werte > 0 liefert
                sl_price = (
                    (price * (1 - Decimal(str(pred.sl_pct)))).quantize(Decimal("0.00000001"))
                    if pred.sl_pct > 0 else None
                )
                tp_price = (
                    (price * (1 + Decimal(str(pred.tp_pct)))).quantize(Decimal("0.00000001"))
                    if pred.tp_pct > 0 else None
                )

                position = PredictionPosition(
                    coin=pred.coin,
                    symbol=symbol,
                    direction="up",
                    confidence=pred.confidence,
                    entry_price=price,
                    amount=amount,
                    cost=position_size,
                    buy_order_id=order_id,
                    opened_at=now,
                    close_at=now + timedelta(hours=getattr(
                        self._config, "prediction_horizon_hours",
                        self._config.prediction_horizon_days * 24)),
                    stop_loss_price=sl_price,
                    take_profit_price=tp_price,
                )
                self._tracker.add_position(position)
                self._active_orders[order_id] = pred.coin
                available -= position_size

                # Binance-Level SL/TP Orders platzieren
                await self._place_sl_tp_orders(position)

                logger.info(
                    "prediction_position_opened",
                    coin=pred.coin,
                    confidence=round(pred.confidence, 3),
                    size_usdt=str(position_size),
                    amount=str(amount),
                    price=str(price),
                    sl=str(sl_price) if sl_price else "disabled",
                    tp=str(tp_price) if tp_price else "disabled",
                    sl_pct=f"{pred.sl_pct:.1%}" if pred.sl_pct > 0 else "disabled",
                    tp_pct=f"{pred.tp_pct:.1%}" if pred.tp_pct > 0 else "disabled",
                )

            except Exception:
                logger.exception("position_open_failed", coin=pred.coin)

    def _calculate_position_size(
        self, pred: PredictionResult, available: Decimal
    ) -> Decimal:
        """Berechnet die Positionsgroesse basierend auf Confidence und ATR.

        Zwei Faktoren bestimmen die Groesse:
        1. Confidence [min_confidence, 1.0] → [25%, 100%] (wie sicher ist das Signal?)
        2. ATR-Faktor [0.5, 1.5] (wie gross ist die erwartete Bewegung?)

        Coins mit hoher Confidence UND hoher Volatilitaet bekommen
        groessere Positionen, weil das Gewinnpotenzial hoeher ist.
        """
        max_per_coin = self._config.total_capital * self._config.max_per_coin_pct

        # Faktor 1: Confidence-basiert (wie bisher)
        confidence_range = 1.0 - self._config.min_confidence
        if confidence_range <= 0:
            confidence_scale = 1.0
        else:
            confidence_above_min = pred.confidence - self._config.min_confidence
            confidence_scale = 0.25 + 0.75 * (confidence_above_min / confidence_range)
            confidence_scale = min(confidence_scale, 1.0)

        # Faktor 2: Quantil-basiert oder ATR-Fallback
        # Wenn Quantil-Daten verfuegbar: q50 (erwarteter Return) bestimmt Groesse
        # Wenn q10 > 0: Selbst im schlechten Fall positiv → Bonus
        if hasattr(pred, "q50") and pred.q50 != 0:
            # Erwarteter Return: 0% → 0.5x, 5% → 1.0x, 10%+ → 1.5x
            q50_scale = max(0.5, min(0.5 + pred.q50 * 10, 1.5))

            # Bonus wenn q10 > 0 (Downside-geschuetzt)
            if hasattr(pred, "q10") and pred.q10 > 0:
                q50_scale = min(q50_scale * 1.2, 1.5)

            move_scale = q50_scale
        else:
            # Fallback: ATR-basiert
            median_tp = 0.15
            if pred.tp_pct > 0:
                atr_ratio = pred.tp_pct / median_tp
                move_scale = max(0.5, min(atr_ratio, 1.5))
            else:
                move_scale = 1.0

        combined_scale = Decimal(str(min(confidence_scale * move_scale, 1.5)))
        size = (max_per_coin * combined_scale).quantize(Decimal("0.01"))
        return min(size, available)

    async def _close_position(self, pos: PredictionPosition, reason: str = "time") -> None:
        """Schliesst eine Position via Market Sell.

        Cancelt zuerst bestehende Binance-Level SL/TP Orders.
        """
        if not self._context:
            return

        try:
            # Bestehende SL/TP Orders canceln (sonst blockieren sie die Menge)
            await self._cancel_sl_tp_orders(pos)

            order_id = await self._context.place_order(
                symbol=pos.symbol,
                side="sell",
                amount=pos.amount,
            )
            self._tracker.mark_closing(pos.coin, order_id)
            self._active_orders[order_id] = pos.coin
            pos.close_reason = reason
            logger.info(
                "prediction_position_close_initiated",
                coin=pos.coin,
                reason=reason,
                amount=str(pos.amount),
            )
        except Exception:
            logger.exception("position_close_failed", coin=pos.coin)

    async def _place_sl_tp_orders(self, pos: PredictionPosition) -> None:
        """Platziert Stop-Loss Order auf Binance.

        Nur SL wird auf Binance platziert (Schutz bei Bot-Ausfall).
        TP bleibt Bot-Level — Binance erlaubt keine zwei Sell-Orders
        fuer die gleiche Menge (InsufficientFunds), ausser via OCO.
        Fallback auf Bot-Level SL/TP wenn die Platzierung fehlschlaegt.
        """
        if not self._context or not pos.stop_loss_price:
            return

        try:
            sl_id = await self._context.place_order(
                symbol=pos.symbol,
                side="sell",
                amount=pos.amount,
                params={"stopLossPrice": float(pos.stop_loss_price)},
            )
            pos.sl_order_id = sl_id
            self._active_orders[sl_id] = pos.coin
            logger.info(
                "binance_sl_order_placed",
                coin=pos.coin,
                order_id=sl_id,
                stop_loss_price=str(pos.stop_loss_price),
            )
        except Exception:
            logger.warning("binance_sl_order_failed_fallback_to_bot", coin=pos.coin, exc_info=True)

    async def _cancel_sl_tp_orders(self, pos: PredictionPosition) -> None:
        """Cancelt bestehende Binance-Level SL-Order fuer eine Position."""
        if not self._context or not pos.sl_order_id:
            return

        try:
            await self._context.cancel_order(pos.sl_order_id, pos.symbol)
            self._active_orders.pop(pos.sl_order_id, None)
            logger.info("binance_sl_cancelled", coin=pos.coin, order_id=pos.sl_order_id)
        except Exception:
            logger.warning("binance_sl_cancel_failed", coin=pos.coin, order_id=pos.sl_order_id, exc_info=True)

        pos.sl_order_id = None
