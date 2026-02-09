"""Results endpoint - full implementation."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.dependencies import DB, AuthenticatedKey
from app.models.database import ExtractionRecord
from app.models.schemas import ExtractionResult, LineItem, ReceiptData

router = APIRouter()


@router.get("/results/{result_id}", response_model=ExtractionResult)
async def get_result(
    result_id: UUID,
    db: DB = None,
    api_key: AuthenticatedKey = None,
) -> ExtractionResult:
    """Retrieve a previous extraction result by ID."""
    result = await db.execute(
        select(ExtractionRecord).where(ExtractionRecord.id == result_id)
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Result not found")

    # Reconstruct ExtractionResult from DB record
    line_items = [LineItem(**item) for item in (record.line_items or [])]

    return ExtractionResult(
        id=record.id,
        status=record.status,
        data=ReceiptData(
            vendor=record.vendor,
            date=record.receipt_date,
            total_amount=record.total_amount,
            currency=record.currency,
            tax_amount=record.tax_amount,
            tax_rate=record.tax_rate,
            line_items=line_items,
            payment_method=record.payment_method,
            receipt_number=record.receipt_number,
            category=record.category or "other",
        ),
        confidence_score=record.confidence_score,
        extraction_method=record.extraction_method,
        model_used=record.model_used,
        processing_time_ms=record.processing_time_ms,
        cost_usd=record.cost_usd,
        created_at=record.created_at,
    )
