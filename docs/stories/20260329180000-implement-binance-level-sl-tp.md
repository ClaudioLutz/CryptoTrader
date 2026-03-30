# Binance-Level Stop-Loss / Take-Profit — Implementationsplan

## Summary

Aktuell werden SL/TP nur durch den Bot geprueft (alle 60 Sekunden Preis-Polling). Wenn der Bot offline ist, gibt es **keinen Schutz**. Dieses Dokument beschreibt, wie SL/TP auf Binance-Ebene via **OCO-Orders** implementiert werden soll, sodass Binance selbst die Orders ausfuehrt — unabhaengig vom Bot-Status.

## Context / Problem

### Ist-Zustand

```
Bot laeuft → on_tick() alle 60s → check_sl_tp(current_price) → Market Sell
```

**Schwaechen:**
- **Kein Schutz bei Bot-Ausfall** — Crash, Netzwerkfehler, Wartung
- **60-Sekunden-Latenz** — Bei Flash-Crashes kann der Preis in <1s durch den SL fallen
- **Abhaengigkeit vom Bot** — Der Bot muss permanent laufen fuer Schutz
- **Kein Auto-Cancel** — SL und TP sind nur im Bot-Speicher, nicht auf der Exchange

### Soll-Zustand

```
Market Buy → OCO Sell Order auf Binance → Binance fuehrt SL oder TP aus
Bot ueberwacht Status → Bei Fill: Position als geschlossen markieren
Bot ueberwacht Zeitbarriere → Bei Ablauf: OCO canceln + Market Sell
```

**Vorteile:**
- Schutz 24/7, auch wenn Bot offline
- Sofortige Ausfuehrung bei Preistrigger (Binance-Engine, ~ms)
- Auto-Cancel: Wenn SL triggert, wird TP automatisch storniert (und umgekehrt)

---

## Recherche-Ergebnisse

### Binance Order-Listen-Typen

| Typ | Beschreibung | Anwendungsfall |
|-----|-------------|----------------|
| **OCO** | 2 Orders; eine wird ausgefuehrt → andere automatisch storniert | **SL + TP Bracket nach Market Buy** |
| OTO | Working-Order triggert Pending-Order | Limit-Buy → dann SL setzen |
| OTOCO | Working-Order triggert OCO-Bracket | Limit-Buy → dann SL + TP |
| OPO | Wie OTO, aber self-funding | Working-Order finanziert Pending |
| OPOCO | Wie OTOCO, aber self-funding | Limit-Buy finanziert SL + TP |

### Warum OCO die beste Wahl ist

1. **Market-Buy ist Pflicht** — Unsere Strategie kauft zum aktuellen Preis (nicht per Limit)
2. **OTOCO/OPOCO erfordern LIMIT als Working-Order** — Market-Buy wird nicht unterstuetzt
3. **OCO ist am laengsten verfuegbar** und am besten getestet
4. **Ablauf**: Zuerst Market Buy, dann OCO Sell Bracket platzieren

### OCO-Order Struktur auf Binance (neuer Endpoint)

**Endpoint**: `POST /api/v3/orderList/oco` (der alte `/api/v3/order/oco` ist deprecated!)

```
OCO Sell Order = {
    LIMIT_MAKER (Take-Profit) — Verkauf bei TP-Preis
    +
    STOP_LOSS_LIMIT (Stop-Loss) — Verkauf bei SL-Preis
}
```

**Preisregel**: `TP-Preis > Aktueller Preis > SL-Trigger-Preis`

**Parameter** (neuer Endpoint mit `aboveType`/`belowType`):

| Parameter | Wert | Beschreibung |
|-----------|------|-------------|
| `symbol` | z.B. `SOLUSDT` | Trading-Paar (ohne `/`) |
| `side` | `SELL` | Verkaufsseite |
| `quantity` | z.B. `0.1` | Menge (gerundet auf stepSize) |
| `aboveType` | `LIMIT_MAKER` | Take-Profit Order-Typ |
| `abovePrice` | z.B. `180.00` | Take-Profit Preis |
| `belowType` | `STOP_LOSS_LIMIT` | Stop-Loss Order-Typ |
| `belowStopPrice` | z.B. `130.00` | SL Trigger-Preis (stopPrice) |
| `belowPrice` | z.B. `129.50` | SL Limit-Preis (Ausfuehrungspreis) |
| `belowTimeInForce` | `GTC` | Good-Till-Cancelled |

