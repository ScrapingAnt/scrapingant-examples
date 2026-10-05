"""Named synthetic six-GET acceptance cases. No provider or credential access."""
import copy
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit
import recover_google as r

TOKEN = 'NAMED_SYNTHETIC_PROVIDER_TOKEN'


class Response:
    def __init__(self, body, **headers):
        self.stream, self.status, self.closed = io.BytesIO(body), 200, False
        self.headers = {'Content-Type': 'application/json', **headers}
    def read1(self, count): return self.stream.read(count)
    def getheader(self, name): return self.headers.get(name)
    def close(self): self.closed = True


class NoEnv:
    def get(self, *args): raise AssertionError('unexpected environment access')


class GoogleRecoveryTests(unittest.TestCase):
    def setUp(self):
        isolated_guard = patch.object(r, 'RECOVERY_READY', False)
        isolated_guard.start()
        self.addCleanup(isolated_guard.stop)
        isolated_paid_guard = patch.object(r.controller, 'ACTIVE_CELL', None)
        isolated_paid_guard.start()
        self.addCleanup(isolated_paid_guard.stop)
        self.spec, self.cell, self.validators, self.crypto, self.recipient = r.load_reviewed()
        self.target = {'id': 'R' * 17, 'userId': 'U' * 17, 'actId': self.cell['actor_id'],
            'defaultDatasetId': 'D' * 17, 'defaultKeyValueStoreId': 'K' * 17,
            'defaultRequestQueueId': 'Q' * 17, 'startedAt': '2026-01-01T00:00:00.000Z',
            'finishedAt': None, 'status': 'ABORTING', 'build': self.cell['build'],
            'extraDatasetAlias': 'NAMED_SYNTHETIC_ALIAS', 'extraDatasetId': 'E' * 17}
        self.spec = {**self.spec, 'target_payload_sha256': r.base.sha(r.base.canonical(self.target))}
        native = {**self.target, 'status': 'ABORTED', 'finishedAt': '2026-01-01T00:00:10.000Z',
            'buildNumber': self.cell['build'], 'options': copy.deepcopy(self.cell['options']),
            'usageTotalUsd': 0.0025, 'storageIds': {'datasets': {'default': 'D' * 17,
                self.target['extraDatasetAlias']: 'E' * 17}, 'keyValueStores': {'default': 'K' * 17},
                'requestQueues': {'default': 'Q' * 17}}}
        native['options']['maxTotalChargeUsd'] = .5
        def meta(kind):
            field = {'dataset': 'defaultDatasetId', 'kv': 'defaultKeyValueStoreId',
                     'queue': 'defaultRequestQueueId', 'extra': 'extraDatasetId'}[kind]
            return {'id': self.target[field], 'userId': self.target['userId'],
                'actId': self.target['actId'], 'actRunId': self.target['id'], 'name': None,
                'createdAt': self.target['startedAt'], 'stats': {'storageBytes': 42},
                'urlSigningSecretKey': 'NAMED_SYNTHETIC_SIGNING_KEY'}
        self.bodies = [r.base.canonical({'data': native})]
        self.bodies += [r.base.canonical({'data': meta(k)}) for k in ('dataset', 'kv', 'queue', 'extra')]
        self.bodies += [r.base.canonical({'data': native})]

    def collect(self, bodies=None, failure=None, headers=None, persist_failure=None):
        calls, saved, responses = [], {}, []
        def opener(request, timeout):
            n = len(calls)
            calls.append(request)
            if n == failure:
                raise HTTPError(request.full_url, 403, 'NAMED_SYNTHETIC_DENIAL', {}, io.BytesIO(b'PRIVATE'))
            response = Response((self.bodies if bodies is None else bodies)[n], **(headers or {}))
            responses.append(response)
            return response
        def persist(stage, blob):
            if stage == persist_failure:
                raise r.fail('encryption_failed', 'evidence')
            saved[stage] = blob
            return {'plaintext_sha256': r.base.sha(blob), 'plaintext_bytes': len(blob),
                    'ciphertext_sha256': 'c' * 64, 'ciphertext_bytes': len(blob) + 200,
                    'durable_encrypted_readback_verified': True}
        with patch.object(r, 'RECOVERY_READY', True):
            transport = r.Transport(TOKEN, self.target, opener=opener, clock=lambda: 0)
            result = r.collect(transport, self.spec, self.cell, self.validators, persist)
        return result, calls, saved, responses

    def change(self, index, key, value):
        bodies = copy.deepcopy(self.bodies)
        obj = r.base.json.loads(bodies[index]); obj['data'][key] = value
        bodies[index] = r.base.canonical(obj)
        return bodies

    def test_closed_guard_before_env_and_network(self):
        with patch.object(r, 'RECOVERY_READY', False), patch.object(r, 'load_reviewed', side_effect=AssertionError()):
            with self.assertRaises(r.base.RecoveryError): r.execute(opt_in=True, environ=NoEnv())
            with self.assertRaises(r.base.RecoveryError): r.Transport(TOKEN, self.target)

    def test_opt_in_before_env(self):
        with patch.object(r, 'RECOVERY_READY', True), self.assertRaises(r.base.RecoveryError):
            r.execute(environ=NoEnv())

    def test_frozen_dependencies_paid_guards_and_spec(self):
        r.load_reviewed()
        with patch.object(r, 'SPEC_SHA256', 'f' * 64), self.assertRaises(r.base.RecoveryError): r.load_reviewed()
        with patch.object(r.controller, 'ACTIVE_CELL', 'breadth-r1-google-search'), self.assertRaises(r.base.RecoveryError): r.load_reviewed()
        with patch.object(r.base, 'RECOVERY_READY', True), self.assertRaises(r.base.RecoveryError): r.load_reviewed()

    def test_offline_dependency_pin_normalizes_only_reviewed_paid_assignment(self):
        name = 'apify-breadth-study/controller.py'
        blob = (r.ROOT.parent / name).read_bytes()
        normalized = r.base.re.sub(rb'^ACTIVE_CELL = (None|\'[^\'\n]+\')$',
                                  b'ACTIVE_CELL = None', blob, flags=r.base.re.MULTILINE)
        expected = self.spec['dependencies_sha256'][name]
        for cell in r.controller.load_plan()['cells']:
            active = normalized.replace(b'ACTIVE_CELL = None',
                                        ('ACTIVE_CELL = ' + repr(cell['cell_id'])).encode())
            self.assertEqual(r.base.dependency_digest(name, active), expected)
        for replacement in (b"ACTIVE_CELL = 'NAMED_SYNTHETIC_UNREVIEWED_CELL'",
                            b'ACTIVE_CELL = True', b'ACTIVE_CELL=None',
                            b'ACTIVE_CELL = None\nACTIVE_CELL = None'):
            with self.assertRaises(ValueError):
                r.base.dependency_digest(name, normalized.replace(b'ACTIVE_CELL = None', replacement))
        self.assertNotEqual(r.base.dependency_digest(name, normalized + b'\n# synthetic edit\n'), expected)

    def test_google_load_reviewed_uses_narrow_dependency_pin(self):
        name = 'apify-breadth-study/controller.py'
        original = Path.read_bytes
        blob = original(r.ROOT.parent / name)
        normalized = r.base.re.sub(rb'^ACTIVE_CELL = (None|\'[^\'\n]+\')$',
                                  b'ACTIVE_CELL = None', blob, flags=r.base.re.MULTILINE)
        active = normalized.replace(b'ACTIVE_CELL = None', b"ACTIVE_CELL = 'breadth-r1-ai-web'")
        def synthetic_read(path):
            return active if path == r.ROOT.parent / name else original(path)
        with patch.object(Path, 'read_bytes', synthetic_read):
            r.load_reviewed()
        def altered_read(path):
            return active + b'\n# synthetic source alteration\n' if path == r.ROOT.parent / name else original(path)
        with patch.object(Path, 'read_bytes', altered_read), self.assertRaises(r.base.RecoveryError):
            r.load_reviewed()

    def test_live_google_recovery_rejects_active_paid_guard_before_env_or_transport(self):
        with patch.object(r, 'RECOVERY_READY', True), \
             patch.object(r.controller, 'ACTIVE_CELL', 'breadth-r1-ai-web'), \
             patch.object(r, 'Transport', side_effect=AssertionError('unexpected transport')) as transport:
            with self.assertRaises(r.base.RecoveryError) as caught:
                r.execute(opt_in=True, environ=NoEnv())
            self.assertEqual(caught.exception.category, 'source_invalid')
            transport.assert_not_called()

    def test_target_exact_hash_fields_ids_and_alias(self):
        blob = r.base.canonical(self.target).decode()
        self.assertEqual(r.target_from_data(blob, self.spec, self.validators, self.cell), self.target)
        for key, value in [('id', 'INVALID_ID'), ('extraDatasetId', 'D' * 17), ('extraDatasetAlias', 'default'),
                           ('finishedAt', '2026-01-01T00:00:10Z'), ('status', 'ABORTED'), ('token', TOKEN)]:
            changed = r.base.canonical({**self.target, key: value}).decode()
            committed = {**self.spec, 'target_payload_sha256': r.base.sha(changed.encode())}
            with self.assertRaises(r.base.RecoveryError): r.target_from_data(changed, committed, self.validators, self.cell)
        with self.assertRaises(r.base.RecoveryError): r.target_from_data(blob + '\n', self.spec, self.validators, self.cell)

    def test_exact_six_get_routes_no_discovery_items_or_mutation(self):
        value, calls, saved, responses = self.collect()
        self.assertTrue(value['capture_complete']); self.assertTrue(value['terminal_verified'])
        self.assertEqual(list(saved), list(r.STAGES)); self.assertEqual(len(calls), 6)
        self.assertEqual([urlsplit(x.full_url).path for x in calls], ['/v2/actor-runs/' + 'R' * 17,
            '/v2/datasets/' + 'D' * 17, '/v2/key-value-stores/' + 'K' * 17,
            '/v2/request-queues/' + 'Q' * 17, '/v2/datasets/' + 'E' * 17, '/v2/actor-runs/' + 'R' * 17])
        self.assertTrue(all(x.get_method() == 'GET' and x.data is None for x in calls))
        self.assertTrue(all(x.closed for x in responses)); self.assertFalse(value['ready_for_next_cell'])
        for request in calls:
            self.assertEqual(request.get_header('Authorization'), 'Bearer ' + TOKEN)
            self.assertNotIn(TOKEN, request.full_url)

    def test_aborting_stops_after_one_get_and_preserves_response(self):
        bodies = self.change(0, 'status', 'ABORTING')
        value, calls, saved, _ = self.collect(bodies)
        self.assertEqual(len(calls), 1); self.assertEqual(list(saved), ['run'])
        self.assertFalse(value['terminal_verified']); self.assertFalse(value['capture_complete'])

    def test_wrong_run_owner_actor_build_options_or_extra_alias_stop(self):
        for key, value in [('id', 'F' * 17), ('userId', 'F' * 17), ('actId', 'F' * 17),
                           ('buildNumber', '0.0.1'), ('options', {}), ('storageIds', {})]:
            result, calls, saved, _ = self.collect(self.change(0, key, value))
            self.assertEqual(len(calls), 1); self.assertFalse(result['capture_complete']); self.assertIn('run', saved)

    def test_store_owner_or_identity_failure_never_reads_next_route(self):
        for index in range(1, 5):
            for key in ('id', 'userId'):
                value, calls, saved, _ = self.collect(self.change(index, key, 'F' * 17))
                self.assertEqual(len(calls), index + 1); self.assertFalse(value['capture_complete'])
                self.assertIn(r.STAGES[index], saved)

    def test_default_role_not_inferred_unnamed_and_extra_not_inferred_named(self):
        bodies = self.change(1, 'name', 'NAMED_SYNTHETIC_DEFAULT_NAME')
        value, _, _, _ = self.collect(bodies)
        self.assertTrue(value['stores']['dataset']['named'])
        self.assertFalse(value['stores']['extra']['named'])
        self.assertTrue(value['original_storage_policy_failure_preserved'])
        self.assertFalse(value['stores']['extra']['all_named_storage_access_absence_proven'])

    def test_missing_metadata_fields_remain_unknown_and_prior_run_not_followed(self):
        bodies = copy.deepcopy(self.bodies)
        obj = r.base.strict(bodies[4]); obj['data'].pop('name'); obj['data'].pop('stats')
        obj['data']['actRunId'] = 'P' * 17; obj['data'].pop('actId')
        bodies[4] = r.base.canonical(obj)
        value, calls, _, _ = self.collect(bodies)
        self.assertEqual(len(calls), 6); self.assertTrue(value['capture_complete'])
        extra = value['stores']['extra']
        self.assertIsNone(extra['named']); self.assertIsNone(extra['storage_bytes'])
        self.assertFalse(extra['associated_run_matches']); self.assertIsNone(extra['associated_actor_matches'])

    def test_first_and_fresh_terminal_identity_status_and_finish_match(self):
        for key, change in [('id', 'F' * 17), ('status', 'FAILED'), ('finishedAt', '2026-01-01T00:00:11.000Z')]:
            value, calls, saved, _ = self.collect(self.change(5, key, change))
            self.assertEqual(len(calls), 6); self.assertFalse(value['capture_complete']); self.assertIn('meter', saved)

    def test_missing_zero_and_above_cap_meters_are_distinct_no_double_count(self):
        for amount, valid in [(None, False), (0, True), (.75, True)]:
            value, _, _, _ = self.collect(self.change(5, 'usageTotalUsd', amount))
            self.assertTrue(value['capture_complete']); self.assertEqual(value['fresh_meter_valid'], valid)
            expected = None if amount is None else str(amount)
            self.assertEqual(value['fresh_run_meter']['usage_total_usd'], expected)
            self.assertEqual(value['hold_release_usd'], '0'); self.assertFalse(value['ready_for_next_cell'])

    def test_public_output_hides_native_identity_alias_name_usage_and_signing_keys(self):
        value, _, saved, _ = self.collect()
        public = r.public_projection(value, {'plaintext_sha256': 'p' * 64, 'ciphertext_sha256': 'c' * 64})
        text = r.base.canonical(public).decode()
        for marker in [TOKEN, 'R' * 17, self.target['extraDatasetAlias'], 'NAMED_SYNTHETIC_SIGNING_KEY', '0.0025']:
            self.assertNotIn(marker, text)
        self.assertIn(b'NAMED_SYNTHETIC_SIGNING_KEY', saved['extra'])

    def test_access_failure_each_stage_no_retry_or_following_get(self):
        for index in range(6):
            value, calls, _, _ = self.collect(failure=index)
            self.assertEqual(len(calls), index + 1)
            self.assertEqual(value['capture_diagnostic'], {'category': 'access_denied', 'stage': r.STAGES[index], 'http_status': 403})

    def test_body_limit_type_compression_and_encryption_failures_stop(self):
        bodies = copy.deepcopy(self.bodies); bodies[0] = b'x' * 131073
        for kwargs in ({'bodies': bodies}, {'headers': {'Content-Type': 'text/plain'}},
                       {'headers': {'Content-Encoding': 'gzip'}}, {'persist_failure': 'run'}):
            value, calls, _, _ = self.collect(**kwargs)
            self.assertEqual(len(calls), 1); self.assertFalse(value['capture_complete'])

    def test_closed_after_transport_and_out_of_order_or_seventh_route_rejected(self):
        with patch.object(r, 'RECOVERY_READY', True):
            transport = r.Transport(TOKEN, self.target, clock=lambda: 0)
            with self.assertRaises(r.base.RecoveryError): transport.route('extra')
            transport.calls = 6
            with self.assertRaises(r.base.RecoveryError): transport.route('run')
            transport.calls = 0
        with self.assertRaises(r.base.RecoveryError): transport.route('run')

    def test_shared_deadline_and_redirect_no_fallback(self):
        with patch.object(r, 'RECOVERY_READY', True):
            clock = [0]
            transport = r.Transport(TOKEN, self.target, opener=lambda *a, **k: self.fail('network reached'), clock=lambda: clock[0])
            clock[0] = 150
            with self.assertRaises(r.base.RecoveryError): transport.get('run')
        redirect = r.base.NoRedirect()
        self.assertIsNone(redirect.redirect_request(None, None, 302, None, {}, 'https://NAMED_SYNTHETIC_FOREIGN.example'))

    def test_workflow_encrypted_allowlist_and_existing_secret_only(self):
        text = (r.ROOT.parents[1] / '.github/workflows/apify-google-readonly-recovery.yml').read_text()
        self.assertIn('secrets.APIFY_TOKEN', text); self.assertIn('secrets.APIFY_GOOGLE_RECOVERY_TARGET', text)
        self.assertIn('github.run_attempt == 1', text); self.assertIn('persist-credentials: false', text)
        self.assertNotIn('/raw.age', text); self.assertNotIn('/log.age', text)
        self.assertIn('/extra.age', text); self.assertNotIn('controller.py --execute', text)


if __name__ == '__main__':
    unittest.main()
