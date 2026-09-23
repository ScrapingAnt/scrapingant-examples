"""Offline checks for the paid runner's spending and disclosure boundaries."""
from contextlib import redirect_stdout
from io import StringIO
import json
import unittest
from unittest.mock import patch

import paid_demo


class PaidBoundaries(unittest.TestCase):
    def test_default_cli_with_credentials_never_calls_network(self):
        for provider, (_, variable) in paid_demo.SPECS.items():
            with self.subTest(provider=provider), patch.dict('os.environ', {variable: 'fixture-secret'}), \
                    patch('sys.argv', ['runner']), \
                    patch('requests.sessions.Session.request', side_effect=AssertionError('Network call')), \
                    redirect_stdout(StringIO()) as output:
                self.assertEqual(paid_demo.cli(provider), 0)
                result = json.loads(output.getvalue())
                self.assertEqual(result['paid_tasks_created'], 0)
                self.assertNotIn('fixture-secret', output.getvalue())

    def test_missing_key_never_starts_a_browser(self):
        with patch.dict('os.environ', {}, clear=True), patch('paid_demo.sync_playwright') as browser:
            result, status = paid_demo.run('2captcha', 1)
        self.assertEqual(status, 2)
        self.assertEqual(result['task_create_requests'], 0)
        browser.assert_not_called()

    def test_zero_balance_never_creates_a_task(self):
        with patch.dict('os.environ', {'TWOCAPTCHA_API_KEY': 'fixture-secret'}), \
                patch.object(paid_demo.MeasuredTwoCaptcha, 'balance', return_value=0), \
                patch.object(paid_demo.MeasuredTwoCaptcha, 'send') as send:
            result, status = paid_demo.run('2captcha', 1)
        self.assertEqual(status, 2)
        self.assertEqual(result['paid_tasks_created'], 0)
        send.assert_not_called()

    def test_a_second_task_request_is_blocked(self):
        result = {'task_create_requests': 0}
        paid_demo.start_task(result)
        with self.assertRaises(RuntimeError):
            paid_demo.start_task(result)
        self.assertEqual(result['task_create_requests'], 1)

    def test_exception_with_credential_is_not_published(self):
        with patch.dict('os.environ', {'TWOCAPTCHA_API_KEY': 'fixture-secret'}), \
                patch.object(paid_demo.MeasuredTwoCaptcha, 'balance',
                             side_effect=RuntimeError('url?key=fixture-secret ERROR_WRONG_USER_KEY')):
            result, status = paid_demo.run('2captcha', 1)
        self.assertEqual(status, 1)
        self.assertNotIn('fixture-secret', json.dumps(result))
        self.assertEqual(result['provider_error_code'], 'ERROR_WRONG_USER_KEY')


if __name__ == '__main__':
    unittest.main()
