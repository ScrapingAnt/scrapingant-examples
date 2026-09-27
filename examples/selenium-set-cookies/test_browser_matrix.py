import unittest
from browser_matrix import EXPECTED, matching_records


class ExtractionOracleTests(unittest.TestCase):
    def test_complete_dataset_can_be_reordered(self):
        self.assertEqual(matching_records(list(reversed(EXPECTED))), 4)

    def test_duplicate_row_does_not_replace_missing_products(self):
        self.assertEqual(matching_records([EXPECTED[0]] * 4), 1)

    def test_missing_product_counts_only_existing_matches(self):
        self.assertEqual(matching_records(EXPECTED[:3]), 3)

    def test_correct_prices_in_wrong_currency_do_not_match(self):
        self.assertEqual(matching_records([dict(r, currency='USD') for r in EXPECTED]), 0)


if __name__ == '__main__': unittest.main()
