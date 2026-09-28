import copy
import json
import unittest
from state import ROOT
from summarize import summarize

class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = ROOT / 'expected_output' / 'live'
        self.capture = json.loads((self.directory / 'live.json').read_text())
    def test_live_capture_matches_saved_html_and_node(self):
        self.assertEqual(summarize(self.capture, self.directory, True)['expected_outcomes'], 6)
    def test_missing_duplicate_or_unknown_case(self):
        for mode in ('missing', 'duplicate', 'unknown'):
            value = copy.deepcopy(self.capture)
            if mode == 'missing': value['calls'].pop()
            elif mode == 'duplicate': value['calls'][-1] = value['calls'][0]
            else: value['calls'][0]['case'] = 'unknown'
            with self.assertRaisesRegex(ValueError, 'CASE_COVERAGE'): summarize(value, self.directory, True)
    def test_forged_results_and_flags_rejected(self):
        for mode in ('result', 'flag', 'status'):
            value = copy.deepcopy(self.capture)
            if mode == 'result': value['calls'][0]['result']['data']['records'][0]['price'] = '$0'
            elif mode == 'flag': value['calls'][0]['passed'] = False
            else: value['calls'][0]['api_status'] = 500
            with self.assertRaises(ValueError): summarize(value, self.directory, True)
    def test_credit_and_request_totals_rejected(self):
        for field in ('known_credits', 'requests_sent', 'automatic_retries'):
            value = copy.deepcopy(self.capture); value[field] += 1
            with self.assertRaises(ValueError): summarize(value, self.directory, True)
    def test_missing_credit_receipt_rejected(self):
        value = copy.deepcopy(self.capture); value['calls'][0]['credits'] = None
        with self.assertRaisesRegex(ValueError, 'CREDIT_RECEIPT'): summarize(value, self.directory, True)

if __name__ == '__main__': unittest.main()
