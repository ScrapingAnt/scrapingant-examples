"""Closed, one-shot recovery of one original RAG scope; at most five GETs.

The public Actor list API's inclusive UTC start filters select a five-row page:
https://docs.apify.com/api/v2/actors-runs-get . There is no pagination or fallback.
Only the committed run fingerprint can advance to its run and default stores.
Normalized identifiers are encrypted for private recovery; public output contains
fixed diagnostics, counts, booleans and evidence hashes. No cleanup is performed.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import evidence_transport as crypto
import runner
from workflow_driver import private_paths

ROOT = Path(__file__).resolve().parent
RECOVERY_READY = False
CELL_ID = 'cap-r2-rag-web-browser-static'
ACTOR_ID = '3ox4R101TgZz67sLr'  # Public Actor resource, not an account identifier.
TARGET_RUN_SHA256 = 'b7dc3309eb7e0b23c1cf1206a844ce8fb9f8fd1591c424021bcf28ac5adce62d'
ORIGINAL_SCOPE_SHA256 = '42afdc176feb612969a25a04ccafd207b50d9b07786dc1e990af01d4b9c02e76'
PLAN_FILE_SHA256 = 'b1b409024d3391bc9a73a506e8722c5227861083907cb98e4441b7b3dc557bcc'
PLAN_CANONICAL_SHA256 = '253afef63e7774d2e36c0a862e8b8e5fc90f3e0b7b99eb81b1b8a2495379a874'
RECIPIENT_FILE_SHA256 = '7da784c7f41ff4e52cce510c67943403dab25843a997bd805d6c4b4c7415ddac'
STARTED_AFTER = '2026-10-02T21:20:00.000Z'
STARTED_BEFORE = '2026-10-02T21:21:00.000Z'
MAX_REQUESTS = 5
MAX_RESPONSE_BYTES = 131072
REQUEST_TIMEOUT_SECONDS = 10
TRANSPORT_WALL_SECONDS = 50
KINDS = ('dataset', 'kv', 'queue')
ROUTES = {'dataset': 'datasets', 'kv': 'key-value-stores', 'queue': 'request-queues'}
STAGES = ('preflight', 'list', 'run', *KINDS, 'evidence')
CATEGORIES = ('guard_closed', 'unreviewed_source', 'invalid_token', 'invalid_route',
    'request_limit', 'deadline_exceeded', 'transport_error', 'access_denied', 'http_error',
    'redirect_denied', 'body_limit', 'invalid_response', 'target_not_found', 'scope_mismatch',
    'run_invalid', 'metadata_invalid', 'encryption_failed', 'ok')


class RecoveryError(Exception):
    def __init__(self, category, stage='preflight', http_status=None):
        self.category = category if category in CATEGORIES else 'transport_error'
        self.stage = stage if stage in STAGES else 'preflight'
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        super().__init__(self.category)
    def safe(self):
        return {'category': self.category, 'stage': self.stage, 'http_status': self.http_status}


def require_guard():
    if RECOVERY_READY is not True:
        raise RecoveryError('guard_closed')


def load_cell():
    try:
        path = ROOT/'capability-plan.json'
        if path.is_symlink() or path.stat().st_size > 1048576:
            raise ValueError()
        blob = path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != PLAN_FILE_SHA256:
            raise ValueError()
        plan = runner.load_reviewed_plan(blob)
        if runner.sha(runner.canonical(plan)) != PLAN_CANONICAL_SHA256 or plan['stage'] != 'CAPABILITY':
            raise ValueError()
        cell = runner.prepare_cell(plan, CELL_ID)
        if cell.spec['actor_id'] != ACTOR_ID or cell.spec['build'] != '1.0.30':
            raise ValueError()
        return cell
    except Exception:
        raise RecoveryError('unreviewed_source') from None


def load_recipient():
    try:
        path = ROOT/'recipient.txt'
        if path.is_symlink() or path.stat().st_size > 128:
            raise ValueError()
        blob = path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != RECIPIENT_FILE_SHA256:
            raise ValueError()
        recipient = blob.decode('ascii').strip()
        if re.fullmatch(r'age1[a-z0-9]{58}', recipient) is None:
            raise ValueError()
        return recipient
    except Exception:
        raise RecoveryError('unreviewed_source') from None


def validate_token(token):
    if not isinstance(token, str) or re.fullmatch(r'[A-Za-z0-9_-]{16,512}', token) is None:
        raise RecoveryError('invalid_token')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpTransport:
    """Fixed host/routes/header-only auth, no retry, bound scope before stores."""
    def __init__(self, token, *, opener=None, clock=time.monotonic):
        validate_token(token)
        self._token = token
        self._opener = opener if opener is not None else build_opener(NoRedirect())
        self._clock = clock
        self._deadline = clock() + TRANSPORT_WALL_SECONDS
        self._count = 0
        self._bound = None
        self._stopped = False
    def __repr__(self):
        return '<read-only original-scope transport>'
    def bind_identity(self, identity):
        if (self._count != 2 or self._stopped or not isinstance(identity, dict)
                or runner.scope_commitment(identity) != ORIGINAL_SCOPE_SHA256
                or hashlib.sha256(identity.get('id', '').encode()).hexdigest() != TARGET_RUN_SHA256
                or identity.get('actId') != ACTOR_ID):
            raise RecoveryError('scope_mismatch', 'run')
        self._bound = copy.deepcopy(identity)
    def _check_time(self, deadline, stage, status=None):
        if self._clock() >= deadline:
            raise RecoveryError('deadline_exceeded', stage, status)
    def _url(self, stage, reference):
        expected = ('list', 'run', *KINDS)
        if self._stopped or self._count >= MAX_REQUESTS:
            raise RecoveryError('request_limit', stage)
        if stage != expected[self._count]:
            raise RecoveryError('invalid_route', stage)
        if stage == 'list':
            if reference is not None:
                raise RecoveryError('invalid_route', stage)
            return 'https://api.apify.com/v2/actors/'+ACTOR_ID+'/runs?' + urlencode({
                'limit': 5, 'offset': 0, 'desc': 'false',
                'startedAfter': STARTED_AFTER, 'startedBefore': STARTED_BEFORE})
        try:
            runner.ident(reference)
        except runner.Fault:
            raise RecoveryError('invalid_route', stage) from None
        if stage == 'run':
            if hashlib.sha256(reference.encode()).hexdigest() != TARGET_RUN_SHA256:
                raise RecoveryError('scope_mismatch', stage)
            return 'https://api.apify.com/v2/actor-runs/'+reference
        if not self._bound or reference != self._bound[runner.STORES[stage][0]]:
            raise RecoveryError('scope_mismatch', stage)
        return 'https://api.apify.com/v2/'+ROUTES[stage]+'/'+reference
    def _read(self, response, deadline, stage, status):
        reader = getattr(response, 'read1', None)
        if not callable(reader):
            raise RecoveryError('invalid_response', stage, status)
        chunks = []
        length = 0
        while True:
            self._check_time(deadline, stage, status)
            # urllib's HTTPResponse socket timeout is reduced for each read1;
            # its original inactivity timeout cannot restart a 10s route budget.
            sock = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
            if sock is not None:
                sock.settimeout(max(0.001, deadline - self._clock()))
            part = reader(min(4096, MAX_RESPONSE_BYTES + 1 - length))
            self._check_time(deadline, stage, status)
            if not isinstance(part, bytes):
                raise RecoveryError('invalid_response', stage, status)
            length += len(part)
            if length > MAX_RESPONSE_BYTES:
                raise RecoveryError('body_limit', stage, status)
            if not part:
                break
            chunks.append(part)
        try:
            value = crypto.json_payload(b''.join(chunks))
        except crypto.TransportError:
            raise RecoveryError('invalid_response', stage, status) from None
        self._check_time(deadline, stage, status)
        return value
    def get(self, stage, reference=None):
        url = self._url(stage, reference)
        deadline = min(self._deadline, self._clock() + REQUEST_TIMEOUT_SECONDS)
        self._check_time(deadline, stage)
        self._count += 1
        status = None
        try:
            request = Request(url, method='GET', headers={
                'Authorization': 'Bearer '+self._token, 'Accept': 'application/json'})
            with self._opener.open(request, timeout=max(0.001, deadline-self._clock())) as response:
                status = response.status if type(response.status) is int else None
                self._check_time(deadline, stage, status)
                if status != 200:
                    category = 'access_denied' if status == 403 else 'redirect_denied' if status and 300 <= status < 400 else 'http_error'
                    raise RecoveryError(category, stage, status)
                content_type = response.getheader('Content-Type')
                if not isinstance(content_type, str) or content_type.split(';', 1)[0].strip().lower() != 'application/json':
                    raise RecoveryError('invalid_response', stage, status)
                return self._read(response, deadline, stage, status)
        except HTTPError as exc:
            status = exc.code
            exc.close()  # Error bodies, messages and redirect destinations are never retained.
            self._stopped = True
            category = 'access_denied' if status == 403 else 'redirect_denied' if 300 <= status < 400 else 'http_error'
            raise RecoveryError(category, stage, status) from None
        except RecoveryError:
            self._stopped = True
            raise
        except (OSError, URLError, ValueError, TypeError):
            self._stopped = True
            category = 'deadline_exceeded' if self._clock() >= deadline else 'transport_error'
            raise RecoveryError(category, stage, status) from None


def selected_run(reply):
    data = reply.get('data') if isinstance(reply, dict) else None
    if (not isinstance(data, dict) or any(type(data.get(k)) is not int or data[k] < 0
            for k in ('total', 'offset', 'limit', 'count'))
            or data['offset'] != 0 or data['limit'] != 5 or data.get('desc') is not False
            or not isinstance(data.get('items'), list) or data['count'] != len(data['items'])
            or data['count'] > 5 or data['total'] < data['count']):
        raise RecoveryError('invalid_response', 'list', 200)
    matches = []
    seen = set()
    for row in data['items']:
        try:
            value = runner.ident(row.get('id')) if isinstance(row, dict) else None
            if value is None or value in seen:
                raise ValueError()
            seen.add(value)
            if hashlib.sha256(value.encode()).hexdigest() == TARGET_RUN_SHA256:
                if row.get('actId') != ACTOR_ID or not runner.timestamp(STARTED_AFTER) <= runner.timestamp(row.get('startedAt')) <= runner.timestamp(STARTED_BEFORE):
                    raise ValueError()
                matches.append(value)
        except (runner.Fault, ValueError):
            raise RecoveryError('invalid_response', 'list', 200) from None
    if len(matches) != 1:
        raise RecoveryError('target_not_found', 'list', 200)
    return matches[0], data['total'] == data['count']


def partial_run_identity(data):
    """Schema-limited private evidence; invalid fields become null, never raw text."""
    if not isinstance(data, dict):
        return None
    result = {}
    # Owner/default-store associations are retained only after the complete
    # original scope commitment verifies. A mismatched body cannot introduce
    # foreign private identifiers into a recovery artifact.
    for field in runner.IDENTITY_FIELDS:
        result[field] = None
    try:
        value = runner.ident(data.get('id'))
        if hashlib.sha256(value.encode()).hexdigest() == TARGET_RUN_SHA256:
            result['id'] = value
    except runner.Fault:
        pass
    if data.get('actId') == ACTOR_ID:
        result['actId'] = ACTOR_ID
    for field in ('startedAt', 'finishedAt'):
        try:
            runner.timestamp(data.get(field)); result[field] = data[field]
        except runner.Fault:
            result[field] = None
    build = data.get('buildNumber')
    result['build'] = build if isinstance(build, str) and re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', build) else None
    result['status'] = data.get('status') if data.get('status') in runner.TERMINAL + runner.ACTIVE else None
    options = data.get('options')
    result['options'] = None
    if isinstance(options, dict):
        opt_build = options.get('build')
        result['options'] = {'build': opt_build if isinstance(opt_build, str) and re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', opt_build) else None,
            'memoryMbytes': options.get('memoryMbytes') if type(options.get('memoryMbytes')) is int and 0 <= options['memoryMbytes'] <= 1048576 else None,
            'timeoutSecs': options.get('timeoutSecs') if type(options.get('timeoutSecs')) is int and 0 <= options['timeoutSecs'] <= 86400 else None,
            'maxTotalChargeUsd': runner.numeric_receipt(options.get('maxTotalChargeUsd')),
            'restartOnError': options.get('restartOnError') if type(options.get('restartOnError')) is bool else None}
    return result


def recover(transport, cell):
    evidence = {'schema_version': 1, 'evidence_type': 'private_original_rag_readonly_recovery',
        'cell_id': CELL_ID, 'plan_file_sha256': PLAN_FILE_SHA256,
        'target_run_sha256': TARGET_RUN_SHA256, 'expected_scope_sha256': ORIGINAL_SCOPE_SHA256,
        'requests_attempted': 0, 'reads': [], 'target_found': False, 'list_page_complete': None,
        'scope_verified': False, 'recovery_identity': None, 'partial_run_identity': None,
        'storage': {}, 'metadata_verified_count': 0, 'complete': False,
        'diagnostic': None, 'provider_start_attempts': 0, 'deletions': 0}
    stage = 'list'
    status = None
    def read(current_stage, reference=None):
        nonlocal stage, status
        stage = current_stage; status = None
        evidence['requests_attempted'] += 1
        reply = transport.get(stage, reference)
        status = 200
        evidence['reads'].append({'stage': stage, 'http_status': 200, 'category': 'ok'})
        return reply
    try:
        target, complete_page = selected_run(read('list'))
        evidence['target_found'] = True
        evidence['list_page_complete'] = complete_page
        reply = read('run', target)
        data = reply.get('data') if isinstance(reply, dict) else None
        evidence['partial_run_identity'] = partial_run_identity(data)
        try:
            identity = runner.validate_run(data, cell)
        except runner.Fault:
            raise RecoveryError('run_invalid', 'run', 200) from None
        if (identity['id'] != target or identity['status'] not in runner.TERMINAL
                or runner.scope_commitment(identity) != ORIGINAL_SCOPE_SHA256):
            raise RecoveryError('scope_mismatch', 'run', 200)
        transport.bind_identity(identity)
        evidence['recovery_identity'] = identity
        evidence['partial_run_identity'] = None
        evidence['scope_verified'] = True
        for kind in KINDS:
            reply = read(kind, identity[runner.STORES[kind][0]])
            data = reply.get('data') if isinstance(reply, dict) else None
            try:
                stats = runner.validate_metadata(data, kind, identity)
            except runner.Fault:
                raise RecoveryError('metadata_invalid', kind, 200) from None
            evidence['storage'][kind] = {k: data[k] for k in ('id', 'userId', 'actRunId', 'actId', 'name', 'createdAt')}
            evidence['storage'][kind]['stats'] = stats
            evidence['metadata_verified_count'] += 1
        evidence['complete'] = True
    except Exception as exc:
        fault = exc if isinstance(exc, RecoveryError) else RecoveryError('transport_error', stage, status)
        evidence['diagnostic'] = fault.safe()
        if not evidence['reads'] or evidence['reads'][-1]['stage'] != stage:
            evidence['reads'].append(fault.safe())
    return evidence


def public_result(evidence, receipt):
    """Explicit allowlist: no identifiers, store stats, paths or provider strings."""
    return {'schema_version': 1, 'evidence_type': 'encrypted_original_rag_readonly_recovery',
        'requests_attempted': evidence['requests_attempted'], 'reads': copy.deepcopy(evidence['reads']),
        'target_found': evidence['target_found'], 'scope_verified': evidence['scope_verified'],
        'metadata_verified_count': evidence['metadata_verified_count'], 'complete': evidence['complete'],
        'diagnostic': copy.deepcopy(evidence['diagnostic']), 'owner_attention_required': not evidence['complete'],
        'provider_start_attempts': 0, 'deletions': 0,
        'plaintext_sha256': receipt['plaintext_sha256'], 'ciphertext_sha256': receipt['ciphertext_sha256'],
        'encrypted_file_readback_verified': receipt['remote_file_readback_verified'] is True}


def checked_encryption(payload, destination, binary, recipient):
    try:
        receipt = crypto.encrypt_capture(payload, destination, binary, recipient)
        if (receipt.get('plaintext_sha256') != crypto.digest(payload)
                or not crypto.checked_hash(receipt.get('ciphertext_sha256'))
                or receipt.get('remote_file_readback_verified') is not True):
            raise crypto.TransportError()
        return receipt
    except Exception:
        raise RecoveryError('encryption_failed', 'evidence') from None


def execute(environ=None):
    require_guard()  # Before environment, source files, paths, crypto or token.
    cell = load_cell()
    recipient = load_recipient()
    env = os.environ if environ is None else environ
    try:
        folder, binary = private_paths(env)
        destination = ROOT/'rag-recovery.age'
        public_path = ROOT/'rag-recovery-public.json'
        if destination.exists() or destination.is_symlink() or public_path.exists() or public_path.is_symlink():
            raise ValueError()
        preflight = folder/'rag-recovery-preflight.age'
        checked_encryption(b'{"synthetic_transport_preflight":true,"provider_calls":0}', preflight, binary, recipient)
        preflight.unlink()
    except Exception:
        raise RecoveryError('encryption_failed', 'preflight') from None
    token = env.get('APIFY_TOKEN')  # Existing secret only after verified crypto readiness.
    validate_token(token)
    evidence = recover(HttpTransport(token), cell)
    receipt = checked_encryption(runner.canonical(evidence), destination, binary, recipient)
    public = public_result(evidence, receipt)
    try:
        crypto.durable_write(public_path, runner.canonical(public))
    except Exception:
        raise RecoveryError('encryption_failed', 'evidence') from None
    return public


def main():
    # Do not initialize locale/argument helpers before the closed guard: some
    # standard-library argument parsing reads process environment implicitly.
    args = sys.argv[1:]
    if args == []:
        print(json.dumps({'mode': 'offline', 'provider_requests': 0, 'deletions': 0}))
        return 0
    if args != ['--execute']:
        print(json.dumps({'diagnostic': RecoveryError('invalid_route').safe(), 'provider_requests': 0}))
        return 1
    try:
        result = execute()
        print(json.dumps(result, sort_keys=True))
        return 0 if result['complete'] else 1
    except Exception as exc:
        fault = exc if isinstance(exc, RecoveryError) else RecoveryError('transport_error')
        print(json.dumps({'diagnostic': fault.safe(), 'owner_attention_required': True,
            'provider_start_attempts': 0, 'deletions': 0}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
