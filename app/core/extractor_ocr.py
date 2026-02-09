"""Tesseract OCR fallback for when VLM fails or budget is exceeded."""

import re

import numpy as np
import pytesseract
import structlog

from app.models.schemas import ReceiptData

logger = structlog.get_logger()


class OCRExtractor:
    """Fallback receipt extraction using Tesseract OCR + regex patterns."""

    # Common patterns for receipt fields
    TOTAL_PATTERNS = [
        r"(?:total|gesamt|summe|betrag)[:\s]*[€$£]?\s*(\d+[.,]\d{2})",
        r"(?:total|gesamt|summe|betrag)[:\s]*(\d+[.,]\d{2})\s*[€$£]?",
        r"(\d+[.,]\d{2})\s*(?:eur|usd|gbp)",
    ]
    DATE_PATTERNS = [
        r"(\d{2}[./]\d{2}[./]\d{4})",    # DD.MM.YYYY or DD/MM/YYYY
        r"(\d{4}-\d{2}-\d{2})",            # YYYY-MM-DD
        r"(\d{2}[./]\d{2}[./]\d{2})",      # DD.MM.YY
    ]
    TAX_PATTERNS = [
        r"(?:mwst|vat|tax|ust)[:\s]*[€$£]?\s*(\d+[.,]\d{2})",
        r"(\d+[.,]\d{2})\s*(?:mwst|vat|tax)",
    ]

    async def extract(self, image_bytes: bytes) -> tuple[ReceiptData, dict]:
        """Extract receipt data using OCR.

        Args:
            image_bytes: Preprocessed image as bytes

        Returns:
            Tuple of (ReceiptData, metadata dict)
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        import cv2
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

        # Run Tesseract with German + English
        text = pytesseract.image_to_string(img, lang="deu+eng")
        logger.info("OCR text extracted", text_length=len(text))

        receipt_data = self._parse_ocr_text(text)

        metadata = {
            "model": "tesseract-ocr",
            "raw_response": text,
            "cost_usd": 0.0,
            "elapsed_ms": 0,  # Caller should measure
        }

        return receipt_data, metadata

    def _parse_ocr_text(self, text: str) -> ReceiptData:
        """Parse OCR text using regex patterns."""
        text_lower = text.lower()

        # Extract total
        total = self._extract_amount(text_lower, self.TOTAL_PATTERNS)

        # Extract date
        receipt_date = self._extract_date(text)

        # Extract tax
        tax_amount = self._extract_amount(text_lower, self.TAX_PATTERNS)

        # Extract vendor (usually first non-empty line)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        vendor = lines[0] if lines else None

        # Detect currency
        currency = self._detect_currency(text)

        return ReceiptData(
            vendor=vendor,
            date=receipt_date,
            total_amount=total,
            currency=currency,
            tax_amount=tax_amount,
            line_items=[],  # OCR doesn't reliably extract line items
        )

    def _extract_amount(self, text: str, patterns: list[str]) -> float | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", ".")
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    def _extract_date(self, text: str) -> str | None:
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                return self._normalize_date(date_str)
        return None

    def _normalize_date(self, date_str: str) -> str | None:
        """Convert various date formats to YYYY-MM-DD."""
        import re as re_mod
        # DD.MM.YYYY
        m = re_mod.match(r"(\d{2})[./](\d{2})[./](\d{4})", date_str)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        # YYYY-MM-DD (already correct)
        m = re_mod.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
        if m:
            return date_str
        # DD.MM.YY
        m = re_mod.match(r"(\d{2})[./](\d{2})[./](\d{2})", date_str)
        if m:
            year = int(m.group(3))
            year = 2000 + year if year < 50 else 1900 + year
            return f"{year}-{m.group(2)}-{m.group(1)}"
        return None

    def _detect_currency(self, text: str) -> str | None:
        text_lower = text.lower()
        if "€" in text or "eur" in text_lower:
            return "EUR"
        if "$" in text or "usd" in text_lower:
            return "USD"
        if "£" in text or "gbp" in text_lower:
            return "GBP"
        return None
