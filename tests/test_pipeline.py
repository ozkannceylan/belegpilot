"""Pipeline integration tests with mocked dependencies."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.core.pipeline import ExtractionPipeline
from app.models.schemas import ExtractionRequest, LineItem, ReceiptData
from app.services.openrouter import BudgetExceededError


@pytest.fixture
def pipeline():
    """Create pipeline with mocked external services."""
    p = ExtractionPipeline()
    return p


@pytest.fixture
def mock_vlm_result():
    """Mock successful VLM extraction result."""
    return ReceiptData(
        vendor="REWE",
        date=date(2026, 2, 7),
        total_amount=47.83,
        currency="EUR",
        tax_amount=7.63,
        tax_rate=19.0,
        line_items=[
            LineItem(description="Milk", quantity=2, unit_price=1.29, total=2.58),
            LineItem(description="Olivenoel", quantity=1, unit_price=5.99, total=5.99),
        ],
        payment_method="Visa ****1234",
    )


@pytest.fixture
def mock_ocr_result():
    """Mock OCR extraction result."""
    return ReceiptData(
        vendor="REWE Markt",
        total_amount=47.83,
        currency="EUR",
    )


@pytest.mark.asyncio
async def test_pipeline_vlm_success(
    pipeline, sample_receipt_bytes, mock_vlm_result, test_db
):
    """Full pipeline with mocked VLM returns ExtractionResult."""
    vlm_meta = {
        "model": "qwen/qwen2-vl-72b-instruct",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_usd": 0.001,
        "elapsed_ms": 3000,
        "raw_response": '{"vendor": "REWE"}',
    }

    with (
        patch.object(
            pipeline.preprocessor, "preprocess", new_callable=AsyncMock
        ) as mock_preprocess,
        patch.object(
            pipeline.vlm_extractor, "extract", new_callable=AsyncMock
        ) as mock_vlm,
    ):
        mock_preprocess.return_value = (sample_receipt_bytes, "base64data")
        mock_vlm.return_value = (mock_vlm_result, vlm_meta)

        result = await pipeline.process(
            file_bytes=sample_receipt_bytes,
            content_type="image/jpeg",
            db=test_db,
            api_key_prefix="riq_live_test...",
        )

    assert result.status == "success"
    assert result.data.vendor == "REWE"
    assert result.confidence_score > 0.5
    assert result.extraction_method == "vlm"
    assert result.cost_usd == 0.001


@pytest.mark.asyncio
async def test_pipeline_vlm_failure_falls_back_to_ocr(
    pipeline, sample_receipt_bytes, mock_ocr_result, test_db
):
    """When VLM fails, pipeline falls back to OCR."""
    with (
        patch.object(
            pipeline.preprocessor, "preprocess", new_callable=AsyncMock
        ) as mock_preprocess,
        patch.object(
            pipeline.vlm_extractor, "extract", new_callable=AsyncMock
        ) as mock_vlm,
        patch.object(
            pipeline.ocr_extractor, "extract", new_callable=AsyncMock
        ) as mock_ocr,
    ):
        mock_preprocess.return_value = (sample_receipt_bytes, "base64data")
        mock_vlm.side_effect = RuntimeError("VLM API unreachable")
        mock_ocr.return_value = (mock_ocr_result, {"model": "tesseract-ocr"})

        result = await pipeline.process(
            file_bytes=sample_receipt_bytes,
            content_type="image/jpeg",
            db=test_db,
            api_key_prefix="riq_live_test...",
        )

    assert result.extraction_method == "ocr"
    assert result.data.vendor == "REWE Markt"


@pytest.mark.asyncio
async def test_pipeline_budget_exceeded_falls_back_to_ocr(
    pipeline, sample_receipt_bytes, mock_ocr_result, test_db
):
    """When budget exceeded, pipeline uses OCR only."""
    with (
        patch.object(
            pipeline.preprocessor, "preprocess", new_callable=AsyncMock
        ) as mock_preprocess,
        patch.object(
            pipeline.vlm_extractor, "extract", new_callable=AsyncMock
        ) as mock_vlm,
        patch.object(
            pipeline.ocr_extractor, "extract", new_callable=AsyncMock
        ) as mock_ocr,
    ):
        mock_preprocess.return_value = (sample_receipt_bytes, "base64data")
        mock_vlm.side_effect = BudgetExceededError("Daily budget exceeded")
        mock_ocr.return_value = (mock_ocr_result, {"model": "tesseract-ocr"})

        result = await pipeline.process(
            file_bytes=sample_receipt_bytes,
            content_type="image/jpeg",
            db=test_db,
            api_key_prefix="riq_live_test...",
        )

    assert result.extraction_method == "ocr"


@pytest.mark.asyncio
async def test_pipeline_force_ocr(
    pipeline, sample_receipt_bytes, mock_ocr_result, test_db
):
    """force_ocr=True skips VLM entirely."""
    with (
        patch.object(
            pipeline.preprocessor, "preprocess", new_callable=AsyncMock
        ) as mock_preprocess,
        patch.object(
            pipeline.vlm_extractor, "extract", new_callable=AsyncMock
        ) as mock_vlm,
        patch.object(
            pipeline.ocr_extractor, "extract", new_callable=AsyncMock
        ) as mock_ocr,
    ):
        mock_preprocess.return_value = (sample_receipt_bytes, "base64data")
        mock_ocr.return_value = (mock_ocr_result, {"model": "tesseract-ocr"})

        request = ExtractionRequest(force_ocr=True)
        result = await pipeline.process(
            file_bytes=sample_receipt_bytes,
            content_type="image/jpeg",
            db=test_db,
            api_key_prefix="riq_live_test...",
            request=request,
        )

    # VLM should NOT have been called
    mock_vlm.assert_not_called()
    assert result.extraction_method == "ocr"


@pytest.mark.asyncio
async def test_pipeline_vlm_returns_none_falls_back(
    pipeline, sample_receipt_bytes, mock_ocr_result, test_db
):
    """When VLM returns None (parse failure), falls back to OCR."""
    vlm_meta = {
        "model": "qwen/qwen2-vl-72b-instruct",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cost_usd": 0.001,
        "elapsed_ms": 3000,
        "raw_response": "invalid json",
    }

    with (
        patch.object(
            pipeline.preprocessor, "preprocess", new_callable=AsyncMock
        ) as mock_preprocess,
        patch.object(
            pipeline.vlm_extractor, "extract", new_callable=AsyncMock
        ) as mock_vlm,
        patch.object(
            pipeline.ocr_extractor, "extract", new_callable=AsyncMock
        ) as mock_ocr,
    ):
        mock_preprocess.return_value = (sample_receipt_bytes, "base64data")
        mock_vlm.return_value = (None, vlm_meta)
        mock_ocr.return_value = (mock_ocr_result, {"model": "tesseract-ocr"})

        result = await pipeline.process(
            file_bytes=sample_receipt_bytes,
            content_type="image/jpeg",
            db=test_db,
            api_key_prefix="riq_live_test...",
        )

    assert result.data.vendor == "REWE Markt"


@pytest.mark.asyncio
async def test_pipeline_db_failure_still_returns_result(
    pipeline, sample_receipt_bytes, mock_ocr_result, test_db
):
    """If DB commit fails, result should still be returned."""
    with (
        patch.object(
            pipeline.preprocessor, "preprocess", new_callable=AsyncMock
        ) as mock_preprocess,
        patch.object(
            pipeline.vlm_extractor, "extract", new_callable=AsyncMock
        ) as mock_vlm,
        patch.object(
            pipeline.ocr_extractor, "extract", new_callable=AsyncMock
        ) as mock_ocr,
        patch.object(
            pipeline, "_store_result", new_callable=AsyncMock
        ) as mock_store,
    ):
        mock_preprocess.return_value = (sample_receipt_bytes, "base64data")
        mock_vlm.side_effect = RuntimeError("VLM down")
        mock_ocr.return_value = (mock_ocr_result, {"model": "tesseract-ocr"})
        mock_store.side_effect = Exception("DB commit failed")

        result = await pipeline.process(
            file_bytes=sample_receipt_bytes,
            content_type="image/jpeg",
            db=test_db,
            api_key_prefix="riq_live_test...",
        )

    # Should still return a result even though DB write failed
    assert result is not None
    assert result.data.vendor == "REWE Markt"
