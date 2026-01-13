# Grid Trading Strategy Documentation

## Overview

The CryptoTrader bot implements an automated **Grid Trading Strategy** that profits from price oscillations by placing multiple buy orders below the current price and sell orders above it. The strategy operates on the principle of "buy low, sell high" at multiple predefined price levels (grids).

## How It Works

### Core Concept

```
Upper Price ($150)  ─────────────────────────────  Take Profit Zone
                    │     SELL orders placed here
                    │         ↑ ↑ ↑ ↑ ↑
Grid Levels         │    ═══════════════════
                    │         ↓ ↓ ↓ ↓ ↓
                    │     BUY orders placed here
Lower Price ($120)  ─────────────────────────────  Stop Loss Zone
```

1. **Grid Setup**: Define a price range (e.g., $120-$150) divided into multiple levels
2. **Initial Orders**: Place buy orders at all grid levels below current price
3. **Buy Fills**: When a buy order fills → automatically place a sell order one level up
4. **Sell Fills**: When a sell order fills → capture profit, place new buy at original level
5. **Repeat**: The cycle continues, profiting from each price oscillation

### Order Lifecycle Example

```
Current Price: $140

1. Initial State:
   Level 5 ($143.45): No orders (above current price)
   Level 4 ($143.45): No orders (above current price)
   Level 3 ($137.19): BUY order placed ← waiting
   Level 2 ($131.20): BUY order placed ← waiting
   Level 1 ($125.48): BUY order placed ← waiting
   Level 0 ($120.00): BUY order placed ← waiting

2. Price drops to $137, Level 3 BUY fills:
   Level 4 ($143.45): SELL order placed ← counter order
   Level 3 ($137.19): Filled (holding position)
   ...

3. Price rises to $143.45, Level 4 SELL fills:
   Level 4 ($143.45): PROFIT CAPTURED! (~$6.26 per unit)
   Level 3 ($137.19): New BUY order placed ← cycle restarts
   ...
```

## Configuration

### Grid Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | required | Trading pair (e.g., "SOL/USDT") |
| `lower_price` | Decimal | required | Lower boundary of grid range |
| `upper_price` | Decimal | required | Upper boundary of grid range |
| `num_grids` | int | 20 | Number of grid levels (3-100) |
| `total_investment` | Decimal | required | Total capital to allocate |
| `spacing` | string | "geometric" | Grid spacing mode |
| `stop_loss_pct` | Decimal | 10% | Stop-loss % below lower_price |
| `take_profit_pct` | Decimal | None | Take-profit % above upper_price |

### Grid Spacing Modes

**Arithmetic Spacing** (equal dollar intervals):
- Best for: Stable pairs, range-bound markets
- Example: $120-$150 with 6 grids = $5 intervals
- Levels: $120, $125, $130, $135, $140, $145, $150

**Geometric Spacing** (equal percentage intervals):
- Best for: Volatile assets (BTC, SOL)
- Example: $120-$150 with 6 grids = ~4.6% intervals
- Levels: $120, $125.48, $131.20, $137.19, $143.45, $150

### Example Configuration

```python
GRID_CONFIGS = [
    {
        "symbol": "SOL/USDT",
        "lower_price": Decimal("120"),
        "upper_price": Decimal("150"),
        "num_grids": 6,
        "total_investment": Decimal("45"),
    },
]
```

## Capital Management

### Order Size Calculation

The strategy reserves 20% of capital as a volatility buffer:

```
Order Size = (Total Investment × 0.80) ÷ Number of Active Grids

Example:
- Investment: $45
- Active grids: 6
- Available capital: $45 × 0.80 = $36
- Order size per level: $36 ÷ 6 = $6 per grid level
```

### Capital Distribution

```
Total Investment: $45
├── Reserve Buffer (20%): $9 (for volatility/fees)
└── Trading Capital (80%): $36
    ├── Level 0: ~$6 worth
    ├── Level 1: ~$6 worth
    ├── Level 2: ~$6 worth
    ├── Level 3: ~$6 worth
    ├── Level 4: ~$6 worth
    └── Level 5: ~$6 worth
```

