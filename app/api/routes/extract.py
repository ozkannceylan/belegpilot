"""Extraction endpoint - full implementation."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.dependencies import DB, AuthenticatedKey
from app.config import settings
from app.core.pipeline import ExtractionPipeline
from app.models.schemas import ErrorResponse, ExtractionRequest, ExtractionResult

router = APIRouter()
pipeline = ExtractionPipeline()

ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024


@router.post(
    "/extract",
    response_model=ExtractionResult,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def extract_receipt(
    file: UploadFile = File(),  # noqa: B008
    force_ocr: bool = False,
    model_override: str | None = None,
    db: DB = None,
    api_key: AuthenticatedKey = None,
) -> ExtractionResult:
    """Extract structured data from a receipt or invoice image."""
    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Accepted: {', '.join(ALLOWED_TYPES)}",
        )

    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    request = ExtractionRequest(
        force_ocr=force_ocr,
        model_override=model_override,
    )

    try:
        result = await pipeline.process(
            file_bytes=file_bytes,
            content_type=file.content_type,
            db=db,
            api_key_prefix=api_key.key_prefix,
            request=request,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}") from e
