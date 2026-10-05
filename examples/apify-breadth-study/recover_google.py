"""Closed six-GET recovery of one committed Google run and registered stores.

Existing Actions authentication only. No Actor start, abort, listing, item read,
retry, redirect, credential creation or store mutation. Native bodies, including
any metadata signing keys, stay age-encrypted. Original storage failure persists.
"""
import copy
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from urllib.request import build_opener
import controller
import recover_existing as base

ROOT = Path(__file__).resolve().parent
RECOVERY_READY = True
SPEC_SHA256 = 'da54dfc87f2f5b950275be137dbc11c279535e663172291a056b694477a6afae'
STAGES = ('run', 'dataset', 'kv', 'queue', 'extra', 'meter')
TARGET_FIELDS = base.TARGET_FIELDS + ('extraDatasetAlias', 'extraDatasetId')


def fail(category, stage='preflight', status=None):
    error = base.RecoveryError(category, stage, status)
    error.stage = stage if stage in STAGES + ('preflight', 'evidence') else 'preflight'
    return error


def guard():
    if RECOVERY_READY is not True:
        raise fail('guard_closed')


def load_reviewed():
    try:
        path = ROOT / 'google-recovery-scope.json'
        if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= 8192:
            raise ValueError()
        blob = path.read_bytes()
        if base.sha(blob) != SPEC_SHA256:
            raise ValueError()
        spec = base.strict(blob)
        if (spec['schema_version'] != 1 or spec['cell_id'] != 'breadth-r1-google-search'
                or spec['maximum_GETs'] != 6 or spec['provider_mutations'] != 0
                or spec['target_secret_name'] != 'APIFY_GOOGLE_RECOVERY_TARGET'
                or spec['body_limit_bytes'] != 131072 or spec['transport_wall_seconds'] != 150
                or spec['route_timeout_seconds'] != 20 or controller.ACTIVE_CELL is not None
                or base.RECOVERY_READY is not False):
            raise ValueError()
        deps = {'apify-breadth-study/controller.py', 'apify-breadth-study/breadth-plan.json',
                'apify-breadth-study/recover_existing.py', 'apify-breadth-study/storage_policy.py',
                'apify-study/runner.py', 'apify-study/billing_projection.py',
                'apify-sustained/evidence_transport.py', 'apify-sustained/recipient.txt'}
        if set(spec['dependencies_sha256']) != deps:
            raise ValueError()
        for name, digest in spec['dependencies_sha256'].items():
            p = ROOT.parent / name
            if p.is_symlink() or not p.is_file() or base.sha(p.read_bytes()) != digest:
                raise ValueError()
        cell = next(c for c in controller.load_plan()['cells'] if c['cell_id'] == spec['cell_id'])
        if (cell['actor'] != 'apify/google-search-scraper' or cell['build'] != '0.0.455'
                or cell['options']['maxTotalChargeUsd'] != '0.50'):
            raise ValueError()
        validators, crypto = controller.load_sources()
        if any(getattr(validators, k) is not False for k in ('RUNNER_READY', 'GRAPH_READY', 'CONCURRENCY_READY')):
            raise ValueError()
        recipient = (ROOT.parent / 'apify-sustained/recipient.txt').read_text().strip()
        if re.fullmatch(r'age1[a-z0-9]{58}', recipient) is None:
            raise ValueError()
        return spec, cell, validators, crypto, recipient
    except Exception:
        raise fail('source_invalid') from None


def target_from_data(value, spec, validators, cell):
    try:
        if type(value) is not str or not 1 <= len(value.encode()) <= 8192:
            raise ValueError()
        if base.sha(value.encode()) != spec['target_payload_sha256']:
            raise ValueError()
        target = base.strict(value.encode())
        if set(target) != set(TARGET_FIELDS):
            raise ValueError()
        for field in base.TARGET_FIELDS[:6] + ('extraDatasetId',):
            if type(target[field]) is not str or re.fullmatch(r'[A-Za-z0-9]{17}', target[field]) is None:
                raise ValueError()
        if (target['actId'] != cell['actor_id'] or target['build'] != cell['build']
                or target['status'] != 'ABORTING' or target['finishedAt'] is not None
                or type(target['extraDatasetAlias']) is not str
                or re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', target['extraDatasetAlias']) is None
                or target['extraDatasetAlias'] == 'default'
                or len({target[k] for k in base.TARGET_FIELDS[3:6] + ('extraDatasetId',)}) != 4):
            raise ValueError()
        validators.timestamp(target['startedAt'])
        return target
    except Exception:
        raise fail('target_invalid') from None


