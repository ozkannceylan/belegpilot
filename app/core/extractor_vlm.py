"""VLM extraction logic wrapping OpenRouter client, parsing responses into Pydantic models."""

import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import LineItem, ReceiptData
from app.services.openrouter import OpenRouterClient

logger = structlog.get_logger()


class VLMExtractor:
    """Extract receipt data using Vision Language Model via OpenRouter."""

    def __init__(self, client: OpenRouterClient) -> None:
        self.client = client

    async def extract(
        self,
        image_base64: str,
        db: AsyncSession,
        model_override: str | None = None,
    ) -> tuple[ReceiptData | None, dict]:
        """Extract receipt data from image.

        Returns:
            Tuple of (ReceiptData or None if parsing failed, metadata dict)
        """
        result = await self.client.extract_receipt(
            image_base64=image_base64,
            db=db,
            model_override=model_override,
        )

        metadata = {
            "model": result["model"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost_usd": result["cost_usd"],
            "elapsed_ms": result["elapsed_ms"],
            "raw_response": result["raw_content"],
        }

        # Parse VLM JSON response into Pydantic model
        try:
            raw_json = json.loads(result["raw_content"])
            receipt_data = self._parse_vlm_response(raw_json)
            return receipt_data, metadata
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse VLM response", error=str(e))
            return None, metadata

    def _parse_vlm_response(self, raw: dict) -> ReceiptData:
        """Parse raw VLM JSON into ReceiptData model.

        Handles common VLM output quirks:
        - Amounts as strings ("47.83" → 47.83)
        - European comma decimals ("47,83" → 47.83)
        - Missing fields gracefully
        """
        line_items = []
        for item in raw.get("line_items", []):
            try:
                line_items.append(LineItem(
                    description=item.get("description", "Unknown"),
                    quantity=self._parse_number(item.get("quantity")),
                    unit_price=self._parse_number(item.get("unit_price")),
                    total=self._parse_number(item.get("total")) or 0.0,
                ))
            except Exception as e:
                logger.debug("Skipping malformed line item", item=item, error=str(e))

        return ReceiptData(
            vendor=raw.get("vendor"),
            date=raw.get("date"),
            total_amount=self._parse_number(raw.get("total_amount")),
            currency=raw.get("currency"),
            tax_amount=self._parse_number(raw.get("tax_amount")),
            tax_rate=self._parse_number(raw.get("tax_rate")),
            line_items=line_items,
            payment_method=raw.get("payment_method"),
            receipt_number=raw.get("receipt_number"),
        )

    @staticmethod
    def _parse_number(value: Any) -> float | None:
        """Safely parse a number from VLM output."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Handle European comma format
            cleaned = value.replace(",", ".").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