**Hinweis zu `belowPrice` vs `belowStopPrice`**:
- `belowStopPrice` = Trigger-Preis (wenn Markt diesen erreicht, wird die Limit-Order aktiviert)
- `belowPrice` = Limit-Preis (zu diesem Preis wird verkauft, leicht unter dem Trigger)
- Empfehlung: `belowPrice = belowStopPrice * 0.995` (0.5% Slippage-Puffer)

### CCXT-Integration

CCXT v4 bietet **keine High-Level-Methode** fuer OCO auf Binance. Die Loesung:

```python
# Impliziter API-Aufruf ueber CCXT
exchange.private_post_orderlist_oco({
    'symbol': 'SOLUSDT',
    'side': 'SELL',
    'quantity': exchange.amount_to_precision('SOL/USDT', amount),
    'aboveType': 'LIMIT_MAKER',
    'abovePrice': exchange.price_to_precision('SOL/USDT', tp_price),
    'belowType': 'STOP_LOSS_LIMIT',
    'belowPrice': exchange.price_to_precision('SOL/USDT', sl_limit_price),
    'belowStopPrice': exchange.price_to_precision('SOL/USDT', sl_trigger_price),
    'belowTimeInForce': 'GTC',
})
```

**Rueckgabe**: JSON mit `orderListId`, `listStatusType`, `orders[]` (2 Order-IDs)

### Binance-Filter die beachtet werden muessen

| Filter | Pruefung | Typischer Fehler |
|--------|----------|-----------------|
| `PRICE_FILTER` | Preis im Bereich, Vielfaches von `tickSize` | Zu viele Dezimalstellen |
| `PERCENT_PRICE` | Preis zwischen `multiplierDown * avgPrice` und `multiplierUp * avgPrice` | SL/TP zu weit vom Markt |
| `LOT_SIZE` | Menge im Bereich, Vielfaches von `stepSize` | Menge nicht gerundet |
| `MIN_NOTIONAL` | `price * quantity >= minNotional` (~10 USDT) | Order zu klein |
| `MAX_NUM_ORDERS` | Max. offene Orders pro Symbol | OCO zaehlt als 2! |
| `MAX_NUM_ORDER_LISTS` | Max. 20 aktive Order-Listen pro Symbol | Limit beachten |

### OCO-Order stornieren

```python
# Storniert beide Orders im OCO-Paar
exchange.private_delete_orderlist({
    'symbol': 'SOLUSDT',
    'orderListId': order_list_id,
})
```

---

## Architektur-Design

### Neuer Ablauf pro Position

```
1. Market Buy (wie bisher)
   ↓
2. Buy-Fill bestaetigt
   ↓
3. OCO Sell Order platzieren:
   - LIMIT_MAKER @ TP-Preis
   - STOP_LOSS_LIMIT @ SL-Preis
   ↓
4a. SL oder TP triggert → Binance fuehrt aus → Bot erkennt Fill
4b. Zeitbarriere erreicht → Bot cancelt OCO → Market Sell
4c. Bot offline → Binance schuetzt trotzdem via SL/TP
```

### Aenderungen an bestehenden Komponenten

#### 1. `base_exchange.py` — Erweitern

```python
class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    # Neu:
    STOP_LOSS = "stop_loss"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"

@dataclass
class OCOOrder:
    """Repraesentiert ein OCO-Orderpaar."""
    order_list_id: str
    symbol: str
    tp_order_id: str
    sl_order_id: str
    tp_price: Decimal
    sl_trigger_price: Decimal
    sl_limit_price: Decimal
    quantity: Decimal
    status: str  # "active", "filled_tp", "filled_sl", "cancelled"
    created_at: datetime
```

**Neue abstrakte Methoden in BaseExchange:**
```python
async def create_oco_sell_order(
    self,
    symbol: str,
    quantity: Decimal,
    tp_price: Decimal,
    sl_trigger_price: Decimal,
    sl_limit_price: Decimal,
) -> OCOOrder: ...

async def cancel_order_list(
    self,
    symbol: str,
    order_list_id: str,
) -> None: ...
```

