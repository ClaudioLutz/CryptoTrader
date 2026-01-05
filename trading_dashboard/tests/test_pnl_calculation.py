"""Unit tests for P&L calculation logic."""

import pytest


def calculate_pnl_from_trades(trades: list, current_price: float = 0) -> dict:
    """Calculate realized and unrealized P&L from actual trade history.

    For grid trading:
    - Realized P&L = total sell value - total buy value (for closed positions)
    - Unrealized P&L = (current price - avg buy price) * holdings

    Returns dict with realized_pnl, unrealized_pnl, total_pnl, holdings, avg_cost, cycles
    """
    total_buy_cost = 0.0
    total_sell_cost = 0.0
    total_buy_amount = 0.0
    total_sell_amount = 0.0
    buy_count = 0
    sell_count = 0

    for trade in trades:
        try:
            cost = float(trade.get("cost", 0) or 0)
            amount = float(trade.get("amount", 0) or 0)
            side = trade.get("side", "").lower()
            if side == "buy":
                total_buy_cost += cost
                total_buy_amount += amount
                buy_count += 1
            elif side == "sell":
                total_sell_cost += cost
                total_sell_amount += amount
                sell_count += 1
        except (ValueError, TypeError):
            continue

    # Current holdings (what we bought minus what we sold)
    holdings = total_buy_amount - total_sell_amount

    # Average cost basis for current holdings
    avg_cost = total_buy_cost / total_buy_amount if total_buy_amount > 0 else 0

    # Realized P&L = sell proceeds - cost of sold units
    realized_pnl = (
        total_sell_cost - (avg_cost * total_sell_amount) if total_sell_amount > 0 else 0
    )

    # Unrealized P&L = (current price - avg cost) * holdings
    unrealized_pnl = (
        (current_price - avg_cost) * holdings
        if current_price > 0 and holdings > 0
        else 0
    )

    # Total P&L
    total_pnl = realized_pnl + unrealized_pnl

    return {
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "holdings": holdings,
        "avg_cost": avg_cost,
        "cycles": min(buy_count, sell_count),
        "buy_count": buy_count,
        "sell_count": sell_count,
    }


