"""Evaluate captured behavior against a fixture manifest independent of the scraper."""
import asyncio
import hashlib
import importlib.metadata
import json
import platform
import random
from collections import Counter
from pathlib import Path

import httpx
from fixture_server import start
from scraper import IO_SECONDS, JOB_SECONDS, make_sink, scrape

ROOT = Path(__file__).parent
OUT = ROOT / 'expected_output'
CASES = json.loads((ROOT / 'fixtures/expected_cases.json').read_text())
ORACLE = json.loads((ROOT / 'fixtures/oracle.json').read_text())
REPEATS = 3
CLOCK_TOLERANCE = 1.0  # scheduling allowance; report it, do not claim hard real time


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


async def main():
    OUT.mkdir(exist_ok=True)
    server = start()
    base = f'http://127.0.0.1:{server.server_port}'
    events, results, checks, stored = [], [], [], []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(IO_SECONDS), trust_env=False,
                                     follow_redirects=False) as client:
            # Intentionally inadequate control: HTTP status says nothing about records.
            naive = []
            for name in ['valid', 'empty', 'malformed', 'missing_price', 'wrong_type', 'wrong_price']:
                response = await client.get(f'{base}/naive/{name}')
                naive.append({'case': name, 'status': response.status_code,
                              'naive_status_success': response.is_success,
                              'body_sha256': hashlib.sha256(response.content).hexdigest()})
            save('naive_control.json', naive)
            for repeat in range(1, REPEATS + 1):
                for case in CASES:
                    key = f'r{repeat}/{case["id"]}'
                    sink = make_sink()
                    if case['id'] == 'sink_failure':
                        # Real SQLite failure, not a fake exception in scraper code.
                        sink.execute('PRAGMA query_only=ON')
                    last = None
                    for delivery in range(2 if case.get('replay') else 1):
                        job = f'{key}/delivery{delivery + 1}'
                        def emit(value, job=job, key=key):
                            events.append({'run_id': f'r{repeat}', 'case_id': case['id'],
                                           'job_id': job, **value})
                        last = await scrape(client, f'{base}/{key}', sink, emit,
                                            rng=random.Random(1234))
                        last.update({'repeat': repeat, 'case_id': case['id'], 'job_id': job})
                        results.append(last)
                    rows = [json.loads(r[0]) for r in sink.execute('SELECT payload FROM records ORDER BY id')]
                    stored.append({'repeat': repeat, 'case_id': case['id'], 'rows': rows})
                    actual_match = all(record == ORACLE for record in rows) if rows else None
                    observed = [r for r in server.observed if r['path'] == '/' + key]
                    expected_attempts = case['attempts'] + (1 if case.get('replay') else 0)
                    assertions = {
                        'terminal_outcome': last['outcome'] == case['outcome'],
                        'attempt_count': last['attempts'] == case['attempts'],
                        'server_attempt_count': len(observed) == expected_attempts,
                        'row_count': len(rows) == case['rows'],
                        'oracle_result': actual_match == case['oracle_match'],
                        'deadline_bound': all(r['elapsed_s'] <= JOB_SECONDS + CLOCK_TOLERANCE
                                              for r in results if r['job_id'].startswith(key + '/')),
                    }
                    if 'minimum_retry_gap_s' in case:
                        gap = observed[1]['monotonic_s'] - observed[0]['monotonic_s']
                        assertions['retry_after_respected'] = gap >= case['minimum_retry_gap_s']
                    checks.append({'repeat': repeat, 'case_id': case['id'], 'assertions': assertions,
                                   'passed': all(assertions.values()), 'oracle_match': actual_match})
                    sink.close()
    finally:
        server.shutdown()
        server.server_close()
    terminal = [event for event in events if event['event'] == 'terminal']
    schema = [event for event in events if event['event'] == 'schema']
    all_rows = [row for capture in stored for row in capture['rows']]
    summary = {
        'fixture_cases': len(CASES), 'repetitions': REPEATS,
        'case_checks_passed': sum(check['passed'] for check in checks), 'case_checks_total': len(checks),
        'jobs_started': len(results), 'http_attempts': sum(r['attempts'] for r in results),
        'terminal_events': len(terminal), 'outcomes': dict(sorted(Counter(r['outcome'] for r in results).items())),
        'schema_valid_records': sum(event['passed'] for event in schema), 'extracted_records': len(schema),
        'stored_records_across_isolated_cases': len(all_rows),
        'oracle_matching_stored_records': sum(row == ORACLE for row in all_rows),
        'schema_valid_wrong_price_deliveries': sum(r['case_id'] == 'wrong_price' and r['outcome'] == 'delivered' for r in results),
        'deadline_violations_with_tolerance': sum(r['elapsed_s'] > JOB_SECONDS + CLOCK_TOLERANCE for r in results),
        'deadline_s': JOB_SECONDS, 'per_io_timeout_s': IO_SECONDS, 'clock_tolerance_s': CLOCK_TOLERANCE,
        'max_observed_job_elapsed_s': max(r['elapsed_s'] for r in results),
        'retry_amplification': sum(r['attempts'] for r in results) / len(results),
        'environment': {'python': platform.python_version(), 'os': platform.platform(),
                        'httpx': importlib.metadata.version('httpx'), 'jsonschema': importlib.metadata.version('jsonschema')},
    }
    save('report.json', {'summary': summary, 'checks': checks, 'jobs': results})
    save('stored_records.json', stored)
    # Port omitted from events: keep diagnostic identity stable and no secrets in URLs.
    save('fixture_requests.json', server.observed)
    (OUT / 'events.jsonl').write_text(''.join(json.dumps(event, sort_keys=True) + '\n' for event in events))
    assert len(terminal) == len(results), 'one terminal event required per job'
    assert sum(r['attempts'] for r in results) == len(server.observed) - len(naive)
    print('Naive control: ' + ', '.join(f'{row["case"]}={row["status"]}' for row in naive))
    print(f'Cases: {len(CASES)} x {REPEATS} repetitions = {len(checks)} checks')
    print(f'Passed: {summary["case_checks_passed"]}/{summary["case_checks_total"]}')
    print(f'Jobs: {len(results)}; HTTP attempts: {summary["http_attempts"]}; terminal events: {len(terminal)}')
    print(f'Schema-valid: {summary["schema_valid_records"]}/{len(schema)} extracted records')
    print(f'Oracle matches: {summary["oracle_matching_stored_records"]}/{len(all_rows)} stored records')
    print(f'Wrong-price deliveries despite valid schema: {summary["schema_valid_wrong_price_deliveries"]}')
    print(f'Deadline violations beyond {JOB_SECONDS} s + {CLOCK_TOLERANCE} s tolerance: {summary["deadline_violations_with_tolerance"]}')
    print('Outcomes: ' + json.dumps(summary['outcomes'], sort_keys=True))
    assert all(check['passed'] for check in checks), 'observed behavior differs from case manifest'


if __name__ == '__main__':
    asyncio.run(main())
