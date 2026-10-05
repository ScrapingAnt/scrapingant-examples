"""Closed fixed-manifest one-start capture. No deletion or account settings routes.

Activate only one exact cell after a durable private reservation, dispatch once,
then immediately close. No retry of an ambiguous start. Raw success responses
are wrapped without rewriting their bytes and authenticated-encrypted separately.
"""
import argparse
import storage_policy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib, json, os, re, sys
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

ACTIVE_CELL = 'breadth-r2-playwright'
PLAN_SHA256 = 'c6de8f32e1e076795eecd7f7c1c61d8cfc85d0d0fb64bba7ead1f83c44bf2831'
ROOT = Path(__file__).resolve().parent
API = 'https://api.apify.com/v2'
# Changing this reviewed allowlist requires a fresh scope decision. Guard
# activation alone cannot admit the deferred Article Actor or a disguised ID.
ALLOWED_ACTORS = {
    'apify/web-scraper': 'moJRLRc85AitArpNN',
    'apify/playwright-scraper': 'MpRbnNmVAoj5RC1Ma',
    'apify/puppeteer-scraper': 'YJCnS9qogi9XxDgLB',
    'apify/rag-web-browser': '3ox4R101TgZz67sLr',
    'apify/google-search-scraper': 'nFJndFXA5zjCTuudP',
    'apify/ai-web-scraper': 'paOtbjvyUiNsr1Qms',
    'apify/google-trends-scraper': 'DyNQEYDj9awfGQf9A',
}
DEFERRED_ACTOR_IDS = ('hy5TYiCBwQ9o8uRKG',)

SOURCE_HASHES = {
    'apify-study/runner.py': 'd7e11778845fb95a95d99a0671a9023cef9304735edf965b84487aafcaf61bfd',
    'apify-study/billing_projection.py': 'f54f05292bc68e9ee3f2bdd8de0b537a5c270069e996b393da620d5541329498',
    'apify-sustained/evidence_transport.py': 'f5c3a9ffdb57add4a20121b0369da7223703a57b49cdbaf2a29015b808d2cbb3',
    'apify-sustained/recipient.txt': '7da784c7f41ff4e52cce510c67943403dab25843a997bd805d6c4b4c7415ddac',
}
CATEGORIES = ('guard_closed', 'opt_in_required', 'invalid_cell', 'source_mismatch',
    'token_unavailable', 'route_rejected', 'deadline_exceeded', 'http_error',
    'redirect_refused', 'connection_error', 'unexpected_status', 'response_too_large',
    'invalid_json', 'scope_mismatch', 'terminal_unknown', 'persistence_failed',
    'meter_unavailable', 'budget_exceeded', 'storage_policy', 'settling_failed')
MAX_TOTAL_CAPTURE_BYTES = 48 * 1048576

class Stopped(Exception):
    def __init__(self, category, status=None):
        self.category = category if category in CATEGORIES else 'scope_mismatch'
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        super().__init__('bounded_study_stopped')
    def safe(self): return {'category': self.category, 'http_status': self.status}

def sha(blob): return hashlib.sha256(blob).hexdigest()
def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
def guard(cell):
    if ACTIVE_CELL is None: raise Stopped('guard_closed')
    if type(cell) is not str or cell != ACTIVE_CELL: raise Stopped('invalid_cell')

def validate_cell_actor(cell):
    if (not isinstance(cell, dict) or cell.get('actor_id') in DEFERRED_ACTOR_IDS
            or cell.get('actor') not in ALLOWED_ACTORS
            or cell.get('actor_id') != ALLOWED_ACTORS[cell['actor']]):
        raise Stopped('invalid_cell')

def strict(blob):
    def pairs(rows):
        out = {}
        for k, v in rows:
            if k in out: raise ValueError()
            out[k] = v
        return out
    def reject(_): raise ValueError()
    def fractional(text):
        n = Decimal(text)
        if not n.is_finite() or abs(n) > Decimal('1e18') or len(text) > 96: raise ValueError()
        return n
    try: return json.loads(blob.decode('utf-8'), object_pairs_hook=pairs,
                           parse_float=fractional, parse_constant=reject)
    except (ValueError, UnicodeError, RecursionError): raise Stopped('invalid_json') from None