class TestPnLCalculation:
    """Test suite for P&L calculation function."""

    def test_empty_trades(self):
        """Test with no trades."""
        result = calculate_pnl_from_trades([])
        assert result["realized_pnl"] == 0
        assert result["unrealized_pnl"] == 0
        assert result["total_pnl"] == 0
        assert result["holdings"] == 0
        assert result["avg_cost"] == 0
        assert result["cycles"] == 0

    def test_single_buy_no_current_price(self):
        """Test single buy with no current price (no unrealized P&L)."""
        trades = [{"side": "buy", "amount": 1.0, "cost": 50000}]
        result = calculate_pnl_from_trades(trades, current_price=0)

        assert result["holdings"] == 1.0
        assert result["avg_cost"] == 50000
        assert result["realized_pnl"] == 0
        assert result["unrealized_pnl"] == 0
        assert result["buy_count"] == 1
        assert result["sell_count"] == 0
        assert result["cycles"] == 0

    def test_single_buy_with_current_price_profit(self):
        """Test single buy with current price showing profit."""
        trades = [{"side": "buy", "amount": 1.0, "cost": 50000}]
        result = calculate_pnl_from_trades(trades, current_price=55000)

        assert result["holdings"] == 1.0
        assert result["avg_cost"] == 50000
        assert result["realized_pnl"] == 0
        assert result["unrealized_pnl"] == 5000  # (55000 - 50000) * 1.0
        assert result["total_pnl"] == 5000

    def test_single_buy_with_current_price_loss(self):
        """Test single buy with current price showing loss."""
        trades = [{"side": "buy", "amount": 1.0, "cost": 50000}]
        result = calculate_pnl_from_trades(trades, current_price=45000)

        assert result["holdings"] == 1.0
        assert result["unrealized_pnl"] == -5000  # (45000 - 50000) * 1.0
        assert result["total_pnl"] == -5000

    def test_buy_and_sell_complete_cycle(self):
        """Test complete buy and sell cycle (realized P&L)."""
        trades = [
            {"side": "buy", "amount": 1.0, "cost": 50000},
            {"side": "sell", "amount": 1.0, "cost": 55000},
        ]
        result = calculate_pnl_from_trades(trades, current_price=55000)

        assert result["holdings"] == 0  # 1.0 - 1.0
        assert result["avg_cost"] == 50000
        assert result["realized_pnl"] == 5000  # 55000 - 50000
        assert result["unrealized_pnl"] == 0  # No holdings
        assert result["total_pnl"] == 5000
        assert result["cycles"] == 1

    def test_multiple_buys_different_prices(self):
        """Test multiple buys at different prices (average cost)."""
        trades = [
            {"side": "buy", "amount": 1.0, "cost": 50000},
            {"side": "buy", "amount": 1.0, "cost": 60000},
        ]
        result = calculate_pnl_from_trades(trades, current_price=55000)

        assert result["holdings"] == 2.0
        assert result["avg_cost"] == 55000  # (50000 + 60000) / 2
        assert result["unrealized_pnl"] == 0  # (55000 - 55000) * 2.0
        assert result["buy_count"] == 2

    def test_partial_sell(self):
        """Test partial position close."""
        trades = [
            {"side": "buy", "amount": 2.0, "cost": 100000},  # avg cost = 50000
            {"side": "sell", "amount": 1.0, "cost": 55000},  # sold 1 at 55000
        ]
        result = calculate_pnl_from_trades(trades, current_price=60000)

        assert result["holdings"] == 1.0  # 2.0 - 1.0
        assert result["avg_cost"] == 50000
        assert result["realized_pnl"] == 5000  # 55000 - (50000 * 1)
        assert result["unrealized_pnl"] == 10000  # (60000 - 50000) * 1.0
        assert result["total_pnl"] == 15000
        assert result["cycles"] == 1

    def test_grid_trading_scenario(self):
        """Test typical grid trading scenario with multiple cycles."""
        trades = [
            # Cycle 1
            {"side": "buy", "amount": 0.1, "cost": 5000},   # Buy at 50000
            {"side": "sell", "amount": 0.1, "cost": 5100},  # Sell at 51000
            # Cycle 2
            {"side": "buy", "amount": 0.1, "cost": 4900},   # Buy at 49000
            {"side": "sell", "amount": 0.1, "cost": 5000},  # Sell at 50000
            # Current position
            {"side": "buy", "amount": 0.1, "cost": 4800},   # Buy at 48000
        ]
        result = calculate_pnl_from_trades(trades, current_price=49000)

        assert result["buy_count"] == 3
        assert result["sell_count"] == 2
        assert result["cycles"] == 2
        assert result["holdings"] == pytest.approx(0.1)  # 0.3 - 0.2 (use approx for float)

    def test_invalid_trade_data_skipped(self):
        """Test that invalid trade data is skipped.

        Note: None values are converted to 0 via `or 0` fallback,
        so only string values that can't be converted to float are skipped.
        """
        trades = [
            {"side": "buy", "amount": 1.0, "cost": 50000},
            {"side": "buy", "amount": "invalid", "cost": "bad"},  # Skipped - string can't convert
            {"side": "sell", "amount": "not_a_number", "cost": 27500},  # Skipped - string can't convert
            {"side": "sell", "amount": 0.5, "cost": 27500},  # Valid
        ]
        result = calculate_pnl_from_trades(trades, current_price=55000)

        assert result["buy_count"] == 1
        assert result["sell_count"] == 1
        assert result["holdings"] == 0.5

    def test_case_insensitive_side(self):
        """Test that side matching is case insensitive."""
        trades = [
            {"side": "BUY", "amount": 1.0, "cost": 50000},
            {"side": "Buy", "amount": 1.0, "cost": 50000},
            {"side": "SELL", "amount": 1.0, "cost": 55000},
        ]
        result = calculate_pnl_from_trades(trades, current_price=55000)

        assert result["buy_count"] == 2
        assert result["sell_count"] == 1
        assert result["holdings"] == 1.0

    def test_zero_cost_trades(self):
        """Test handling of zero-cost trades."""
        trades = [
            {"side": "buy", "amount": 1.0, "cost": 0},
        ]
        result = calculate_pnl_from_trades(trades, current_price=50000)

        assert result["holdings"] == 1.0
        assert result["avg_cost"] == 0
        assert result["unrealized_pnl"] == 50000  # (50000 - 0) * 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
