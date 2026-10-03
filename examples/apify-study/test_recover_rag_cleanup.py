"""Synthetic offline renewed-cleanup tests; never use owner credentials."""
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
from urllib.error import HTTPError
from urllib.parse import urlsplit

import evidence_transport as crypto
import recover_rag_readonly as recovery
import recover_rag_cleanup as cleanup
import runner
from test_recover_rag_readonly import (TOKEN, FakeTransport, Opener, Response,
    TrackedEnvironment, UnreadableEnvironment, listing, metadata, run_data)


KINDS = ('dataset', 'kv', 'queue')


def proof(blob):
    return {'plaintext_sha256': crypto.digest(blob), 'ciphertext_sha256': 'b'*64,
        'remote_file_readback_verified': True}


class FakeCleanupTransport(FakeTransport):
    def __init__(self, replies=None, outcomes=None, clock=lambda: 0):
        super().__init__(replies)
        self.clock = clock
        self.fresh_deadline = None
        self.outcomes = outcomes or [cleanup.CleanupReply(204), cleanup.CleanupReply(404, True)]*3
        self.mutations = []
        self.authorized = False
    def get(self, stage, reference=None):
        if stage == 'run':
            self.fresh_deadline = self.clock()+120
        return super().get(stage, reference)
    def authorize_cleanup(self, blob, receipt):
        cleanup.require_guard()
        if self.clock() >= self.fresh_deadline:
            raise cleanup.CleanupError('deadline_exceeded', 'evidence')
        self.authorized = True
    def cleanup_call(self, operation):
        if not self.authorized or self.clock() >= self.fresh_deadline:
            raise cleanup.CleanupError('deadline_exceeded', operation)
        self.mutations.append(operation)
        value = self.outcomes[len(self.mutations)-1]
        if isinstance(value, Exception):
            raise value
        return value


class CleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cell = recovery.load_cell()
    def setUp(self):
        self.identity = runner.validate_run(run_data(), self.cell)
        self.pins = patch.multiple(recovery,
            TARGET_RUN_SHA256=hashlib.sha256(run_data()['id'].encode()).hexdigest(),
            ORIGINAL_SCOPE_SHA256=runner.scope_commitment(self.identity))
        self.pins.start(); self.addCleanup(self.pins.stop)
        self.ready = patch.object(cleanup, 'CLEANUP_READY', True)
        self.ready.start(); self.addCleanup(self.ready.stop)

    def test_all_fresh_metadata_and_durable_proof_precede_every_delete(self):
        transport = FakeCleanupTransport(); saved = []
        def persist(blob):
            self.assertEqual(len(transport.calls), 5)
            self.assertEqual(transport.mutations, [])
            saved.append(crypto.json_payload(blob)); return proof(blob)
        result = cleanup.perform(transport, self.cell, persist)
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['requests_attempted'], 11)
        self.assertEqual(transport.mutations, [p+'_'+k for k in KINDS for p in ('delete', 'absence')])
        self.assertEqual(saved[0]['recovery_identity'], self.identity)
        self.assertEqual(result['recovery_identity'], self.identity)
        self.assertEqual(result['initial_capture'], saved[0])
        self.assertTrue(all(row['absence_verified'] for row in result['stores'].values()))
        self.assertEqual(result['deletions_attempted'], 3)

    def test_lookup_scope_active_build_options_and_time_mismatch_never_delete(self):
        for field, value in [('id', 'ForeignRun'), ('userId', 'ForeignOwner'), ('status', 'RUNNING'),
                ('buildNumber', '1.0.31'), ('finishedAt', '2026-10-02T21:20:21Z')]:
            with self.subTest(field=field):
                data = run_data(); data[field] = value
                transport = FakeCleanupTransport([listing(), {'data': data}])
                result = cleanup.perform(transport, self.cell, proof)
                self.assertFalse(result['cleanup_complete'])
                self.assertEqual(transport.mutations, [])
        data = run_data(); data['options']['memoryMbytes'] = 4096
        transport = FakeCleanupTransport([listing(), {'data': data}])
        self.assertFalse(cleanup.perform(transport, self.cell, proof)['cleanup_complete'])
        self.assertEqual(transport.mutations, [])
        with patch.object(recovery, 'ORIGINAL_SCOPE_SHA256', '0'*64):
            transport = FakeCleanupTransport()
            self.assertFalse(cleanup.perform(transport, self.cell, proof)['cleanup_complete'])
            self.assertEqual(transport.mutations, [])

    def test_every_store_scope_name_creation_or_missing_stat_failure_blocks_all_deletes(self):
        for kind in KINDS:
            for field, value in [('id', 'ForeignStore'), ('userId', 'ForeignOwner'),
                    ('actRunId', 'ForeignRun'), ('actId', 'ForeignActor'), ('name', 'Shared'),
                    ('createdAt', '2026-10-03T00:00:00Z'), ('stats', {})]:
                with self.subTest(kind=kind, field=field):
                    rows = [listing(), {'data': run_data()}, *[metadata(k) for k in KINDS]]
                    rows[2+KINDS.index(kind)]['data'][field] = value
                    transport = FakeCleanupTransport(rows)
                    result = cleanup.perform(transport, self.cell, proof)
                    self.assertFalse(result['cleanup_complete'])
                    self.assertEqual(transport.mutations, [])

    def test_denial_during_reads_stops_and_preserves_private_identity(self):
        transport = FakeCleanupTransport([listing(), {'data': run_data()}, metadata('dataset'),
            recovery.RecoveryError('access_denied', 'kv', 403)])
        result = cleanup.perform(transport, self.cell, proof)
        self.assertEqual(len(transport.calls), 4)
        self.assertEqual(transport.mutations, [])
        self.assertEqual(result['recovery_identity'], self.identity)
        self.assertEqual(result['diagnostic']['http_status'], 403)

    def test_persistence_error_wrong_digest_or_unverified_readback_blocks_every_delete(self):
        def failed(_):
            raise OSError(TOKEN)
        for callback in [failed, lambda _: {'plaintext_sha256': '0'*64,
                'ciphertext_sha256': 'b'*64, 'remote_file_readback_verified': True},
                lambda blob: {**proof(blob), 'remote_file_readback_verified': False}]:
            transport = FakeCleanupTransport()
            result = cleanup.perform(transport, self.cell, callback)
            self.assertEqual(transport.mutations, [])
            self.assertFalse(result['cleanup_complete'])
            self.assertNotIn(TOKEN, runner.canonical(result).decode())

    def test_fresh_120_second_deadline_includes_persistence(self):
        clock = [0.0]; transport = FakeCleanupTransport(clock=lambda: clock[0])
        def late(blob):
            clock[0] = 120; return proof(blob)
        result = cleanup.perform(transport, self.cell, late)
        self.assertEqual(transport.mutations, [])
        self.assertEqual(result['diagnostic']['category'], 'deadline_exceeded')

    def test_deadline_before_second_delete_keeps_first_receipt_and_identity(self):
        clock = [0.0]; transport = FakeCleanupTransport(clock=lambda: clock[0])
        original = transport.cleanup_call
        def timed(operation):
            if operation == 'delete_kv':
                clock[0] = 120
            return original(operation)
        transport.cleanup_call = timed
        result = cleanup.perform(transport, self.cell, proof)
        self.assertEqual(transport.mutations, ['delete_dataset', 'absence_dataset'])
        self.assertTrue(result['stores']['dataset']['absence_verified'])
        self.assertIsNone(result['stores']['kv']['delete_http_status'])
        self.assertEqual(result['recovery_identity'], self.identity)
        self.assertFalse(result['cleanup_complete'])

    def test_second_delete_denial_preserves_partial_success_and_stops_queue(self):
        transport = FakeCleanupTransport(outcomes=[cleanup.CleanupReply(204), cleanup.CleanupReply(404, True),
            cleanup.CleanupError('access_denied', 'delete_kv', 403)])
        result = cleanup.perform(transport, self.cell, proof)
        self.assertEqual(transport.mutations, ['delete_dataset', 'absence_dataset', 'delete_kv'])
        self.assertTrue(result['stores']['dataset']['absence_verified'])
        self.assertEqual(result['diagnostic']['http_status'], 403)
        self.assertIsNone(result['stores']['queue']['delete_http_status'])
        self.assertEqual(result['recovery_identity'], self.identity)

    def test_bad_absence_reply_stops_without_claiming_absence_or_later_delete(self):
        for reply in (cleanup.CleanupReply(200), cleanup.CleanupReply(404, False), {'status': 404}):
            transport = FakeCleanupTransport(outcomes=[cleanup.CleanupReply(204), reply])
            result = cleanup.perform(transport, self.cell, proof)
            self.assertFalse(result['stores']['dataset']['absence_verified'])
            self.assertEqual(len(transport.mutations), 2)
            self.assertFalse(result['cleanup_complete'])

    def test_public_capture_and_final_project_no_identifiers_or_raw_error_values(self):
        result = cleanup.perform(FakeCleanupTransport(), self.cell, proof)
        result['raw'] = TOKEN
        public = cleanup.public_result(result, proof(runner.canonical(result)), 'final')
        blob = runner.canonical(public).decode()
        for value in [TOKEN, *[self.identity[k] for k in runner.IDENTITY_FIELDS]]:
            self.assertNotIn(value, blob)
        self.assertNotIn('initial_capture', public)
        self.assertNotIn('storage', public)
        self.assertEqual(public['requests_attempted'], 11)

    def test_closed_guard_blocks_before_environment_source_crypto_and_transport(self):
        with patch.object(cleanup, 'CLEANUP_READY', False), \
                patch.object(cleanup.os, 'environ', new=UnreadableEnvironment()), \
                patch.object(recovery, 'load_cell', side_effect=AssertionError()), \
                patch.object(cleanup, 'private_paths', side_effect=AssertionError()), \
                patch.object(cleanup, 'HttpTransport', side_effect=AssertionError()):
            with self.assertRaises(cleanup.CleanupError) as caught:
                cleanup.execute()
        self.assertEqual(caught.exception.category, 'guard_closed')

    def test_crypto_preflight_failure_precedes_token_lookup(self):
        with tempfile.TemporaryDirectory() as temp:
            env = TrackedEnvironment(temp)
            with patch.object(cleanup, 'private_paths', return_value=(Path(temp), Path('/synthetic/age'))), \
                    patch.object(cleanup.crypto, 'encrypt_capture', side_effect=crypto.TransportError()), \
                    patch.object(cleanup, 'HttpTransport', side_effect=AssertionError()):
                with self.assertRaises(cleanup.CleanupError):
                    cleanup.execute(env)
            self.assertNotIn('APIFY_TOKEN', env.reads)