def load_plan():
    p = ROOT / 'breadth-plan.json'
    if p.is_symlink() or not p.is_file() or not 1 <= p.stat().st_size <= 32 * 1048576:
        raise Stopped('source_mismatch')
    blob = p.read_bytes()
    if sha(blob) != PLAN_SHA256: raise Stopped('source_mismatch')
    plan = strict(blob)
    if not isinstance(plan, dict) or not isinstance(plan.get('cells'), list):
        raise Stopped('invalid_cell')
    for cell in plan['cells']: validate_cell_actor(cell)
    return plan

def load_sources():
    for name, expected in SOURCE_HASHES.items():
        p = ROOT.parent / name
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 262144 or sha(p.read_bytes()) != expected:
            raise Stopped('source_mismatch')
    # Only reviewed pure validators and authenticated crypto are used. Their
    # historical execution guards and transports are never activated or called.
    import importlib.util
    p = ROOT.parent / 'apify-study/billing_projection.py'
    spec = importlib.util.spec_from_file_location('billing_projection', p)
    billing = importlib.util.module_from_spec(spec)
    sys.modules['billing_projection'] = billing
    spec.loader.exec_module(billing)
    p = ROOT.parent / 'apify-study/runner.py'
    spec = importlib.util.spec_from_file_location('expanded_validators', p)
    runner = importlib.util.module_from_spec(spec)
    sys.modules['expanded_validators'] = runner
    spec.loader.exec_module(runner)
    p = ROOT.parent / 'apify-sustained/evidence_transport.py'
    spec = importlib.util.spec_from_file_location('expanded_crypto', p)
    crypto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crypto)
    return runner, crypto

def validate_meter_budget(meter, cell):
    value = meter.get('usage_total_usd')
    if type(value) is not str:
        raise Stopped('meter_unavailable')
    try:
        n = Decimal(value)
        if not n.is_finite() or n < 0: raise ValueError()
    except (ValueError, ArithmeticError): raise Stopped('meter_unavailable') from None
    if n > Decimal(cell['options']['maxTotalChargeUsd']):
        raise Stopped('budget_exceeded')

def project_run_meter(validators, data, cell):
    meter = validators.run_receipt(data, SimpleNamespace(spec=cell))
    # The legacy pure projection represents integral native amounts as integers.
    # Normalize only this monetary field to exact decimal text, preserving zero.
    if type(meter.get('usage_total_usd')) is int:
        meter['usage_total_usd'] = str(meter['usage_total_usd'])
    return meter

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

