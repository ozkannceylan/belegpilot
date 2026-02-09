"""Validator tests."""

from datetime import date, timedelta

import pytest

from app.core.validator import ReceiptValidator
from app.models.schemas import LineItem, ReceiptData


@pytest.fixture
def validator():
    return ReceiptValidator()


def test_perfect_receipt(validator):
    data = ReceiptData(
        vendor="REWE",
        date=date.today(),
        total_amount=10.0,
        currency="EUR",
        tax_amount=1.60,
        tax_rate=19.0,
        line_items=[
            LineItem(description="Milk", quantity=2, unit_price=1.29, total=2.58),
            LineItem(description="Bread", quantity=1, unit_price=2.49, total=2.49),
            LineItem(description="Butter", quantity=1, unit_price=4.93, total=4.93),
        ],
    )
    _, confidence, _ = validator.validate_and_score(data)
    assert confidence >= 0.8


def test_empty_receipt(validator):
    data = ReceiptData()
    _, confidence, _ = validator.validate_and_score(data)
    assert confidence < 0.3


def test_future_date_low_confidence(validator):
    data = ReceiptData(
        vendor="Test",
        date=date(2030, 1, 1),
        total_amount=10.0,
    )
    _, confidence, scores = validator.validate_and_score(data)
    assert scores["date"] < 0.5


def test_line_items_sum_mismatch(validator):
    data = ReceiptData(
        vendor="Test",
        total_amount=100.0,
        line_items=[
            LineItem(description="Item", total=10.0),
        ],
    )
    _, _, scores = validator.validate_and_score(data)
    assert scores["line_items"] < 0.8


def test_negative_total(validator):
    """Negative total should score very low."""
    data = ReceiptData(
        vendor="Test",
        total_amount=-5.0,
    )
    _, _, scores = validator.validate_and_score(data)
    assert scores["total"] <= 0.1


def test_tax_greater_than_total(validator):
    """Tax amount exceeding total should lower tax score."""
    data = ReceiptData(
        vendor="Test",
        total_amount=10.0,
        tax_amount=15.0,
    )
    _, _, scores = validator.validate_and_score(data)
    assert scores["tax"] < 0.5


def test_very_old_date(validator):
    """Receipt from more than 2 years ago scores 0.5 for date."""
    old_date = date.today() - timedelta(days=800)
    data = ReceiptData(
        vendor="Test",
        date=old_date,
        total_amount=10.0,
    )
    _, _, scores = validator.validate_and_score(data)
    assert scores["date"] == 0.5


def test_line_items_sum_close_match(validator):
    """Items summing close to total (within 10%) should score high."""
    data = ReceiptData(
        vendor="REWE",
        total_amount=10.0,
        line_items=[
            LineItem(description="Item A", total=5.0),
            LineItem(description="Item B", total=4.8),
        ],
    )
    _, _, scores = validator.validate_and_score(data)
    assert scores["line_items"] >= 0.7


def test_vendor_too_short(validator):
    """Single character vendor should score 0.3."""
    data = ReceiptData(vendor="X")
    _, _, scores = validator.validate_and_score(data)
    assert scores["vendor"] == 0.3


def test_format_penalty_no_clean_parse(validator):
    """VLM not parsing cleanly should lower format score."""
    data = ReceiptData(vendor="Test")
    _, _, scores = validator.validate_and_score(data, vlm_parsed_cleanly=False)
    assert scores["format"] == 0.3


def test_weights_sum_to_one(validator):
    """Weights must sum to 1.0."""
    total = sum(validator.WEIGHTS.values())
    assert abs(total - 1.0) < 0.001


def test_very_high_total(validator):
    """Total > 100k should score 0.3."""
    data = ReceiptData(
        vendor="Test",
        total_amount=200000.0,
    )
    _, _, scores = validator.validate_and_score(data)
    assert scores["total"] == 0.3