class CleanupTransportTests(unittest.TestCase):
    setUpClass = classmethod(CleanupTests.setUpClass.__func__)
    setUp = CleanupTests.setUp
    def session(self, cleanup_responses, clock=None):
        values = [listing(), {'data': run_data()}, *[metadata(k) for k in KINDS]]
        responses = [Response(runner.canonical(v)) for v in values] + cleanup_responses
        opener = Opener(responses)
        transport = cleanup.HttpTransport(TOKEN, opener=opener, clock=clock or (lambda: 0))
        return transport, opener

    def test_actual_transport_fixed_get_delete_pairs_exact_11_no_post_or_query_auth(self):
        responses = [value for _ in KINDS for value in
            (Response(b'', 204), Response(b'{"error":{"type":"record-not-found","message":"'+TOKEN.encode()+b'"}}', 404))]
        transport, opener = self.session(responses)
        result = cleanup.perform(transport, self.cell, proof)
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(len(opener.calls), 11)
        self.assertEqual([req.get_method() for req, _ in opener.calls], ['GET']*5+['DELETE', 'GET']*3)
        for request, timeout in opener.calls:
            self.assertEqual(urlsplit(request.full_url).netloc, 'api.apify.com')
            self.assertNotIn(TOKEN, request.full_url)
            self.assertEqual(request.get_header('Authorization'), 'Bearer '+TOKEN)
            self.assertLessEqual(timeout, 10)
        for index, kind in enumerate(KINDS):
            route = '/v2/'+recovery.ROUTES[kind]+'/'+self.identity[runner.STORES[kind][0]]
            self.assertEqual(urlsplit(opener.calls[5+index*2][0].full_url).path, route)
            self.assertEqual(urlsplit(opener.calls[6+index*2][0].full_url).path, route)
        self.assertNotIn(TOKEN, runner.canonical(result).decode())
        with self.assertRaises(cleanup.CleanupError):
            transport.cleanup_call('delete_dataset')
        self.assertEqual(len(opener.calls), 11)

    def test_real_http_error_typed_404_is_proof_without_retaining_body(self):
        body = Response(b'{"error":{"type":"record-not-found","message":"'+TOKEN.encode()+b'"}}')
        error = HTTPError('https://invalid.test/'+TOKEN, 404, TOKEN,
            {'Content-Type': 'application/json'}, body)
        transport, opener = self.session([Response(b'', 204), error,
            Response(b'', 204), Response(b'{"error":{"type":"record-not-found"}}', 404),
            Response(b'', 204), Response(b'{"error":{"type":"record-not-found"}}', 404)])
        result = cleanup.perform(transport, self.cell, proof)
        self.assertTrue(result['cleanup_complete'])
        self.assertTrue(body.closed)
        self.assertNotIn(TOKEN, runner.canonical(result).decode())

    def test_wrong_missing_html_oversized_or_malformed_404_stop_after_first_delete(self):
        variants = [(b'{"error":{"type":"wrong"}}', 'application/json'),
            (b'{"error":{}}', 'application/json'), (TOKEN.encode(), 'text/html'),
            (b'{', 'application/json'), (b' '*131073, 'application/json')]
        for raw, content_type in variants:
            with self.subTest(content_type=content_type, size=len(raw)):
                transport, opener = self.session([Response(b'', 204), Response(raw, 404, content_type)])
                result = cleanup.perform(transport, self.cell, proof)
                self.assertFalse(result['cleanup_complete'])
                self.assertFalse(result['stores']['dataset']['absence_verified'])
                self.assertEqual(len(opener.calls), 7)
                self.assertNotIn(TOKEN, runner.canonical(result).decode())

    def test_mutation_requires_exact_immutable_capture_proof_and_all_metadata(self):
        transport, opener = self.session([])
        capture = recovery.recover(transport, self.cell)
        for change in ('hash', 'scope', 'metadata', 'unverified'):
            value = copy.deepcopy(capture)
            receipt = proof(runner.canonical(value))
            if change == 'scope':
                value['recovery_identity']['userId'] = 'ForeignOwner'
                receipt = proof(runner.canonical(value))
            elif change == 'metadata':
                value['storage']['kv']['name'] = 'Shared'
                receipt = proof(runner.canonical(value))
            elif change == 'unverified':
                receipt['remote_file_readback_verified'] = False
            else:
                receipt['plaintext_sha256'] = '0'*64
            with self.subTest(change=change):
                with self.assertRaises(cleanup.CleanupError):
                    transport.authorize_cleanup(runner.canonical(value), receipt)
        with self.assertRaises(cleanup.CleanupError):
            transport.cleanup_call('delete_dataset')
        self.assertEqual(len(opener.calls), 5)

    def test_wrong_order_route_and_fresh_deadline_rejected_before_delete_open(self):
        clock = [0.0]; transport, opener = self.session([], clock=lambda: clock[0])
        capture = recovery.recover(transport, self.cell); blob = runner.canonical(capture)
        transport.authorize_cleanup(blob, proof(blob))
        for operation in ('start', 'delete_run', 'delete_queue', 'https://evil.invalid/'):
            with self.assertRaises(cleanup.CleanupError):
                transport.cleanup_call(operation)
        clock[0] = 120
        with self.assertRaises(cleanup.CleanupError):
            transport.cleanup_call('delete_dataset')
        self.assertEqual(len(opener.calls), 5)

    def test_http_delete_denial_stops_all_later_mutations_without_body_read(self):
        body = Response(TOKEN.encode())
        error = HTTPError('https://invalid.test/'+TOKEN, 403, TOKEN, {}, body)
        transport, opener = self.session([error])
        result = cleanup.perform(transport, self.cell, proof)
        self.assertFalse(result['cleanup_complete'])
        self.assertEqual(result['diagnostic']['http_status'], 403)
        self.assertEqual(len(opener.calls), 6)
        self.assertEqual(body.read_calls, 0)
        self.assertNotIn(TOKEN, runner.canonical(result).decode())

    def test_late_delete_response_revokes_remaining_mutations(self):
        clock = [0.0]
        response = Response(b'', 204, clock=clock)
        transport, opener = self.session([response], clock=lambda: clock[0])
        original = opener.open
        def late(request, timeout):
            result = original(request, timeout)
            if request.get_method() == 'DELETE':
                clock[0] += 11
            return result
        opener.open = late
        result = cleanup.perform(transport, self.cell, proof)
        self.assertFalse(result['cleanup_complete'])
        self.assertEqual(result['diagnostic']['category'], 'deadline_exceeded')
        self.assertEqual(len(opener.calls), 6)
        self.assertFalse(result['stores']['dataset']['absence_verified'])


