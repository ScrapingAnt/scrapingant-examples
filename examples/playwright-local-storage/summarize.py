"""Recompute every result from raw observations; no browsers or network needed."""
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from spec import DIAGNOSTICS, EXTRACTION, JSON_PAYLOAD
from state import EXPECTED_EU, EXPECTED_US, record_tuples, score_records, validate_origin


BROWSERS = {'chromium', 'firefox'}


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Timestamps must carry a timezone')
    return result


def observation_passed(case, origins):
    name = case['case']
    if name in EXTRACTION:
        region, stored, query, label = EXTRACTION[name]
        origin = origins[label]
        url = urlsplit(case['request_url'])
        expected_records = EXPECTED_EU if region == 'eu' else EXPECTED_US
        expected_mode = 'browser_dom'
        expected_page_url = origin + '/' + ('?region=eu' if name == 'query_only_without_storage' else '')
        return (case['kind'] == 'extraction' and case['mode'] == expected_mode
                and case['origin'] == origin and case['page_url'] == expected_page_url
                and f'{url.scheme}://{url.netloc}' == origin
                and url.path == '/api/catalog' and not url.fragment
                and parse_qs(url.query, keep_blank_values=True) == ({'region': [query]} if query else {})
                and case['page_status'] == 200 and case['request_status'] == 200
                and case['response_region'] == region and case['storage_region'] == stored
                and Counter(record_tuples(case['records'])) == Counter(expected_records)
                and Counter(record_tuples(case['api_records'])) == Counter(expected_records))
    if case['kind'] != 'diagnostic':
        return False
    observed = case['observed']
    if name == 'json_argument_round_trip':
        return (set(observed) == {'input', 'parsed', 'raw', 'stored_type'}
                and observed['input'] == JSON_PAYLOAD and observed['parsed'] == JSON_PAYLOAD
                and observed['stored_type'] == 'string'
                and json.loads(observed['raw']) == JSON_PAYLOAD)
    if name == 'storage_crud':
        return observed == {'initial': None, 'after_set': 'first', 'after_update': 'second',
                            'after_remove': None, 'count_before_clear': 2, 'count_after_clear': 0}
    if name == 'session_storage_not_restored':
        return observed == {'original_local': 'eu', 'original_session': 'tab-only',
            'new_page_local': 'eu', 'new_page_session': None, 'restored_local': 'eu',
            'restored_session': None, 'snapshot': {'cookies': [], 'origins': [
                {'origin': origins['primary'], 'localStorage': [{'name': 'region', 'value': 'eu'}]}]}}
    if name == 'storage_event_other_page':
        return observed == {'writer_events': [], 'reader_events': [
            {'key': 'region', 'oldValue': None, 'newValue': 'eu', 'storageArea': 'localStorage'}],
            'writer_value': 'eu', 'reader_value': 'eu'}
    raise ValueError('Unknown diagnostic')


def validate_captures(captures, expected_browsers):
    try:
        expected = list(expected_browsers)
        if not expected or len(set(expected)) != len(expected) or set(expected) - BROWSERS:
            raise ValueError('Expected distinct supported browser names')
        if Counter(data['browser'] for data in captures) != Counter(expected):
            raise ValueError('Capture browser coverage differs from requested browser coverage')
        for data in captures:
            if data['schema_version'] != 1 or type(data['rounds']) is not int or data['rounds'] != 3:
                raise ValueError('Expected schema version 1 and exactly three rounds')
            started, completed = timestamp(data['started_at']), timestamp(data['completed_at'])
            if completed < started:
                raise ValueError('Completion precedes start')
            env = data['environment']
            if set(env) != {'python', 'platform', 'machine', 'playwright', 'browser'} or any(
                    not isinstance(value, str) or not value for value in env.values()):
                raise ValueError('Missing captured environment/version metadata')
            origins = data['fixture_origins']
            if set(origins) != {'primary', 'secondary'} or len(set(origins.values())) != 2:
                raise ValueError('Expected distinct primary and secondary fixture origins')
            for origin in origins.values():
                validate_origin(origin)
            if (any(type(run['round']) is not int for run in data['runs'])
                    or [run['round'] for run in data['runs']] != [1, 2, 3]):
                raise ValueError('Expected rounds one, two and three, exactly once each')
            for run in data['runs']:
                if Counter(case['case'] for case in run['cases']) != Counter(set(EXTRACTION) | DIAGNOSTICS):
                    raise ValueError('Every declared case must appear exactly once per round')
                for case in run['cases']:
                    if not started <= timestamp(case['captured_at']) <= completed:
                        raise ValueError('Case timestamp outside capture interval')
                    expected_kind = 'extraction' if case['case'] in EXTRACTION else 'diagnostic'
                    if case['kind'] != expected_kind:
                        raise ValueError('Case kind differs from the predeclared experiment')
                    if case['case'] in EXTRACTION:
                        score = score_records(case['records'])
                        if any(type(case[key]) is not type(value) or case[key] != value
                               for key, value in score.items()):
                            raise ValueError('Stored score disagrees with independently rescored rows')
                    passed = observation_passed(case, origins)
                    if type(case['check_passed']) is not bool or case['check_passed'] != passed:
                        raise ValueError('Stored check flag disagrees with raw observed result')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Malformed capture structure') from error


def summarize_captures(captures, expected_browsers):
    validate_captures(captures, expected_browsers)
    cases = [case for data in captures for run in data['runs'] for case in run['cases']]
    rows = [case for case in cases if case['kind'] == 'extraction']
    diagnostics = [case for case in cases if case['kind'] == 'diagnostic']
    summary = {'browsers': {data['browser']: data['environment'] for data in captures},
               'rounds_per_browser': 3, 'checks': len(cases),
               'passed_checks': sum(case['check_passed'] for case in cases),
               'extraction_observations': len(rows), 'diagnostic_observations': len(diagnostics),
               'records_per_extraction': 4, 'record_opportunities': len(rows) * 4,
               'matching_record_observations': sum(case['matching_records'] for case in rows),
               'exact_extraction_observations': sum(case['exact_match'] for case in rows),
               'http_200_extraction_observations': sum(case['request_status'] == 200 for case in rows),
               'four_row_extraction_observations': sum(case['row_count'] == 4 for case in rows),
               'cases': {}, 'diagnostics': {}}
    for name in EXTRACTION:
        selected = [case for case in rows if case['case'] == name]
        summary['cases'][name] = {'observations': len(selected),
            'matching_record_counts': sorted({case['matching_records'] for case in selected}),
            'all_checks_passed': all(case['check_passed'] for case in selected)}
    for name in sorted(DIAGNOSTICS):
        selected = [case for case in diagnostics if case['case'] == name]
        summary['diagnostics'][name] = {'observations': len(selected),
            'all_checks_passed': all(case['check_passed'] for case in selected)}
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, default=Path('expected_output'))
    parser.add_argument('--browsers', nargs='+', choices=sorted(BROWSERS), default=['chromium', 'firefox'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = summarize_captures([json.loads((args.input_dir / f'{browser}.json').read_text())
                                for browser in args.browsers], args.browsers)
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')
    if result['checks'] != result['passed_checks']:
        raise SystemExit('One or more observed hypotheses failed')
