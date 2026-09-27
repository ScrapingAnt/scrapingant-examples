"""Opt-in, eight-call maximum cookie experiment using synthetic values only."""
import argparse
import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlsplit

import requests

EXPECTED = {'sa_region': 'eu', 'sa_tier': 'member'}
TARGET = 'https://httpbingo.org/cookies'
SEED = TARGET+'/set?sa_region=eu&sa_tier=member'


def expected_cookies(value):
    if not isinstance(value, str): return {}
    jar = SimpleCookie()
    try: jar.load(value)
    except CookieError: return {}
    return {k: jar[k].value for k, v in EXPECTED.items() if k in jar and jar[k].value == v}


class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts = []
    def handle_data(self, data): self.parts.append(data)


def echo_cookies(body):
    if not isinstance(body, str): return {}
    for candidate in [body]:
        try:
            data = json.loads(candidate)
            return data.get('cookies', {}) if isinstance(data, dict) else {}
        except (ValueError, TypeError): pass
    parser = Text(); parser.feed(body)
    try:
        data = json.loads(''.join(parser.parts))
        return data.get('cookies', {}) if isinstance(data, dict) else {}
    except (ValueError, TypeError): return {}


class ApiProbe:
    def __init__(self, key, session=None):
        self.key = key
        self.session = session or requests.Session()
        self.requests = 0

    def call(self, label, mode, target, cookie_values=None):
        if target not in (TARGET, SEED): raise ValueError('Only the fixed public demo target is allowed')
        if self.requests >= 8: raise RuntimeError('Eight-request experiment limit reached')
        self.requests += 1
        params = {'url': target, 'browser': mode, 'proxy_type': 'datacenter', 'timeout': 60}
        if cookie_values:
            if any(EXPECTED.get(k) != v for k, v in cookie_values.items()): raise ValueError('Non-demo cookie')
            params['cookies'] = ';'.join(f'{k}={v}' for k, v in sorted(cookie_values.items()))
        record = {'call': self.requests, 'case': label, 'browser': mode == 'true', 'request_sent': True}
        try:
            response = self.session.get('https://api.scrapingant.com/v2/extended', params=params,
                                        headers={'x-api-key': self.key}, timeout=(10, 90), allow_redirects=False)
            record['api_status'] = response.status_code
            credit = response.headers.get('Ant-credits-cost')
            record['credits'] = int(credit) if credit and credit.isdigit() else None
            data = response.json() if response.status_code == 200 else {}
            if not isinstance(data, dict): data = {}
            record['target_status'] = data.get('status_code') if isinstance(data.get('status_code'), int) else None
            received = expected_cookies(data.get('cookies'))
            field = 'html' if 'html' in data else 'content' if 'content' in data else None
            echoed = echo_cookies(data.get(field, ''))
            record.update({'body_field': field, 'received_demo_names': sorted(received),
                           'received_all_expected': received == EXPECTED,
                           'echoed_demo_names': sorted(k for k in EXPECTED if k in echoed),
                           'echo_matches_expected': all(echoed.get(k) == v for k, v in EXPECTED.items())})
            return record, received
        except Exception as exc:
            # Never persist str(exc), URLs, response bodies or arbitrary headers.
            record['error_class'] = type(exc).__name__
            return record, {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('run_output/scrapingant.json'))
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({'live': False, 'maximum_requests': 8, 'target_origin': 'https://httpbingo.org',
                          'cases_per_mode': ['baseline', 'receive_after_set', 'without_replay', 'explicit_replay']}))
        return 0
    key = os.environ.get('SCRAPINGANT_API_KEY')
    if not key: raise SystemExit('Set SCRAPINGANT_API_KEY in the environment; never put it in source.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists(): raise SystemExit('Output exists; choose a new path only for an intentional new experiment.')
    probe = ApiProbe(key)
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'target': 'https://httpbingo.org',
              'synthetic_cookie_names': sorted(EXPECTED), 'maximum_requests': 8, 'calls': []}

    def capture(label, mode, target, cookies=None):
        record, received = probe.call(label, mode, target, cookies)
        report['calls'].append(record)
        report['requests_sent'] = probe.requests
        report['known_credits'] = sum(c.get('credits') or 0 for c in report['calls'])
        report['missing_credit_receipts'] = sum(c.get('credits') is None for c in report['calls'])
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(record), flush=True)
        return received

    for mode in ('false', 'true'):
        capture('baseline', mode, TARGET)
        received = capture('receive_after_set', mode, SEED)
        capture('without_replay', mode, TARGET)
        if received == EXPECTED: capture('explicit_replay', mode, TARGET, received)
        else:
            report.setdefault('skipped', []).append({'browser': mode == 'true', 'case': 'explicit_replay', 'reason': 'Expected cookie pair was not received'})
            args.output.write_text(json.dumps(report, indent=2)+'\n')
    # Captured failures are evidence; success requires both modes' complete round trip.
    replay = [c for c in report['calls'] if c['case'] == 'explicit_replay']
    return 0 if len(replay) == 2 and all(c.get('echo_matches_expected') for c in replay) else 1


if __name__ == '__main__': raise SystemExit(main())
