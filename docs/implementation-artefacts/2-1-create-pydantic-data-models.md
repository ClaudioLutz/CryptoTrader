# Story 2.1: Create Pydantic Data Models

Status: review

## Story

As a **developer**,
I want **Pydantic models that represent API response data**,
So that **data is validated, typed, and easy to work with in components**.

## Acceptance Criteria

1. **AC1:** `HealthResponse` model defined with status, uptime_seconds, message fields
2. **AC2:** `PairData` model defined with symbol, current_price, pnl_today, position_size, order_count
3. **AC3:** `DashboardData` model aggregates health, pairs, total_pnl, last_update
4. **AC4:** All models include field validation
5. **AC5:** Models can be instantiated from dict (API JSON response)
6. **AC6:** Models use correct Python types (Decimal for money, datetime for timestamps)

## Tasks / Subtasks

- [x] Task 1: Create data_models.py file (AC: 1-3)
  - [x] Create `HealthResponse` model
  - [x] Create `PairData` model
  - [x] Create `DashboardData` model

- [x] Task 2: Add field validation (AC: 4, 6)
  - [x] Add validators for status enum values
  - [x] Use Decimal for price and P&L fields
  - [x] Use datetime for timestamp fields

- [x] Task 3: Test model instantiation (AC: 5)
  - [x] Test creating models from dict
  - [x] Test validation error handling

## Dev Notes

### Data Models Implementation

[Source: docs/planning-artefacts/architecture.md - Format Patterns]

```python
"""CryptoTrader Dashboard - Data Models.

Pydantic models for API response parsing and validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Bot health status response."""

    status: Literal["healthy", "degraded", "error"] = Field(
        description="Current health status"
    )
    uptime_seconds: int = Field(
        ge=0,
        description="Bot uptime in seconds"
    )
    message: str | None = Field(
        default=None,
        description="Optional status message"
    )


class PairData(BaseModel):
    """Trading pair data."""

    symbol: str = Field(
        description="Trading pair symbol (e.g., BTC/USDT)"
    )
    current_price: Decimal = Field(
        description="Current market price"
    )
    pnl_today: Decimal = Field(
        description="Profit/loss for today"
    )
    position_size: Decimal = Field(
        default=Decimal("0"),
        description="Current position size"
    )
    order_count: int = Field(
        ge=0,
        default=0,
        description="Number of open orders"
    )


class DashboardData(BaseModel):
    """Aggregated dashboard data."""

    health: HealthResponse | None = Field(
        default=None,
        description="Bot health status"
    )
    pairs: list[PairData] = Field(
        default_factory=list,
        description="All trading pair data"
    )
    total_pnl: Decimal = Field(
        default=Decimal("0"),
        description="Total P&L across all pairs"
    )
    last_update: datetime | None = Field(
        default=None,
        description="Timestamp of last successful data fetch"
    )
```

### Type Rules

[Source: _bmad-output/project-context.md - Python-Specific Rules]

- **Decimal for Money:** Use `Decimal` not `float` for all financial calculations
- **Union Syntax:** Use `X | None` not `Optional[X]` (Python 3.11+)
- **Type Hints:** Required on all fields

### Usage Example

```python
# From API response dict
data = {
    "status": "healthy",
    "uptime_seconds": 3600,
    "message": None
}
health = HealthResponse(**data)

# Or using model_validate
health = HealthResponse.model_validate(data)
```

### API Response Mapping

The models should match the existing bot API responses:
- `/health` → `HealthResponse`
- `/pairs` → `list[PairData]`
- `/dashboard` → `DashboardData` (if aggregated endpoint exists)

### Project Structure Notes

- File location: `dashboard/services/data_models.py`
- Import pattern: `from dashboard.services.data_models import HealthResponse`

### References

- [Architecture Document](docs/planning-artefacts/architecture.md#format-patterns)
- [Project Context](/_bmad-output/project-context.md#python-specific-rules)
- [Pydantic Documentation](https://docs.pydantic.dev/latest/)

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- Created HealthResponse with Literal["healthy", "degraded", "error"] status
- Created PairData with Decimal for price/pnl fields, added pnl_percent field
- Created DashboardData with computed properties (pair_count, is_healthy)
- Added OrderData and TradeData models for expanded row details (future stories)
- All models use X | None syntax (Python 3.11+)
- Field constraints: ge=0 for prices, amounts, counts
- Tested model_validate() from dict successfully

### File List

- dashboard/services/data_models.py (created)

