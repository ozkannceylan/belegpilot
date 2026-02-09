"""Expense categorization based on keywords."""

from app.models.schemas import ReceiptData

KEYWORD_CATEGORIES = {
    "groceries": ["rewe", "lidl", "aldi", "edeka", "penny", "netto", "kaufland",
                   "dm", "rossmann", "supermarkt", "lebensmittel"],
    "restaurant": ["restaurant", "bistro", "café", "cafe", "bar", "pizza",
                    "burger", "sushi", "trinkgeld", "tip", "kellner"],
    "transport": ["uber", "bolt", "taxi", "db", "bahn", "bvg", "tankstelle",
                   "shell", "aral", "esso", "parking", "parkhaus"],
    "office": ["büro", "office", "staples", "papier", "drucker", "toner"],
    "accommodation": ["hotel", "hostel", "airbnb", "booking", "motel",
                        "übernachtung", "zimmer"],
    "entertainment": ["kino", "cinema", "theater", "konzert", "spotify",
                        "netflix", "museum"],
    "utilities": ["strom", "gas", "wasser", "internet", "telefon", "vodafone",
                   "telekom", "o2"],
}


class ExpenseCategorizer:
    """Categorize receipts based on vendor name and line items."""

    def categorize(self, data: ReceiptData) -> str:
        """Return expense category based on keywords in vendor and items."""
        text_parts = []
        if data.vendor:
            text_parts.append(data.vendor.lower())
        for item in data.line_items:
            text_parts.append(item.description.lower())
        combined = " ".join(text_parts)

        for category, keywords in KEYWORD_CATEGORIES.items():
            if any(kw in combined for kw in keywords):
                return category

        return "other"