class Transport:
    def __init__(self, cell, token, *, opener=None, clock=monotonic):
        guard(cell['cell_id'])
        validate_cell_actor(cell)
        if type(token) is not str or not 1 <= len(token) <= 512 or any(ord(x) < 33 or ord(x) > 126 for x in token):
            raise Stopped('token_unavailable')
        self.cell, self._token, self.clock = cell, token, clock
        self.deadline, self.counts, self.identity, self.failed = clock() + 6300, {}, None, False
        self._storage_breach = False
        self._open = opener if opener is not None else build_opener(NoRedirect()).open
    def __repr__(self): return '<fixed one-start private capture transport>'
    def bind(self, identity):
        if self.identity is not None: raise Stopped('scope_mismatch')
        for key in ('id', 'userId', 'actId', 'defaultDatasetId', 'defaultKeyValueStoreId', 'defaultRequestQueueId'):
            if type(identity.get(key)) is not str or re.fullmatch(r'[A-Za-z0-9]{17}', identity[key]) is None:
                raise Stopped('scope_mismatch')
        if identity['actId'] != self.cell['actor_id']: raise Stopped('scope_mismatch')
        self.identity = dict(identity)
    def permit_storage_abort(self, reason):
        guard(self.cell['cell_id'])
        if self.identity is None or self.failed or self.identity.get('status') not in ('READY','RUNNING','TIMING-OUT','ABORTING'):
            raise Stopped('route_rejected')
        if reason not in ('extra_storage_alias','malformed_storage_aliases','named_state_log'):
            raise Stopped('route_rejected')
        self._storage_breach = True
    def route(self, operation):
        validate_cell_actor(self.cell)
        if operation == 'start':
            if self.identity is not None or self.counts: raise Stopped('route_rejected')
            o = self.cell['options']
            query = urlencode({'build': o['build'], 'memory': o['memoryMbytes'], 'timeout': o['timeoutSecs'],
                'maxTotalChargeUsd': o['maxTotalChargeUsd'], 'restartOnError': 'false',
                'forcePermissionLevel': 'LIMITED_PERMISSIONS'})
            return 'POST', f"{API}/acts/{self.cell['actor_id']}/runs?{query}", 201, 30, 131072, 1
        if self.identity is None: raise Stopped('route_rejected')
        identity = self.identity
        if operation == 'abort':
            if not self._storage_breach: raise Stopped('route_rejected')
            return 'POST', f"{API}/actor-runs/{identity['id']}/abort?gracefully=false", 200, 15, 131072, 1
        if operation == 'poll':
            return 'GET', f"{API}/actor-runs/{identity['id']}?waitForFinish=60", 200, 65, 131072, 95
        if operation == 'meter':
            return 'GET', f"{API}/actor-runs/{identity['id']}", 200, 15, 131072, 1
        if operation == 'export':
            q = urlencode({'format': 'json', 'clean': 'false', 'skipHidden': 'false', 'skipEmpty': 'false',
                           'limit': self.cell['assigned_case_count'] + 1})
            return 'GET', f"{API}/datasets/{identity['defaultDatasetId']}/items?{q}", 200, 30, 4194304, 1
        if operation == 'log':
            return 'GET', f"{API}/actor-runs/{identity['id']}/log", 200, 30, 2097152, 1
        stores = {'dataset': ('datasets', 'defaultDatasetId'), 'kv': ('key-value-stores', 'defaultKeyValueStoreId'),
                  'queue': ('request-queues', 'defaultRequestQueueId')}
        if operation in stores:
            route, key = stores[operation]
            return 'GET', f"{API}/{route}/{identity[key]}", 200, 15, 131072, 1
        raise Stopped('route_rejected')
    def request(self, operation):
        guard(self.cell['cell_id'])
        if self.failed: raise Stopped('route_rejected')
        method, url, expected, seconds, limit, cap = self.route(operation)
        if self.counts.get(operation, 0) >= cap: raise Stopped('route_rejected')
        remaining = self.deadline - self.clock()
        if remaining < seconds: raise Stopped('deadline_exceeded')
        self.counts[operation] = self.counts.get(operation, 0) + 1
        end = min(self.deadline, self.clock() + seconds)
        request = Request(url, data=canonical(self.cell['input']) if operation == 'start' else None, method=method,
            headers={'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json',
                     'Accept-Encoding': 'identity', 'Accept': 'text/plain' if operation == 'log' else 'application/json'})
        response = None
        try:
            response = self._open(request, timeout=seconds)
            if response.status != expected: raise Stopped('unexpected_status', response.status)
            raw = bytearray()
            while True:
                if self.clock() >= end: raise Stopped('deadline_exceeded')
                chunk = response.read1(min(8192, limit + 1 - len(raw)))
                if self.clock() > end: raise Stopped('deadline_exceeded')
                if not chunk: break
                raw.extend(chunk)
                if len(raw) > limit: raise Stopped('response_too_large')
            body = bytes(raw)
            try: body.decode('utf-8')
            except UnicodeError: raise Stopped('invalid_json') from None
            return body
        except HTTPError as exc:
            status = exc.code
            exc.close()  # Never persist or log raw provider errors.
            self.failed = True
            raise Stopped('redirect_refused' if 300 <= status <= 399 else 'http_error', status) from None
        except Stopped:
            self.failed = True
            raise
        except (URLError, OSError):
            self.failed = True
            raise Stopped('connection_error') from None
        finally:
            if response is not None: response.close()

