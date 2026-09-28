"""Regression tests: independent values and mutations, not fixture-generated truth."""
import copy
import unittest

from oracle import exact_records, has_class_token
from summarize import summarize
from case_contract import EXTRACTION, DIAGNOSTICS
from oracle import FIELDS
from browser_support import source_hashes


RECORDS = [
    {'sku': 'C-101', 'title': 'Café & Cocoa', 'currency': 'USD', 'price': '12.50', 'href': '/products/cafe', 'badge': 'New'},
    {'sku': 'T-202', 'title': 'Tea "No. 2"', 'currency': 'EUR', 'price': '8.00', 'href': '/products/tea', 'badge': None},
    {'sku': 'N-303', 'title': 'Notebook <A5>', 'currency': 'GBP', 'price': '5.25', 'href': '/products/notebook', 'badge': 'Sale'},
]


class OracleTests(unittest.TestCase):
    def test_complete_records_accept_optional_null_and_reordered_rows(self):
        self.assertTrue(exact_records(list(reversed(RECORDS))))

    def test_empty_missing_duplicate_and_extra_are_rejected(self):
        for value in ([], RECORDS[:2], RECORDS + [RECORDS[0]], [RECORDS[0]] * 3):
            with self.subTest(value=value):
                self.assertFalse(exact_records(value))

    def test_wrong_value_in_every_field_is_rejected(self):
        for key in RECORDS[0]:
            value = copy.deepcopy(RECORDS)
            value[0][key] = 'wrong'
            with self.subTest(key=key):
                self.assertFalse(exact_records(value))

    def test_schema_missing_extra_numeric_price_and_null_are_rejected(self):
        missing = copy.deepcopy(RECORDS)
        del missing[1]['badge']
        extra = copy.deepcopy(RECORDS)
        extra[0]['unexpected'] = True
        numeric = copy.deepcopy(RECORDS)
        numeric[0]['price'] = 12.5
        for value in (None, {}, [None], missing, extra, numeric):
            with self.subTest(value=value):
                self.assertFalse(exact_records(value))

    def test_active_is_not_a_substring_match_for_inactive(self):
        self.assertTrue(has_class_token('product\tactive featured', 'active'))
        self.assertFalse(has_class_token('product inactive', 'active'))


class SummaryTests(unittest.TestCase):
    def packet(self):
        # Synthetic transport fixture for mutation tests; never presented as browser evidence.
        observations = []
        for round_number in (1, 2, 3):
            for name, spec in EXTRACTION.items():
                observations.append({'round': round_number, 'case': name, 'kind': 'extraction',
                                     'records': [dict(zip(FIELDS, row)) for row in spec['records']],
                                     'error': spec['error']})
            for name, value in DIAGNOSTICS.items():
                observations.append({'round': round_number, 'case': name, 'kind': 'diagnostic', 'values': copy.deepcopy(value)})
        return {'schema_version': 1, 'rounds': 3,
                'environment': {'browser': 'chrome', 'browser_version': '1.0', 'driver_version': '1.0',
                                'python': '3.12.0', 'selenium': '4.49.0', 'os': 'Linux', 'os_release': '1', 'architecture': 'x86_64'},
                'source_hashes': source_hashes(), 'observations': observations}

    def test_exact_case_round_counts_and_separate_diagnostics(self):
        summary = summarize([self.packet()])
        self.assertEqual(summary['extraction_observations'], 36)
        self.assertEqual(summary['complete_target_observations'], 21)
        self.assertEqual(summary['expected_wrong_observations'], 15)
        self.assertEqual(summary['diagnostic_observations'], 15)

    def test_missing_duplicate_unknown_round_and_forged_success_rejected(self):
        mutations = []
        missing = self.packet(); missing['observations'].pop(); mutations.append(missing)
        duplicate = self.packet(); duplicate['observations'][-1] = duplicate['observations'][0]; mutations.append(duplicate)
        unknown = self.packet(); unknown['observations'][0]['case'] = 'unknown'; mutations.append(unknown)
        bad_round = self.packet(); bad_round['observations'][0]['round'] = 4; mutations.append(bad_round)
        forged = self.packet(); forged['observations'][0]['passed'] = True; mutations.append(forged)
        for value in mutations:
            with self.subTest(value=value['observations'][0]['case']), self.assertRaises(ValueError):
                summarize([value])

    def test_wrong_control_must_return_its_literal_wrong_records(self):
        packet = self.packet()
        packet['observations'][0]['records'] = []
        with self.assertRaises(ValueError):
            summarize([packet])

    def test_wrong_target_record_is_rejected(self):
        packet = self.packet()
        packet['observations'][1]['records'][0]['price'] = '0.00'
        with self.assertRaises(ValueError):
            summarize([packet])

    def test_stale_without_exception_and_failed_refind_are_rejected(self):
        for case in ('stale_handle', 'refind_after_replacement'):
            packet = self.packet()
            observation = next(row for row in packet['observations'] if row['case'] == case)
            observation['error'] = None
            observation['records'] = []
            with self.subTest(case=case), self.assertRaises(ValueError):
                summarize([packet])

    def test_diagnostic_value_tamper_rejected(self):
        packet = self.packet()
        next(row for row in packet['observations'] if row['case'] == 'missing_plural')['values']['count'] = 1
        with self.assertRaises(ValueError):
            summarize([packet])

    def test_missing_environment_version_and_changed_source_rejected(self):
        packet = self.packet()
        packet['environment']['browser_version'] = ''
        with self.assertRaises(ValueError):
            summarize([packet])
        packet = self.packet()
        packet['source_hashes']['oracle.py'] = '0' * 64
        with self.assertRaises(ValueError):
            summarize([packet])

    def test_duplicate_browser_capture_rejected(self):
        with self.assertRaises(ValueError):
            summarize([self.packet(), self.packet()])

    def test_empty_capture_is_not_evidence(self):
        with self.assertRaises(ValueError):
            summarize([])

    def test_missing_environment_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize([{'observations': [], 'browser': 'chrome', 'rounds': 3}])

    def test_declared_success_without_observations_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize([{'environment': {'browser': 'chrome'}, 'observations': [], 'passed': 999}])


if __name__ == '__main__':
    unittest.main()
