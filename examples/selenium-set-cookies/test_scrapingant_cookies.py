import json
import unittest
from scrapingant_cookies import ApiProbe, expected_cookies, echo_cookies


class Response:
    status_code = 200
    headers = {'Ant-credits-cost': '10'}
    def json(self):
        return {'html': '<pre>{"cookies":{"sa_region":"eu","sa_tier":"member"}}</pre>',
                'cookies': 'sa_region=eu;sa_tier=member;incidental=do-not-store', 'status_code': 200}


class Session:
    def __init__(self): self.calls = []
    def get(self, url, **kwargs): self.calls.append((url, kwargs)); return Response()


class ProbeTests(unittest.TestCase):
    def test_key_is_header_only_and_output_omits_incidental_cookie(self):
        session = Session(); probe = ApiProbe('sentinel-credential', session)
        record, cookies = probe.call('baseline', 'false', 'https://httpbingo.org/cookies')
        url, args = session.calls[0]
        self.assertNotIn('sentinel-credential', url+json.dumps(args['params']))
        self.assertEqual(args['headers']['x-api-key'], 'sentinel-credential')
        self.assertFalse(args['allow_redirects'])
        self.assertNotIn('sentinel-credential', json.dumps(record))
        self.assertNotIn('do-not-store', json.dumps(record))
        self.assertEqual(cookies, {'sa_region': 'eu', 'sa_tier': 'member'})

    def test_foreign_targets_and_ninth_call_are_rejected_without_request(self):
        session = Session(); probe = ApiProbe('sentinel-credential', session)
        with self.assertRaises(ValueError): probe.call('bad', 'false', 'https://other.test/cookies')
        self.assertEqual(session.calls, [])
        probe.requests = 8
        with self.assertRaises(RuntimeError): probe.call('ninth', 'false', 'https://httpbingo.org/cookies')
        self.assertEqual(session.calls, [])

    def test_no_arbitrary_cookie_is_replayed(self):
        self.assertEqual(expected_cookies('sa_region=eu;secret=unknown;sa_tier=wrong'), {'sa_region': 'eu'})

    def test_json_echo_in_html_and_plain_body(self):
        for body in ['{"cookies":{"sa_region":"eu"}}', '<html><body><pre>{"cookies":{"sa_region":"eu"}}</pre></body></html>']:
            self.assertEqual(echo_cookies(body), {'sa_region': 'eu'})


if __name__ == '__main__': unittest.main()
