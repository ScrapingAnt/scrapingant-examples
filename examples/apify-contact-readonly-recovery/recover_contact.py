"""PRIVATE CANDIDATE: fixed Contact start diagnostic, closed by default.

At most five ordered GETs. An empty page is only an absence observation,
never proof of rejected-before-run or zero charge. No start, abort, deletion,
retry, pagination, output export, settings or new credential route exists.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener
import copy, hashlib, importlib.util, json, os, re, sys, time

ROOT = Path(__file__).resolve().parent
RECOVERY_READY = False
SPEC_SHA256 = '70ee216c9d6fb133fe24793904cdcd597e74e1bd48449dea94c443d845a7a0b8'
STAGES = ('list', 'run', 'kv', 'input', 'meter')
TERMINAL = ('SUCCEEDED', 'FAILED', 'TIMED-OUT', 'ABORTED')
CATEGORIES = ('guard_closed', 'opt_in_required', 'source_invalid', 'preflight_failed',
    'token_unavailable', 'route_invalid', 'deadline_exceeded', 'http_error',
    'redirect_refused', 'transport_error', 'body_limit', 'response_invalid',
    'scope_mismatch', 'incomplete_list', 'multiple_candidates', 'nonterminal',
    'input_mismatch', 'meter_unknown', 'budget_exceeded', 'encryption_failed')

def sha(blob): return hashlib.sha256(blob).hexdigest()
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
        allow_nan=False).encode()

class Stop(Exception):
    def __init__(self, category, stage='preflight', status=None):
        self.category = category if category in CATEGORIES else 'scope_mismatch'
        self.stage = stage if stage in STAGES + ('preflight', 'evidence') else 'preflight'
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        super().__init__('contact_readonly_diagnostic_stopped')
    def safe(self):
        return {'category': self.category, 'stage': self.stage, 'http_status': self.status}

def guard():
    if RECOVERY_READY is not True: raise Stop('guard_closed')

def strict(blob):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result: raise ValueError()
            result[key] = value
        return result
    def reject(_): raise ValueError()
    def number(text):
        value = Decimal(text)
        if not value.is_finite() or abs(value) > Decimal('1e18') or len(text) > 96:
            raise ValueError()
        return value
    try:
        return json.loads(blob, object_pairs_hook=pairs, parse_float=number,
            parse_constant=reject)
    except Exception: raise Stop('response_invalid') from None

def stamp(value):
    try:
        if type(value) is not str or len(value) > 64: raise ValueError()
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() != timedelta(0): raise ValueError()
        return result
    except Exception: raise Stop('scope_mismatch') from None

def ident(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9]{17}', value) is None:
        raise Stop('scope_mismatch')
    return value

def load_reviewed():
    try:
        path = ROOT / 'scope.json'
        if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= 8192:
            raise ValueError()
        raw = path.read_bytes()
        if sha(raw) != SPEC_SHA256: raise ValueError()
        spec = strict(raw)
        if not (spec['schema_version'] == 1 and spec['cell_id'] == 'continuation-contact-pilot'
            and spec['actor_id'] == '9Sk4JJhEma9vBKqrg' and spec['build'] == '0.2.238'
            and spec['options'] == {'build':'0.2.238','memoryMbytes':512,'timeoutSecs':120,
                'maxTotalChargeUsd':'0.50','restartOnError':False}
            and spec['started_after'] == '2026-10-06T13:30:00Z'
            and spec['started_before'] == '2026-10-06T13:30:59.999999Z'
            and spec['list_limit'] == 5 and spec['maximum_GETs'] == 5
            and spec['body_limit_bytes'] == 131072 and spec['route_seconds'] == 15
            and spec['wall_seconds'] == 90
            and spec['native_input_sha256'] == 'a1a3b32ef5fcb52d05f47903440885dfac6a5f0de737ddff70674a150579fca7'
            and re.fullmatch('[a-f0-9]{64}', spec['owner_id_sha256'])): raise ValueError()
        names = {'examples/apify-study/runner.py','examples/apify-study/billing_projection.py',
            'examples/apify-sustained/evidence_transport.py','examples/apify-sustained/recipient.txt'}
        if set(spec['dependency_sha256']) != names: raise ValueError()
        source = ROOT.parent.parent
        for name, digest in spec['dependency_sha256'].items():
            dependency = source / name
            if dependency.is_symlink() or not dependency.is_file() or sha(dependency.read_bytes()) != digest:
                raise ValueError()
        sys.path.insert(0, str(source / 'examples/apify-study'))
        import runner
        if any(getattr(runner, key) is not False for key in ('RUNNER_READY','GRAPH_READY','CONCURRENCY_READY')):
            raise ValueError()
        module_spec = importlib.util.spec_from_file_location('contact_evidence_crypto',
            source / 'examples/apify-sustained/evidence_transport.py')
        crypto = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(crypto)
        recipient = (source / 'examples/apify-sustained/recipient.txt').read_text().strip()
        if re.fullmatch('age1[a-z0-9]{58}', recipient) is None: raise ValueError()
        return spec, runner, crypto, recipient
    except Exception: raise Stop('source_invalid') from None

def select_candidate(body, spec):
    data = body.get('data') if isinstance(body, dict) else None
    if (not isinstance(data, dict) or any(type(data.get(k)) is not int or data[k] < 0
            for k in ('offset','limit','count','total')) or data['offset'] != 0
        or data['limit'] != 5 or data.get('desc') is not False
        or not isinstance(data.get('items'), list) or len(data['items']) != data['count']
        or data['count'] > 5 or data['total'] < data['count']): raise Stop('response_invalid','list')
    seen = set(); starts = []; rows = []
    for row in data['items']:
        if not isinstance(row, dict): raise Stop('response_invalid','list')
        reference = ident(row.get('id'))
        when = stamp(row.get('startedAt'))
        if (reference in seen or row.get('actId') != spec['actor_id']
            or not stamp(spec['started_after']) <= when <= stamp(spec['started_before'])):
            raise Stop('scope_mismatch','list')
        if 'userId' in row and sha(ident(row['userId']).encode()) != spec['owner_id_sha256']:
            raise Stop('scope_mismatch','list')
        seen.add(reference); starts.append(when); rows.append(row)
    if starts != sorted(starts): raise Stop('response_invalid','list')
    if data['total'] != data['count']: raise Stop('incomplete_list','list')
    if len(rows) > 1: raise Stop('multiple_candidates','list')
    return rows[0]['id'] if rows else None

def validate_run(data, spec, validators, candidate, initial=None):
    try:
        identity = validators.validate_run(data, SimpleNamespace(spec=spec), initial)
        if (identity['id'] != candidate or sha(identity['userId'].encode()) != spec['owner_id_sha256']
            or not stamp(spec['started_after']) <= stamp(identity['startedAt']) <= stamp(spec['started_before'])
            or data.get('buildNumber') != spec['build']): raise ValueError()
        if initial and (identity['status'] != initial['status'] or identity['finishedAt'] != initial['finishedAt']):
            raise ValueError()
        return identity
    except Exception: raise Stop('scope_mismatch') from None

def validate_kv(data, identity, validators, observed):
    try:
        validators.validate_metadata(data, 'kv', identity)
        if (data.get('actId') != identity['actId'] or data.get('actRunId') != identity['id']
            or 'name' not in data or data['name'] is not None
            or not stamp(identity['startedAt']) <= stamp(data.get('createdAt'))
                <= min(stamp(observed), stamp(identity['finishedAt']))): raise ValueError()
    except Exception: raise Stop('scope_mismatch','kv') from None

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

class Transport:
    def __init__(self, token, spec, *, opener=None, clock=time.monotonic):
        guard()
        if type(token) is not str or re.fullmatch('[A-Za-z0-9_-]{16,512}', token) is None:
            raise Stop('token_unavailable')
        self._token = token; self.spec = copy.deepcopy(spec); self.clock = clock
        self.deadline = clock() + 90; self.calls = 0; self.failed = False
        self.candidate = None; self.identity = None
        self._open = opener if opener is not None else build_opener(NoRedirect()).open
    def __repr__(self): return '<fixed Contact read-only diagnostic transport>'
    def bind_candidate(self, value):
        if self.calls != 1 or self.failed or self.candidate is not None: raise Stop('route_invalid')
        self.candidate = ident(value)
    def bind_identity(self, identity):
        if self.calls != 2 or self.failed or self.identity is not None or identity['id'] != self.candidate:
            raise Stop('route_invalid')
        self.identity = copy.deepcopy(identity)
    def route(self, stage):
        guard()
        if self.failed or self.calls >= 5 or stage != STAGES[self.calls]: raise Stop('route_invalid',stage)
        api = 'https://api.apify.com/v2/'
        if stage == 'list':
            return api + 'actors/' + self.spec['actor_id'] + '/runs?' + urlencode({
                'limit':5,'offset':0,'desc':'false','startedAfter':self.spec['started_after'],
                'startedBefore':self.spec['started_before']})
        if self.candidate is None: raise Stop('route_invalid',stage)
        if stage == 'run': return api + 'actor-runs/' + self.candidate
        if self.identity is None: raise Stop('route_invalid',stage)
        if stage == 'meter': return api + 'actor-runs/' + self.identity['id']
        path = api + 'key-value-stores/' + self.identity['defaultKeyValueStoreId']
        return path + ('/records/INPUT' if stage == 'input' else '')
    def get(self, stage):
        url = self.route(stage); end = min(self.deadline, self.clock() + 15)
        if self.clock() >= end: raise Stop('deadline_exceeded',stage)
        self.calls += 1; response = None
        try:
            request = Request(url, method='GET', headers={'Authorization':'Bearer '+self._token,
                'Accept':'application/json','Accept-Encoding':'identity'})
            response = self._open(request, timeout=max(.001,end-self.clock()))
            if response.status != 200: raise Stop('http_error',stage,response.status)
            mime = response.getheader('Content-Type')
            if type(mime) is not str or mime.split(';',1)[0].strip().lower() != 'application/json':
                raise Stop('response_invalid',stage)
            if response.getheader('Content-Encoding') not in (None,'identity'):
                raise Stop('response_invalid',stage)
            raw = bytearray()
            while True:
                remaining = end - self.clock()
                if remaining <= 0: raise Stop('deadline_exceeded',stage)
                sock = getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                if sock is not None: sock.settimeout(max(.001,remaining))
                chunk = response.read1(min(8192,131073-len(raw)))
                if self.clock() >= end: raise Stop('deadline_exceeded',stage)
                if not isinstance(chunk,bytes): raise Stop('response_invalid',stage)
                if not chunk: break
                raw.extend(chunk)
                if len(raw) > 131072: raise Stop('body_limit',stage)
            return bytes(raw)
        except HTTPError as error:
            status = error.code; error.close(); self.failed = True
            raise Stop('redirect_refused' if 300 <= status <= 399 else 'http_error',stage,status) from None
        except Stop: self.failed = True; raise
        except (URLError,OSError):
            self.failed = True; raise Stop('transport_error',stage) from None
        finally:
            if response is not None: response.close()

def collect(transport, spec, validators, persist, *, utc=lambda:datetime.now(timezone.utc).isoformat()):
    result = {'schema_version':1,'scope_sha256':SPEC_SHA256,'files':{},'observations':{},
        'capture_complete':False,'diagnostic':None,'candidate':None,'identity':None,
        'complete_empty_window_observed':False,'terminal_identity_and_input_verified':False,
        'latest_terminal_run_meter':None,'latest_meter_snapshot_used_once':False,
        'rejected_before_run_proven':False,'Actor_starts':0,'aborts':0,'DELETEs':0,
        'item_exports':0,'hold_release_usd':'0','ready_for_next_Actor_start':False,
        'invoice_finality':False,'retained_run_cap_usd':'0.50','retained_ancillary_hold_usd':'0.03'}
    stage = 'list'
    try:
        for stage in STAGES:
            raw = transport.get(stage); observed = utc()
            result['files'][stage+'.age'] = persist(stage,raw)
            result['observations'][stage] = observed
            body = strict(raw)
            data = body.get('data') if isinstance(body,dict) else None
            if stage == 'list':
                candidate = select_candidate(body,spec)
                if candidate is None:
                    result['complete_empty_window_observed'] = True
                    result['capture_complete'] = True
                    break
                result['candidate'] = candidate; transport.bind_candidate(candidate)
            elif stage in ('run','meter'):
                identity = validate_run(data,spec,validators,result['candidate'],result['identity'])
                result['identity'] = identity
                if identity['status'] not in TERMINAL: raise Stop('nonterminal',stage)
                if stamp(identity['finishedAt']) > stamp(observed): raise Stop('scope_mismatch',stage)
                if stage == 'run': transport.bind_identity(identity)
                else:
                    meter = validators.run_receipt(data,SimpleNamespace(spec=spec))
                    amount = meter.get('usage_total_usd')
                    if type(amount) is int: amount = str(amount)
                    if type(amount) is not str: raise Stop('meter_unknown','meter')
                    value = Decimal(amount)
                    if not value.is_finite() or value < 0: raise Stop('meter_unknown','meter')
                    if value > Decimal('0.50'): raise Stop('budget_exceeded','meter')
                    meter['usage_total_usd'] = amount
                    result['latest_terminal_run_meter'] = meter
                    result['latest_meter_snapshot_used_once'] = True
                    result['terminal_identity_and_input_verified'] = True
                    result['capture_complete'] = True
            elif stage == 'kv': validate_kv(data,result['identity'],validators,observed)
            elif stage == 'input':
                if not isinstance(body,dict) or sha(canonical(body)) != spec['native_input_sha256']:
                    raise Stop('input_mismatch','input')
    except Exception as error:
        stop = error if isinstance(error,Stop) else Stop('scope_mismatch',stage)
        result['diagnostic'] = stop.safe()
        result['capture_complete'] = False
    result['requests_attempted'] = transport.calls
    return result

def encrypt_raw(raw, path, binary, recipient, crypto):
    try:
        if not isinstance(raw,bytes) or not 1 <= len(raw) <= 1048576 or path.exists() or path.is_symlink():
            raise ValueError()
        cipher = crypto.crypto(binary,['--encrypt','--recipient',recipient],raw)
        if not cipher.startswith(b'age-encryption.org/v1\n'): raise ValueError()
        crypto.durable_write(path,cipher)
        return {'plaintext_sha256':sha(raw),'plaintext_bytes':len(raw),
            'ciphertext_sha256':sha(cipher),'ciphertext_bytes':len(cipher),
            'durable_encrypted_readback_verified':True}
    except Exception: raise Stop('encryption_failed','evidence') from None

def public_projection(result, manifest_proof):
    keys = ('schema_version','scope_sha256','capture_complete','diagnostic','requests_attempted',
        'complete_empty_window_observed','terminal_identity_and_input_verified',
        'rejected_before_run_proven','Actor_starts','aborts','DELETEs','item_exports',
        'hold_release_usd','ready_for_next_Actor_start','invoice_finality')
    return {**{key:result[key] for key in keys},**manifest_proof}

def execute(env):
    guard()
    if env.get('APIFY_CONTACT_READONLY_OPT_IN') != 'yes': raise Stop('opt_in_required')
    spec, validators, crypto, recipient = load_reviewed()
    output = ROOT/'capture'
    if output.exists() or output.is_symlink(): raise Stop('preflight_failed')
    temporary = env.get('RUNNER_TEMP')
    if type(temporary) is not str: raise Stop('preflight_failed')
    binary = Path(temporary)/'age-v1.3.2/age/age'
    output.mkdir(mode=0o700)
    probe = output/'preflight.age'
    encrypt_raw(b'{"named_synthetic_preflight":true}',probe,binary,recipient,crypto)
    probe.unlink()
    transport = Transport(env.get('APIFY_TOKEN'),spec)
    result = collect(transport,spec,validators,
        lambda stage,raw:encrypt_raw(raw,output/(stage+'.age'),binary,recipient,crypto))
    proof = encrypt_raw(canonical(result),output/'manifest.age',binary,recipient,crypto)
    public = public_projection(result,proof)
    crypto.durable_write(output/'recovery-public.json',canonical(public))
    return public

if __name__ == '__main__':
    if sys.argv[1:] != ['--execute']:
        print('{"mode":"offline","provider_requests":0,"Actor_starts":0,"DELETEs":0}')
    else:
        try: print(canonical(execute(os.environ)).decode())
        except Stop as error:
            print(canonical({'diagnostic':error.safe(),'Actor_starts':0,'DELETEs':0}).decode())
            sys.exit(2)