def validate_run(blob, validators, cell, target, initial=None):
    data = base.strict(blob).get('data')
    try:
        identity = validators.validate_run(data, SimpleNamespace(spec=cell), initial or target)
        mapping = data.get('storageIds')
        expected = {'datasets': {'default': target['defaultDatasetId'],
                                 target['extraDatasetAlias']: target['extraDatasetId']},
                    'keyValueStores': {'default': target['defaultKeyValueStoreId']},
                    'requestQueues': {'default': target['defaultRequestQueueId']}}
        if mapping != expected:
            raise ValueError()
        if initial and (identity['status'] != initial['status'] or identity['finishedAt'] != initial['finishedAt']):
            raise ValueError()
    except Exception:
        raise fail('scope_mismatch') from None
    if identity['status'] not in validators.TERMINAL:
        raise fail('preflight_failed')
    return data, identity


def store_projection(data, stage, target, identity):
    field = {'dataset': 'defaultDatasetId', 'kv': 'defaultKeyValueStoreId',
             'queue': 'defaultRequestQueueId', 'extra': 'extraDatasetId'}[stage]
    if not isinstance(data, dict) or data.get('id') != target[field] or data.get('userId') != target['userId']:
        raise fail('scope_mismatch', stage, 200)
    name_known = 'name' in data and (data['name'] is None or type(data['name']) is str)
    stats = data.get('stats') if isinstance(data.get('stats'), dict) else {}
    size = stats.get('storageBytes')
    if type(size) is not int or size < 0:
        size = None
    inflated = stats.get('inflatedBytes')
    if type(inflated) is not int or inflated < 0:
        inflated = None
    def match(key, expected):
        return None if data.get(key) is None else data[key] == expected
    return {'role': 'extra_registered_dataset' if stage == 'extra' else 'run_default_' + stage,
        'id_and_owner_match': True, 'name_present_and_valid': name_known,
        'named': None if not name_known else data['name'] is not None,
        'name': data.get('name') if name_known else None,
        'associated_run_matches': match('actRunId', identity['id']),
        'associated_actor_matches': match('actId', identity['actId']),
        'created_at': data.get('createdAt'), 'storage_bytes': size, 'inflated_bytes': inflated,
        'all_named_storage_access_absence_proven': False, 'store_items_read': False}


class Transport(base.Transport):
    """Reuse the verified no-redirect body-bounded GET implementation only."""
    def __init__(self, token, target, *, opener=None, clock=time.monotonic):
        guard()
        if type(token) is not str or re.fullmatch(r'[A-Za-z0-9_-]{16,512}', token) is None:
            raise fail('token_unavailable')
        self._token, self.target, self.clock = token, copy.deepcopy(target), clock
        self._open = opener or build_opener(base.NoRedirect()).open
        self.deadline, self.calls, self.failed = clock() + 150, 0, False

    def __repr__(self):
        return '<bounded six-GET Google read-only transport>'

    def route(self, stage):
        guard()
        if self.failed or self.calls >= 6 or stage != STAGES[self.calls]:
            raise fail('route_invalid', stage)
        t = self.target
        if stage in ('run', 'meter'):
            path = 'actor-runs/' + t['id']
        else:
            route, field = {'dataset': ('datasets', 'defaultDatasetId'),
                'kv': ('key-value-stores', 'defaultKeyValueStoreId'),
                'queue': ('request-queues', 'defaultRequestQueueId'),
                'extra': ('datasets', 'extraDatasetId')}[stage]
            path = route + '/' + t[field]
        return 'https://api.apify.com/v2/' + path, 131072

    def get(self, stage):
        try:
            return super().get(stage)
        except base.RecoveryError as exc:
            raise fail(exc.category, stage, exc.status) from None


