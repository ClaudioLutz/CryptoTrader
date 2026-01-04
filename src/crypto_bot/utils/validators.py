"""Input validation utilities for configuration and trading parameters.

This module provides:
- Symbol format validation
- Numeric value validation
- Risk parameter validation
- Configuration consistency checks
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str):
        """Initialize validation error.

        Args:
            field: Field that failed validation.
            message: Error message.
        """
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_symbol(symbol: str) -> str:
    """Validate trading symbol format.

    Args:
        symbol: Trading pair symbol.

    Returns:
        Validated symbol.

    Raises:
        ValidationError: If format is invalid.
    """
    pattern = r"^[A-Z0-9]+/[A-Z0-9]+$"
    if not re.match(pattern, symbol):
        raise ValidationError(
            "symbol",
            f"Invalid format: {symbol}. Expected 'BASE/QUOTE' (e.g., 'BTC/USDT')",
        )
    return symbol


def validate_positive_decimal(value: Any, field_name: str) -> Decimal:
    """Validate value is positive decimal.

    Args:
        value: Value to validate.
        field_name: Name of field for error message.

    Returns:
        Validated decimal value.

    Raises:
        ValidationError: If value is not positive decimal.
    """
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(field_name, f"Invalid number: {value}")

    if dec <= 0:
        raise ValidationError(field_name, f"Must be positive, got: {dec}")

    return dec


def validate_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    """Validate value is non-negative decimal.

    Args:
        value: Value to validate.
        field_name: Name of field for error message.

    Returns:
        Validated decimal value.

    Raises:
        ValidationError: If value is negative.
    """
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(field_name, f"Invalid number: {value}")

    if dec < 0:
        raise ValidationError(field_name, f"Must be non-negative, got: {dec}")

    return dec


def validate_percentage(
    value: Any,
    field_name: str,
    allow_zero: bool = False,
) -> Decimal:
    """Validate value is valid percentage (0-1).

    Args:
        value: Value to validate.
        field_name: Name of field for error message.
        allow_zero: Whether to allow zero.

    Returns:
        Validated decimal value.

    Raises:
        ValidationError: If value is not valid percentage.
    """
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(field_name, f"Invalid number: {value}")

    if dec < 0 or dec > 1:
        raise ValidationError(field_name, f"Must be between 0 and 1, got: {dec}")

    if not allow_zero and dec == 0:
        raise ValidationError(field_name, "Must be greater than 0")

    return dec


def validate_price_range(lower: Decimal, upper: Decimal) -> None:
    """Validate price range is valid.

    Args:
        lower: Lower price bound.
        upper: Upper price bound.

    Raises:
        ValidationError: If range is invalid.
    """
    if lower >= upper:
        raise ValidationError(
            "price_range",
            f"Lower price ({lower}) must be less than upper ({upper})",
        )

    if lower <= 0:
        raise ValidationError("lower_price", "Lower price must be positive")

    spread = (upper - lower) / lower
    if spread > Decimal("2.0"):
        raise ValidationError(
            "price_range",
            f"Price range too wide ({spread:.0%}). Consider narrowing.",
        )


def validate_grid_count(value: int) -> int:
    """Validate grid count is within acceptable range.

    Args:
        value: Number of grids.

    Returns:
        Validated grid count.

    Raises:
        ValidationError: If count is out of range.
    """
    if value < 3:
        raise ValidationError("num_grids", "Must be at least 3")
    if value > 100:
        raise ValidationError("num_grids", "Cannot exceed 100")
    return value


def validate_risk_parameters(
    max_position_pct: Decimal,
    max_daily_loss_pct: Decimal,
    risk_per_trade_pct: Decimal,
) -> list[str]:
    """Validate risk parameters are consistent.

    Args:
        max_position_pct: Maximum position as percentage of balance.
        max_daily_loss_pct: Maximum daily loss percentage.
        risk_per_trade_pct: Risk per trade percentage.

    Returns:
        List of warning messages (empty if all valid).
    """
    warnings = []

    if max_position_pct > Decimal("0.5"):
        warnings.append(
            f"max_position_pct ({max_position_pct:.0%}) exceeds recommended 50%"
        )

    if risk_per_trade_pct > Decimal("0.05"):
        warnings.append(
            f"risk_per_trade_pct ({risk_per_trade_pct:.0%}) exceeds recommended 5%"
        )

    if max_daily_loss_pct < risk_per_trade_pct:
        warnings.append(
            "max_daily_loss_pct should be >= risk_per_trade_pct"
        )

    return warnings


class ValidatedGridConfig(BaseModel):
    """Pydantic model for validated grid configuration."""

    symbol: str
    lower_price: Decimal
    upper_price: Decimal
    num_grids: int
    total_investment: Decimal
    stop_loss_pct: Decimal = Decimal("0.10")

    @field_validator("symbol")
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        return validate_symbol(v)

    @field_validator("lower_price", "upper_price", "total_investment")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Must be positive")
        return v

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_loss(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 1:
            raise ValueError("Must be between 0 and 1")
        return v

    @field_validator("num_grids")
    @classmethod
    def validate_grid_count_field(cls, v: int) -> int:
        return validate_grid_count(v)

    @model_validator(mode="after")
    def validate_price_range_model(self) -> "ValidatedGridConfig":
        validate_price_range(self.lower_price, self.upper_price)
        return self


class ValidatedRiskConfig(BaseModel):
    """Pydantic model for validated risk configuration."""

    max_position_pct: Decimal = Decimal("0.20")
    max_daily_loss_pct: Decimal = Decimal("0.05")
    max_drawdown_pct: Decimal = Decimal("0.15")
    risk_per_trade_pct: Decimal = Decimal("0.02")

    @field_validator("max_position_pct")
    @classmethod
    def validate_max_position(cls, v: Decimal) -> Decimal:
        if v > Decimal("0.5"):
            raise ValueError("max_position_pct should not exceed 50%")
        return validate_percentage(v, "max_position_pct")

    @field_validator("risk_per_trade_pct")
    @classmethod
    def validate_risk_per_trade(cls, v: Decimal) -> Decimal:
        if v > Decimal("0.05"):
            raise ValueError("risk_per_trade_pct should not exceed 5%")
        return validate_percentage(v, "risk_per_trade_pct")

    @model_validator(mode="after")
    def validate_risk_consistency(self) -> "ValidatedRiskConfig":
        if self.max_daily_loss_pct < self.risk_per_trade_pct:
            raise ValueError(
                "max_daily_loss_pct must be >= risk_per_trade_pct"
            )
        return self


def validate_all_config(settings: Any) -> tuple[list[str], list[str]]:
    """Validate all configuration at startup.

    Args:
        settings: Application settings object.

    Returns:
        Tuple of (errors, warnings).
    """
    errors = []
    warnings = []

    # Validate exchange settings
    if hasattr(settings, "exchange"):
        if not settings.exchange.testnet and hasattr(settings, "trading"):
            if getattr(settings.trading, "dry_run", True):
                warnings.append(
                    "Running dry-run on mainnet - no trades will execute"
                )

    # Validate trading settings
    if hasattr(settings, "trading"):
        try:
            validate_symbol(settings.trading.symbol)
        except ValidationError as e:
            errors.append(str(e))

    # Validate risk settings
    if hasattr(settings, "risk"):
        risk = settings.risk
        risk_warnings = validate_risk_parameters(
            getattr(risk, "max_position_pct", Decimal("0.20")),
            getattr(risk, "max_daily_loss_pct", Decimal("0.05")),
            getattr(risk, "risk_per_trade_pct", Decimal("0.02")),
        )
        warnings.extend(risk_warnings)

    return errors, warnings
