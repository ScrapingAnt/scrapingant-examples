import copy
import unittest
from state import CASES, expected, score

class OracleTests(unittest.TestCase):
    def test_complete_literal_records(self):
        self.assertTrue(score('catalog_1', expected('catalog_1'), None))
    def test_count_is_not_correctness(self):
        value = copy.deepcopy(expected('catalog_1'))
        value['data']['records'][0]['price'] = '$0.00'
        self.assertFalse(score('catalog_1', value, None))
    def test_missing_extra_duplicate_and_reordered_records(self):
        for mode in ('missing', 'extra', 'duplicate', 'reordered'):
            value = copy.deepcopy(expected('catalog_1')); rows = value['data']['records']
            if mode == 'missing': rows.pop()
            elif mode == 'extra': rows.append(rows[0].copy())
            elif mode == 'duplicate': rows[1] = rows[0].copy()
            else: rows.reverse()
            self.assertFalse(score('catalog_1', value, None))
    def test_transport_probe_must_survive_exactly(self):
        value = copy.deepcopy(expected('catalog_1'))
        value['data']['transport_probe'] = value['data']['transport_probe'].replace('&amp;', '&')
        self.assertFalse(score('catalog_1', value, None))
    def test_negative_controls_require_specific_outcomes(self):
        self.assertTrue(score('return_only', None, 'MARKER_COUNT'))
        self.assertFalse(score('return_only', None, 'JSON_INVALID'))
        self.assertTrue(score('missing_selector', expected('missing_selector'), None))
        self.assertFalse(score('missing_selector', None, 'MARKER_COUNT'))
    def test_boolean_is_not_interchangeable_with_integer(self):
        value = copy.deepcopy(expected('delayed')); value['data']['awaited'] = 1
        self.assertFalse(score('delayed', value, None))

if __name__ == '__main__': unittest.main()
