"""Reject corrupted or incomplete captures before computing article denominators."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from summarize import summarize_captures


class SummaryTests(unittest.TestCase):
    def setUp(self):
        capture = json.loads((Path(__file__).parent / 'expected_output/chromium.json').read_text())
        capture['runs'] = capture['runs'][:1]
        self.capture = capture

    def test_diagnostics_do_not_inflate_record_denominator(self):
        result = summarize_captures([self.capture])
        self.assertEqual(result['primary_extraction_observations'], 12)
        self.assertEqual(result['primary_diagnostic_observations'], 6)
        self.assertEqual(result['primary_checks'], 18)
        self.assertEqual(result['record_opportunities'], 48)
        self.assertEqual(result['matching_record_observations'], 20)
        self.assertEqual(result['exact_extraction_observations'], 5)

    def test_duplicate_records_with_stale_scores_are_rejected(self):
        case = next(c for c in self.capture['runs'][0]['cases'] if c.get('exact_match'))
        case['records'] = [case['records'][0]] * 4
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])

    def test_mismatched_check_flag_is_rejected(self):
        self.capture['runs'][0]['cases'][0]['check_passed'] = False
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])

    def test_missing_case_is_rejected(self):
        self.capture['runs'][0]['cases'].pop()
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])

    def test_duplicate_case_is_rejected(self):
        cases = self.capture['runs'][0]['cases']
        cases[-1] = deepcopy(cases[0])
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])

    def test_duplicate_browser_capture_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize_captures([self.capture, deepcopy(self.capture)])

    def test_round_gap_is_rejected(self):
        self.capture['runs'][0]['round'] = 2
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])

    def test_wrong_kind_cannot_hide_extraction_from_denominator(self):
        self.capture['runs'][0]['cases'][0]['kind'] = 'diagnostic'
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])

    def test_route_count_must_agree_with_diagnostic_check(self):
        case = next(c for c in self.capture['runs'][0]['cases'] if c['case'] == 'route_fetch_then_continue')
        case['server_hits'] = 1
        with self.assertRaises(ValueError):
            summarize_captures([self.capture])


if __name__ == '__main__':
    unittest.main()
