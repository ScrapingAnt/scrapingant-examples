"""Strict rescan: never trust cached pass flags, match counts, or supplied denominators."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from case_contract import DIAGNOSTICS, EXTRACTIONS
from oracle import desired_matches, exact_dataset
from storage_state import JSON_VALUE, SPECIAL_KEY, SPECIAL_VALUE, validate_snapshot


def require(condition, message):
    if not condition:
        raise ValueError(message)


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: '+key)
        result[key] = value
    return result


def read_capture(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))


def loopback_origin(value):
    require(isinstance(value, str), 'origin must be a string')
    parts = urlsplit(value)
    require(parts.scheme == 'http' and parts.hostname == '127.0.0.1' and parts.port is not None
            and value == 'http://127.0.0.1:'+str(parts.port), 'not an exact fixture origin')


def check_extraction(case):
    region, stored, session, transport = EXTRACTIONS[case['case']]
    fields = {'case', 'kind', 'transport', 'stored_region', 'session_region', 'rendered_region',
              'page_path', 'request_path', 'request_event', 'records', 'ready', 'matching_records', 'row_count',
              'expected_records', 'assertion_passed'}
    require(set(case) == fields, 'extraction schema mismatch')
    require(case['transport'] == transport and case['stored_region'] == stored
            and case['session_region'] == session and case['rendered_region'] == region,
            'storage/transport/data state contradicts case')
    path = '/api/catalog' if case['case'] == 'query_parameter_missing' else '/api/catalog?region='+region
    page_path = path if transport == 'http' else ('/catalog?region=eu' if case['case'] == 'query_page_without_storage' else '/catalog')
    require(case['page_path'] == page_path, 'page URL contract mismatch')
    event = case['request_event']
    require(isinstance(event, dict) and set(event) == {'path', 'region', 'status', 'records'}, 'invalid request event')
    require(case['request_path'] == path and event['path'] == path and event['region'] == region
            and type(event['status']) is int and event['status'] == 200, 'request contract mismatch')
    require(exact_dataset(case['records'], region), 'records differ from independent oracle')
    require(exact_dataset(event['records'], region) and event['records'] == case['records'], 'request/DOM records differ')
    matched = desired_matches(case['records'])
    for field, expected in [('matching_records', matched), ('row_count', len(case['records'])), ('expected_records', 4)]:
        require(type(case[field]) is int and case[field] == expected, 'contradictory '+field)
    require(case['ready'] is True and case['assertion_passed'] is True, 'false or malformed extraction flag')
    return matched


def check_diagnostic(case):
    name = case['case']
    require(case['assertion_passed'] is True, 'diagnostic flag is not true')
    actual = {k: v for k, v in case.items() if k not in ('case', 'kind', 'assertion_passed')}
    expected = {
        'opaque_origin': {'error': 'SecurityError'},
        'argument_roundtrip': {'key': SPECIAL_KEY, 'value': SPECIAL_VALUE},
        'legacy_interpolation_failure': {'error': 'JavascriptException', 'legacy_value': None},
        'json_roundtrip': {'python_value': JSON_VALUE, 'browser_value': JSON_VALUE},
        'crud_selective_removal': {'removed_value': None, 'retained_value': 'retained'},
        'async_precondition': {'observed': {'storedRegion': None, 'region': 'us', 'stage': 'scheduled'}},
    }
    if name in expected:
        # JSON equality distinguishes false from zero, unlike Python structural equality.
        require(json.dumps(actual, sort_keys=True) == json.dumps(expected[name], sort_keys=True), 'diagnostic data mismatch: '+name)
    elif name == 'wrong_origin_restore_rejected':
        require(set(actual) == {'error', 'unchanged', 'before_items', 'after_items', 'source_origin', 'current_origin'}, 'origin diagnostic schema')
        loopback_origin(actual['source_origin']); loopback_origin(actual['current_origin'])
        require(actual['source_origin'] != actual['current_origin'] and actual['error'] == 'ValueError'
                and actual['unchanged'] is True and actual['before_items'] == [] and actual['after_items'] == [],
                'origin diagnostic mismatch')
    elif name == 'snapshot_restore_contents':
        require(set(actual) == {'exported_snapshot', 'restored_snapshot'}, 'snapshot diagnostic schema')
        for snapshot in actual.values():
            validate_snapshot(snapshot); loopback_origin(snapshot['origin'])
        require(actual['exported_snapshot'] == actual['restored_snapshot'], 'snapshot restore differs')
        items = dict(actual['restored_snapshot']['items'])
        require(set(items) == {'demo_region', SPECIAL_KEY, 'json'} and items['demo_region'] == 'eu'
                and items[SPECIAL_KEY] == SPECIAL_VALUE and json.loads(items['json']) == JSON_VALUE,
                'snapshot values differ')
    else:
        raise ValueError('unknown diagnostic')


def summarize(reports):
    require(isinstance(reports, list) and len(reports) in (1, 2), 'supply one or two browser captures')
    seen_browsers = set()
    rows = {name: {'observations': 0, 'desired_dataset': 0, 'matching_records': 0, 'expected_records': 0,
                   'transport': expected[3]} for name, expected in EXTRACTIONS.items()}
    diagnostics = 0
    for report in reports:
        require(isinstance(report, dict) and set(report) == {'schema_version', 'tested_at', 'browser', 'python', 'selenium', 'os', 'runs', 'assertions', 'passed'}, 'report schema mismatch')
        require(type(report['schema_version']) is int and report['schema_version'] == 1, 'unsupported report schema')
        kind = report['browser']
        require(kind in ('chrome', 'firefox') and kind not in seen_browsers, 'missing or duplicate browser identity')
        seen_browsers.add(kind)
        for key in ('tested_at', 'python', 'selenium', 'os'):
            require(isinstance(report[key], str) and bool(report[key]), 'missing environment metadata')
        require(datetime.fromisoformat(report['tested_at']).tzinfo is not None, 'timestamp needs timezone')
        require(isinstance(report['runs'], list) and len(report['runs']) == 3, 'exactly three rounds required')
        count = 0
        for index, run in enumerate(report['runs'], 1):
            require(isinstance(run, dict) and set(run) == {'round', 'environment', 'cases'}, 'round schema mismatch')
            require(type(run['round']) is int and run['round'] == index, 'missing/duplicate/out-of-order round')
            env = run['environment']
            require(isinstance(env, dict) and set(env) == {'browser', 'browser_version', 'driver_version'}
                    and all(isinstance(v, str) and v for v in env.values()) and env['browser'] == kind, 'invalid browser environment')
            cases = run['cases']
            require(isinstance(cases, list) and len(cases) == len(EXTRACTIONS)+len(DIAGNOSTICS), 'incomplete case set')
            seen = set()
            for case in cases:
                require(isinstance(case, dict) and isinstance(case.get('case'), str) and case['case'] not in seen, 'invalid/duplicate case')
                name = case['case']; seen.add(name)
                if name in EXTRACTIONS:
                    require(case.get('kind') == 'extraction', 'misclassified extraction')
                    matched = check_extraction(case)
                    rows[name]['observations'] += 1
                    rows[name]['desired_dataset'] += int(matched == 4)
                    rows[name]['matching_records'] += matched
                    rows[name]['expected_records'] += 4
                else:
                    require(name in DIAGNOSTICS and case.get('kind') == 'diagnostic', 'unknown/misclassified diagnostic')
                    check_diagnostic(case); diagnostics += 1
            require(seen == set(EXTRACTIONS) | DIAGNOSTICS, 'case set mismatch')
            by_name = {case['case']: case for case in cases}
            require(by_name['wrong_origin_restore_rejected']['source_origin'] ==
                    by_name['snapshot_restore_contents']['exported_snapshot']['origin'],
                    'snapshot and origin-guard diagnostics contradict each other')
            count += len(cases)
        for field in ('assertions', 'passed'):
            require(type(report[field]) is int and report[field] == count, 'contradictory report total')
    return {'browsers': sorted(seen_browsers), 'rounds_per_browser': 3,
            'extraction_observations': sum(row['observations'] for row in rows.values()),
            'browser_extraction_observations': sum(row['observations'] for row in rows.values() if row['transport'] == 'browser'),
            'direct_http_observations': sum(row['observations'] for row in rows.values() if row['transport'] == 'http'),
            'diagnostic_observations': diagnostics, 'cases': rows,
            'interpretation': 'Observed fixture outcomes, including expected wrong-state controls; no production success estimate.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('captures', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, default=Path('run_output/summary.json'))
    args = parser.parse_args()
    result = summarize([read_capture(path) for path in args.captures])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
