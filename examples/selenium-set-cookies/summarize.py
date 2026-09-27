"""Rebuild the primary comparison from committed captures without network calls."""
import json
from pathlib import Path


def summarize(root):
    sources = {name: json.loads((root/'expected_output'/f'{name}.json').read_text()) for name in ('chrome', 'firefox')}
    rows = [dict(browser=name, round=run['round'], **case)
            for name, data in sources.items() for run in data['runs'] for case in run['cases'] if case['kind'] == 'extraction']
    summary = {
        'primary_browsers': {name: {'environment': data['runs'][0]['environment'], 'assertions': data['assertions'], 'passed': data['passed']}
                             for name, data in sources.items()},
        'case_outcomes': {},
        'primary_assertions': sum(d['assertions'] for d in sources.values()),
        'primary_extraction_observations': len(rows), 'records_per_observation': 4,
        'limitations': [
            'Synthetic deterministic dataset, not a production-site reliability estimate.',
            'Three repeats per browser share one host and fixture design.',
            'Exploratory installed Firefox109.0.1 results are archived separately and excluded from the primary comparison.',
            'Cross-site SameSite behavior, partitioned cookies, browser profiles, SSO and real account portability were not tested.',
        ],
    }
    for case in dict.fromkeys(x['case'] for x in rows):
        records = [x for x in rows if x['case'] == case]
        summary['case_outcomes'][case] = {
            'observations': len(records), 'statuses': sorted(set(x['target_status'] for x in records)),
            'row_counts': sorted(set(x['row_count'] for x in records)),
            'matching_record_counts': sorted(set(x['matching_records'] for x in records)),
            'all_assertions_passed': all(x['assertion_passed'] for x in records),
        }
    api = json.loads((root/'expected_output/scrapingant.json').read_text())
    summary['api'] = {'requests': api['requests_sent'], 'known_credits': api['known_credits'],
                      'missing_credit_receipts': api['missing_credit_receipts'],
                      'replay_confirmed_modes': [c['browser'] for c in api['calls'] if c['case'] == 'explicit_replay' and c['echo_matches_expected']]}
    return summary


if __name__ == '__main__':
    print(json.dumps(summarize(Path(__file__).resolve().parent), indent=2))
