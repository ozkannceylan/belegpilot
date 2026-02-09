"""Categorizer tests."""

from app.core.categorizer import ExpenseCategorizer
from app.models.schemas import LineItem, ReceiptData


def test_categorize_grocery_rewe():
    """REWE should categorize as groceries."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="REWE Markt GmbH", total_amount=45.0)
    assert categorizer.categorize(data) == "groceries"


def test_categorize_grocery_lidl():
    """Lidl should categorize as groceries."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="Lidl Filiale", total_amount=30.0)
    assert categorizer.categorize(data) == "groceries"


def test_categorize_grocery_aldi():
    """Aldi should categorize as groceries."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="ALDI Sued", total_amount=25.0)
    assert categorizer.categorize(data) == "groceries"


def test_categorize_restaurant():
    """Restaurant keyword should categorize correctly."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="Pizza Hut Restaurant", total_amount=22.0)
    assert categorizer.categorize(data) == "restaurant"


def test_categorize_transport():
    """Transport keywords should match."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="Uber Trip", total_amount=12.50)
    assert categorizer.categorize(data) == "transport"


def test_categorize_hotel():
    """Hotel should categorize as accommodation."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="Holiday Inn Hotel", total_amount=150.0)
    assert categorizer.categorize(data) == "accommodation"


def test_categorize_from_line_items():
    """Should match keywords in line item descriptions."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(
        vendor="Unknown Store",
        line_items=[LineItem(description="Netflix Monthly Sub", total=12.99)],
    )
    assert categorizer.categorize(data) == "entertainment"


def test_categorize_unknown():
    """Unknown vendor should return 'other'."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(vendor="XYZ Corp", total_amount=99.0)
    assert categorizer.categorize(data) == "other"


def test_categorize_no_vendor():
    """No vendor at all should return 'other'."""
    categorizer = ExpenseCategorizer()
    data = ReceiptData(total_amount=50.0)
    assert categorizer.categorize(data) == "other"