## Risk Management

### Stop-Loss

- **Trigger**: When price drops below `lower_price × (1 - stop_loss_pct)`
- **Action**: Stops strategy, optionally cancels all orders
- **Default**: 10% below lower price

```
Lower Price: $120
Stop-Loss (10%): $120 × 0.90 = $108
```

### Take-Profit

- **Trigger**: When price rises above `upper_price × (1 + take_profit_pct)`
- **Action**: Cancels all orders, locks in profits
- **Default**: Disabled (None)

## Profit Tracking

### Per-Cycle Profit

```
Profit = (Sell Price - Buy Price) × Amount - Fees

Example:
- Buy at $137.19, Sell at $143.45
- Amount: 0.065 SOL
- Gross profit: ($143.45 - $137.19) × 0.065 = $0.41
- Fees (0.1% each side): ~$0.02
- Net profit: ~$0.39 per cycle
```

### Statistics Tracked

| Metric | Description |
|--------|-------------|
| `total_profit` | Cumulative profit from all completed cycles |
| `total_fees` | Estimated fees paid (0.1% per side) |
| `completed_cycles` | Number of buy-sell cycles completed |
| `active_buy_orders` | Current open buy orders |
| `active_sell_orders` | Current open sell orders |

## State Management

### Persistence

The strategy state is automatically saved to the database after every tick, enabling crash recovery:

```json
{
  "version": 1,
  "config": {
    "lower_price": "120",
    "upper_price": "150",
    "num_grids": 6
  },
  "grid_levels": [
    {
      "index": 0,
      "price": "120.00",
      "buy_order_id": "16047668018",
      "filled_buy": false,
      "quantity": "0.075"
    }
  ],
  "statistics": {
    "total_profit": "0",
    "completed_cycles": 0
  }
}
```

### Reconciliation on Startup

When the bot restarts, it reconciles local state with the exchange:

1. **Orphan Orders**: Orders on exchange but not in local state → Cancel
2. **Phantom Orders**: Orders in local state but not on exchange → Remove from state
3. **Filled Orders**: Orders filled while bot was offline → Process fills, place counter orders

## Dashboard Display

### Orders Panel
```
ORDERS          DISTANCES                    GRID
 3    1         Next BUY: $131.20 (+6.6%)    $120 - $150
BUY  SELL       TP: $143.45 (+2.1%)          6 levels | $45
```

### Metrics Shown
- Buy/Sell order counts
- Distance to next buy order (%)
- Distance to take-profit (%)
- Grid range and configuration
- Per-trade unrealized P&L

## Best Practices

### Grid Range Selection
- **Too narrow**: More trades but smaller profits per cycle
- **Too wide**: Larger profits but fewer cycles
- **Recommended**: 20-30% range for volatile assets

### Number of Grids
- **Few grids (3-10)**: Larger order sizes, fewer but bigger profits
- **Many grids (20-50)**: Smaller orders, more frequent trades
- **Warning**: >50 grids = high cumulative fees

### Capital Allocation
- Start small to test the strategy
- Don't allocate more than you can afford to lose
- Consider multiple pairs to diversify

## Limitations

1. **Ranging Markets Required**: Performs poorly in strong trends
2. **Capital Lock-up**: Funds tied up in pending orders
3. **Gap Risk**: Fast price moves may skip grid levels
4. **Fee Impact**: High grid counts increase fee costs

## Files Reference

| File | Purpose |
|------|---------|
| `src/crypto_bot/strategies/grid_trading.py` | Core strategy implementation |
| `src/crypto_bot/strategies/base_strategy.py` | Strategy interface/protocol |
| `src/crypto_bot/strategies/strategy_state.py` | State persistence & reconciliation |
| `src/crypto_bot/bot.py` | Bot lifecycle & execution context |
| `src/crypto_bot/main.py` | Configuration & entry point |
