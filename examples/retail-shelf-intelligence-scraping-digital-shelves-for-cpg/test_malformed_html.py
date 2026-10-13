"""Malformed HTML must remain an incomplete observation, not a traceback."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import collector

ROOT = Path(__file__).parent
MALFORMED = b'<![broken]><html>error shell</html>'
AT = '2026-10-13T12:00:00Z'


class MalformedHTML(unittest.TestCase):
    def test_marked_section_failure_returns_no_accepted_stock_observation(self):
        try:
            result = collector.parse_page(MALFORMED, requested_source_url=collector.SOURCE, observed_at_utc=AT)
        except AssertionError:
            self.fail('Malformed marked section escaped the source acceptance boundary')
        self.assertFalse(result['complete'])
        self.assertEqual(result['records'], [])
        self.assertTrue(result['rejected'])

    def test_HTTP200_malformed_content_retains_known_receipt_cost(self):
        receipt = {'transport':'managed', 'requested_source_url':collector.SOURCE,
            'api_http_status':200, 'target_http_status':200, 'target_media_type':'text/html',
            'actual_receipt_credits':1, 'credit_receipt_state':'known',
            'body_bytes':len(MALFORMED), 'body_sha256':hashlib.sha256(MALFORMED).hexdigest(), 'error':None}
        try:
            result = collector.collection({'usable':True, 'body':MALFORMED, 'receipt':receipt},
                source=collector.SOURCE, observed_at_utc=AT)
        except AssertionError:
            self.fail('Malformed HTML dropped the structured receipt and acceptance result')
        self.assertFalse(result['complete'])
        self.assertEqual(result['records'], [])
        self.assertEqual(result['acquisition'], receipt)
        self.assertEqual(result['cost'], {'actual_receipt_credits':1, 'unknown_charge_requests':0,
            'accepted_records':0, 'credits_per_accepted_record':None})

    def test_replay_CLI_emits_incomplete_JSON_without_traceback(self):
        with tempfile.TemporaryDirectory(prefix='retail-malformed-') as directory:
            fixture = Path(directory) / 'source.html'
            fixture.write_bytes(MALFORMED)
            environment = os.environ.copy()
            environment.pop('SCRAPINGANT_API_KEY', None)
            result = subprocess.run([sys.executable, str(ROOT / 'collector.py'), 'replay', str(fixture),
                '--source', 'adagio', '--observed-at', AT], env=environment, text=True,
                capture_output=True, timeout=10)
        self.assertEqual(result.stderr, '', 'Malformed source must not produce a traceback')
        self.assertEqual(result.returncode, 1)
        output = json.loads(result.stdout)
        self.assertFalse(output['complete'])
        self.assertEqual(output['records'], [])
        self.assertEqual(output['acquisition']['transport'], 'offline_replay')
        self.assertIsNone(output['cost']['actual_receipt_credits'])
