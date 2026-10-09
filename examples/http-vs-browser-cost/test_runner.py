import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
from types import SimpleNamespace

from runner import validate_options, replay, acquire, run, receipt_is_expected
from contract import schedule, summary
from test_contract import STATIC


class RunnerTests(unittest.TestCase):
    def test_live_requires_explicit_exact_credit_cap(self):
        for cap in (None, 0, 21, 219, 221):
            with self.assertRaises(ValueError):
                validate_options(True, 10, cap)
        self.assertEqual(validate_options(True, 10, 220), 220)

    def test_local_never_accepts_a_paid_budget(self):
        self.assertEqual(validate_options(False, 10, None), 0)
        with self.assertRaises(ValueError):
            validate_options(False, 10, 220)

    def test_repeats_bounded(self):
        for n in (0, 11):
            with self.assertRaises(ValueError):
                validate_options(False, n, None)

    def test_replay_rejects_omitted_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            report = json.loads(Path('expected_output/local/report.json').read_text())
            report['rows'] = report['rows'][:-1]
            path = Path(root)/'report.json'; path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'Missing/reordered attempts'):
                replay(path)

    def test_replay_rejects_changed_body(self):
        with tempfile.TemporaryDirectory() as root:
            report = json.loads(Path('expected_output/local/report.json').read_text())
            Path(root, report['rows'][0]['body_file']).write_text('tampered')
            path = Path(root)/'report.json'; path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'Body hash mismatch'):
                replay(path)

    def test_receipt_requires_expected_mode_cost_or_zero_for_api_error(self):
        self.assertTrue(receipt_is_expected(200, 10, 10))
        self.assertTrue(receipt_is_expected(403, 0, 10))
        for actual in (None, 0, 2, 11):
            self.assertFalse(receipt_is_expected(200, actual, 10))

    def test_replay_rejects_forged_short_plan(self):
        source = Path('expected_output/local/report.json')
        if not source.exists():
            self.skipTest('Stored captures are not available yet')
        report = json.loads(source.read_text())
        report['plan'] = report['plan'][:4]; report['rows'] = report['rows'][:4]
        report['summary'] = summary(report['rows'])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'report.json'; path.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                replay(path)

    def test_interrupt_preserves_unknown_api_attempt(self):
        class Session:
            def get(self, *args, **kwargs):
                raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as root:
            result = acquire('api_raw', 'static', 'https://example.test', {'api_raw': Session()}, None, 'synthetic-key', Path(root), 0)
            self.assertEqual(result['outcome'], 'aborted')
            self.assertFalse(result['valid'])
            self.assertIsNone(result['credits'])
            self.assertTrue(Path(root, result['body_file']).exists())

    def test_cleanup_failure_keeps_successful_capture(self):
        class Response:
            status = 200
        class Page:
            def goto(self, *args, **kwargs): return Response()
            def wait_for_selector(self, *args, **kwargs): pass
            def content(self): return STATIC
        class Context:
            def new_page(self): return Page()
            def close(self): raise RuntimeError('synthetic cleanup failure')
        class Browser:
            def new_context(self): return Context()
        with tempfile.TemporaryDirectory() as root:
            result = acquire('playwright', 'static', 'https://example.test', {}, Browser(), None, Path(root), 0)
            self.assertTrue(result['valid'])
            self.assertEqual(result['cleanup_exception_class'], 'RuntimeError')
            self.assertTrue(Path(root, result['body_file']).exists())

    def test_requests_has_ten_second_acquisition_deadline(self):
        limits = []
        @contextmanager
        def deadline(seconds):
            limits.append(seconds)
            yield
        class Response:
            status_code = 200
            content = STATIC.encode()
        class Session:
            def get(self, *args, **kwargs): return Response()
        with tempfile.TemporaryDirectory() as root, patch('runner.wall_deadline', deadline):
            acquire('requests', 'static', 'https://example.test', {'requests': Session()}, None, None, Path(root), 0)
        self.assertEqual(limits[0], 10)

    def test_hard_stop_after_body_write_preserves_replayable_intent(self):
        @contextmanager
        def fake_fixture(): yield 'https://example.test'
        class Browser:
            version = 'synthetic'
            def close(self): pass
        class PW:
            chromium = None
            def __init__(self): self.chromium = self
            def launch(self, **kwargs): return Browser()
        @contextmanager
        def fake_playwright(): yield PW()
        def hard_stop(arm, target, url, sessions, browser, key, out, index):
            (out/f'body-{index:03d}.html').write_bytes(b'captured before hard stop')
            raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as root, patch('runner.fixtures', fake_fixture), patch('runner.sync_playwright', fake_playwright), patch('runner.acquire', hard_stop):
            out = Path(root)/'run'
            with self.assertRaises(KeyboardInterrupt):
                run(SimpleNamespace(live=False, repeats=1, approved_credits=None, out=str(out)))
            result = replay(out/'report.json')
            self.assertEqual(result[0]['attempts'], 1)
            self.assertIsNone(result[0]['median_all_ms'])


if __name__ == '__main__':
    unittest.main()
