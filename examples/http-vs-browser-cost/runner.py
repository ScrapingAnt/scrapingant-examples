"""Local by default. Live consumes credits only with explicit bounded opt-in.

This CLI flag is a guard, not authorization: obtain the owner's approval first.
Never import an SDK with hidden retry behavior or print raw transport exceptions.
"""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import signal
import threading
import time
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from contract import ARMS, TARGETS, api_parameters, assess, reserve, schedule, summary

ROOT = Path(__file__).resolve().parent
API = 'https://api.scrapingant.com/v2/general'


def digest(body):
    return hashlib.sha256(body).hexdigest()


def receipt_is_expected(status, actual, reserved):
    return type(actual) is int and (actual == reserved or (status is not None and status >= 400 and actual == 0))


def validate_options(live, repeats, approved_credits):
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError('Repeats must be 1–10')
    required = repeats * 22
    if live and approved_credits != required:
        raise ValueError(f'Live requires prior owner approval and --approved-credits {required}')
    if not live and approved_credits is not None:
        raise ValueError('A paid budget is not used by a local run')
    return required if live else 0


class FixtureHandler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        return 'text/html; charset=utf-8' if str(path).endswith('.html') else super().guess_type(path)

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def fixtures():
    handler = partial(FixtureHandler, directory=str(ROOT/'fixtures'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown(); server.server_close(); thread.join()


def inspect_public(out):
    """Two read-only checks of fixed owned fixtures; never accesses an API key."""
    receipts = []
    with requests.Session() as session:
        session.trust_env = False
        for target, config in TARGETS.items():
            response = session.get(config['url'], timeout=(5, 10), allow_redirects=False)
            local = (ROOT/'fixtures'/config['file']).read_bytes()
            receipt = dict(target=target, url=config['url'], status=response.status_code,
                           source_sha256=digest(local), public_sha256=digest(response.content),
                           byte_equal=response.content == local)
            receipts.append(receipt)
            time.sleep(1)
    result = dict(checked_at=datetime.now(timezone.utc).isoformat(), checks=receipts,
                  ownership='ScrapingAnt/scrapingant-examples tracked fixtures and fixtures/README.md; existing GitHub Pages publication')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    if any(r['status'] != 200 or not r['byte_equal'] for r in receipts):
        raise ValueError('Public fixture differs from source; review before any API call')
    return result


def deadline_handler(signum, frame):
    raise TimeoutError('Caller wall deadline exceeded')


@contextlib.contextmanager
def wall_deadline(seconds):
    if not hasattr(signal, 'setitimer'):
        raise RuntimeError('This harness requires a POSIX caller deadline')
    previous = signal.signal(signal.SIGALRM, deadline_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def acquire(arm, target, url, sessions, browser, key, out, index):
    started = time.perf_counter()
    row = dict(arm=arm, target=target, status=None, target_status=None, credits=None,
               valid=False, valid_records=0, records=[], ready=False, outcome='exception',
               retries=0, body_file=f'body-{index:03d}.html')
    body = b''
    page = None
    context = None
    try:
        with wall_deadline(15 if arm.startswith('api_') else 10):
            if arm == 'playwright':
                context = browser.new_context()
                page = context.new_page()
                remaining = lambda: max(1, (10 - (time.perf_counter()-started))*1000)
                response = page.goto(url, wait_until='domcontentloaded', timeout=remaining())
                row['status'] = row['target_status'] = response.status if response else None
                if row['status'] == 200:
                    page.wait_for_selector(TARGETS[target]['selector'], state='attached', timeout=remaining())
                body = page.content().encode('utf-8')
            else:
                session = sessions[arm]
                kwargs = dict(timeout=(5, 10), allow_redirects=False)
                if arm.startswith('api_'):
                    kwargs.update(params=api_parameters(target, arm, url), headers={'x-api-key': key})
                    response = session.get(API, **kwargs)
                    row['status'] = response.status_code
                    target_header = response.headers.get('Ant-page-status-code')
                    credit_header = response.headers.get('Ant-credits-cost')
                    row['target_status'] = int(target_header) if target_header and target_header.isdecimal() else None
                    row['credits'] = int(credit_header) if credit_header and credit_header.isdecimal() else None
                else:
                    response = session.get(url, **kwargs)
                    row['status'] = row['target_status'] = response.status_code
                body = response.content
        remaining_validation = 15 - (time.perf_counter()-started)
        if remaining_validation <= 0:
            raise TimeoutError('Caller wall deadline exceeded')
        with wall_deadline(remaining_validation):
            row.update(assess(target, body.decode('utf-8'), row['status'], row['target_status']))
    except BaseException as exc:
        row.update(valid=False, valid_records=0)
        row['outcome'] = ('aborted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else
                          'timeout' if isinstance(exc, (TimeoutError, requests.Timeout)) or type(exc).__name__ == 'TimeoutError' else 'exception')
        row['exception_class'] = type(exc).__name__
    finally:
        row['elapsed_ms'] = (time.perf_counter()-started)*1000
        # Cleanup is deliberately outside timed acquisition/validation.
        if context:
            try:
                context.close()
            except BaseException as exc:
                row['cleanup_exception_class'] = type(exc).__name__
    (out/row['body_file']).write_bytes(body)
    row['body_sha256'] = digest(body)
    return row


def replay(path):
    report = json.loads(path.read_text())
    if report.get('mode') not in ('local', 'live') or report.get('seed') != 607:
        raise ValueError('Invalid declared mode or seed')
    validate_options(report['mode'] == 'live', report.get('repeats'), report.get('approved_credit_ceiling') if report['mode'] == 'live' else None)
    declared_arms = list(ARMS) if report['mode'] == 'live' else ['requests', 'playwright']
    canonical_plan = schedule(declared_arms, report['repeats'], report['seed'])
    if [tuple(item) for item in report['plan']] != canonical_plan:
        raise ValueError('Stored plan does not match declared run')
    identities = [(r['round'], r['target'], r['arm']) for r in report['rows']]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate attempts')
    expected = [tuple(item) for item in report['plan']]
    if report['complete'] and identities != expected:
        raise ValueError('Missing/reordered attempts')
    if not report['complete'] and identities != expected[:len(identities)]:
        raise ValueError('Invalid partial-run prefix')
    if report.get('api_calls') != sum(r['arm'].startswith('api_') for r in report['rows']):
        raise ValueError('API attempt count mismatch')
    if report.get('actual_credits_receipted') != sum(r['credits'] for r in report['rows'] if r['arm'].startswith('api_') and r['credits'] is not None):
        raise ValueError('Receipted credit total mismatch')
    for target, config in report.get('fixtures', {}).items():
        if config['sha256'] != digest((ROOT/'fixtures'/TARGETS[target]['file']).read_bytes()):
            raise ValueError('Fixture source hash mismatch')
    for filename, expected_hash in report.get('source_sha256', {}).items():
        if filename not in ('runner.py', 'contract.py', 'requirements.txt') or digest((ROOT/filename).read_bytes()) != expected_hash:
            raise ValueError('Harness source hash mismatch; replay with recorded source revision')
    for row in report['rows']:
        if Path(row['body_file']).name != row['body_file']:
            raise ValueError('Body path must remain inside capture directory')
        body = (path.parent/row['body_file']).read_bytes()
        if digest(body) != row['body_sha256']:
            raise ValueError('Body hash mismatch')
        if 'exception_class' not in row:
            result = assess(row['target'], body.decode('utf-8'), row['status'], row['target_status'])
            if any(row[field] != value for field, value in result.items()):
                raise ValueError('Capture assessment mismatch')
        elif row['valid'] or row['valid_records']:
            raise ValueError('Exception cannot be valid')
    computed = summary(report['rows'])
    if report.get('summary') is not None and report['summary'] != computed:
        raise ValueError('Summary mismatch')
    return computed


def run(args):
    ceiling = validate_options(args.live, args.repeats, args.approved_credits)
    if args.live:
        key = os.environ.get('SCRAPINGANT_API_KEY')
        if not key:
            raise ValueError('Set SCRAPINGANT_API_KEY in the environment; do not put it in commands')
    else:
        key = None
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    if args.live:
        inspect_public(out/'fixture-check.json')
    arms = list(ARMS) if args.live else ['requests', 'playwright']
    report = dict(tested_at=datetime.now(timezone.utc).isoformat(), mode='live' if args.live else 'local',
                  seed=607, repeats=args.repeats, plan=schedule(arms, args.repeats, 607), rows=[], complete=False,
                  approved_credit_ceiling=ceiling, api_calls=0, actual_credits_receipted=0,
                  environment=dict(python=platform.python_version(), os=platform.platform(), architecture=platform.machine(),
                                   timezone=time.tzname, client_region='not supplied',
                                   dependencies={p: importlib.metadata.version(p) for p in ('requests', 'playwright', 'beautifulsoup4')}),
                  fixtures={target: dict(url=config['url'], sha256=digest((ROOT/'fixtures'/config['file']).read_bytes())) for target, config in TARGETS.items()},
                  timing=dict(acquisition_readiness_seconds=10, caller_wall_seconds=15, latency='acquisition through validation; excludes browser launch/context cleanup',
                              requests='connect=5/read=10 plus caller wall deadline', browser_reuse='one browser; fresh context per attempt',
                              api_worker_version='unobserved', api_worker_reuse='unobserved'),
                  unrun_arms=[] if args.live else ['api_raw', 'api_rendered'])
    report['source_sha256'] = {filename: digest((ROOT/filename).read_bytes()) for filename in ('runner.py', 'contract.py', 'requirements.txt')}
    def save():
        temporary = out/'report.json.tmp'
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        temporary.replace(out/'report.json')
    with contextlib.ExitStack() as stack:
        origin = None if args.live else stack.enter_context(fixtures())
        sessions = {}
        for arm in arms:
            if arm != 'playwright':
                sessions[arm] = stack.enter_context(requests.Session())
                sessions[arm].trust_env = False
        pw = stack.enter_context(sync_playwright())
        started = time.perf_counter(); browser = pw.chromium.launch(headless=True, chromium_sandbox=True)
        report['browser_launch_ms'] = (time.perf_counter()-started)*1000
        report['environment']['chromium'] = browser.version
        stack.callback(browser.close)
        save()
        for index, (round_id, target, arm) in enumerate(report['plan']):
            if args.live:
                time.sleep(1)
            expected_credit = reserve(ceiling, report['actual_credits_receipted'], arm) if arm.startswith('api_') else None
            url = TARGETS[target]['url'] if args.live else origin+'/'+TARGETS[target]['file']
            # Durable intent before acquisition: a hard stop cannot hide potential billing.
            pending = dict(arm=arm, target=target, round=round_id, status=None, target_status=None,
                           credits=None, valid=False, valid_records=0, records=[], ready=False,
                           outcome='unfinished', exception_class='UnfinishedAttempt', retries=0,
                           elapsed_ms=None, body_file=f'pending-{index:03d}.html', body_sha256=digest(b''))
            (out/pending['body_file']).write_bytes(b'')
            report['rows'].append(pending)
            if expected_credit is not None:
                report['api_calls'] += 1
            save()
            row = acquire(arm, target, url, sessions, browser, key, out, index)
            row['round'] = round_id
            report['rows'][-1] = row
            if expected_credit is not None:
                if row['credits'] is not None:
                    report['actual_credits_receipted'] += row['credits']
                if not receipt_is_expected(row['status'], row['credits'], expected_credit):
                    report['stop_reason'] = 'Missing/unexpected receipt; billing reconciliation required before further calls'
                    report['summary'] = summary(report['rows']); save()
                    raise ValueError(report['stop_reason'])
            if row['outcome'] == 'aborted' or 'cleanup_exception_class' in row:
                report['stop_reason'] = 'Interrupted attempt or browser cleanup failure; resume only after review'
                report['summary'] = summary(report['rows']); save()
                raise ValueError(report['stop_reason'])
            save()
        report['complete'] = True
        report['summary'] = summary(report['rows']); save()
    replay(out/'report.json')
    print(json.dumps(dict(mode=report['mode'], attempts=len(report['rows']), api_calls=report['api_calls'],
                          actual_credits_receipted=report['actual_credits_receipted'], summary=report['summary']), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--approved-credits', type=int)
    parser.add_argument('--repeats', type=int, default=10)
    parser.add_argument('--out', default='run_output/local')
    parser.add_argument('--inspect-public', action='store_true')
    parser.add_argument('--replay', type=Path)
    args = parser.parse_args()
    try:
        if args.replay:
            print(json.dumps(replay(args.replay), indent=2))
        elif args.inspect_public:
            if args.live or args.approved_credits is not None:
                raise ValueError('Inspection is read-only and cannot be combined with paid options')
            out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
            print(json.dumps(inspect_public(out/'fixture-check.json'), indent=2))
        else:
            run(args)
    except Exception as exc:
        # Raw exception strings can include requests/credentials; keep them out of output.
        print(json.dumps({'error_class': type(exc).__name__, 'result': 'stopped; inspect preserved report or option requirements'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
