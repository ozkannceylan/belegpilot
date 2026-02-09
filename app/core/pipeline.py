"""Main orchestrator that ties everything together."""

import time
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.categorizer import ExpenseCategorizer
from app.core.extractor_ocr import OCRExtractor
from app.core.extractor_vlm import VLMExtractor
from app.core.preprocessor import ImagePreprocessor
from app.core.validator import ReceiptValidator
from app.models.database import ExtractionRecord
from app.models.schemas import ExtractionRequest, ExtractionResult, ReceiptData
from app.services.openrouter import BudgetExceededError, OpenRouterClient

logger = structlog.get_logger()

VLM_CONFIDENCE_THRESHOLD = 0.5  # Below this, supplement with OCR


class ExtractionPipeline:
    """Orchestrates the full receipt extraction flow."""

    def __init__(self) -> None:
        self.preprocessor = ImagePreprocessor()
        self.openrouter = OpenRouterClient()
        self.vlm_extractor = VLMExtractor(self.openrouter)
        self.ocr_extractor = OCRExtractor()
        self.validator = ReceiptValidator()
        self.categorizer = ExpenseCategorizer()

    async def close(self) -> None:
        """Clean up resources."""
        await self.openrouter.close()

    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        db: AsyncSession,
        api_key_prefix: str,
        request: ExtractionRequest | None = None,
    ) -> ExtractionResult:
        """Full extraction pipeline.

        Flow:
        1. Preprocess image
        2. Try VLM extraction (unless force_ocr or budget exceeded)
        3. Validate + compute confidence
        4. If confidence < threshold, supplement with OCR
        5. Categorize expense
        6. Store result in DB
        7. Return ExtractionResult
        """
        start_time = time.time()
        request = request or ExtractionRequest()

        # Step 1: Preprocess
        jpeg_bytes, image_b64 = await self.preprocessor.preprocess(
            file_bytes, content_type
        )

        receipt_data = None
        extraction_method = "vlm"
        model_used = None
        cost_usd = 0.0
        raw_response = None

        # Step 2: VLM extraction (unless force_ocr)
        if not request.force_ocr:
            try:
                receipt_data, vlm_meta = await self.vlm_extractor.extract(
                    image_base64=image_b64,
                    db=db,
                    model_override=request.model_override,
                )
                model_used = vlm_meta.get("model")
                cost_usd = vlm_meta.get("cost_usd", 0.0)
                raw_response = vlm_meta.get("raw_response")
            except BudgetExceededError:
                logger.warning("Budget exceeded, falling back to OCR only")
                extraction_method = "ocr"
            except Exception as e:
                logger.error("VLM extraction failed", error=str(e))
                extraction_method = "ocr"

        # Step 3: Validate VLM result
        vlm_parsed = receipt_data is not None
        if receipt_data:
            receipt_data, confidence, field_scores = self.validator.validate_and_score(
                receipt_data, vlm_parsed_cleanly=True
            )
        else:
            confidence = 0.0

        # Step 4: OCR fallback if needed
        if (
            receipt_data is None
            or confidence < VLM_CONFIDENCE_THRESHOLD
            or request.force_ocr
        ):
            ocr_data, ocr_meta = await self.ocr_extractor.extract(jpeg_bytes)
            if receipt_data is None:
                receipt_data = ocr_data
                extraction_method = "ocr"
            else:
                receipt_data = self._merge_results(receipt_data, ocr_data)
                extraction_method = "hybrid"
            # Re-validate after merge/OCR
            receipt_data, confidence, field_scores = self.validator.validate_and_score(
                receipt_data, vlm_parsed_cleanly=vlm_parsed
            )

        # Step 5: Categorize
        if receipt_data:
            category = self.categorizer.categorize(receipt_data)
            receipt_data.category = category

        # Fallback if nothing worked
        if receipt_data is None:
            receipt_data = ReceiptData()

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Step 6: Build result
        result_id = uuid.uuid4()
        status = "success" if confidence >= 0.5 else ("partial" if confidence > 0 else "failed")

        result = ExtractionResult(
            id=result_id,
            status=status,
            data=receipt_data,
            confidence_score=confidence,
            extraction_method=extraction_method,
            model_used=model_used,
            processing_time_ms=elapsed_ms,
            cost_usd=cost_usd,
        )

        # Step 7: Store in DB (don't fail the response if DB write fails)
        try:
            await self._store_result(db, result, raw_response, api_key_prefix)
        except Exception as e:
            logger.error("Failed to store extraction result", error=str(e))

        logger.info(
            "Extraction complete",
            result_id=str(result_id),
            status=status,
            confidence=confidence,
            method=extraction_method,
            elapsed_ms=elapsed_ms,
        )

        return result

    def _merge_results(
        self, vlm_data: ReceiptData, ocr_data: ReceiptData
    ) -> ReceiptData:
        """Merge VLM and OCR results, preferring VLM but filling gaps with OCR."""
        return ReceiptData(
            vendor=vlm_data.vendor or ocr_data.vendor,
            date=vlm_data.date or ocr_data.date,
            total_amount=vlm_data.total_amount or ocr_data.total_amount,
            currency=vlm_data.currency or ocr_data.currency,
            tax_amount=vlm_data.tax_amount or ocr_data.tax_amount,
            tax_rate=vlm_data.tax_rate or ocr_data.tax_rate,
            line_items=vlm_data.line_items or ocr_data.line_items,
            payment_method=vlm_data.payment_method or ocr_data.payment_method,
            receipt_number=vlm_data.receipt_number or ocr_data.receipt_number,
        )

    async def _store_result(
        self,
        db: AsyncSession,
        result: ExtractionResult,
        raw_response: str | None,
        api_key_prefix: str,
    ) -> None:
        """Persist extraction result to database."""
        record = ExtractionRecord(
            id=result.id,
            status=result.status,
            vendor=result.data.vendor,
            receipt_date=result.data.date,
            total_amount=result.data.total_amount,
            currency=result.data.currency,
            tax_amount=result.data.tax_amount,
            tax_rate=result.data.tax_rate,
            line_items=[item.model_dump() for item in result.data.line_items],
            payment_method=result.data.payment_method,
            receipt_number=result.data.receipt_number,
            category=(
                result.data.category.value
                if hasattr(result.data.category, 'value')
                else str(result.data.category)
            ),
            confidence_score=result.confidence_score,
            extraction_method=result.extraction_method,
            model_used=result.model_used,
            processing_time_ms=result.processing_time_ms,
            cost_usd=result.cost_usd,
            raw_vlm_response=raw_response,
            api_key_prefix=api_key_prefix,
        )
        db.add(record)
        await db.commit()
