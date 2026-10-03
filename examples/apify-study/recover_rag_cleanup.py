"""Closed, renewed cleanup of the three stores in one committed original scope.

Five fresh scope GETs, durable encrypted capture, then three DELETE/absence
pairs; at most eleven requests. This dedicated authorization does not change
the study runner's original approval windows or activate any Actor run.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import copy
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request

import evidence_transport as crypto
import recover_rag_readonly as recovery
import runner
from workflow_driver import private_paths

ROOT = Path(__file__).resolve().parent
CLEANUP_READY = False
MAX_REQUESTS = 11
REQUEST_TIMEOUT_SECONDS = 10
TRANSPORT_WALL_SECONDS = 150
FRESH_SCOPE_SECONDS = 120
KINDS = recovery.KINDS
OPERATIONS = tuple(p+'_'+kind for kind in KINDS for p in ('delete', 'absence'))
STAGES = (*recovery.STAGES, *OPERATIONS)
CATEGORIES = (*recovery.CATEGORIES, 'delete_unconfirmed', 'absence_unconfirmed', 'evidence_invalid')


class CleanupError(recovery.RecoveryError):
    def __init__(self, category, stage='preflight', http_status=None):
        self.category = category if category in CATEGORIES else 'transport_error'
        self.stage = stage if stage in STAGES else 'preflight'
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        Exception.__init__(self, self.category)


@dataclass(frozen=True)
class CleanupReply:
    http_status: int
    absence_verified: bool = False


def require_guard():
    if CLEANUP_READY is not True:
        raise CleanupError('guard_closed')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def checked_proof(payload, receipt):
    if (not isinstance(receipt, dict) or receipt.get('plaintext_sha256') != crypto.digest(payload)
            or not crypto.checked_hash(receipt.get('ciphertext_sha256'))
            or receipt.get('remote_file_readback_verified') is not True):
        raise CleanupError('evidence_invalid', 'evidence')
    return {key: receipt[key] for key in ('plaintext_sha256', 'ciphertext_sha256', 'remote_file_readback_verified')}


def verify_saved_cipher(path, payload, receipt):
    """Verify the durable ciphertext actually present before any deletion."""
    proof = checked_proof(payload, receipt)
    try:
        destination = Path(path)
        info = destination.lstat()
        if (destination.is_symlink() or not destination.is_file() or info.st_mode & 0o777 != 0o600
                or not 1 <= info.st_size <= crypto.MAX_CIPHERTEXT_BYTES):
            raise ValueError()
        cipher = destination.read_bytes()
        if not cipher.startswith(b'age-encryption.org/v1\n') or crypto.digest(cipher) != proof['ciphertext_sha256']:
            raise ValueError()
        return proof
    except Exception:
        raise CleanupError('evidence_invalid', 'evidence') from None


class HttpTransport(recovery.HttpTransport):
    """The reviewed five GETs, then exact original-store DELETE/GET pairs only."""
    def __init__(self, token, *, opener=None, clock=time.monotonic):
        super().__init__(token, opener=opener, clock=clock)
        self._deadline = clock() + TRANSPORT_WALL_SECONDS
        self.fresh_deadline = None
        self.fresh_checked_at = None
        self._cleanup_authorized = False
    def __repr__(self):
        return '<original-three-store cleanup transport>'
    def _check_time(self, deadline, stage, status=None):
        if self._clock() >= deadline:
            raise CleanupError('deadline_exceeded', stage, status)
    def get(self, stage, reference=None):
        if stage == 'run' and self._count == 1:
            # Count the run GET itself inside the renewed fresh-scope lifetime.
            self.fresh_deadline = self._clock() + FRESH_SCOPE_SECONDS
            self.fresh_checked_at = utc_now()
        return super().get(stage, reference)
    def authorize_cleanup(self, payload, receipt):
        self._cleanup_authorized = False
        require_guard()
        checked_proof(payload, receipt)
        try:
            capture = crypto.json_payload(payload)
            identity = capture['recovery_identity']
            if (self._count != 5 or self._stopped or self._bound != identity
                    or identity['status'] != 'SUCCEEDED'
                    or runner.scope_commitment(identity) != recovery.ORIGINAL_SCOPE_SHA256
                    or capture.get('scope_verified') is not True or capture.get('complete') is not True
                    or capture.get('metadata_verified_count') != 3 or set(capture['storage']) != set(KINDS)):
                raise ValueError()
            for kind in KINDS:
                # Projected fractional numeric receipts use strings; restore
                # only those known numeric scalars for the native validator.
                data = copy.deepcopy(capture['storage'][kind])
                if set(data) != {'id', 'userId', 'actRunId', 'actId', 'name', 'createdAt', 'stats'}:
                    raise ValueError()
                for key, value in data['stats'].items():
                    if isinstance(value, str):
                        if len(value) > 96:
                            raise ValueError()
                        data['stats'][key] = Decimal(value)
                runner.validate_metadata(data, kind, identity)
        except Exception:
            raise CleanupError('scope_mismatch', 'evidence') from None
        if self.fresh_deadline is None:
            raise CleanupError('scope_mismatch', 'evidence')
        self._check_time(min(self._deadline, self.fresh_deadline), 'evidence')
        self._cleanup_authorized = True
    def _typed_absence(self, response, content_type, deadline, stage):
        if not isinstance(content_type, str) or content_type.split(';', 1)[0].strip().lower() != 'application/json':
            raise CleanupError('absence_unconfirmed', stage, 404)
        body = self._read(response, deadline, stage, 404)
        error = body.get('error') if isinstance(body, dict) else None
        if not isinstance(error, dict) or error.get('type') != 'record-not-found':
            raise CleanupError('absence_unconfirmed', stage, 404)
        return CleanupReply(404, True)
    def cleanup_call(self, operation):
        require_guard()
        if self._stopped or not self._cleanup_authorized or self._count >= MAX_REQUESTS:
            raise CleanupError('request_limit', operation)
        index = self._count - 5
        if not 0 <= index < len(OPERATIONS) or operation != OPERATIONS[index]:
            raise CleanupError('invalid_route', operation)
        if self.fresh_deadline is None:
            raise CleanupError('scope_mismatch', operation)
        deadline = min(self._deadline, self.fresh_deadline, self._clock()+REQUEST_TIMEOUT_SECONDS)
        self._check_time(deadline, operation)
        method, kind = operation.split('_', 1)
        reference = self._bound[runner.STORES[kind][0]]
        url = 'https://api.apify.com/v2/'+recovery.ROUTES[kind]+'/'+reference
        self._count += 1
        status = None
        try:
            request = Request(url, method='DELETE' if method == 'delete' else 'GET',
                headers={'Authorization': 'Bearer '+self._token, 'Accept': 'application/json'})
            with self._opener.open(request, timeout=max(0.001, deadline-self._clock())) as response:
                status = response.status if type(response.status) is int else None
                self._check_time(deadline, operation, status)
                if method == 'delete' and status == 204:
                    return CleanupReply(204)
                if method == 'absence' and status == 404:
                    return self._typed_absence(response, response.getheader('Content-Type'), deadline, operation)
                category = ('access_denied' if status == 403 else 'redirect_denied' if status and 300 <= status < 400
                    else 'delete_unconfirmed' if method == 'delete' else 'absence_unconfirmed')
                raise CleanupError(category, operation, status)
        except HTTPError as exc:
            status = exc.code if type(exc.code) is int else None
            try:
                self._check_time(deadline, operation, status)
                if method == 'absence' and status == 404:
                    return self._typed_absence(exc.fp, exc.headers.get('Content-Type'), deadline, operation)
                category = 'access_denied' if status == 403 else 'redirect_denied' if status and 300 <= status < 400 else 'http_error'
                raise CleanupError(category, operation, status)
            except Exception:
                self._stopped = True
                self._cleanup_authorized = False
                raise
            finally:
                exc.close()
        except recovery.RecoveryError:
            self._stopped = True
            self._cleanup_authorized = False
            raise
        except (OSError, URLError, ValueError, TypeError):
            self._stopped = True
            self._cleanup_authorized = False
            category = 'deadline_exceeded' if self._clock() >= deadline else 'transport_error'
            raise CleanupError(category, operation, status) from None


def perform(transport, cell, persist_capture):
    """The callback must save/verify encrypted bytes; no old capture is accepted."""
    require_guard()
    capture = recovery.recover(transport, cell)
    capture['fresh_terminal_checked_at'] = getattr(transport, 'fresh_checked_at', None)
    result = {'schema_version': 1, 'evidence_type': 'private_original_rag_renewed_cleanup',
        'cell_id': recovery.CELL_ID, 'expected_scope_sha256': recovery.ORIGINAL_SCOPE_SHA256,
        'initial_capture': copy.deepcopy(capture), 'recovery_identity': copy.deepcopy(capture['recovery_identity']),
        'capture_proof': None, 'requests_attempted': capture['requests_attempted'],
        'deletions_attempted': 0, 'provider_start_attempts': 0,
        'stores': {k: {'delete_http_status': None, 'delete_confirmed': False,
            'absence_http_status': None, 'absence_verified': False} for k in KINDS},
        'cleanup_complete': False, 'cleaned_at': None, 'diagnostic': copy.deepcopy(capture['diagnostic'])}
    operation = 'evidence'
    try:
        payload = runner.canonical(capture)
        result['capture_proof'] = checked_proof(payload, persist_capture(payload))
        if not capture['complete']:
            return result
        transport.authorize_cleanup(payload, result['capture_proof'])
        for kind in KINDS:
            for prefix, expected in (('delete', 204), ('absence', 404)):
                operation = prefix+'_'+kind
                result['requests_attempted'] += 1
                if prefix == 'delete':
                    result['deletions_attempted'] += 1
                reply = transport.cleanup_call(operation)
                if not isinstance(reply, CleanupReply) or reply.http_status != expected:
                    raise CleanupError(prefix+'_unconfirmed', operation, getattr(reply, 'http_status', None))
                result['stores'][kind][prefix+'_http_status'] = reply.http_status
                if prefix == 'delete':
                    result['stores'][kind]['delete_confirmed'] = True
                elif reply.absence_verified is True:
                    result['stores'][kind]['absence_verified'] = True
                else:
                    raise CleanupError('absence_unconfirmed', operation, reply.http_status)
        result['cleanup_complete'] = True
        result['cleaned_at'] = utc_now()
    except Exception as exc:
        fault = exc if isinstance(exc, recovery.RecoveryError) else CleanupError('encryption_failed' if operation == 'evidence' else 'transport_error', operation)
        result['diagnostic'] = CleanupError(fault.category, fault.stage, fault.http_status).safe()
        if operation in OPERATIONS:
            prefix, kind = operation.split('_', 1)
            result['stores'][kind][prefix+'_http_status'] = fault.http_status
    return result


def public_result(evidence, receipt, phase):
    proof = checked_proof(runner.canonical(evidence), receipt)
    final = phase == 'final'
    capture = evidence['initial_capture'] if final else evidence
    diagnostic = evidence.get('diagnostic')
    if isinstance(diagnostic, dict):
        diagnostic = CleanupError(diagnostic.get('category'), diagnostic.get('stage'), diagnostic.get('http_status')).safe()
    stores = evidence.get('stores', {}) if final else {}
    return {'schema_version': 1, 'evidence_type': 'encrypted_original_rag_cleanup',
        'phase': 'final' if final else 'capture', 'scope_verified': capture['scope_verified'],
        'metadata_verified_count': capture['metadata_verified_count'],
        'requests_attempted': evidence['requests_attempted'], 'provider_start_attempts': 0,
        'deletions_attempted': evidence.get('deletions_attempted', 0) if final else 0,
        'stores': {k: {f: stores[k][f] for f in ('delete_http_status', 'delete_confirmed', 'absence_http_status', 'absence_verified')}
            for k in KINDS} if final else {},
        'cleanup_complete': evidence.get('cleanup_complete') is True if final else False,
        'owner_attention_required': evidence.get('cleanup_complete') is not True if final else not capture['complete'],
        'diagnostic': diagnostic, **proof}


def save_encrypted(evidence, phase, binary, recipient):
    payload = runner.canonical(evidence)
    destination = ROOT/('rag-cleanup-'+phase+'.age')
    receipt = recovery.checked_encryption(payload, destination, binary, recipient)
    proof = verify_saved_cipher(destination, payload, receipt)
    public = public_result(evidence, proof, phase)
    crypto.durable_write(ROOT/('rag-cleanup-'+phase+'-public.json'), runner.canonical(public))
    return proof


def execute(environ=None):
    require_guard()  # No environment, source/identity, files or token before this guard.
    cell = recovery.load_cell()
    recipient = recovery.load_recipient()
    env = os.environ if environ is None else environ
    try:
        folder, binary = private_paths(env)
        for phase in ('capture', 'final'):
            for suffix in ('.age', '-public.json'):
                path = ROOT/('rag-cleanup-'+phase+suffix)
                if path.exists() or path.is_symlink():
                    raise ValueError()
        preflight = folder/'rag-cleanup-preflight.age'
        payload = b'{"synthetic_transport_preflight":true,"provider_calls":0}'
        proof = recovery.checked_encryption(payload, preflight, binary, recipient)
        verify_saved_cipher(preflight, payload, proof)
        preflight.unlink()
    except Exception:
        raise CleanupError('encryption_failed', 'preflight') from None
    token = env.get('APIFY_TOKEN')
    recovery.validate_token(token)
    transport = HttpTransport(token)
    result = perform(transport, cell, lambda blob: save_encrypted(crypto.json_payload(blob), 'capture', binary, recipient))
    try:
        final_proof = save_encrypted(result, 'final', binary, recipient)
        return public_result(result, final_proof, 'final')
    except Exception:
        raise CleanupError('encryption_failed', 'evidence') from None


def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({'mode': 'offline', 'provider_requests': 0, 'deletions': 0}))
        return 0
    if args != ['--execute']:
        print(json.dumps({'diagnostic': CleanupError('invalid_route').safe(), 'provider_requests': 0}))
        return 1
    try:
        result = execute()
        print(json.dumps(result, sort_keys=True))
        return 0 if result['cleanup_complete'] else 1
    except Exception as exc:
        fault = exc if isinstance(exc, recovery.RecoveryError) else CleanupError('transport_error')
        print(json.dumps({'diagnostic': CleanupError(fault.category, fault.stage, fault.http_status).safe(),
            'owner_attention_required': True, 'provider_start_attempts': 0}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
