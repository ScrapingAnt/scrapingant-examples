"""Independent, literal member-EUR extraction oracle; no fixture imports."""
from collections import Counter
EXPECTED = (
    ("BK-101", "EUR", 1499),
    ("PN-202", "EUR", 799),
    ("NB-303", "EUR", 2199),
    ("BG-404", "EUR", 4299),
)


def score(records):
    actual = Counter((r["sku"], r["currency"], r["price_minor"]) for r in records)
    expected = Counter(EXPECTED)
    matches = sum((actual & expected).values())
    return {"matching_records": matches, "expected_records": 4,
            "exact_match": actual == expected}
