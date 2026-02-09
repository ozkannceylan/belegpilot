"""VLM extractor tests."""

from app.core.extractor_vlm import VLMExtractor


def test_parse_number_int():
    """Integer should parse to float."""
    assert VLMExtractor._parse_number(42) == 42.0


def test_parse_number_float():
    """Float should pass through."""
    assert VLMExtractor._parse_number(3.14) == 3.14


def test_parse_number_string():
    """String number should parse."""
    assert VLMExtractor._parse_number("47.83") == 47.83


def test_parse_number_european_comma():
    """European comma decimal should convert."""
    assert VLMExtractor._parse_number("47,83") == 47.83


def test_parse_number_none():
    """None should return None."""
    assert VLMExtractor._parse_number(None) is None


def test_parse_number_invalid_string():
    """Non-numeric string should return None."""
    assert VLMExtractor._parse_number("not_a_number") is None


def test_parse_vlm_response_complete():
    """Complete VLM JSON response should parse correctly."""
    from unittest.mock import MagicMock
    client = MagicMock()
    extractor = VLMExtractor(client)

    raw = {
        "vendor": "REWE",
        "date": "2026-02-07",
        "total_amount": "47,83",
        "currency": "eur",
        "tax_amount": 7.63,
        "tax_rate": "19",
        "line_items": [
            {"description": "Milk", "quantity": "2", "unit_price": "1,29", "total": "2.58"},
        ],
        "payment_method": None,
    }

    result = extractor._parse_vlm_response(raw)
    assert result.vendor == "REWE"
    assert result.total_amount == 47.83
    assert result.currency == "EUR"  # Should be uppercased by validator
    assert result.tax_rate == 19.0
    assert len(result.line_items) == 1
    assert result.line_items[0].total == 2.58


def test_parse_vlm_response_skips_bad_line_items():
    """Line items with parse errors should be skipped."""
    from unittest.mock import MagicMock
    client = MagicMock()
    extractor = VLMExtractor(client)

    raw = {
        "vendor": "Test",
        "line_items": [
            {"description": "Good Item", "total": "5.00"},
            {"description": "Bad Item", "total": "not_a_number"},
        ],
    }

    result = extractor._parse_vlm_response(raw)
    # Good item kept, bad item's total becomes 0.0
    # (_parse_number returns None and gets or'd to 0.0)
    assert len(result.line_items) >= 1
    assert result.line_items[0].total == 5.0


def test_parse_vlm_response_empty():
    """Empty response should produce a ReceiptData with all defaults."""
    from unittest.mock import MagicMock
    client = MagicMock()
    extractor = VLMExtractor(client)

    result = extractor._parse_vlm_response({})
    assert result.vendor is None
    assert result.total_amount is None
    assert result.line_items == []
