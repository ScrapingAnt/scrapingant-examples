"""Offline regression checks for evidence semantics and spending boundaries."""
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from broad_matrix import make_schedule, run_one, main
from broad_cases import classify_verification, safe_verification


class BroadBoundaries(unittest.TestCase):
    def test_default_broad_cli_prints_plan_without_network_or_jobs(self):
        output = io.StringIO()
        with patch('sys.argv', ['broad_matrix.py']), patch('sys.stdout', output), \
             patch('broad_matrix.balance', side_effect=AssertionError('Network call')), \
             patch('broad_matrix.run_one', side_effect=AssertionError('Paid job')):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.getvalue())['max_tasks'], 120)

    def test_resume_does_not_reissue_failed_or_ambiguous_paid_jobs(self):
        job = make_schedule(1)[0]
        with TemporaryDirectory() as directory:
            output = Path(directory)
            for outcome in ('error', 'process_timeout', 'started'):
                record = {**job, 'outcome': outcome, 'task_creation_uncertain': True}
                (output / (job['id'] + '.json')).write_text(json.dumps(record))
                with patch('broad_matrix.subprocess.Popen', side_effect=AssertionError('Repeated task')):
                    self.assertEqual(run_one(job, output), record)

    def test_schedule_is_bounded_and_each_cell_is_balanced(self):
        rows = make_schedule(10)
        self.assertEqual(len(rows), 120)
        self.assertEqual(len({r['id'] for r in rows}), 120)
        for provider in ('2captcha', 'anticaptcha'):
            self.assertEqual(sum(r['provider'] == provider for r in rows), 60)
        with self.assertRaises(ValueError):
            make_schedule(11)

    def test_v3_token_or_success_without_score_is_not_an_accepted_threshold(self):
        for payload in ({'success': True}, {'success': 'true', 'score': 0.9},
                        {'success': True, 'score': 0.3, 'action': 'examples/v3scores'}):
            self.assertFalse(classify_verification('recaptcha-v3', 200, payload))
        self.assertTrue(classify_verification('recaptcha-v3', 200,
            {'success': True, 'score': 0.9, 'action': 'examples/v3scores',
             'hostname': 'recaptcha-demo.appspot.com'}))

    def test_http_success_or_nonempty_solution_is_not_geetest_acceptance(self):
        self.assertFalse(classify_verification('geetest-v4', 200, {'result': 'fail'}))
        self.assertFalse(classify_verification('geetest-v4', 500, {'result': 'success'}))
        self.assertTrue(classify_verification('geetest-v4', 200, {'result': 'success'}))

    def test_turnstile_without_verifier_is_never_counted_as_accepted(self):
        self.assertFalse(classify_verification('turnstile', 200, {'success': True}))

    def test_whitelist_drops_raw_solutions_keys_ips_and_free_text(self):
        raw = {'success': True, 'score': 0.7, 'token': 'secret-token',
               'clientKey': 'secret-key', 'ip': '192.0.2.1',
               'errorDescription': 'url?key=secret-key',
               'error-codes': ['invalid-input-response'],
               'hostname': 'recaptcha-demo.appspot.com'}
        self.assertEqual(safe_verification(raw), {'success': True, 'score': 0.7,
            'error-codes': ['invalid-input-response'], 'hostname': 'recaptcha-demo.appspot.com'})

    def test_geetest_typed_api_rejection_is_retained_without_free_text(self):
        self.assertEqual(safe_verification({'status': 'error', 'code': '-50005',
                         'msg': 'token=secret', 'desc': {'type': 'defined error'}}),
                         {'status': 'error', 'code': '-50005'})


if __name__ == '__main__':
    unittest.main()
