"""Regression tests: duplicate rows and wrong-origin state must not pass."""
import unittest

from state import region_params, score_records


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'sku': 'SKU-101', 'currency': 'EUR', 'price': '8.10'},
            {'sku': 'SKU-202', 'currency': 'EUR', 'price': '16.20'},
            {'sku': 'SKU-303', 'currency': 'EUR', 'price': '24.30'},
            {'sku': 'SKU-404', 'currency': 'EUR', 'price': '32.40'},
        ]

    def test_four_independent_records_match_in_any_order(self):
        result = score_records(list(reversed(self.rows)))
        self.assertEqual(result['matching_records'], 4)
        self.assertTrue(result['exact_match'])

    def test_duplicate_rows_cannot_replace_missing_skus(self):
        result = score_records([self.rows[0]] * 4)
        self.assertEqual(result['matching_records'], 1)
        self.assertFalse(result['exact_match'])

    def test_extra_duplicate_invalidates_otherwise_complete_output(self):
        result = score_records(self.rows + [self.rows[0]])
        self.assertEqual(result['matching_records'], 4)
        self.assertFalse(result['exact_match'])

    def test_wrong_price_currency_and_missing_sku_do_not_match(self):
        self.rows[0]['price'] = '9.00'
        self.rows[1]['currency'] = 'USD'
        del self.rows[2]['sku']
        self.assertEqual(score_records(self.rows)['matching_records'], 1)


class StateBoundaryTests(unittest.TestCase):
    def test_region_comes_from_exact_origin(self):
        state = {'origins': [
            {'origin': 'http://localhost:1234.evil.test', 'localStorage': [{'name': 'region', 'value': 'US'}]},
            {'origin': 'http://localhost:1234', 'localStorage': [{'name': 'region', 'value': 'EU'}]},
        ]}
        self.assertEqual(region_params(state, 'http://localhost:1234'), {'region': 'EU'})

    def test_missing_origin_rejects_instead_of_using_foreign_state(self):
        state = {'origins': [{'origin': 'http://localhost:4321', 'localStorage': [{'name': 'region', 'value': 'EU'}]}]}
        with self.assertRaises(ValueError):
            region_params(state, 'http://localhost:1234')

    def test_absent_region_is_not_silently_defaulted(self):
        with self.assertRaises(ValueError):
            region_params({'origins': []}, 'http://localhost:1234')

    def test_invalid_or_ambiguous_region_is_rejected(self):
        for values in (['AU'], ['EU', 'US']):
            state = {'origins': [{'origin': 'http://localhost:1234', 'localStorage': [{'name': 'region', 'value': v} for v in values]}]}
            with self.subTest(values=values), self.assertRaises(ValueError):
                region_params(state, 'http://localhost:1234')


if __name__ == '__main__':
    unittest.main()