class WorkflowAndPersistenceTests(unittest.TestCase):
    def test_workflow_manual_main_attempt_one_read_only_github_and_ciphertext_only(self):
        path = Path(__file__).resolve().parents[2]/'.github/workflows/apify-rag-cleanup.yml'
        text = path.read_text()
        self.assertIn('workflow_dispatch:', text)
        self.assertNotIn('push:', text); self.assertNotIn('pull_request:', text); self.assertNotIn('schedule:', text)
        self.assertIn('contents: read', text)
        self.assertIn("github.ref == 'refs/heads/main' && github.run_attempt == 1", text)
        self.assertIn('default: false', text)
        self.assertIn('persist-credentials: false', text)
        self.assertEqual(text.count('APIFY_TOKEN: ${{ secrets.APIFY_TOKEN }}'), 1)
        for name in ('rag-cleanup-capture.age', 'rag-cleanup-capture-public.json',
                'rag-cleanup-final.age', 'rag-cleanup-final-public.json'):
            self.assertIn(name, text)
        self.assertNotIn('private.json', text)
        self.assertIn('cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10', text)

    def test_saved_cipher_verification_rejects_missing_tamper_mode_and_false_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'synthetic.age'; payload = b'{"synthetic":true}'
            cipher = b'age-encryption.org/v1\nsynthetic'
            receipt = {'plaintext_sha256': crypto.digest(payload), 'ciphertext_sha256': crypto.digest(cipher),
                'remote_file_readback_verified': True}
            with self.assertRaises(cleanup.CleanupError):
                cleanup.verify_saved_cipher(path, payload, receipt)
            crypto.durable_write(path, cipher)
            self.assertEqual(cleanup.verify_saved_cipher(path, payload, receipt), receipt)
            for change in ('content', 'mode', 'receipt'):
                crypto.durable_write(path, cipher); current = dict(receipt)
                if change == 'content':
                    crypto.durable_write(path, cipher+b'tamper')
                elif change == 'mode':
                    path.chmod(0o644)
                else:
                    current['remote_file_readback_verified'] = False
                with self.subTest(change=change):
                    with self.assertRaises(cleanup.CleanupError):
                        cleanup.verify_saved_cipher(path, payload, current)

    def test_age_partial_final_roundtrip_preserves_original_ids_but_no_public_ids(self):
        binary = Path(os.environ.get('STUDY_TEST_AGE_BIN', '/tmp/apify-age-bin/age/age'))
        keygen = binary.with_name('age-keygen')
        if not binary.is_file() or not keygen.is_file():
            self.skipTest('standard age unavailable')
        cell = recovery.load_cell(); identity = runner.validate_run(run_data(), cell)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); key = folder/'synthetic-key.txt'
            result = subprocess.run([str(keygen), '-o', str(key)], capture_output=True, check=True,
                env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            key.chmod(0o600); recipient = result.stderr.decode().strip().split()[-1]
            proofs = []
            def persist(blob):
                path = folder/'capture.age'
                receipt = crypto.encrypt_capture(blob, path, binary, recipient)
                proofs.append(cleanup.verify_saved_cipher(path, blob, receipt)); return receipt
            with patch.object(cleanup, 'CLEANUP_READY', True), patch.multiple(recovery,
                    TARGET_RUN_SHA256=hashlib.sha256(identity['id'].encode()).hexdigest(),
                    ORIGINAL_SCOPE_SHA256=runner.scope_commitment(identity)):
                transport = FakeCleanupTransport(outcomes=[cleanup.CleanupReply(204), cleanup.CleanupReply(404, True),
                    cleanup.CleanupError('access_denied', 'delete_kv', 403)])
                evidence = cleanup.perform(transport, cell, persist)
            blob = runner.canonical(evidence); destination = folder/'final.age'
            receipt = crypto.encrypt_capture(blob, destination, binary, recipient)
            cleanup.verify_saved_cipher(destination, blob, receipt)
            def validated(value):
                return value['recovery_identity'] == identity and value['stores']['dataset']['absence_verified'] is True and value['cleanup_complete'] is False
            crypto.decrypt_and_verify(destination.read_bytes(), folder/'readback.json', binary, key,
                receipt['plaintext_sha256'], receipt['ciphertext_sha256'], validate_payload=validated)
            self.assertEqual((folder/'readback.json').read_bytes(), blob)
            public = runner.canonical(cleanup.public_result(evidence, receipt, 'final'))
            for field in runner.IDENTITY_FIELDS:
                self.assertNotIn(identity[field].encode(), public)
            self.assertNotIn(TOKEN.encode(), blob)


if __name__ == '__main__':
    unittest.main()
