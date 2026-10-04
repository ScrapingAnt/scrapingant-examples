"""Closed seven-GET recovery of one committed terminal Web run; no mutation.

Target identity arrives through GitHub's encrypted data-only secret entry.
Existing APIFY_TOKEN authenticates reads; existing age recipient protects bodies.
Count/cap failures remain failures while the remaining diagnostic reads complete.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode
from urllib.error import HTTPError
import copy, hashlib, json, os, re, sys, time
import controller

ROOT = Path(__file__).resolve().parent
RECOVERY_READY = False
SPEC_SHA256 = '4829bb2439460e3a9c36848ab5d9deeb57df99b4d0ad939214031d2c32de21b4'
STAGES = ('run', 'raw', 'dataset', 'kv', 'queue', 'log', 'meter')
MAX_GETS = 7
SMALL_LIMIT, RAW_LIMIT, LOG_LIMIT = 131072, 4194304, 8388608
WALL_SECONDS, ROUTE_SECONDS = 180, 20
TARGET_FIELDS = ('id', 'userId', 'actId', 'defaultDatasetId',
                 'defaultKeyValueStoreId', 'defaultRequestQueueId',
                 'startedAt', 'finishedAt', 'status', 'build')
CATEGORIES = ('guard_closed', 'opt_in_required', 'source_invalid', 'target_invalid',
              'preflight_failed', 'token_unavailable', 'route_invalid',
              'deadline_exceeded', 'access_denied', 'http_error', 'redirect_refused',
              'transport_error', 'body_limit', 'response_invalid', 'scope_mismatch',
              'encryption_failed')


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


class RecoveryError(Exception):
    def __init__(self, category, stage='preflight', status=None):
        self.category = category if category in CATEGORIES else 'transport_error'
        self.stage = stage if stage in STAGES + ('preflight', 'evidence') else 'preflight'
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        super().__init__('bounded_readonly_recovery_stopped')

    def safe(self):
        return {'category': self.category, 'stage': self.stage, 'http_status': self.status}


def guard():
    if RECOVERY_READY is not True:
        raise RecoveryError('guard_closed')


def strict(blob):
    try:
        return controller.strict(blob)
    except Exception:
        raise RecoveryError('response_invalid') from None


def load_reviewed():
    try:
        path = ROOT / 'recovery-scope.json'
        if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= 8192:
            raise ValueError()
        blob = path.read_bytes()
        if sha(blob) != SPEC_SHA256:
            raise ValueError()
        spec = strict(blob)
        if (type(spec['schema_version']) is not int or spec['schema_version'] != 1
                or spec['cell_id'] != 'breadth-r1-web' or spec['maximum_GETs'] != MAX_GETS
                or spec['expected_status'] != 'ABORTED'
                or spec['target_secret_name'] != 'APIFY_WEB_RECOVERY_TARGET'
                or controller.ACTIVE_CELL is not None):
            raise ValueError()
        expected_deps = {'apify-breadth-study/controller.py', 'apify-breadth-study/breadth-plan.json',
                         'apify-breadth-study/storage_policy.py', 'apify-study/runner.py',
                         'apify-study/billing_projection.py', 'apify-sustained/evidence_transport.py',
                         'apify-sustained/recipient.txt'}
        if set(spec['dependencies_sha256']) != expected_deps:
            raise ValueError()
        for name, digest in spec['dependencies_sha256'].items():
            p = ROOT.parent / name
            if p.is_symlink() or not p.is_file() or sha(p.read_bytes()) != digest:
                raise ValueError()
        cell = next(c for c in controller.load_plan()['cells'] if c['cell_id'] == spec['cell_id'])
        if (cell['actor'] != 'apify/web-scraper' or cell['assigned_case_count'] != spec['assigned_case_count']
                or cell['options']['maxTotalChargeUsd'] != spec['strict_run_cap_usd']):
            raise ValueError()
        validators, crypto = controller.load_sources()
        if any(getattr(validators, k) is not False for k in
               ('RUNNER_READY', 'GRAPH_READY', 'CONCURRENCY_READY')):
            raise ValueError()
        recipient = (ROOT.parent / 'apify-sustained/recipient.txt').read_text().strip()
        if re.fullmatch(r'age1[a-z0-9]{58}', recipient) is None:
            raise ValueError()
        return spec, cell, validators, crypto, recipient
    except Exception:
        raise RecoveryError('source_invalid') from None


def target_from_data(value, spec, validators, cell):
    try:
        if type(value) is not str or not 1 <= len(value.encode()) <= 8192:
            raise ValueError()
        blob = value.encode()
        if sha(blob) != spec['target_payload_sha256']:
            raise ValueError()
        target = strict(blob)
        if set(target) != set(TARGET_FIELDS) or target['status'] != spec['expected_status']:
            raise ValueError()
        for key in TARGET_FIELDS[:6]:
            if type(target[key]) is not str or re.fullmatch(r'[A-Za-z0-9]{17}', target[key]) is None:
                raise ValueError()
        if (target['actId'] != cell['actor_id'] or target['build'] != cell['build']
                or len({target[k] for k in TARGET_FIELDS[3:6]}) != 3
                or validators.timestamp(target['finishedAt']) < validators.timestamp(target['startedAt'])):
            raise ValueError()
        return target
    except Exception:
        raise RecoveryError('target_invalid') from None


def validate_run(blob, validators, cell, target, stage):
    try:
        body = strict(blob)
        data = body.get('data') if isinstance(body, dict) else None
        identity = validators.validate_run(data, SimpleNamespace(spec=cell),
                                           target, target['status'])
        if any(identity.get(k) != target[k] for k in TARGET_FIELDS):
            raise ValueError()
        controller.storage_policy.aliases(data)
        return data, identity
    except Exception:
        raise RecoveryError('scope_mismatch', stage, 200) from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Transport:
    def __init__(self, token, target, *, opener=None, clock=time.monotonic):
        guard()
        if (type(token) is not str or not 16 <= len(token) <= 512
                or re.fullmatch(r'[A-Za-z0-9_-]+', token) is None):
            raise RecoveryError('token_unavailable')
        self._token, self.target, self.clock = token, copy.deepcopy(target), clock
        self._open = opener or build_opener(NoRedirect()).open
        self.deadline, self.calls, self.failed = clock() + WALL_SECONDS, 0, False

    def __repr__(self):
        return '<bounded seven-GET read-only transport>'

    def route(self, stage):
        guard()
        if self.failed or self.calls >= MAX_GETS or stage != STAGES[self.calls]:
            raise RecoveryError('route_invalid', stage)
        t = self.target
        if stage in ('run', 'meter'):
            return 'https://api.apify.com/v2/actor-runs/' + t['id'], SMALL_LIMIT
        if stage == 'raw':
            query = urlencode({'format': 'json', 'offset': 0, 'limit': 3841, 'desc': 'false',
                               'clean': 'false', 'skipHidden': 'false', 'skipEmpty': 'false'})
            return 'https://api.apify.com/v2/datasets/' + t['defaultDatasetId'] + '/items?' + query, RAW_LIMIT
        if stage == 'log':
            return 'https://api.apify.com/v2/actor-runs/' + t['id'] + '/log?stream=false&raw=true', LOG_LIMIT
        route, field = {'dataset': ('datasets', 'defaultDatasetId'),
                        'kv': ('key-value-stores', 'defaultKeyValueStoreId'),
                        'queue': ('request-queues', 'defaultRequestQueueId')}[stage]
        return 'https://api.apify.com/v2/' + route + '/' + t[field], SMALL_LIMIT

    def get(self, stage):
        url, limit = self.route(stage)
        deadline = min(self.deadline, self.clock() + ROUTE_SECONDS)
        if self.clock() >= deadline:
            raise RecoveryError('deadline_exceeded', stage)
        self.calls += 1
        response, status = None, None
        try:
            request = Request(url, method='GET', headers={'Authorization': 'Bearer ' + self._token,
                'Accept': 'text/plain' if stage == 'log' else 'application/json', 'Accept-Encoding': 'identity'})
            response = self._open(request, timeout=max(.001, deadline - self.clock()))
            status = response.status
            if type(status) is not int or status != 200:
                raise RecoveryError('http_error', stage, status)
            ctype = response.getheader('Content-Type')
            expected = 'text/plain' if stage == 'log' else 'application/json'
            if (type(ctype) is not str or ctype.split(';', 1)[0].strip().lower() != expected
                    or response.getheader('Content-Encoding') not in (None, 'identity')):
                raise RecoveryError('response_invalid', stage, status)
            raw = bytearray()
            while True:
                remaining = deadline - self.clock()
                if remaining <= 0:
                    raise RecoveryError('deadline_exceeded', stage, status)
                sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
                if sock is not None:
                    sock.settimeout(max(.001, remaining))
                chunk = response.read1(min(65536, limit + 1 - len(raw)))
                if self.clock() >= deadline:
                    raise RecoveryError('deadline_exceeded', stage, status)
                if not isinstance(chunk, bytes):
                    raise RecoveryError('response_invalid', stage, status)
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > limit:
                    raise RecoveryError('body_limit', stage, status)
            headers = {name: response.getheader(name) for name in
                       ('Date', 'Content-Type', 'Content-Length', 'X-Apify-Pagination-Offset',
                        'X-Apify-Pagination-Limit', 'X-Apify-Pagination-Count',
                        'X-Apify-Pagination-Total', 'X-Apify-Pagination-Desc')}
            return bytes(raw), headers
        except HTTPError as exc:
            status = exc.code
            exc.close()
            self.failed = True
            raise RecoveryError('access_denied' if status in (401, 403) else
                                'redirect_refused' if 300 <= status < 400 else 'http_error', stage, status) from None
        except RecoveryError:
            self.failed = True
            raise
        except Exception:
            self.failed = True
            raise RecoveryError('deadline_exceeded' if self.clock() >= deadline else 'transport_error', stage, status) from None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass


def meter_gate(value, spec):
    amount = value.get('usage_total_usd')
    if type(amount) is not str:
        return {'state': 'unknown', 'strict_run_cap_passed': False, 'within_retained_allocation': None}
    number = Decimal(amount)
    return {'state': 'known', 'strict_run_cap_passed': number <= Decimal(spec['strict_run_cap_usd']),
            'within_retained_allocation': number <= Decimal(spec['retained_allocation_usd'])}


def pagination_gate(headers, rows):
    keys = ('Offset', 'Limit', 'Count', 'Total')
    numbers = {}
    for key in keys:
        value = headers.get('X-Apify-Pagination-' + key)
        if type(value) is not str or re.fullmatch(r'[0-9]{1,9}', value) is None:
            return {'state': 'unknown', 'complete_single_page': False}
        numbers[key] = int(value)
    return {'state': 'known', 'complete_single_page': numbers['Offset'] == 0
            and numbers['Limit'] == 3841 and numbers['Count'] == numbers['Total'] == rows}


def collect(transport, spec, cell, validators, persist):
    value = {'schema_version': 1, 'evidence_type': 'private_terminal_Web_readonly_recovery',
             'scope_spec_sha256': SPEC_SHA256, 'target_payload_sha256': spec['target_payload_sha256'],
             'identity': None, 'reads': [], 'files': {}, 'requests_attempted': 0,
             'capture_complete': False, 'capture_diagnostic': None, 'count_gate_passed': False,
             'meter_gate': None, 'fresh_run_meter': None, 'evidence_gates_passed': False,
             'pagination_gate': None, 'raw_within_assigned_bound': False,
             'ready_for_next_cell': False, 'Actor_starts': 0, 'DELETEs': 0,
             'hold_release_usd': '0',
             'original_failed_capture_rewritten': False, 'invoice_finality': False}
    stage = 'run'
    rows, metadata = None, None
    try:
        for stage in STAGES:
            blob, headers = transport.get(stage)
            observed = datetime.now(timezone.utc).isoformat()
            if stage in ('run', 'meter'):
                data, identity = validate_run(blob, validators, cell, transport.target, stage)
                value['identity'] = identity
            elif stage in ('dataset', 'kv', 'queue'):
                body = strict(blob)
                data = body.get('data') if isinstance(body, dict) else None
                validators.validate_metadata(data, stage, value['identity'])
                if stage == 'dataset':
                    if type(data.get('itemCount')) is not int or not 0 <= data['itemCount'] <= 3841:
                        raise RecoveryError('response_invalid', stage, 200)
                    metadata = data
            elif stage == 'raw':
                rows = strict(blob)
                if not isinstance(rows, list) or len(rows) > 3841:
                    raise RecoveryError('response_invalid', stage, 200)
                value['pagination_gate'] = pagination_gate(headers, len(rows))
                value['raw_within_assigned_bound'] = len(rows) <= spec['assigned_case_count']
            else:
                blob.decode('utf-8')
            proof = persist(stage, blob)
            value['files'][stage + '.age'] = {**proof, 'headers': headers,
                                            'observed_at_utc': observed, 'stage': stage}
            value['reads'].append({'stage': stage, 'http_status': 200, 'category': 'ok'})
            if stage == 'dataset':
                value['raw_row_count'] = len(rows)
                value['native_dataset_item_count'] = metadata['itemCount']
                value['raw_minus_native_item_count'] = len(rows) - metadata['itemCount']
                value['count_gate_passed'] = len(rows) == metadata['itemCount']
            if stage == 'meter':
                value['fresh_run_meter'] = controller.project_run_meter(validators, data, cell)
                value['meter_gate'] = meter_gate(value['fresh_run_meter'], spec)
        value['capture_complete'] = True
        value['evidence_gates_passed'] = (value['count_gate_passed']
                                         and value['raw_within_assigned_bound']
                                         and value['pagination_gate']['complete_single_page']
                                         and value['meter_gate']['strict_run_cap_passed'])
    except Exception as exc:
        error = exc if isinstance(exc, RecoveryError) else RecoveryError('scope_mismatch', stage, 200)
        value['capture_diagnostic'] = error.safe()
    value['requests_attempted'] = transport.calls
    return value


def encrypt_raw(blob, destination, binary, recipient, crypto):
    try:
        if destination.exists() or destination.is_symlink() or not isinstance(blob, bytes) or not 1 <= len(blob) <= LOG_LIMIT:
            raise ValueError()
        cipher = crypto.crypto(binary, ['--encrypt', '--recipient', recipient], blob)
        if not cipher.startswith(b'age-encryption.org/v1\n') or len(cipher) > LOG_LIMIT + 65536:
            raise ValueError()
        crypto.durable_write(destination, cipher)
        return {'plaintext_sha256': sha(blob), 'plaintext_bytes': len(blob),
                'ciphertext_sha256': sha(cipher), 'ciphertext_bytes': len(cipher),
                'durable_encrypted_readback_verified': True}
    except Exception:
        raise RecoveryError('encryption_failed', 'evidence') from None


def public_projection(value, proof):
    # No native IDs, rows/counts, headers, meter amounts, log strings or target data.
    return {'schema_version': 1, 'requests_attempted': value['requests_attempted'], 'maximum_GETs': MAX_GETS,
            'capture_complete': value['capture_complete'], 'capture_diagnostic': value['capture_diagnostic'],
            'ready_for_next_cell': False, 'Actor_starts': 0, 'DELETEs': 0,
            'manifest_plaintext_sha256': proof['plaintext_sha256'],
            'manifest_ciphertext_sha256': proof['ciphertext_sha256']}


def execute(*, opt_in=False, environ=None):
    guard()
    if opt_in is not True:
        raise RecoveryError('opt_in_required')
    spec, cell, validators, crypto, recipient = load_reviewed()
    env = os.environ if environ is None else environ
    target = target_from_data(env.get(spec['target_secret_name']), spec, validators, cell)
    temp = env.get('RUNNER_TEMP')
    if type(temp) is not str or not Path(temp).is_absolute():
        raise RecoveryError('preflight_failed')
    output = ROOT / 'recovery'
    if output.exists() or output.is_symlink():
        raise RecoveryError('preflight_failed')
    output.mkdir(mode=0o700)
    binary = Path(temp) / 'age-v1.3.2/age/age'
    preflight = output / 'preflight.age'
    encrypt_raw(b'{"named_synthetic_preflight":true}', preflight, binary, recipient, crypto)
    preflight.unlink()
    transport = Transport(env.get('APIFY_TOKEN'), target)
    value = collect(transport, spec, cell, validators,
                    lambda stage, blob: encrypt_raw(blob, output / (stage + '.age'), binary, recipient, crypto))
    proof = encrypt_raw(canonical(value), output / 'manifest.age', binary, recipient, crypto)
    public = public_projection(value, proof)
    crypto.durable_write(output / 'recovery-public.json', canonical(public))
    return public


if __name__ == '__main__':
    if sys.argv[1:] != ['--execute']:
        print('{"mode":"offline","provider_requests":0,"Actor_starts":0,"DELETEs":0}')
    else:
        try:
            result = execute(opt_in=True)
            print(json.dumps(result, sort_keys=True))
            raise SystemExit(0 if result['capture_complete'] else 1)
        except RecoveryError as exc:
            print(json.dumps({'diagnostic': exc.safe(), 'Actor_starts': 0, 'DELETEs': 0}))
            raise SystemExit(1)
        except Exception:
            print('{"diagnostic":{"category":"preflight_failed"},"Actor_starts":0,"DELETEs":0}')
            raise SystemExit(1)
