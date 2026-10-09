"""Offline integrity tests: no requests, API key or acquisition."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from contract import summary
from verify_capture import verify

ROOT = Path(__file__).resolve().parent


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.capture = Path(self.temp.name)/'live'
        shutil.copytree(ROOT/'expected_output/live', self.capture)
        self.path = self.capture/'report.json'
        self.report = json.loads(self.path.read_text())

    def check_modified(self, error):
        self.report['actual_credits_receipted'] = sum(r['credits'] for r in self.report['rows'] if r['arm'].startswith('api_') and r['credits'] is not None)
        self.report['summary'] = summary(self.report['rows'])
        self.path.write_text(json.dumps(self.report))
        with self.assertRaisesRegex(ValueError, error):
            verify(self.path)

    def test_canonical_live_report_passes(self):
        result = verify(self.path)
        self.assertTrue(result['complete'])
        self.assertEqual(result['billing_status'], 'complete_receipts')
        self.assertEqual(result['actual_credits_receipted'], 220)
        self.assertEqual(len(result['summary']), 8)

    def test_legacy_local_report_is_explicitly_unbound(self):
        result = verify(ROOT/'expected_output/local/report.json')
        self.assertTrue(result['complete'])
        self.assertFalse(result['runtime_hashes_present'])
        self.assertEqual(result['billing_status'], 'no_api_calls')

    def test_successful_zero_credit_receipt_is_rejected(self):
        next(r for r in self.report['rows'] if r['arm'] == 'api_raw')['credits'] = 0
        self.check_modified('Unexpected completed receipt')

    def test_receipts_above_ceiling_are_rejected(self):
        for row in self.report['rows']:
            if row['credits'] is not None:
                row['credits'] *= 2
        self.check_modified('Credit ceiling exceeded')

    def test_missing_runtime_map_is_rejected(self):
        del self.report['source_sha256']
        self.check_modified('Complete runtime hash map required')

    def test_partial_runtime_map_is_rejected(self):
        del self.report['source_sha256']['requirements.txt']
        self.check_modified('Complete runtime hash map required')

    def test_missing_fixture_map_is_rejected(self):
        del self.report['fixtures']
        self.check_modified('Complete fixture map required')

    def test_changed_fixture_url_is_rejected(self):
        self.report['fixtures']['static']['url'] = 'https://example.invalid/other'
        self.check_modified('Fixture URL mismatch')

    def test_incomplete_unknown_billing_remains_explicit(self):
        index = next(i for i,r in enumerate(self.report['rows']) if r['arm'].startswith('api_'))
        self.report['rows'] = self.report['rows'][:index+1]
        row = self.report['rows'][-1]
        row.update(credits=None, valid=False, valid_records=0, records=[], ready=False,
                   outcome='unfinished', exception_class='UnfinishedAttempt', elapsed_ms=None)
        (self.capture/row['body_file']).write_bytes(b'')
        row['body_sha256'] = hashlib.sha256(b'').hexdigest()
        self.report.update(complete=False, api_calls=1, actual_credits_receipted=0, summary=summary(self.report['rows']))
        self.path.write_text(json.dumps(self.report))
        result = verify(self.path)
        self.assertFalse(result['complete'])
        self.assertEqual(result['billing_status'], 'partial_unknown_or_anomaly')
        self.assertEqual(result['actual_credits_receipted'], 0)
        self.assertFalse(result['summary'][-1]['cost_status'] == 'receipted')


if __name__ == '__main__':
    unittest.main()
