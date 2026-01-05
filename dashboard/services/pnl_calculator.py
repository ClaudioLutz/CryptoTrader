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
    """Calculate realized and unrealized P&L from actual trade history.

    For grid trading:
    - Realized P&L = total sell value - total buy value (for closed positions)
    - Unrealized P&L = (current price - avg buy price) * holdings

    Args:
        trades: List of TradeData objects.
        current_price: Current market price for unrealized P&L calculation.

    Returns:
        PnLResult with all P&L metrics.
    """
    total_buy_cost = Decimal("0")
    total_sell_cost = Decimal("0")
    total_buy_amount = Decimal("0")
    total_sell_amount = Decimal("0")
    buy_count = 0
    sell_count = 0

    for trade in trades:
        try:
            # Calculate cost from price * amount if cost not available
            cost = trade.cost if trade.cost else trade.price * trade.amount
            amount = trade.amount
            side = trade.side.lower()

            if side == "buy":
                total_buy_cost += cost
                total_buy_amount += amount
                buy_count += 1
            elif side == "sell":
                total_sell_cost += cost
                total_sell_amount += amount
                sell_count += 1
        except (ValueError, TypeError, AttributeError):
            continue

    # Current holdings (what we bought minus what we sold)
    holdings = total_buy_amount - total_sell_amount

    # Average cost basis for current holdings
    avg_cost = total_buy_cost / total_buy_amount if total_buy_amount > 0 else Decimal("0")

    # Realized P&L = sell proceeds - cost of sold units
    realized_pnl = (
        total_sell_cost - (avg_cost * total_sell_amount)
        if total_sell_amount > 0
        else Decimal("0")
    )

    # Unrealized P&L = (current price - avg cost) * holdings
    unrealized_pnl = (
        (current_price - avg_cost) * holdings
        if current_price > 0 and holdings > 0
        else Decimal("0")
    )

    # Total P&L
    total_pnl = realized_pnl + unrealized_pnl

    return PnLResult(
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        holdings=holdings,
        avg_cost=avg_cost,
        cycles=min(buy_count, sell_count),
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
