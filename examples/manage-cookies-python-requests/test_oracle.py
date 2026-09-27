"""A duplicated expected row must not stand in for three absent SKUs."""
import unittest
from oracle import score


class OracleTests(unittest.TestCase):
    def test_four_correct_rows_match(self):
        rows = [
            {"sku": "BK-101", "currency": "EUR", "price_minor": 1499},
            {"sku": "PN-202", "currency": "EUR", "price_minor": 799},
            {"sku": "NB-303", "currency": "EUR", "price_minor": 2199},
            {"sku": "BG-404", "currency": "EUR", "price_minor": 4299},
        ]
        self.assertEqual(score(rows), {"matching_records": 4, "expected_records": 4, "exact_match": True})

    def test_duplicate_cannot_replace_missing_products(self):
        row = {"sku": "BK-101", "currency": "EUR", "price_minor": 1499}
        self.assertEqual(score([row] * 4)["matching_records"], 1)
        self.assertFalse(score([row] * 4)["exact_match"])

    def test_extra_duplicate_rejects_exact_match(self):
        rows = [
            {"sku": "BK-101", "currency": "EUR", "price_minor": 1499},
            {"sku": "PN-202", "currency": "EUR", "price_minor": 799},
            {"sku": "NB-303", "currency": "EUR", "price_minor": 2199},
            {"sku": "BG-404", "currency": "EUR", "price_minor": 4299},
        ]
        self.assertEqual(score(rows + rows[:1])["matching_records"], 4)
        self.assertFalse(score(rows + rows[:1])["exact_match"])

    def test_wrong_currency_or_price_is_not_correct(self):
        self.assertEqual(score([
            {"sku": "BK-101", "currency": "USD", "price_minor": 1499},
            {"sku": "PN-202", "currency": "EUR", "price_minor": 800},
        ])["matching_records"], 0)

    def test_empty_is_not_success(self):
        self.assertFalse(score([])["exact_match"])


if __name__ == "__main__":
    unittest.main()