#### 2. `ccxt_wrapper.py` — Basis-Implementierung

```python
async def create_oco_sell_order(self, symbol, quantity, tp_price, sl_trigger_price, sl_limit_price):
    market = self._markets[symbol]
    raw = self.exchange.private_post_orderlist_oco({
        'symbol': market['id'],
        'side': 'SELL',
        'quantity': self.exchange.amount_to_precision(symbol, float(quantity)),
        'aboveType': 'LIMIT_MAKER',
        'abovePrice': self.exchange.price_to_precision(symbol, float(tp_price)),
        'belowType': 'STOP_LOSS_LIMIT',
        'belowStopPrice': self.exchange.price_to_precision(symbol, float(sl_trigger_price)),
        'belowPrice': self.exchange.price_to_precision(symbol, float(sl_limit_price)),
        'belowTimeInForce': 'GTC',
    })
    return self._convert_oco_order(raw, symbol, tp_price, sl_trigger_price, sl_limit_price, quantity)
```

#### 3. `binance_adapter.py` — Binance-spezifische Validierung

```python
async def create_oco_sell_order(self, symbol, quantity, tp_price, sl_trigger_price, sl_limit_price):
    # 1. LOT_SIZE validieren
    quantity = self._apply_lot_size_filter(symbol, quantity)
    # 2. PRICE_FILTER fuer beide Preise
    tp_price = self._apply_price_filter(symbol, tp_price)
    sl_trigger_price = self._apply_price_filter(symbol, sl_trigger_price)
    sl_limit_price = self._apply_price_filter(symbol, sl_limit_price)
    # 3. MIN_NOTIONAL pruefen fuer beide Seiten
    self._check_min_notional(symbol, quantity, min(tp_price, sl_limit_price))
    # 4. Preisregel pruefen: TP > current > SL
    ticker = await self.fetch_ticker(symbol)
    if not (tp_price > ticker.last > sl_trigger_price):
        raise InvalidOrderError(f"OCO price rule violated: TP={tp_price} > current={ticker.last} > SL={sl_trigger_price}")
    # 5. An Parent delegieren
    return await super().create_oco_sell_order(symbol, quantity, tp_price, sl_trigger_price, sl_limit_price)
```

#### 4. `position_tracker.py` — OCO-Tracking

```python
@dataclass
class PredictionPosition:
    # ... bestehende Felder ...
    # Neu:
    oco_order_list_id: Optional[str] = None
    oco_tp_order_id: Optional[str] = None
    oco_sl_order_id: Optional[str] = None
    oco_placed: bool = False  # True wenn OCO auf Binance aktiv
```

#### 5. `prediction_strategy.py` — Kernlogik aendern

**Aenderung in `_process_predictions()`** (nach Market Buy):
```python
# Nach Buy-Fill: OCO Sell Order platzieren
sl_limit_price = sl_price * Decimal("0.995")  # 0.5% Slippage-Puffer
oco = await self._context.create_oco_sell_order(
    symbol=symbol,
    quantity=amount,
    tp_price=tp_price,
    sl_trigger_price=sl_price,
    sl_limit_price=sl_limit_price,
)
position.oco_order_list_id = oco.order_list_id
position.oco_tp_order_id = oco.tp_order_id
position.oco_sl_order_id = oco.sl_order_id
position.oco_placed = True
```

**Aenderung in `on_tick()`**:
```python
# Statt: Bot prueft SL/TP per Polling
# Neu: Bot prueft OCO-Status per Polling
for pos in self._tracker.get_open_positions():
    if pos.oco_placed:
        # Pruefen ob OCO-Order gefuellt wurde
        try:
            tp_status = await self._context.fetch_order(pos.oco_tp_order_id, pos.symbol)
            sl_status = await self._context.fetch_order(pos.oco_sl_order_id, pos.symbol)

            if tp_status.status == OrderStatus.CLOSED:
                self._tracker.mark_closed(pos.coin, tp_status.price, reason="take_profit")
            elif sl_status.status == OrderStatus.CLOSED:
                self._tracker.mark_closed(pos.coin, sl_status.price, reason="stop_loss")
        except Exception:
            logger.exception("oco_status_check_failed", coin=pos.coin)
    else:
        # Fallback: Bot-Level SL/TP (wie bisher, fuer alte Positionen)
        current_price = await self._context.get_current_price(pos.symbol)
        trigger = pos.check_sl_tp(current_price)
        if trigger:
            await self._close_position(pos, reason=trigger)

# Zeitbarriere: OCO canceln + Market Sell
for pos in self._tracker.get_positions_to_close(now):
    if pos.oco_placed and pos.oco_order_list_id:
        await self._context.cancel_order_list(pos.symbol, pos.oco_order_list_id)
    await self._close_position(pos, reason="time")
```

