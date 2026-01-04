"""Binance-specific adapter with exchange quirks handling."""

from decimal import Decimal
from typing import Any

import structlog

from crypto_bot.config.settings import ExchangeSettings
from crypto_bot.exchange.base_exchange import (
    ExchangeError,
    InsufficientFundsError,
    InvalidOrderError,
    Order,
    OrderNotFoundError,
    OrderSide,
    OrderType,
)
from crypto_bot.exchange.ccxt_wrapper import CCXTExchange

logger = structlog.get_logger()


# Binance-specific error codes
BINANCE_ERROR_CODES: dict[int, str] = {
    -1000: "Unknown error",
    -1001: "Disconnected",
    -1002: "Unauthorized",
    -1003: "Too many requests",
    -1006: "Unexpected response",
    -1007: "Timeout",
    -1010: "Invalid message",
    -1015: "Too many orders",
    -1016: "Service shutting down",
    -1020: "Unsupported operation",
    -1021: "Invalid timestamp",
    -1022: "Invalid signature",
    -2010: "Insufficient balance",
    -2011: "Unknown order",
    -2013: "Order does not exist",
    -2014: "Bad API key format",
    -2015: "Invalid API key",
}


class BinanceAdapter(CCXTExchange):
    """Binance-specific exchange adapter.

    Extends CCXTExchange with Binance-specific handling for:
    - Testnet configuration
    - Binance filter validation (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL)
    - Binance-specific error codes
    - OCO and other Binance-specific order types
    """

    def __init__(self, settings: ExchangeSettings) -> None:
        """Initialize Binance adapter.

        Args:
            settings: Exchange configuration settings.

        Raises:
            ValueError: If exchange name is not 'binance'.
        """
        if settings.name != "binance":
            raise ValueError(
                f"BinanceAdapter requires exchange name 'binance', got '{settings.name}'"
            )
        super().__init__(settings)
        self._logger = logger.bind(
            component="binance_adapter",
            testnet=settings.testnet,
        )

    async def connect(self) -> None:
        """Initialize connection with Binance-specific configuration."""
        await super().connect()

        if self._settings.testnet:
            self._logger.info(
                "using_binance_testnet",
                url="testnet.binance.vision",
            )

    async def create_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        """Place order with Binance-specific validation.

        Validates order against Binance filters before submission.
        """
        # Validate against Binance filters
        validated_amount, validated_price = self.validate_order_params(
            symbol, amount, price
        )

        return await super().create_order(
            symbol=symbol,
            order_type=order_type,
            side=side,
            amount=validated_amount,
            price=validated_price,
        )

    def validate_order_params(
        self,
        symbol: str,
        amount: Decimal,
        price: Decimal | None,
    ) -> tuple[Decimal, Decimal | None]:
        """Validate and adjust order parameters per Binance filters.

        Applies:
        - LOT_SIZE filter (quantity step/min/max)
        - PRICE_FILTER (price precision/min/max)
        - MIN_NOTIONAL (minimum order value)

        Args:
            symbol: Trading pair symbol.
            amount: Order quantity.
            price: Order price (for limit orders).

        Returns:
            Tuple of (validated_amount, validated_price).

        Raises:
            InvalidOrderError: If order violates filters.
            InsufficientFundsError: If order value below MIN_NOTIONAL.
        """
        market = self._markets.get(symbol)
        if not market:
            return amount, price

        limits = market.get("limits", {})
        precision = market.get("precision", {})
        info = market.get("info", {})

        # Extract filters from market info
        filters = self._extract_filters(info)

        # Apply LOT_SIZE filter
        validated_amount = self._apply_lot_size_filter(
            amount, filters.get("LOT_SIZE"), limits
        )

        # Apply PRICE_FILTER
        validated_price = price
        if price is not None:
            validated_price = self._apply_price_filter(
                price, filters.get("PRICE_FILTER"), precision
            )

        # Check MIN_NOTIONAL
        self._check_min_notional(
            symbol, validated_amount, validated_price, filters.get("MIN_NOTIONAL"), limits
        )

        return validated_amount, validated_price

    def _extract_filters(self, market_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Extract filter configurations from Binance market info."""
        filters: dict[str, dict[str, Any]] = {}

        filter_list = market_info.get("filters", [])
        for f in filter_list:
            filter_type = f.get("filterType")
            if filter_type:
                filters[filter_type] = f

        return filters

    def _apply_lot_size_filter(
        self,
        amount: Decimal,
        lot_size_filter: dict[str, Any] | None,
        limits: dict[str, Any],
    ) -> Decimal:
        """Apply LOT_SIZE filter to quantity.

        LOT_SIZE requires:
        - quantity >= minQty
        - quantity <= maxQty
        - (quantity - minQty) % stepSize == 0
        """
        if not lot_size_filter:
            # Fall back to market limits
            min_amount = limits.get("amount", {}).get("min")
            if min_amount and amount < Decimal(str(min_amount)):
                raise InvalidOrderError(
                    f"Amount {amount} below minimum {min_amount}"
                )
            return amount

        min_qty = Decimal(str(lot_size_filter.get("minQty", "0")))
        max_qty = Decimal(str(lot_size_filter.get("maxQty", "999999999")))
        step_size = Decimal(str(lot_size_filter.get("stepSize", "0.00000001")))

        # Check bounds
        if amount < min_qty:
            raise InvalidOrderError(
                f"Amount {amount} below minimum {min_qty}"
            )
        if amount > max_qty:
            raise InvalidOrderError(
                f"Amount {amount} exceeds maximum {max_qty}"
            )

        # Round to step size
        adjusted_amount = self._round_to_step(amount, min_qty, step_size)

        return adjusted_amount

    def _apply_price_filter(
        self,
        price: Decimal,
        price_filter: dict[str, Any] | None,
        precision: dict[str, Any],
    ) -> Decimal:
        """Apply PRICE_FILTER to order price.

        PRICE_FILTER requires:
        - price >= minPrice
        - price <= maxPrice
        - price % tickSize == 0
        """
        if not price_filter:
            # Fall back to precision
            price_precision = precision.get("price")
            if price_precision:
                return self._round_to_precision(price, price_precision)
            return price

        min_price = Decimal(str(price_filter.get("minPrice", "0")))
        max_price = Decimal(str(price_filter.get("maxPrice", "999999999")))
        tick_size = Decimal(str(price_filter.get("tickSize", "0.00000001")))

        # Check bounds (only if > 0, 0 means disabled)
        if min_price > 0 and price < min_price:
            raise InvalidOrderError(
                f"Price {price} below minimum {min_price}"
            )
        if max_price > 0 and price > max_price:
            raise InvalidOrderError(
                f"Price {price} exceeds maximum {max_price}"
            )

        # Round to tick size
        if tick_size > 0:
            adjusted_price = (price // tick_size) * tick_size
            return adjusted_price

        return price

    def _check_min_notional(
        self,
        symbol: str,
        amount: Decimal,
        price: Decimal | None,
        min_notional_filter: dict[str, Any] | None,
        limits: dict[str, Any],
    ) -> None:
        """Check MIN_NOTIONAL filter.

        MIN_NOTIONAL requires:
        - price * quantity >= minNotional
        """
        if not price:
            # For market orders, we can't check this pre-trade
            return

        min_notional: Decimal | None = None

        if min_notional_filter:
            min_notional = Decimal(str(min_notional_filter.get("minNotional", "0")))
        else:
            # Fall back to market limits
            cost_min = limits.get("cost", {}).get("min")
            if cost_min:
                min_notional = Decimal(str(cost_min))

        if min_notional and min_notional > 0:
            order_value = amount * price
            if order_value < min_notional:
                raise InsufficientFundsError(
                    f"Order value {order_value} below minimum notional {min_notional} for {symbol}"
                )

    @staticmethod
    def _round_to_step(
        value: Decimal,
        min_value: Decimal,
        step_size: Decimal,
    ) -> Decimal:
        """Round value to step size, ensuring it's a valid increment from min.

        Args:
            value: The value to round.
            min_value: The minimum allowed value.
            step_size: The step increment.

        Returns:
            Rounded value aligned to step size.
        """
        if step_size <= 0:
            return value

        # Calculate how many steps from min
        steps = (value - min_value) // step_size
        adjusted = min_value + (steps * step_size)

        return adjusted

    def handle_binance_error(self, error_code: int, message: str) -> None:
        """Handle Binance-specific error codes.

        Args:
            error_code: Binance error code.
            message: Error message from Binance.

        Raises:
            Appropriate exception based on error code.
        """
        error_desc = BINANCE_ERROR_CODES.get(error_code, "Unknown error")

        self._logger.error(
            "binance_error",
            error_code=error_code,
            error_description=error_desc,
            message=message,
        )

        if error_code in (-2010,):
            raise InsufficientFundsError(f"Binance error {error_code}: {error_desc}")
        elif error_code in (-2011, -2013):
            raise OrderNotFoundError(f"Binance error {error_code}: {error_desc}")
        elif error_code in (-1002, -2014, -2015):
            from crypto_bot.exchange.base_exchange import AuthenticationError
            raise AuthenticationError(f"Binance error {error_code}: {error_desc}")
        else:
            raise ExchangeError(f"Binance error {error_code}: {error_desc}")