# Official dataset item counters can lag writes by up to five seconds.
# One bounded six-second settle precedes the already allowed single metadata GET;
# it adds no request, retry or relaxed count comparison.
METADATA_SETTLE_SECONDS = 6

def settle_metadata(transport, *, sleeper=sleep):
    guard(transport.cell['cell_id'])
    if transport.failed or transport.counts.get('export') != 1 or transport.counts.get('dataset', 0):
        raise Stopped('settling_failed')
    began = transport.clock()
    if transport.deadline - began < METADATA_SETTLE_SECONDS + 15:
        raise Stopped('deadline_exceeded')
    try: sleeper(METADATA_SETTLE_SECONDS)
    except Exception: raise Stopped('settling_failed') from None
    ended = transport.clock()
    if ended < began + METADATA_SETTLE_SECONDS:
        raise Stopped('settling_failed')
    if transport.deadline - ended < 15:
        raise Stopped('deadline_exceeded')
    guard(transport.cell['cell_id'])
    return METADATA_SETTLE_SECONDS

def execute(cell_id, *, opt_in=False, environ=None, clock=monotonic):
    guard(cell_id)
    if opt_in is not True: raise Stopped('opt_in_required')
    plan = load_plan()
    cells = [c for c in plan['cells'] if c['cell_id'] == cell_id]
    if len(cells) != 1: raise Stopped('invalid_cell')
    cell = cells[0]
    validate_cell_actor(cell)
    runner, crypto = load_sources()
    env = os.environ if environ is None else environ
    temp = env.get('RUNNER_TEMP')
    if type(temp) is not str or not Path(temp).is_absolute(): raise Stopped('persistence_failed')
    output = ROOT / 'capture'
    if output.exists() or output.is_symlink(): raise Stopped('persistence_failed')
    output.mkdir(mode=0o700)
    binary = Path(temp) / 'age-v1.3.2/age/age'
    recipient = (ROOT.parent / 'apify-sustained/recipient.txt').read_text().strip()
    preflight = output / 'preflight.age'
    crypto.encrypt_capture(b'{"synthetic_preflight":true,"provider_starts":0}', preflight, binary, recipient)
    preflight.unlink()
    transport = Transport(cell, env.get('APIFY_TOKEN'), clock=clock)
    files, identity, diagnostic, meter = {}, None, None, None
    started = datetime.now(timezone.utc)
    settled_seconds = None
    def read(operation, label):
        raw = transport.request(operation)
        wrapped = canonical({'schema_version': 1, 'operation': operation, 'raw_sha256': sha(raw),
                             'raw_bytes': len(raw), 'response_body_utf8': raw.decode('utf-8')})
        # Keep the whole encrypted upload within the separately reviewed archive
        # envelope. No Actor retry/start follows a capture-envelope failure.
        used = sum((output / name).stat().st_size for name in files)
        if used + len(wrapped) + 65536 > MAX_TOTAL_CAPTURE_BYTES:
            raise Stopped('persistence_failed')
        receipt = crypto.encrypt_capture(wrapped, output / (label + '.age'), binary, recipient)
        files[label + '.age'] = {**receipt, 'operation': operation, 'raw_sha256': sha(raw), 'raw_bytes': len(raw)}
        return raw
    try:
        raw = read('start', 'start')
        value = strict(raw)
        identity = runner.validate_run(value.get('data'), SimpleNamespace(spec=cell))
        age = (datetime.now(timezone.utc) - runner.timestamp(identity['startedAt'])).total_seconds()
        if not -5 <= age <= 300: raise Stopped('scope_mismatch')
        transport.bind(identity)
        storage_policy.aliases(value['data'])
        value = value['data']
        for n in range(95):
            if value['status'] in runner.TERMINAL: break
            value = strict(read('poll', f'poll-{n:02d}')).get('data')
            identity = runner.validate_run(value, SimpleNamespace(spec=cell), identity)
            storage_policy.aliases(value)
        if value['status'] not in runner.TERMINAL: raise Stopped('terminal_unknown')
        if identity['build'] != cell['build']: raise Stopped('scope_mismatch')
        # Preserve the raw export, including native failure rows and metadata.
        raw = read('export', 'raw')
        rows = strict(raw)
        if not isinstance(rows, list) or len(rows) > cell['assigned_case_count']: raise Stopped('scope_mismatch')
        settled_seconds = settle_metadata(transport)
        for kind in ('dataset', 'kv', 'queue'):
            meta = strict(read(kind, kind)).get('data')
            runner.validate_metadata(meta, kind, identity)
            if kind == 'dataset' and meta.get('itemCount') != len(rows): raise Stopped('scope_mismatch')
        log = read('log', 'log').decode('utf-8')
        storage_policy.require_log_scope(cell, log)
        value = strict(read('meter', 'meter')).get('data')
        runner.validate_run(value, SimpleNamespace(spec=cell), identity, identity['status'])
        storage_policy.aliases(value)
        meter = project_run_meter(runner, value, cell)
        validate_meter_budget(meter, cell)
    except storage_policy.PolicyBreach as exc:
        diagnostic = Stopped('storage_policy').safe()
        if identity is not None and identity['status'] not in runner.TERMINAL and not transport.failed:
            try:
                transport.permit_storage_abort(exc.reason)
                read('abort', 'abort')
            except Exception: pass  # Uncertain abort stays a stop; never retry or start again.
    except Stopped as exc: diagnostic = exc.safe()
    except Exception: diagnostic = Stopped('scope_mismatch').safe()
    manifest = {'schema_version': 1, 'cell_id': cell_id, 'plan_sha256': PLAN_SHA256,
        'native_input_sha256': cell['native_input_sha256'], 'identity': identity, 'files': files,
        'requests': transport.counts, 'start_attempts': transport.counts.get('start', 0), 'DELETEs': 0,
        'started_at_utc': started.isoformat(), 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'latest_run_meter': meter, 'metadata_settle_seconds': settled_seconds, 'diagnostic': diagnostic, 'complete': diagnostic is None,
        'invoice_finality': False, 'cleanup_authorized': False,
        'retained_run_cap_usd': cell['options']['maxTotalChargeUsd'],
        'retained_ancillary_reserve_usd': cell['ancillary_reserve_usd']}
    receipt = crypto.encrypt_capture(canonical(manifest), output / 'manifest.age', binary, recipient)
    public = {'schema_version': 1, 'cell_id': cell_id, 'plan_sha256': PLAN_SHA256, 'complete': manifest['complete'],
        'diagnostic': diagnostic, 'start_attempts': manifest['start_attempts'], 'DELETEs': 0,
        'request_counts': transport.counts, 'encrypted_files': len(files), **receipt}
    crypto.durable_write(output / 'capture-public.json', canonical(public))
    return public

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cell', required=True)
    p.add_argument('--execute', action='store_true')
    args = p.parse_args()
    if not args.execute:
        print(json.dumps({'mode': 'offline', 'provider_requests': 0, 'guard_closed': ACTIVE_CELL is None}))
        return 0
    try:
        result = execute(args.cell, opt_in=True)
        print(json.dumps(result, sort_keys=True))
        return 0 if result['complete'] else 1
    except Exception as exc:
        safe = exc.safe() if isinstance(exc, Stopped) else Stopped('persistence_failed').safe()
        print(json.dumps({'complete': False, 'diagnostic': safe, 'private_capture': 'unconfirmed'}))
        return 1

if __name__ == '__main__': raise SystemExit(main())