#### 6. `daily_prediction_run.py` — OCO-Unterstuetzung

```python
# Nach Market Buy: OCO platzieren
oco_raw = exchange.exchange.private_post_orderlist_oco({...})
pos["oco_order_list_id"] = oco_raw["orderListId"]

# Beim Schliessen (Zeitbarriere): OCO erst canceln
if pos.get("oco_order_list_id"):
    exchange.exchange.private_delete_orderlist({
        'symbol': pos['symbol'].replace('/', ''),
        'orderListId': pos['oco_order_list_id'],
    })
```

#### 7. `ExecutionContext` — Erweitern

```python
# Neue Methoden in ExecutionContext:
async def create_oco_sell_order(self, symbol, quantity, tp_price, sl_trigger_price, sl_limit_price) -> OCOOrder
async def cancel_order_list(self, symbol, order_list_id) -> None
async def fetch_order(self, order_id, symbol) -> Order
```

---

## Migration bestehender Positionen

Fuer die 3 aktuell offenen Positionen (TRX, ANKR, AAVE):

1. Bot startet mit neuem Code
2. Erkennt: `oco_placed == False` (oder Feld fehlt)
3. Holt aktuellen Preis → prueft ob Preisregel erfuellt (TP > current > SL)
4. Wenn ja: OCO nachtraeglich platzieren
5. Wenn nein (z.B. Preis bereits unter SL): Bot-Level-Closing wie bisher

```python
# In initialize() oder on_tick():
async def _migrate_positions_to_oco(self):
    for pos in self._tracker.get_open_positions():
        if pos.oco_placed or not pos.stop_loss_price or not pos.take_profit_price:
            continue
        try:
            ticker = await self._context.get_current_price(pos.symbol)
            if pos.take_profit_price > ticker > pos.stop_loss_price:
                sl_limit = pos.stop_loss_price * Decimal("0.995")
                oco = await self._context.create_oco_sell_order(
                    symbol=pos.symbol,
                    quantity=pos.amount,
                    tp_price=pos.take_profit_price,
                    sl_trigger_price=pos.stop_loss_price,
                    sl_limit_price=sl_limit,
                )
                pos.oco_order_list_id = oco.order_list_id
                pos.oco_tp_order_id = oco.tp_order_id
                pos.oco_sl_order_id = oco.sl_order_id
                pos.oco_placed = True
                logger.info("position_migrated_to_oco", coin=pos.coin)
            else:
                logger.warning("position_cannot_migrate_oco", coin=pos.coin, reason="price_rule_violated")
        except Exception:
            logger.exception("oco_migration_failed", coin=pos.coin)
```

---

## Fehlerbehandlung

| Szenario | Handling |
|----------|---------|
| OCO-Platzierung fehlschlaegt | Fallback auf Bot-Level SL/TP (wie bisher) |
| PERCENT_PRICE-Verletzung | SL/TP anpassen oder Fallback |
| MIN_NOTIONAL-Verletzung | Position zu klein fuer OCO → Bot-Level |
| Bot startet nach Crash | OCO-Status auf Binance pruefen, State aktualisieren |
| OCO teilweise gefuellt | Verbleibende Menge via Bot-Level schliessen |
| Zeitbarriere + OCO aktiv | OCO canceln, dann Market Sell |
| Menge weicht ab (Fees) | `quantity = amount - fee` bei OCO-Platzierung |

### Fee-Beruecksichtigung

Binance zieht Trading-Fees von der gekauften Menge ab (0.1% Spot). Wenn wir 100 SOL kaufen, erhalten wir ~99.9 SOL. Die OCO-Sell-Menge muss die tatsaechlich erhaltene Menge sein:

