"""Confidence scoring and business rule validation."""

from datetime import date, timedelta

import structlog

from app.models.schemas import ReceiptData

logger = structlog.get_logger()


class ReceiptValidator:
    """Validate extracted receipt data and compute confidence scores."""

    # Field weights for overall confidence
    WEIGHTS = {
        "vendor": 0.15,
        "date": 0.15,
        "total": 0.25,
        "line_items": 0.25,
        "tax": 0.10,
        "format": 0.10,
    }

    def validate_and_score(
        self, data: ReceiptData, vlm_parsed_cleanly: bool = True
    ) -> tuple[ReceiptData, float, dict[str, float]]:
        """Validate receipt data and compute confidence score.

        Args:
            data: Extracted receipt data
            vlm_parsed_cleanly: Whether VLM response was valid JSON

        Returns:
            Tuple of (possibly corrected data, overall confidence, per-field scores)
        """
        scores: dict[str, float] = {}

        scores["vendor"] = self._score_vendor(data)
        scores["date"] = self._score_date(data)
        scores["total"] = self._score_total(data)
        scores["line_items"] = self._score_line_items(data)
        scores["tax"] = self._score_tax(data)
        scores["format"] = 1.0 if vlm_parsed_cleanly else 0.3

        overall = sum(
            scores[field] * weight
            for field, weight in self.WEIGHTS.items()
        )

        logger.info(
            "Receipt validated",
            overall_confidence=round(overall, 3),
            field_scores={k: round(v, 3) for k, v in scores.items()},
        )

        return data, round(overall, 3), scores

    def _score_vendor(self, data: ReceiptData) -> float:
        if not data.vendor:
            return 0.0
        if len(data.vendor) < 2 or len(data.vendor) > 200:
            return 0.3
        return 1.0

    def _score_date(self, data: ReceiptData) -> float:
        if not data.date:
            return 0.0
        try:
            d = data.date if isinstance(data.date, date) else date.fromisoformat(str(data.date))
            # Date shouldn't be in the future or more than 2 years old
            today = date.today()
            if d > today + timedelta(days=1):
                return 0.2  # Future date is suspicious
            if d < today - timedelta(days=730):
                return 0.5  # Very old receipt
            return 1.0
        except (ValueError, TypeError):
            return 0.1

    def _score_total(self, data: ReceiptData) -> float:
        if data.total_amount is None:
            return 0.0
        if data.total_amount <= 0:
            return 0.1
        if data.total_amount > 100000:
            return 0.3  # Unusually high
        return 1.0

    def _score_line_items(self, data: ReceiptData) -> float:
        if not data.line_items:
            return 0.3  # Some receipts genuinely have no items
        # Check if line items sum to approximately the total
        if data.total_amount and data.total_amount > 0:
            items_sum = sum(item.total for item in data.line_items)
            if items_sum > 0:
                ratio = items_sum / data.total_amount
                if 0.9 <= ratio <= 1.1:
                    return 1.0  # Items sum matches total
                elif 0.7 <= ratio <= 1.3:
                    return 0.7  # Close but not exact
                else:
                    return 0.4  # Significant mismatch
        return 0.6  # Items exist but can't cross-validate

    def _score_tax(self, data: ReceiptData) -> float:
        if data.tax_amount is None and data.tax_rate is None:
            return 0.5  # Tax not always shown
        score = 0.5
        if data.tax_amount is not None and data.tax_amount > 0:
            score += 0.25
            # Tax should be less than total
            if data.total_amount and data.tax_amount > data.total_amount:
                score -= 0.3
        if data.tax_rate is not None:
            if data.tax_rate in (7.0, 19.0, 20.0, 21.0, 25.0, 0.0):
                score += 0.25  # Common European tax rates
            elif 0 < data.tax_rate < 30:
                score += 0.15
        return min(score, 1.0)
