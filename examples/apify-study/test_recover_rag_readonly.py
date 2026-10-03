"""Offline synthetic tests; no provider requests or owner decryption key."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import evidence_transport as crypto
import runner
import recover_rag_readonly as recovery


TOKEN = 'OFFLINE_SECRET_NEVER_REAL'
KINDS = ('dataset', 'kv', 'queue')


def run_data():
    return {'id': 'OriginalRunSynthetic', 'userId': 'OwnerSynthetic',
        'actId': recovery.ACTOR_ID, 'defaultDatasetId': 'DatasetSynthetic',
        'defaultKeyValueStoreId': 'KvSynthetic', 'defaultRequestQueueId': 'QueueSynthetic',
        'status': 'SUCCEEDED', 'startedAt': '2026-10-02T21:20:10.357Z',
        'finishedAt': '2026-10-02T21:20:20.743Z', 'buildNumber': '1.0.30',
        'options': {'build': '1.0.30', 'memoryMbytes': 8192, 'timeoutSecs': 120,
            'maxTotalChargeUsd': 0.08, 'restartOnError': False}}


def listing(data=None):
    rows = [run_data()] if data is None else data
    return {'data': {'total': len(rows), 'offset': 0, 'limit': 5, 'desc': False,
        'count': len(rows), 'items': rows}}


def metadata(kind, data=None):
    data = run_data() if data is None else data
    field = runner.STORES[kind][0]
    return {'data': {'id': data[field], 'userId': data['userId'], 'actRunId': data['id'],
        'actId': data['actId'], 'name': None, 'createdAt': data['startedAt'],
        'stats': {'storageBytes': 1866 if kind == 'kv' else 0,
            'readCount': 1, 'writeCount': 2}, 'itemCount': 1,
        'urlSigningSecretKey': TOKEN, 'signedUrl': 'https://invalid.test/?token='+TOKEN,
        'profile': {'email': TOKEN}, 'generalAccess': 'FOLLOW_USER_SETTING'}}


class FakeTransport:
    def __init__(self, replies=None):
        self.replies = replies or [listing(), {'data': run_data()}, *[metadata(k) for k in KINDS]]
        self.calls = []
        self.bound = None
    def get(self, stage, reference=None):
        self.calls.append((stage, reference))
        value = self.replies[len(self.calls)-1]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)
    def bind_identity(self, identity):
        self.bound = copy.deepcopy(identity)


class Response:
    status = 200
    def __init__(self, body, status=200, content_type='application/json', clock=None, step=0):
        self.body = body
        self.status = status
        self.content_type = content_type
        self.offset = 0
        self.clock = clock
        self.step = step
        self.read_calls = 0
        self.closed = False
    def getheader(self, _):
        return self.content_type
    def read(self, *_):
        raise AssertionError('unbounded read must not be used')
    def read1(self, size):
        self.read_calls += 1
        if self.clock is not None:
            self.clock[0] += self.step
        part = self.body[self.offset:self.offset+size]
        self.offset += len(part)
        return part
    def close(self):
        self.closed = True
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.close()


class Opener:
    def __init__(self, responses, clock=None, open_step=0):
        self.responses = responses
        self.calls = []
        self.clock = clock
        self.open_step = open_step
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.clock is not None:
            self.clock[0] += self.open_step
        value = self.responses[len(self.calls)-1]
        if isinstance(value, Exception):
            raise value
        return value


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cell = recovery.load_cell()
    def setUp(self):
        self.identity = runner.validate_run(run_data(), self.cell)
        self.pins = patch.multiple(recovery,
            TARGET_RUN_SHA256=hashlib.sha256(run_data()['id'].encode()).hexdigest(),
            ORIGINAL_SCOPE_SHA256=runner.scope_commitment(self.identity))
        self.pins.start()
        self.addCleanup(self.pins.stop)

    def test_exact_five_gets_and_normalized_private_scope(self):
        transport = FakeTransport()
        evidence = recovery.recover(transport, self.cell)
        self.assertTrue(evidence['complete'])
        self.assertEqual([s for s, _ in transport.calls], ['list', 'run', *KINDS])
        self.assertEqual(evidence['recovery_identity'], self.identity)
        self.assertEqual(set(evidence['recovery_identity']), set(runner.IDENTITY_FIELDS) |
            {'startedAt', 'finishedAt', 'build', 'options', 'status'})
        self.assertEqual(evidence['metadata_verified_count'], 3)
        serialized = runner.canonical(evidence).decode()
        self.assertNotIn(TOKEN, serialized)
        for key in ('urlSigningSecretKey', 'signedUrl', 'profile', 'generalAccess', 'usageTotalUsd'):
            self.assertNotIn(key, serialized)
        self.assertEqual(set(evidence['storage']['dataset']),
            {'id', 'userId', 'actRunId', 'actId', 'name', 'createdAt', 'stats'})

    def test_no_target_stops_after_list_without_fallback(self):
        wrong = run_data(); wrong['id'] = 'UnrelatedSynthetic'
        transport = FakeTransport([listing([wrong])])
        evidence = recovery.recover(transport, self.cell)
        self.assertEqual(len(transport.calls), 1)
        self.assertFalse(evidence['complete'])
        self.assertEqual(evidence['diagnostic']['category'], 'target_not_found')
        self.assertNotIn(wrong['id'], runner.canonical(evidence).decode())

    def test_duplicate_or_malformed_list_is_not_expanded(self):
        invalid = [listing([run_data(), run_data()]), listing([run_data()]*6),
            {'data': {'items': [run_data()]}}, listing()]
        invalid[-1]['data']['count'] = True
        for reply in invalid:
            with self.subTest(reply_type=type(reply).__name__):
                transport = FakeTransport([reply])
                result = recovery.recover(transport, self.cell)
                self.assertFalse(result['complete'])
                self.assertEqual(len(transport.calls), 1)

    def test_list_target_requires_actor_and_inclusive_window(self):
        for field, value in [('actId', 'ForeignActor'), ('startedAt', '2026-10-02T21:19:59Z')]:
            wrong = run_data(); wrong[field] = value
            transport = FakeTransport([listing([wrong])])
            self.assertFalse(recovery.recover(transport, self.cell)['complete'])
            self.assertEqual(len(transport.calls), 1)

    def test_known_hash_can_be_selected_from_bounded_incomplete_page(self):
        reply = listing(); reply['data']['total'] = 6
        transport = FakeTransport([reply, {'data': run_data()}, *[metadata(k) for k in KINDS]])
        result = recovery.recover(transport, self.cell)
        self.assertTrue(result['complete'])
        self.assertFalse(result['list_page_complete'])
        self.assertEqual(len(transport.calls), 5)

    def test_exact_scope_hash_required_before_any_store_get(self):
        with patch.object(recovery, 'ORIGINAL_SCOPE_SHA256', '0'*64):
            transport = FakeTransport()
            result = recovery.recover(transport, self.cell)
        self.assertEqual(len(transport.calls), 2)
        self.assertFalse(result['scope_verified'])
        self.assertEqual(result['partial_run_identity']['id'], self.identity['id'])
        self.assertIsNone(result['recovery_identity'])

    def test_all_original_run_identity_options_and_time_branches_fail_closed(self):
        changes = [('id', 'ForeignRun'), ('userId', 'ForeignOwner'),
            ('defaultDatasetId', 'ForeignDataset'), ('buildNumber', '1.0.31'),
            ('status', 'RUNNING'), ('startedAt', '2026-10-02T21:20:11Z'),
            ('finishedAt', '2026-10-02T21:20:22Z')]
        for field, value in changes:
            with self.subTest(field=field):
                data = run_data(); data[field] = value
                transport = FakeTransport([listing(), {'data': data}])
                result = recovery.recover(transport, self.cell)
                self.assertFalse(result['complete'])
                self.assertEqual(len(transport.calls), 2)
                self.assertEqual(result['metadata_verified_count'], 0)
        data = run_data(); data['options']['memoryMbytes'] = 4096
        result = recovery.recover(FakeTransport([listing(), {'data': data}]), self.cell)
        self.assertFalse(result['scope_verified'])

    def test_ownership_name_and_creation_mismatch_stop_without_later_reads(self):
        for field, value in [('id', 'ForeignStore'), ('userId', 'ForeignOwner'),
            ('actRunId', 'ForeignRun'), ('actId', 'ForeignActor'), ('name', 'SharedName'),
            ('createdAt', '2026-10-03T00:00:00Z')]:
            with self.subTest(field=field):
                reply = metadata('dataset'); reply['data'][field] = value
                transport = FakeTransport([listing(), {'data': run_data()}, reply])
                result = recovery.recover(transport, self.cell)
                self.assertEqual(len(transport.calls), 3)
                self.assertEqual(result['metadata_verified_count'], 0)
                self.assertFalse(result['complete'])
                self.assertNotIn('SharedName', runner.canonical(result).decode())

    def test_old_terminal_capture_does_not_apply_cleanup_expiry(self):
        result = recovery.recover(FakeTransport(), self.cell)
        self.assertTrue(result['complete'])
        self.assertEqual(result['recovery_identity']['finishedAt'], '2026-10-02T21:20:20.743Z')
        self.assertEqual(result['deletions'], 0)

    def test_403_stops_and_preserves_already_verified_metadata(self):
        transport = FakeTransport([listing(), {'data': run_data()}, metadata('dataset'),
            recovery.RecoveryError('access_denied', 'kv', 403)])
        result = recovery.recover(transport, self.cell)
        self.assertEqual(len(transport.calls), 4)
        self.assertEqual(result['metadata_verified_count'], 1)
        self.assertEqual(result['diagnostic']['http_status'], 403)
        self.assertIsNotNone(result['recovery_identity'])

    def test_arbitrary_exception_messages_never_retained(self):
        result = recovery.recover(FakeTransport([RuntimeError(TOKEN)]), self.cell)
        self.assertNotIn(TOKEN, runner.canonical(result).decode())
        self.assertEqual(result['diagnostic']['category'], 'transport_error')

    def test_public_projection_has_no_provider_ids_or_private_partial_fields(self):
        result = recovery.recover(FakeTransport(), self.cell)
        result['raw'] = {'token': TOKEN}
        public = recovery.public_result(result, {'plaintext_sha256': 'a'*64,
            'ciphertext_sha256': 'b'*64, 'remote_file_readback_verified': True})
        serialized = runner.canonical(public).decode()
        for value in [TOKEN, *[self.identity[k] for k in runner.IDENTITY_FIELDS]]:
            self.assertNotIn(value, serialized)
        self.assertNotIn('storage', public)
        self.assertEqual(public['provider_start_attempts'], 0)
        self.assertEqual(public['deletions'], 0)

    def test_guard_precedes_environment_files_and_crypto(self):
        with patch.object(recovery, 'RECOVERY_READY', False), \
                patch.object(recovery, 'load_cell', side_effect=AssertionError()), \
                patch.object(recovery, 'private_paths', side_effect=AssertionError()), \
                patch.object(recovery.os, 'environ', new=UnreadableEnvironment()):
            with self.assertRaises(recovery.RecoveryError) as caught:
                recovery.execute()
        self.assertEqual(caught.exception.category, 'guard_closed')

    def test_preflight_failure_precedes_token_lookup_and_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            env = TrackedEnvironment(temp)
            with patch.object(recovery, 'RECOVERY_READY', True), \
                    patch.object(recovery, 'private_paths', return_value=(Path(temp), Path('/synthetic/age'))), \
                    patch.object(recovery.crypto, 'encrypt_capture', side_effect=crypto.TransportError()), \
                    patch.object(recovery, 'HttpTransport', side_effect=AssertionError()):
                with self.assertRaises(recovery.RecoveryError):
                    recovery.execute(env)
            self.assertNotIn('APIFY_TOKEN', env.reads)

    def test_fixed_plan_and_recipient_failure_precede_token(self):
        for helper in ('load_cell', 'load_recipient'):
            env = TrackedEnvironment('/tmp/synthetic')
            with patch.object(recovery, 'RECOVERY_READY', True), \
                    patch.object(recovery, helper, side_effect=recovery.RecoveryError('unreviewed_source', 'preflight')):
                with self.assertRaises(recovery.RecoveryError):
                    recovery.execute(env)
            self.assertNotIn('APIFY_TOKEN', env.reads)

    def test_actual_fixed_plan_and_recipient_sources_validate(self):
        self.assertEqual(recovery.load_cell().cell_id, recovery.CELL_ID)
        self.assertTrue(recovery.load_recipient().startswith('age1'))

    def test_execute_encrypts_partial_denial_after_preflight_and_before_public_write(self):
        recipient = recovery.load_recipient()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); env = TrackedEnvironment(temp); payloads = []
            def encrypt(payload, destination, binary, value):
                if not payloads:
                    self.assertNotIn('APIFY_TOKEN', env.reads)
                self.assertEqual(value, recipient)
                payloads.append(crypto.json_payload(payload))
                cipher = b'age-encryption.org/v1\nsynthetic-cipher-'+str(len(payloads)).encode()
                crypto.durable_write(destination, cipher)
                return {'plaintext_sha256': crypto.digest(payload), 'ciphertext_sha256': crypto.digest(cipher),
                    'remote_file_readback_verified': True}
            transport = FakeTransport([listing(), {'data': run_data()}, metadata('dataset'),
                recovery.RecoveryError('access_denied', 'kv', 403)])
            with patch.object(recovery, 'RECOVERY_READY', True), \
                    patch.object(recovery, 'ROOT', folder), patch.object(recovery, 'load_cell', return_value=self.cell), \
                    patch.object(recovery, 'load_recipient', return_value=recipient), \
                    patch.object(recovery, 'private_paths', return_value=(folder, Path('/synthetic/age'))), \
                    patch.object(recovery.crypto, 'encrypt_capture', side_effect=encrypt), \
                    patch.object(recovery, 'HttpTransport', return_value=transport):
                public = recovery.execute(env)
            self.assertEqual(len(payloads), 2)
            self.assertEqual(payloads[1]['recovery_identity'], self.identity)
            self.assertEqual(payloads[1]['metadata_verified_count'], 1)
            self.assertEqual(public['diagnostic']['http_status'], 403)
            self.assertFalse(public['complete'])
            blob = (folder/'rag-recovery-public.json').read_bytes()
            self.assertNotIn(TOKEN.encode(), blob)
            for key in runner.IDENTITY_FIELDS:
                self.assertNotIn(self.identity[key].encode(), blob)
            self.assertFalse((folder/'rag-recovery-preflight.age').exists())

    def test_partial_foreign_ids_and_unverified_associations_are_not_retained(self):
        data = run_data(); data['id'] = 'ForeignRun'; data['userId'] = 'ForeignOwner'
        data['defaultDatasetId'] = 'ForeignDataset'
        partial = recovery.partial_run_identity(data)
        for field in ('id', 'userId', 'defaultDatasetId', 'defaultKeyValueStoreId', 'defaultRequestQueueId'):
            self.assertIsNone(partial[field])
        self.assertNotIn('Foreign', runner.canonical(partial).decode())


class UnreadableEnvironment:
    def get(self, *_):
        raise AssertionError('environment must remain unread')


class TrackedEnvironment(dict):
    def __init__(self, temp):
        super().__init__(RUNNER_TEMP=temp, APIFY_TOKEN=TOKEN)
        self.reads = []
    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.cell = recovery.load_cell()
        self.identity = runner.validate_run(run_data(), self.cell)
        self.pins = patch.multiple(recovery,
            TARGET_RUN_SHA256=hashlib.sha256(run_data()['id'].encode()).hexdigest(),
            ORIGINAL_SCOPE_SHA256=runner.scope_commitment(self.identity))
        self.pins.start(); self.addCleanup(self.pins.stop)

    def transport(self, values, **kwargs):
        opener = Opener(values, kwargs.get('clock_value'), kwargs.pop('open_step', 0))
        kwargs.pop('clock_value', None)
        return recovery.HttpTransport(TOKEN, opener=opener, **kwargs), opener

    def test_reviewed_ten_second_routes_and_fifty_second_wall(self):
        self.assertEqual(recovery.REQUEST_TIMEOUT_SECONDS, 10)
        self.assertEqual(recovery.TRANSPORT_WALL_SECONDS, 50)
        clock = [0.0]
        transport, opener = self.transport([], clock=lambda: clock[0])
        clock[0] = 50
        with self.assertRaises(recovery.RecoveryError) as caught:
            transport.get('list')
        self.assertEqual(caught.exception.category, 'deadline_exceeded')
        self.assertEqual(len(opener.calls), 0)

    def test_fixed_routes_header_token_and_exact_five_call_budget(self):
        values = [listing(), {'data': run_data()}, *[metadata(k) for k in KINDS]]
        transport, opener = self.transport([Response(runner.canonical(v)) for v in values])
        self.assertTrue(recovery.recover(transport, self.cell)['complete'])
        requests = [v[0] for v in opener.calls]
        self.assertEqual(len(requests), 5)
        for request in requests:
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(urlsplit(request.full_url).netloc, 'api.apify.com')
            self.assertNotIn(TOKEN, request.full_url)
            self.assertEqual(request.get_header('Authorization'), 'Bearer '+TOKEN)
        first = urlsplit(requests[0].full_url)
        self.assertEqual(first.path, '/v2/actors/'+recovery.ACTOR_ID+'/runs')
        self.assertEqual(parse_qs(first.query), {'limit': ['5'], 'offset': ['0'], 'desc': ['false'],
            'startedAfter': [recovery.STARTED_AFTER], 'startedBefore': [recovery.STARTED_BEFORE]})
        self.assertFalse(any(urlsplit(r.full_url).query for r in requests[1:]))
        with self.assertRaises(recovery.RecoveryError):
            transport.get('queue', self.identity['defaultRequestQueueId'])
        self.assertEqual(len(opener.calls), 5)

    def test_foreign_run_wrong_order_and_arbitrary_route_rejected_before_open(self):
        transport, opener = self.transport([])
        for stage, reference in [('run', 'ForeignRun'), ('dataset', 'DatasetSynthetic'),
                ('https://evil.invalid/', None), ('users', None), ('delete', None)]:
            with self.subTest(stage=stage):
                with self.assertRaises(recovery.RecoveryError):
                    transport.get(stage, reference)
        self.assertEqual(opener.calls, [])

    def test_metadata_reads_require_bound_exact_scope(self):
        transport, opener = self.transport([Response(runner.canonical(listing())), Response(b'{"data":{}}')])
        transport.get('list'); transport.get('run', run_data()['id'])
        with self.assertRaises(recovery.RecoveryError):
            transport.get('dataset', self.identity['defaultDatasetId'])
        foreign = copy.deepcopy(self.identity); foreign['userId'] = 'ForeignOwner'
        with self.assertRaises(recovery.RecoveryError):
            transport.bind_identity(foreign)
        self.assertEqual(len(opener.calls), 2)

    def test_http_403_400_and_redirect_errors_never_read_raw_body_or_retry(self):
        for status in (403, 400, 302):
            body = Response(TOKEN.encode())
            error = HTTPError('https://invalid.test/'+TOKEN, status, TOKEN, {}, body)
            transport, opener = self.transport([error])
            with self.assertRaises(recovery.RecoveryError) as caught:
                transport.get('list')
            self.assertEqual(caught.exception.http_status, status)
            self.assertEqual(body.read_calls, 0)
            self.assertEqual(len(opener.calls), 1)
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_no_redirect_handler(self):
        self.assertIsNone(recovery.NoRedirect().redirect_request(None, None, 302, TOKEN, {}, 'https://invalid.test'))

    def test_body_limit_invalid_json_utf8_duplicate_and_html_are_fixed_errors(self):
        values = [(b' '*131073, 'application/json'), (b'{', 'application/json'),
            (b'{"data":1,"data":2}', 'application/json'), (b'\xff', 'application/json'),
            (b'{"data":NaN}', 'application/json'), (TOKEN.encode(), 'text/html')]
        for body, content_type in values:
            with self.subTest(content_type=content_type, size=len(body)):
                response = Response(body, content_type=content_type)
                transport, opener = self.transport([response])
                with self.assertRaises(recovery.RecoveryError) as caught:
                    transport.get('list')
                self.assertEqual(caught.exception.http_status, 200)
                self.assertNotIn(TOKEN, str(caught.exception))
                self.assertTrue(response.closed)
                self.assertEqual(len(opener.calls), 1)

    def test_trickle_and_open_overrun_stop_on_route_deadline(self):
        for step, open_step in [(26, 0), (0, 51)]:
            clock = [0.0]
            response = Response(b' '*8193, clock=clock, step=step)
            transport, opener = self.transport([response], clock=lambda: clock[0],
                clock_value=clock, open_step=open_step)
            with self.assertRaises(recovery.RecoveryError) as caught:
                transport.get('list')
            self.assertEqual(caught.exception.category, 'deadline_exceeded')
            self.assertLessEqual(response.read_calls, 2)
            self.assertEqual(len(opener.calls), 1)

    def test_json_parse_overrun_retains_no_decoded_raw_response(self):
        clock = [0.0]
        transport, opener = self.transport([Response(b'{"data":{}}')], clock=lambda: clock[0])
        original = crypto.json_payload
        def late_parse(blob):
            result = original(blob); clock[0] = 51; return result
        with patch.object(recovery.crypto, 'json_payload', side_effect=late_parse):
            with self.assertRaises(recovery.RecoveryError) as caught:
                transport.get('list')
        self.assertEqual(caught.exception.category, 'deadline_exceeded')
        self.assertEqual(len(opener.calls), 1)

    def test_connection_error_and_bad_token_do_not_retry_or_leak(self):
        transport, opener = self.transport([URLError(TOKEN)])
        with self.assertRaises(recovery.RecoveryError) as caught:
            transport.get('list')
        self.assertEqual(caught.exception.category, 'transport_error')
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertEqual(len(opener.calls), 1)
        for token in (None, '', 'x\nAuthorization: secret'):
            with self.assertRaises(recovery.RecoveryError):
                recovery.HttpTransport(token, opener=Opener([]))


class WorkflowAndCryptoTests(unittest.TestCase):
    def test_workflow_is_manual_main_attempt_one_read_only_and_encrypted_artifacts(self):
        text = (Path(__file__).resolve().parents[2]/'.github/workflows/apify-rag-recovery-readonly.yml').read_text()
        self.assertIn('workflow_dispatch:', text)
        self.assertNotIn('schedule:', text); self.assertNotIn('pull_request:', text); self.assertNotIn('push:', text)
        self.assertIn('contents: read', text)
        self.assertIn("github.ref == 'refs/heads/main' && github.run_attempt == 1", text)
        self.assertIn('default: false', text)
        self.assertIn('persist-credentials: false', text)
        self.assertEqual(text.count('APIFY_TOKEN: ${{ secrets.APIFY_TOKEN }}'), 1)
        self.assertIn('rag-recovery.age', text); self.assertIn('rag-recovery-public.json', text)
        self.assertNotIn('state.json', text); self.assertNotIn('private.json', text)
        self.assertIn('cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10', text)
        self.assertNotIn('run_id:', text)

    def test_offline_cli_is_closed_and_reads_no_environment(self):
        with patch.object(recovery.os, 'environ', new=UnreadableEnvironment()), \
                patch.object(recovery, 'load_cell', side_effect=AssertionError()), \
                patch('sys.argv', ['recover_rag_readonly.py']), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(recovery.main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['provider_requests'], 0)

    def test_standard_age_synthetic_roundtrip_preserves_private_identity_only(self):
        binary = Path(os.environ.get('STUDY_TEST_AGE_BIN', '/tmp/apify-age-bin/age/age'))
        keygen = binary.with_name('age-keygen')
        if not binary.is_file() or not keygen.is_file():
            self.skipTest('standard age binary unavailable')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); key = folder/'synthetic-key.txt'
            result = subprocess.run([str(keygen), '-o', str(key)], capture_output=True, check=True,
                env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            key.chmod(0o600)
            recipient = result.stderr.decode().strip().split()[-1]
            cell = recovery.load_cell(); identity = runner.validate_run(run_data(), cell)
            with patch.multiple(recovery, TARGET_RUN_SHA256=hashlib.sha256(run_data()['id'].encode()).hexdigest(),
                    ORIGINAL_SCOPE_SHA256=runner.scope_commitment(identity)):
                evidence = recovery.recover(FakeTransport(), cell)
            blob = runner.canonical(evidence); cipher_path = folder/'synthetic.age'
            proof = crypto.encrypt_capture(blob, cipher_path, binary, recipient)
            validated = []
            def check(value):
                validated.append(value)
                return value['recovery_identity'] == identity and value['complete'] is True
            crypto.decrypt_and_verify(cipher_path.read_bytes(), folder/'readback.json', binary, key,
                proof['plaintext_sha256'], proof['ciphertext_sha256'], validate_payload=check)
            self.assertEqual((folder/'readback.json').read_bytes(), blob)
            self.assertEqual(len(validated), 1)
            self.assertNotIn(TOKEN.encode(), blob)
            public = runner.canonical(recovery.public_result(evidence, proof))
            self.assertNotIn(identity['id'].encode(), public)


if __name__ == '__main__':
    unittest.main()
