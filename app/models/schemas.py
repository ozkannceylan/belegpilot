"""Pydantic models for API request/response and internal data flow."""

from datetime import UTC
from datetime import date as DateType  # noqa: N812
from datetime import datetime as DateTimeType  # noqa: N812
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class ExpenseCategory(StrEnum):
    """Categories for expense classification."""
    GROCERIES = "groceries"
    RESTAURANT = "restaurant"
    TRANSPORT = "transport"
    OFFICE = "office"
    ACCOMMODATION = "accommodation"
    ENTERTAINMENT = "entertainment"
    UTILITIES = "utilities"
    OTHER = "other"


class LineItem(BaseModel):
    """A single line item from a receipt."""
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    total: float

    @field_validator("total")
    @classmethod
    def total_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Line item total must be non-negative")
        return v


class ReceiptData(BaseModel):
    """Core extracted data from a receipt/invoice."""
    vendor: str | None = None
    date: DateType | None = None
    total_amount: float | None = None
    currency: str | None = Field(None, max_length=3)
    tax_amount: float | None = None
    tax_rate: float | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    payment_method: str | None = None
    receipt_number: str | None = None
    category: ExpenseCategory = ExpenseCategory.OTHER

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str | None) -> str | None:
        if v is not None:
            return v.upper()
        return v


class ExtractionResult(BaseModel):
    """Full result returned to API caller."""
    id: UUID = Field(default_factory=uuid4)
    status: str = "success"  # success | partial | failed
    data: ReceiptData
    confidence_score: float = Field(ge=0.0, le=1.0)
    extraction_method: str = "vlm"  # vlm | ocr | hybrid
    model_used: str | None = None
    processing_time_ms: int = 0
    cost_usd: float = 0.0
    created_at: DateTimeType = Field(default_factory=lambda: DateTimeType.now(UTC))


class ExtractionRequest(BaseModel):
    """Optional parameters for extraction request."""
    force_ocr: bool = False  # Skip VLM, use OCR only
    model_override: str | None = None  # Use specific model


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str
    detail: str | None = None
    request_id: str | None = None


class APIKeyCreate(BaseModel):
    """Request model for creating a new API key."""
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class APIKeyResponse(BaseModel):
    """Returned ONCE when key is created. Key never shown again."""
    key: str  # Full key, shown only at creation
    name: str
    key_prefix: str  # riq_live_<first8chars>... for identification
    created_at: DateTimeType


class CostSummary(BaseModel):
    """Cost tracking summary."""
    daily_spend_usd: float
    monthly_spend_usd: float
    daily_limit_usd: float
    monthly_limit_usd: float
    requests_today: int
    requests_this_month: int
