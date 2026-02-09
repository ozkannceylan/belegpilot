"""API endpoint tests."""

from unittest.mock import patch

import pytest

from app.models.schemas import ExtractionResult, ReceiptData


@pytest.mark.asyncio
async def test_extract_requires_file(client):
    """Extract endpoint requires a file upload."""
    response = await client.post("/api/v1/extract")
    assert response.status_code == 422  # Missing file


@pytest.mark.asyncio
async def test_extract_rejects_wrong_type(client):
    """Extract endpoint rejects non-image files."""
    response = await client.post(
        "/api/v1/extract",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_success(client, sample_receipt_bytes, mock_vlm_response):
    """Successful extraction returns ExtractionResult."""
    with patch("app.core.pipeline.ExtractionPipeline.process") as mock_process:
        mock_result = ExtractionResult(
            status="success",
            data=ReceiptData(**mock_vlm_response),
            confidence_score=0.92,
            extraction_method="vlm",
            model_used="qwen/qwen2.5-vl-72b-instruct",
            processing_time_ms=3500,
            cost_usd=0.002,
        )
        mock_process.return_value = mock_result

        response = await client.post(
            "/api/v1/extract",
            files={"file": ("receipt.jpg", sample_receipt_bytes, "image/jpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["vendor"] == "REWE"
    assert data["confidence_score"] == 0.92


@pytest.mark.asyncio
async def test_extract_force_ocr(client, sample_receipt_bytes):
    """Force OCR mode skips VLM."""
    with patch("app.core.pipeline.ExtractionPipeline.process") as mock_process:
        mock_result = ExtractionResult(
            status="partial",
            data=ReceiptData(vendor="REWE", total_amount=47.83),
            confidence_score=0.5,
            extraction_method="ocr",
            processing_time_ms=1000,
        )
        mock_process.return_value = mock_result

        response = await client.post(
            "/api/v1/extract",
            files={"file": ("receipt.jpg", sample_receipt_bytes, "image/jpeg")},
            params={"force_ocr": True},
        )

    assert response.status_code == 200
    assert response.json()["extraction_method"] == "ocr"


@pytest.mark.asyncio
async def test_extract_oversized_file(client):
    """Oversized file returns 413."""
    # Create a file just over the max size limit
    from app.config import settings
    oversized = b"x" * (settings.max_upload_size_mb * 1024 * 1024 + 1)

    with patch("app.core.pipeline.ExtractionPipeline.process"):
        response = await client.post(
            "/api/v1/extract",
            files={"file": ("big.jpg", oversized, "image/jpeg")},
        )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()
