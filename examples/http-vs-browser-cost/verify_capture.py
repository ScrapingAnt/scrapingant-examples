"""Strict offline capture verification; never acquires pages or reads credentials.

The recorded acquisition source stays byte-identical to the executed revision.
runner.replay supplies mechanical plan/body/oracle/summary checks. This wrapper
also validates provenance completeness and the declared budget/receipt rules.
Hashes protect artifact integrity; they do not authenticate provider billing.
"""
import argparse
import json
from pathlib import Path

from contract import TARGETS
from runner import receipt_is_expected, replay, validate_options

RUNTIME_FILES = {'runner.py', 'contract.py', 'requirements.txt'}


def verify(path):
    path = Path(path)
    report = json.loads(path.read_text())
    if type(report.get('complete')) is not bool:
        raise ValueError('Explicit complete/incomplete status required')
    live = report.get('mode') == 'live'
    ceiling = validate_options(live, report.get('repeats'), report.get('approved_credit_ceiling') if live else None)
    fixtures = report.get('fixtures')
    if not isinstance(fixtures, dict) or set(fixtures) != set(TARGETS):
        raise ValueError('Complete fixture map required')
    for target, config in TARGETS.items():
        if fixtures[target].get('url') != config['url']:
            raise ValueError('Fixture URL mismatch')
    source = report.get('source_sha256')
    if (live or source is not None) and (not isinstance(source, dict) or set(source) != RUNTIME_FILES):
        raise ValueError('Complete runtime hash map required')
    total = report.get('actual_credits_receipted')
    if type(total) is not int or total < 0:
        raise ValueError('Nonnegative integer receipt total required')
    if total > ceiling:
        raise ValueError('Credit ceiling exceeded')
    rows = report['rows']
    for index, row in enumerate(rows):
        actual = row['credits']
        if row['arm'].startswith('api_'):
            if not live:
                raise ValueError('Local run cannot contain an API attempt')
            if actual is not None and (type(actual) is not int or actual < 0):
                raise ValueError('Invalid receipt value')
            expected = 10 if row['arm'] == 'api_rendered' else 1
            if report['complete'] or index < len(rows)-1:
                if not receipt_is_expected(row['status'], actual, expected):
                    raise ValueError('Unexpected completed receipt')
            elif actual is not None and not receipt_is_expected(row['status'], actual, expected):
                if not report.get('stop_reason'):
                    raise ValueError('Unexpected partial receipt needs an explicit stop reason')
        elif actual is not None:
            raise ValueError('Direct acquisition cannot have an API receipt')
    computed = replay(path)
    return dict(complete=report['complete'], runtime_hashes_present=source is not None,
                billing_status=('complete_receipts' if report['complete'] else 'partial_unknown_or_anomaly') if live else 'no_api_calls',
                actual_credits_receipted=total, summary=computed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.report), indent=2))
    except Exception as exc:
        print(json.dumps({'error_class': type(exc).__name__, 'result': 'verification failed; captured evidence unchanged'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
