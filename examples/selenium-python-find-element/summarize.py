"""Recompute results from raw values; refuse incomplete, stale or forged captures."""
import argparse
import json
from pathlib import Path

from browser_support import source_hashes
from case_contract import EXTRACTION, DIAGNOSTICS
from oracle import exact_records


def require(condition, message):
    if not condition:
        raise ValueError(message)


def summarize(packets):
    require(isinstance(packets, list) and bool(packets), 'no captures')
    seen_browsers = set()
    environments = []
    results = []
    for packet in packets:
        require(isinstance(packet, dict) and set(packet) == {'schema_version', 'rounds', 'environment', 'source_hashes', 'observations'}, 'capture schema')
        require(type(packet['schema_version']) is int and packet['schema_version'] == 1, 'schema version')
        require(type(packet['rounds']) is int and packet['rounds'] == 3, 'exactly three rounds required')
        env = packet['environment']
        required = {'browser', 'browser_version', 'driver_version', 'python', 'selenium', 'os', 'os_release', 'architecture'}
        require(isinstance(env, dict) and set(env) == required and all(isinstance(env[key], str) and env[key] for key in required), 'environment incomplete')
        require(env['browser'] in {'chrome', 'firefox'} and env['browser'] not in seen_browsers, 'browser coverage duplicate or unknown')
        require(env['selenium'] == '4.49.0', 'unexpected Selenium version')
        require(packet['source_hashes'] == source_hashes(), 'source hashes differ; regenerate capture')
        seen_browsers.add(env['browser'])
        environments.append(env)
        rows = packet['observations']
        require(isinstance(rows, list), 'observations must be a list')
        seen = set()
        for row in rows:
            require(isinstance(row, dict), 'observation schema')
            kind = row.get('kind')
            keys = {'round', 'case', 'kind', 'records', 'error'} if kind == 'extraction' else {'round', 'case', 'kind', 'values'}
            require(kind in {'extraction', 'diagnostic'} and set(row) == keys, 'observation schema')
            require(type(row['round']) is int and row['round'] in (1, 2, 3), 'round coverage')
            contract = EXTRACTION if kind == 'extraction' else DIAGNOSTICS
            require(row['case'] in contract, 'unknown case')
            key = (row['round'], row['case'])
            require(key not in seen, 'duplicate observation')
            seen.add(key)
            spec = contract[row['case']]
            target = None
            if kind == 'extraction':
                require(row['error'] == spec['error'] and exact_records(row['records'], spec['records']), 'unexpected extraction: ' + row['case'])
                target = exact_records(row['records'])
                require(target is spec['target'], 'unexpected target status')
            else:
                # JSON canonical equality also distinguishes bool from numeric diagnostics.
                require(json.dumps(row['values'], sort_keys=True) == json.dumps(spec, sort_keys=True), 'unexpected diagnostic: ' + row['case'])
            results.append({'browser': env['browser'], 'round': row['round'], 'case': row['case'], 'kind': kind,
                            'expected_observation': True, 'complete_target': target})
        expected = {(number, case) for number in (1, 2, 3) for case in (*EXTRACTION, *DIAGNOSTICS)}
        require(seen == expected, 'incomplete case/round coverage')
    require('chrome' in seen_browsers, 'Chrome capture required')
    extraction = [row for row in results if row['kind'] == 'extraction']
    return {'schema_version': 1, 'environments': environments, 'rounds_per_browser': 3,
            'extraction_cases': len(EXTRACTION), 'diagnostic_cases': len(DIAGNOSTICS),
            'extraction_observations': len(extraction),
            'complete_target_observations': sum(row['complete_target'] for row in extraction),
            'expected_wrong_observations': sum(not row['complete_target'] for row in extraction),
            'diagnostic_observations': len(results) - len(extraction),
            'expected_observations': len(results), 'results': results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('captures', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    summary = summarize([json.loads(path.read_text()) for path in args.captures])
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key not in {'results', 'environments'}}, indent=2))


if __name__ == '__main__':
    main()