def collect(transport, spec, cell, validators, persist):
    value = {'schema_version': 1, 'scope_spec_sha256': SPEC_SHA256,
        'target_payload_sha256': spec['target_payload_sha256'], 'identity': None,
        'files': {}, 'reads': [], 'requests_attempted': 0, 'capture_complete': False,
        'capture_diagnostic': None, 'terminal_verified': False, 'stores': {},
        'fresh_run_meter': None, 'fresh_meter_valid': False, 'ready_for_next_cell': False,
        'original_storage_policy_failure_preserved': True, 'hold_release_usd': '0',
        'Actor_starts': 0, 'aborts': 0, 'DELETEs': 0, 'invoice_finality': False}
    stage = 'run'
    try:
        for stage in STAGES:
            blob, headers = transport.get(stage)
            # Persist exact evidence before checking it. A mismatched body cannot
            # authorize a following route; the same strict target still binds it.
            proof = persist(stage, blob)
            value['files'][stage + '.age'] = {**proof, 'headers': headers,
                'observed_at_utc': datetime.now(timezone.utc).isoformat()}
            value['reads'].append({'stage': stage, 'http_status': 200})
            if stage in ('run', 'meter'):
                data, identity = validate_run(blob, validators, cell, transport.target, value['identity'])
                value['identity'], value['terminal_verified'] = identity, True
                if stage == 'meter':
                    value['fresh_run_meter'] = controller.project_run_meter(validators, data, cell)
                    value['fresh_meter_valid'] = value['fresh_run_meter']['usage_total_usd'] is not None
            else:
                value['stores'][stage] = store_projection(base.strict(blob).get('data'), stage,
                                                        transport.target, value['identity'])
        value['capture_complete'] = True
    except Exception as exc:
        safe = exc if isinstance(exc, base.RecoveryError) else fail('scope_mismatch', stage)
        value['capture_diagnostic'] = fail(safe.category, stage, safe.status).safe()
    value['requests_attempted'] = transport.calls
    return value


def public_projection(value, proof):
    return {'schema_version': 1, 'maximum_GETs': 6, 'requests_attempted': value['requests_attempted'],
        'capture_complete': value['capture_complete'], 'capture_diagnostic': value['capture_diagnostic'],
        'ready_for_next_cell': False, 'Actor_starts': 0, 'aborts': 0, 'DELETEs': 0,
        'manifest_plaintext_sha256': proof['plaintext_sha256'],
        'manifest_ciphertext_sha256': proof['ciphertext_sha256']}


def execute(*, opt_in=False, environ=None):
    guard()
    if opt_in is not True:
        raise fail('opt_in_required')
    spec, cell, validators, crypto, recipient = load_reviewed()
    env = base.os.environ if environ is None else environ
    target = target_from_data(env.get(spec['target_secret_name']), spec, validators, cell)
    temp = env.get('RUNNER_TEMP')
    if type(temp) is not str or not Path(temp).is_absolute():
        raise fail('preflight_failed')
    output = ROOT / 'google-recovery'
    if output.exists() or output.is_symlink():
        raise fail('preflight_failed')
    output.mkdir(mode=0o700)
    binary = Path(temp) / 'age-v1.3.2/age/age'
    preflight = output / 'preflight.age'
    base.encrypt_raw(b'{"named_synthetic_preflight":true}', preflight, binary, recipient, crypto)
    preflight.unlink()
    transport = Transport(env.get('APIFY_TOKEN'), target)
    value = collect(transport, spec, cell, validators,
        lambda stage, blob: base.encrypt_raw(blob, output / (stage + '.age'), binary, recipient, crypto))
    proof = base.encrypt_raw(base.canonical(value), output / 'manifest.age', binary, recipient, crypto)
    public = public_projection(value, proof)
    crypto.durable_write(output / 'recovery-public.json', base.canonical(public))
    return public


if __name__ == '__main__':
    if sys.argv[1:] != ['--execute']:
        print('{"mode":"offline","provider_requests":0,"Actor_starts":0,"DELETEs":0}')
    else:
        try:
            result = execute(opt_in=True)
            print(base.json.dumps(result, sort_keys=True))
            raise SystemExit(0 if result['capture_complete'] else 1)
        except base.RecoveryError as exc:
            print(base.json.dumps({'diagnostic': exc.safe(), 'Actor_starts': 0, 'DELETEs': 0}))
            raise SystemExit(1)
        except Exception:
            print('{"diagnostic":{"category":"preflight_failed"},"Actor_starts":0,"DELETEs":0}')
            raise SystemExit(1)
