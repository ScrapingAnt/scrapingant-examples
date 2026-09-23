"""Opt-in six-case comparison: at most 120 tasks; durable no-retry job records.

Default prints a plan and performs no network calls. --live spends funds.
Each child gets a 400-second external process deadline. Existing job records,
including errors and interrupted requests, are NEVER automatically repeated.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import threading
import time

from playwright.sync_api import sync_playwright
from broad_cases import CASES, IMAGE_DIR, image_fixture, prepare_page, verify_solution
from broad_providers import (ENV, balance, bounded_transport, solver_for, solve,
                             extra_cost_receipt, safe_error)

PROCESS_TIMEOUT = 400


def make_schedule(rounds):
    if type(rounds) is not int or not 1 <= rounds <= 10:
        raise ValueError('Choose 1 to 10 trials per cell; maximum120 paid tasks')
    rows = []
    rng = random.Random(20260923)
    for trial in range(1, rounds + 1):
        cases = list(CASES)
        rng.shuffle(cases)
        for case in cases:
            providers = ('2captcha', 'anticaptcha') if trial % 2 else ('anticaptcha', '2captcha')
            for provider in providers:
                rows.append({'id': f'{case}-{provider}-{trial:02}', 'case': case,
                             'provider': provider, 'trial': trial})
    return rows


def write_record(path, record):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(record, indent=2) + '\n')
    temp.replace(path)


def execute_job(job, path, control=False):
    spec = CASES[job['case']]
    result = {**job, 'tested_at': datetime.now(timezone.utc).isoformat(),
              'target': spec['url'], 'criterion': spec['criterion'],
              'outcome': 'started', 'task_create_requests': 0, 'paid_tasks_created': 0,
              'task_creation_uncertain': False, 'solution_delivered': False,
              'server_acceptance_tested': False, 'server_accepted': None,
              'provider_reported_cost_usd': None, 'control': control,
              'headless': True, 'process_timeout_seconds': PROCESS_TIMEOUT}
    # Atomic reservation means concurrent invocations cannot spend twice on an ID.
    with path.open('x') as file:
        file.write(json.dumps(result, indent=2) + '\n')
    def save():
        write_record(path, result)
    start, solver = time.monotonic(), None
    stage = 'fixture_setup'
    try:
        if not control:
            package = '2captcha-python' if job['provider'] == '2captcha' else 'anticaptchaofficial'
            result.update(package=package, package_version=metadata.version(package))
            if not os.environ.get(ENV[job['provider']]):
                result.update(outcome='unavailable', reason='missing_credential')
                return result
        with bounded_transport(), sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                result['browser'] = browser.version
                page = browser.new_page(viewport={'width': 1200, 'height': 850}, locale='en-US')
                page.set_default_timeout(20000)
                image_bytes = None
                if job['case'] == 'image-text':
                    fixture = image_fixture(job['trial'])
                    image_bytes = (IMAGE_DIR / fixture['file']).read_bytes()
                    digest = hashlib.sha256(image_bytes).hexdigest()
                    if digest != fixture['sha256']:
                        raise ValueError('Fixture hash mismatch')
                    result['image_sha256'] = digest
                else:
                    result['navigation_status'] = prepare_page(page, job['case'])
                if control:
                    solution = ({'captcha_id': spec['sitekey'], 'lot_number': '0' * 32,
                                 'pass_token': '0' * 32, 'gen_time': str(int(time.time())),
                                 'captcha_output': 'invalid-control'}
                                if job['case'] == 'geetest-v4' else 'invalid-control')
                else:
                    stage = 'provider_solve'
                    solver = solver_for(job['provider'], job['case'], spec, result, save)
                    started = time.monotonic()
                    try:
                        solution = solve(solver, job['provider'], job['case'], spec, image_bytes)
                    finally:
                        result['provider_elapsed_seconds'] = round(time.monotonic() - started, 3)
                    valid = bool(solution) and isinstance(solution, (str, dict))
                    result['solution_delivered'] = valid
                    if not valid:
                        raise ValueError('Provider returned no solution')
                    result['solution_length'] = len(solution) if isinstance(solution, str) else None
                    if isinstance(solution, dict):
                        result['solution_fields'] = sorted(k for k in solution if k in
                            ('captcha_id', 'lot_number', 'pass_token', 'gen_time', 'captcha_output'))
                    save()
                stage = 'verification'
                if job['case'] == 'image-text':
                    result['ground_truth_match'] = (isinstance(solution, str)
                                                   and solution.strip().upper() == fixture['answer'])
                    result['outcome'] = 'correct_text' if result['ground_truth_match'] else 'wrong_text'
                else:
                    result.update(verify_solution(page, job['case'], solution))
                    result['outcome'] = ('token_delivered_unverified' if job['case'] == 'turnstile'
                                         else 'accepted' if result['server_accepted'] else 'rejected')
                    save()  # Preserve primary acceptance before optional replay/receipt work.
                    # Only JSON-verifier cases can replay without altering page state.
                    if not control and job['trial'] == 1 and result['server_accepted'] and job['case'] in ('recaptcha-v3', 'geetest-v4'):
                        try:
                            result['immediate_replay'] = verify_solution(page, job['case'], solution)
                        except Exception as exc:
                            result['immediate_replay'] = {'error_class': type(exc).__name__, 'server_accepted': None}
                if control:
                    result['control_assertion_passed'] = (result.get('rejection_observed') is True
                        and result.get('server_accepted') is False) if job['case'] != 'image-text' else not result['ground_truth_match']
                    if job['case'] == 'turnstile':
                        result['control_assertion_passed'] = None
                        result['outcome'] = 'fixture_inspected_no_server_verifier'
                result['workflow_elapsed_seconds'] = round(time.monotonic() - start, 3)
                # The invisible demo echoes the token in overflowing <pre> text;
                # a bounding-box mask cannot safely cover it. Keep JSON only.
                if job['trial'] == 1 and job['case'] == 'recaptcha-invisible':
                    result['screenshot_omitted_reason'] = 'demo-echoes-token-in-overflowing-pre'
                if job['trial'] == 1 and job['case'] == 'recaptcha-v2':
                    directory = path.parent / 'screenshots'
                    directory.mkdir(exist_ok=True)
                    try:
                        page.screenshot(path=str(directory / (job['id'] + '.png')),
                            mask=[page.locator('pre, code, textarea, input, .token')], timeout=5000)
                        result['screenshot'] = 'screenshots/' + job['id'] + '.png'
                    except Exception as exc:
                        result['screenshot_error'] = type(exc).__name__
            finally:
                browser.close()
    except Exception as exc:
        result.update(outcome='error', error_stage=stage, **safe_error(exc, solver))
    finally:
        # Run receipt lookup even after a rejected token; never repeat a solve.
        if solver is not None and result['paid_tasks_created']:
            extra_cost_receipt(solver, job['provider'], result)
        result['elapsed_seconds'] = round(time.monotonic() - start, 3)
        save()
    return result


def run_one(job, output, semaphore=None):
    path = output / (job['id'] + '.json')
    if path.exists():
        return json.loads(path.read_text())
    with semaphore or nullcontext():
        command = [sys.executable, str(Path(__file__).resolve()), '--live', '--job', job['id'], '--output', str(output)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            process.communicate(timeout=PROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            record = json.loads(path.read_text()) if path.exists() else {**job, 'paid_tasks_created': 0, 'task_creation_uncertain': True}
            record['execution_outcome'] = 'process_timeout'
            if record.get('outcome') == 'started':
                record['outcome'] = 'process_timeout'
            write_record(path, record)
        if not path.exists():
            write_record(path, {**job, 'outcome': 'child_failed_before_record', 'paid_tasks_created': 0,
                                'task_creation_uncertain': True})
        result = json.loads(path.read_text())
        if result.get('outcome') == 'started':
            result['outcome'] = 'child_interrupted'
            write_record(path, result)
        # Raw stderr can contain token-bearing request URLs; never print it.
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--controls', action='store_true')
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument('--output', type=Path, default=Path('run_output/broad'))
    parser.add_argument('--job', choices=[r['id'] for r in make_schedule(10)])
    args = parser.parse_args()
    rows = make_schedule(args.rounds)
    if not args.live and not args.controls:
        print(json.dumps({'max_tasks': len(rows), 'cases': CASES, 'jobs': rows}, indent=2))
        return 0
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.controls:
        failures = 0
        for case in CASES:
            job = {'id': case + '-negative-control', 'case': case, 'provider': 'none', 'trial': 1}
            path = args.output / (job['id'] + '.json')
            record = json.loads(path.read_text()) if path.exists() else execute_job(job, path, control=True)
            print(json.dumps(record), flush=True)
            failures += record.get('outcome') == 'error' or record.get('control_assertion_passed') is False
        return 1 if failures else 0
    if args.job:
        job = next(r for r in make_schedule(10) if r['id'] == args.job)
        record = execute_job(job, args.output / (job['id'] + '.json'))
        return 1 if record['outcome'] in ('error', 'unavailable') else 0
    initial = {}
    for provider in ENV:
        initial[provider] = balance(provider)
        if initial[provider] <= 0:
            raise SystemExit('No positive provider balance; no tasks started')
    gate = {provider: threading.Semaphore(2) for provider in ENV}
    plan = {'planned_tasks': len(rows), 'rounds': args.rounds, 'max_concurrency': args.workers,
            'max_concurrency_per_provider': 2, 'cases': CASES, 'jobs': rows,
            'task_creation_retries': 0, 'process_timeout_seconds': PROCESS_TIMEOUT,
            'created_at': datetime.now(timezone.utc).isoformat()}
    write_record(args.output / 'plan.json', plan)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_one, job, args.output, gate[job['provider']]) for job in rows]
        for future in as_completed(futures):
            record = future.result()
            print(json.dumps({k: record.get(k) for k in ('id', 'outcome', 'paid_tasks_created',
                'provider_elapsed_seconds', 'server_accepted', 'ground_truth_match', 'provider_error_code')}), flush=True)
    # Balance deltas are aggregate observations, not per-task prices. Concurrent
    # account activity/refunds can affect them. Do not persist actual balances.
    spending = {}
    for provider in ENV:
        try:
            spending[provider] = round(initial[provider] - balance(provider), 6)
        except Exception:
            spending[provider] = None
    receipt = {'started_at': plan['created_at'], 'finished_at': datetime.now(timezone.utc).isoformat(),
               'balance_decrease_usd': spending,
               'caveat': 'This invocation only; concurrent account activity or refunds can affect deltas.'}
    receipt_path = args.output / ('spending-' + str(time.time_ns()) + '.json')
    write_record(receipt_path, receipt)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