```python
# Nach Buy-Fill:
actual_amount = order.filled  # z.B. 99.9 SOL (nach Fee-Abzug)
# OCO mit actual_amount platzieren, nicht mit bestellter Menge
```

**Alternative mit BNB-Fee**: Wenn der User BNB fuer Fees aktiviert hat, wird die volle Menge gutgeschrieben. Dies muss geprueft werden:
```python
# Pruefen ob BNB-Fee aktiv (ueber Account-Info oder Heuristik)
if order.filled == order.amount:
    oco_quantity = order.filled  # Volle Menge
else:
    oco_quantity = order.filled  # Reduzierte Menge nach Fee
```

---

## Implementierungs-Reihenfolge

### Phase 1: Exchange-Layer (geschaetzte Komplexitaet: mittel)
1. `base_exchange.py`: `OCOOrder` Dataclass + abstrakte Methoden
2. `ccxt_wrapper.py`: `create_oco_sell_order()`, `cancel_order_list()`
3. `binance_adapter.py`: Binance-spezifische Validierung + Filter

### Phase 2: Position-Tracking (geschaetzte Komplexitaet: gering)
4. `position_tracker.py`: OCO-Felder auf `PredictionPosition`
5. Serialisierung/Deserialisierung der neuen Felder

### Phase 3: Strategie-Integration (geschaetzte Komplexitaet: hoch)
6. `prediction_strategy.py`:
   - OCO nach Buy-Fill platzieren
   - `on_tick()`: OCO-Status pruefen statt Preis-Polling
   - Zeitbarriere: OCO canceln + Market Sell
   - Migration bestehender Positionen
7. `ExecutionContext` erweitern

### Phase 4: Daily Script (geschaetzte Komplexitaet: mittel)
8. `daily_prediction_run.py`: OCO-Platzierung nach Buy + Cancel bei Close

### Phase 5: Testing (geschaetzte Komplexitaet: mittel)
9. Unit-Tests fuer OCO-Erstellung und -Validierung
10. Dry-Run-Test mit echtem Binance-Account (OCO platzieren + canceln)
11. Live-Test mit kleiner Position

---

## Risiken und Massnahmen

| Risiko | Wahrscheinlichkeit | Massnahme |
|--------|-------------------|-----------|
| OCO-API aendert sich | Gering | CCXT abstrahiert, Fallback auf Bot-Level |
| PERCENT_PRICE blockiert OCO | Mittel | Dynamische SL/TP-Anpassung an erlaubten Bereich |
| Doppelte Ausfuehrung (Bot + Binance) | Gering | Bot prueft OCO-Status BEVOR eigene Action |
| Fee-Differenz bei Menge | Hoch | `order.filled` statt `order.amount` verwenden |
| OCO zaehlt als 2 Orders (MAX_NUM_ORDERS) | Mittel | Bei 38 Coins max. 76 OCO-Orders → Limit beachten |

---

## Offene Fragen

1. **Trailing-Stop statt fixem SL?** — Binance unterstuetzt Trailing-Delta in OCO-Orders. Soll der SL nachziehen wenn der Preis steigt?
2. **SL als STOP_LOSS (Market) statt STOP_LOSS_LIMIT?** — Market garantiert Ausfuehrung, Limit garantiert Preis. Bei illiquiden Coins kann ein Limit-SL nicht ausgefuehrt werden.
3. **Dashboard-Anzeige** — Soll das Dashboard den OCO-Status anzeigen (aktiv/ausgefuehrt)?
4. **BNB-Fee-Rabatt** — Ist BNB-Fee aktiviert auf dem Account? Beeinflusst die OCO-Menge.

---

## Zusammenfassung

Die Migration von Bot-Level SL/TP zu Binance-Level OCO-Orders ist der wichtigste naechste Schritt fuer die Prediction-Strategie. Der Schutz ist dann **permanent aktiv**, unabhaengig vom Bot-Status, und reagiert in Millisekunden statt 60 Sekunden. Die Implementierung erfordert Aenderungen an 7 Dateien, wobei der Exchange-Layer und die Strategie-Integration die groessten Aenderungen darstellen. Ein Fallback auf Bot-Level SL/TP bleibt fuer Edge-Cases bestehen (zu kleine Positionen, Preisregel-Verletzung).
