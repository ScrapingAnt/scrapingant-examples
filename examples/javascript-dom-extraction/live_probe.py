"""Explicit opt-in: six requests, owned fixtures, no retries or redirects."""
import argparse
import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from protocol import ResultError, parse_html, parse_marker
from state import CASES, TARGETS, score, snippet

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs): return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('run_output/live/live.json'))
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({'live': False, 'maximum_requests': 6, 'estimated_credits': 60, 'cases': CASES}))
        return 0
    key = os.environ.get('SCRAPINGANT_API_KEY')
    if not key: raise SystemExit('Set SCRAPINGANT_API_KEY in the environment.')
    if args.output.exists(): raise SystemExit('Output already exists; choose a new path only for an intentional new run.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'maximum_requests': 6,
              'automatic_retries': 0, 'calls': []}
    opener = build_opener(NoRedirect())
    for index, case in enumerate(CASES, 1):
        marker = 'sa-extract-' + uuid.uuid4().hex
        target = TARGETS['delayed' if case == 'delayed' else 'catalog']
        params = {'url': target, 'browser': 'true', 'return_page_source': 'false',
                  'proxy_type': 'datacenter', 'timeout': '60',
                  'js_snippet': base64.b64encode(snippet(case, marker).encode('utf-8')).decode('ascii')}
        if case == 'delayed': params['wait_for_selector'] = '#loaded'
        request = Request('https://api.scrapingant.com/v2/general?' + urlencode(params), headers={'x-api-key': key})
        row = {'call': index, 'case': case, 'target': target, 'marker': marker,
               'api_status': None, 'credits': None, 'result': None, 'transport_error': None, 'passed': False}
        try:
            with opener.open(request, timeout=90) as response:
                row['api_status'] = response.status
                credit = response.headers.get('Ant-credits-cost')
                row['credits'] = int(credit) if credit and credit.isdigit() else None
                html = response.read().decode('utf-8')
            if key in html: raise ValueError('Credential reflected')
            if row['api_status'] == 200:
                (args.output.parent / (case + '.html')).write_text(html)
                try:
                    row['result'] = parse_marker(html, marker)
                    if parse_html(html, marker) != row['result']: raise ResultError('PARSER_MISMATCH')
                except ResultError as exc:
                    row['transport_error'] = str(exc)
                row['passed'] = score(case, row['result'], row['transport_error'])
        except HTTPError as exc:
            row['api_status'] = exc.code
            row['error_class'] = type(exc).__name__
        except Exception as exc:
            # No raw exception, request URL, key, arbitrary response headers or error body.
            row['error_class'] = type(exc).__name__
        report['calls'].append(row)
        report['requests_sent'] = len(report['calls'])
        report['known_credits'] = sum(call['credits'] or 0 for call in report['calls'])
        report['missing_credit_receipts'] = sum(call['credits'] is None for call in report['calls'])
        report['passed'] = len(report['calls']) == 6 and all(call['passed'] for call in report['calls'])
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({k: row[k] for k in ('case', 'api_status', 'credits', 'passed', 'transport_error')}), flush=True)
    return 0 if report['passed'] else 1

if __name__ == '__main__': raise SystemExit(main())
