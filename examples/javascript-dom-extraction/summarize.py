"""Recompute evidence from raw values; runner success flags are not evidence."""
import json
import subprocess
from pathlib import Path
from protocol import ResultError, parse_html, parse_marker
from state import CASES, ROOT, TARGETS, score

def summarize(report, directory, live=False):
    rows = report.get('calls' if live else 'observations', [])
    if len(rows) != len(CASES) or [row['case'] for row in rows] != CASES:
        raise ValueError('CASE_COVERAGE')
    passed = 0
    for row in rows:
        case, marker = row['case'], row['marker']
        if row.get('api_status' if live else 'http_status') != 200:
            raise ValueError('HTTP_STATUS')
        if live and row.get('target') != TARGETS['delayed' if case == 'delayed' else 'catalog']:
            raise ValueError('TARGET')
        html_path = directory / (case + '.html')
        html = html_path.read_text()
        result, error = None, None
        try:
            result = parse_marker(html, marker)
            if parse_html(html, marker) != result: raise ValueError('PARSER_MISMATCH')
        except ResultError as exc:
            error = str(exc)
        if row.get('result') != result or row.get('transport_error') != error or not score(case, result, error):
            raise ValueError('OUTCOME')
        node = subprocess.run(['node', str(ROOT / 'parse-marker.mjs'), str(html_path), marker], capture_output=True, text=True)
        if result is None:
            if node.returncode != 1 or node.stderr.strip() != error: raise ValueError('NODE_MISMATCH')
        elif node.returncode != 0 or json.loads(node.stdout) != result:
            raise ValueError('NODE_MISMATCH')
        if row.get('passed') is not True: raise ValueError('FLAG_MISMATCH')
        passed += 1
    summary = {'checks': len(rows), 'expected_outcomes': passed, 'catalog_extractions': 3,
               'catalog_records': 9, 'return_only_missing_marker': 1,
               'explicit_extraction_error': 1, 'delayed_dom_result': 1,
               'python_and_node_parsers_agree': passed}
    if live:
        if report.get('requests_sent') != 6 or report.get('maximum_requests') != 6 or report.get('automatic_retries') != 0:
            raise ValueError('REQUEST_COUNT')
        if any(type(row.get('credits')) is not int or row['credits'] < 0 for row in rows):
            raise ValueError('CREDIT_RECEIPT')
        summary['credits'] = sum(row['credits'] for row in rows)
        if report.get('known_credits') != summary['credits'] or report.get('missing_credit_receipts') != 0:
            raise ValueError('CREDIT_TOTAL')
    elif report.get('api_requests') != 0:
        raise ValueError('PAID_CALL_IN_LOCAL')
    return summary

if __name__ == '__main__':
    output = {}
    for mode in ('local', 'live'):
        directory = ROOT / 'expected_output' / mode
        output[mode] = summarize(json.loads((directory / (mode + '.json')).read_text()), directory, mode == 'live')
    print(json.dumps(output, indent=2))
