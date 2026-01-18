"""P&L calculation from actual trade history.

Mirrors the calculation logic from the old Streamlit dashboard to provide
accurate realized and unrealized P&L values.
"""

from dataclasses import dataclass
from decimal import Decimal

from dashboard.services.data_models import TradeData


@dataclass
class PnLResult:
    """P&L calculation result."""

    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    holdings: Decimal
    avg_cost: Decimal
    cycles: int
    buy_count: int
    sell_count: int


def calculate_pnl_from_trades(
    trades: list[TradeData],
    current_price: Decimal = Decimal("0"),
) -> PnLResult:
    """Calculate realized and unrealized P&L using FIFO (First-In-First-Out) method.

    FIFO matches sells against the oldest buys first, which is the standard
    method used by Binance and most exchanges for tax reporting.

    Args:
        trades: List of TradeData objects.
        current_price: Current market price for unrealized P&L calculation.

    Returns:
        PnLResult with all P&L metrics.
    """
    # Sort trades by timestamp (oldest first) for FIFO
    sorted_trades = sorted(trades, key=lambda t: t.timestamp)

    buy_queue: list[dict] = []  # FIFO queue of buys: [{price, qty, cost}, ...]
    realized_pnl = Decimal("0")
    total_fees = Decimal("0")
    buy_count = 0
    sell_count = 0

    for trade in sorted_trades:
        try:
            total_fees += trade.fee if trade.fee else Decimal("0")
            cost = trade.cost if trade.cost else trade.price * trade.amount
            side = trade.side.lower()

            if side == "buy":
                buy_queue.append({
                    "price": trade.price,
                    "qty": trade.amount,
                    "cost": cost,
                })
                buy_count += 1
            elif side == "sell":
                sell_qty = trade.amount
                sell_proceeds = cost
                cost_basis = Decimal("0")
                sell_count += 1

                # Match against oldest buys (FIFO)
                while sell_qty > 0 and buy_queue:
                    buy = buy_queue[0]
                    matched_qty = min(sell_qty, buy["qty"])
                    cost_basis += buy["price"] * matched_qty

                    buy["qty"] -= matched_qty
                    sell_qty -= matched_qty

                    if buy["qty"] <= 0:
                        buy_queue.pop(0)

                # Realized P&L for this sell = proceeds - cost basis
                realized_pnl += (sell_proceeds - cost_basis)
        except (ValueError, TypeError, AttributeError):
            continue

    # Remaining holdings from buy queue
    holdings = sum(Decimal(str(b["qty"])) for b in buy_queue)

    # Average cost of remaining holdings
    if holdings > 0:
        avg_cost = (
            sum(Decimal(str(b["price"])) * Decimal(str(b["qty"])) for b in buy_queue)
            / holdings
        )
    else:
        avg_cost = Decimal("0")

    # Unrealized P&L = (current price - avg cost) * holdings
    unrealized_pnl = (
        (current_price - avg_cost) * holdings
        if current_price > 0 and holdings > 0
        else Decimal("0")
    )

    # Subtract fees from realized P&L
    realized_pnl_after_fees = realized_pnl - total_fees

    # Total P&L
    total_pnl = realized_pnl_after_fees + unrealized_pnl

    return PnLResult(
        realized_pnl=realized_pnl_after_fees,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        holdings=holdings,
        avg_cost=avg_cost,
        cycles=sell_count,
        buy_count=buy_count,
        sell_count=sell_count,
    )


def calculate_portfolio_pnl(
    trades_by_symbol: dict[str, list[TradeData]],
    current_prices: dict[str, Decimal],
) -> tuple[Decimal, Decimal, Decimal, int]:
    """Calculate aggregate P&L across all trading pairs.

    Args:
        trades_by_symbol: Dict mapping symbol to list of trades.
        current_prices: Dict mapping symbol to current price.

    Returns:
        Tuple of (total_realized, total_unrealized, total_pnl, total_cycles).
    """
    total_realized = Decimal("0")
    total_unrealized = Decimal("0")
    total_cycles = 0

    for symbol, trades in trades_by_symbol.items():
        current_price = current_prices.get(symbol, Decimal("0"))
        pnl = calculate_pnl_from_trades(trades, current_price)

        total_realized += pnl.realized_pnl
        total_unrealized += pnl.unrealized_pnl
        total_cycles += pnl.cycles

    total_pnl = total_realized + total_unrealized

    return total_realized, total_unrealized, total_pnl, total_cycles
