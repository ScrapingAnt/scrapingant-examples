"""Named synthetic transport/privacy acceptance cases; never provider calls."""
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs
from decimal import Decimal
import copy, io, json, os, tempfile, unittest
import recover_existing as r

TOKEN = 'NAMED_SYNTHETIC_API_TOKEN'


class Response:
    def __init__(self, blob, ctype='application/json', status=200, headers=None):
        self.stream, self.status, self.closed = io.BytesIO(blob), status, False
        self.headers = {'Content-Type': ctype, **(headers or {})}
    def read1(self, count): return self.stream.read(count)
    def getheader(self, name): return self.headers.get(name)
    def close(self): self.closed = True


class NoEnv:
    def get(self, *args): raise AssertionError('Environment access forbidden')


def fixtures():
    spec, cell, validators, crypto, recipient = r.load_reviewed()
    spec = copy.deepcopy(spec)
    target = {'id': 'R' * 17, 'userId': 'U' * 17, 'actId': cell['actor_id'],
              'defaultDatasetId': 'D' * 17, 'defaultKeyValueStoreId': 'K' * 17,
              'defaultRequestQueueId': 'Q' * 17, 'status': 'ABORTED', 'build': cell['build'],
              'startedAt': '2026-01-01T00:00:00.000Z', 'finishedAt': '2026-01-01T00:00:10.000Z'}
    spec['target_payload_sha256'] = r.sha(r.canonical(target))
    native = {**target, 'buildNumber': cell['build'], 'options': copy.deepcopy(cell['options']),
              'usageTotalUsd': .70}
    native['options']['maxTotalChargeUsd'] = .75
    def meta(kind):
        key = {'dataset': 'defaultDatasetId', 'kv': 'defaultKeyValueStoreId', 'queue': 'defaultRequestQueueId'}[kind]
        v = {'id': target[key], 'userId': target['userId'], 'actRunId': target['id'],
             'actId': target['actId'], 'name': None, 'createdAt': target['startedAt'],
             'stats': {'storageBytes': 100, 'readCount': 0, 'writeCount': 2},
             'urlSigningSecretKey': 'NAMED_SYNTHETIC_SIGNING_SECRET'}
        if kind == 'dataset': v['itemCount'] = 2
        return v
    rows = [{'named_synthetic_case': 1}, {'#error': True, '#debug': {'errorMessages': ['NAMED_SYNTHETIC_TIMEOUT']}}]
    bodies = [r.canonical({'data': native}), r.canonical(rows)]
    bodies += [r.canonical({'data': meta(k)}) for k in ('dataset', 'kv', 'queue')]
    bodies += [b'NAMED_SYNTHETIC_NATIVE_LOG\n', r.canonical({'data': native})]
    return spec, cell, validators, crypto, recipient, target, bodies


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.spec, self.cell, self.validators, self.crypto, self.recipient, self.target, self.bodies = fixtures()

    def collect(self, bodies=None, failure_at=None, headers=None):
        calls, saved, responses = [], {}, []
        data = self.bodies if bodies is None else bodies
        def opener(request, timeout):
            n = len(calls); calls.append((request, timeout))
            if n == failure_at:
                raise HTTPError(request.full_url, 403, 'NAMED_SYNTHETIC_PRIVATE_ERROR', {}, io.BytesIO(b'PRIVATE_BODY'))
            h = {'X-Apify-Pagination-Offset': '0', 'X-Apify-Pagination-Limit': '3841',
                 'X-Apify-Pagination-Count': '2', 'X-Apify-Pagination-Total': '2'} if n == 1 else {}
            if headers is not None and n == 1: h = headers
            response = Response(data[n], 'text/plain' if n == 5 else 'application/json', headers=h)
            responses.append(response); return response
        def persist(stage, blob):
            saved[stage] = blob
            return {'plaintext_sha256': r.sha(blob), 'plaintext_bytes': len(blob),
                    'ciphertext_sha256': 'e' * 64, 'ciphertext_bytes': len(blob) + 200,
                    'durable_encrypted_readback_verified': True}
        with patch.object(r, 'RECOVERY_READY', True):
            t = r.Transport(TOKEN, self.target, opener=opener, clock=lambda: 0)
            value = r.collect(t, self.spec, self.cell, self.validators, persist)
        return value, calls, saved, responses

    def test_closed_guard_precedes_environment_and_http(self):
        with patch.object(r, 'RECOVERY_READY', False), patch.object(r, 'load_reviewed', side_effect=AssertionError()):
            with self.assertRaises(r.RecoveryError) as e: r.execute(opt_in=True, environ=NoEnv())
            self.assertEqual(e.exception.category, 'guard_closed')
            with self.assertRaises(r.RecoveryError): r.Transport(TOKEN, self.target)

    def test_explicit_opt_in_precedes_environment(self):
        with patch.object(r, 'RECOVERY_READY', True), self.assertRaises(r.RecoveryError) as e:
            r.execute(environ=NoEnv())
        self.assertEqual(e.exception.category, 'opt_in_required')

    def test_reviewed_dependencies_and_all_paid_guards_closed(self):
        r.load_reviewed()
        with patch.object(r, 'SPEC_SHA256', 'f' * 64), self.assertRaises(r.RecoveryError): r.load_reviewed()
        with patch.object(r.controller, 'ACTIVE_CELL', 'breadth-r1-web'), self.assertRaises(r.RecoveryError): r.load_reviewed()
        with patch.object(self.validators, 'RUNNER_READY', True), patch.object(r.controller, 'load_sources', return_value=(self.validators, self.crypto)), self.assertRaises(r.RecoveryError): r.load_reviewed()

    def test_exact_data_payload_hash_and_no_alternative_target(self):
        blob = r.canonical(self.target).decode()
        self.assertEqual(r.target_from_data(blob, self.spec, self.validators, self.cell), self.target)
        for value in (None, '', blob + '\n', blob.replace('R' * 17, 'F' * 17), '{}'):
            with self.assertRaises(r.RecoveryError): r.target_from_data(value, self.spec, self.validators, self.cell)

    def test_duplicate_or_extra_target_fields_fail_even_under_hash_commitment(self):
        for blob in ('{"id":1,"id":2}', r.canonical({**self.target, 'token': TOKEN}).decode()):
            spec = {**self.spec, 'target_payload_sha256': r.sha(blob.encode())}
            with self.assertRaises(r.RecoveryError): r.target_from_data(blob, spec, self.validators, self.cell)

    def test_seven_exact_gets_no_discovery_retry_start_or_delete(self):
        value, calls, saved, responses = self.collect()
        self.assertTrue(value['capture_complete']); self.assertTrue(value['evidence_gates_passed'])
        self.assertEqual(len(calls), 7); self.assertEqual(tuple(saved), r.STAGES)
        paths = [urlsplit(c[0].full_url).path for c in calls]
        self.assertEqual(paths, ['/v2/actor-runs/' + self.target['id'],
            '/v2/datasets/' + self.target['defaultDatasetId'] + '/items',
            '/v2/datasets/' + self.target['defaultDatasetId'],
            '/v2/key-value-stores/' + self.target['defaultKeyValueStoreId'],
            '/v2/request-queues/' + self.target['defaultRequestQueueId'],
            '/v2/actor-runs/' + self.target['id'] + '/log', '/v2/actor-runs/' + self.target['id']])
        for req, timeout in calls:
            self.assertEqual(req.get_method(), 'GET'); self.assertIsNone(req.data)
            self.assertEqual(req.get_header('Authorization'), 'Bearer ' + TOKEN)
            self.assertNotIn(TOKEN, req.full_url); self.assertLessEqual(timeout, r.ROUTE_SECONDS)
        self.assertTrue(all(x.closed for x in responses)); self.assertFalse(value['ready_for_next_cell'])

    def test_raw_and_log_exact_bytes_headers_preserved(self):
        value, calls, saved, _ = self.collect()
        for n, stage in enumerate(r.STAGES): self.assertEqual(saved[stage], self.bodies[n])
        q = parse_qs(urlsplit(calls[1][0].full_url).query)
        self.assertEqual(q, {'format': ['json'], 'offset': ['0'], 'limit': ['3841'], 'desc': ['false'],
                             'clean': ['false'], 'skipHidden': ['false'], 'skipEmpty': ['false']})
        self.assertEqual(parse_qs(urlsplit(calls[5][0].full_url).query), {'stream': ['false'], 'raw': ['true']})
        self.assertEqual(value['files']['raw.age']['headers']['X-Apify-Pagination-Total'], '2')

    def test_count_disagreement_remains_failed_but_does_not_hide_log_or_meter(self):
        bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[2]); obj['data']['itemCount'] = 1
        bodies[2] = r.canonical(obj); value, calls, saved, _ = self.collect(bodies)
        self.assertEqual(len(calls), 7); self.assertTrue(value['capture_complete'])
        self.assertFalse(value['count_gate_passed']); self.assertFalse(value['evidence_gates_passed'])
        self.assertEqual(value['raw_minus_native_item_count'], 1)
        self.assertIn('log', saved); self.assertIn('meter', saved); self.assertFalse(value['original_failed_capture_rewritten'])

    def test_fresh_meter_over_cap_retained_once_no_waiver_or_allowance(self):
        bodies = copy.deepcopy(self.bodies)
        bodies[6] = bodies[6].replace(b'"usageTotalUsd":0.7', b'"usageTotalUsd":0.7551')
        value, calls, _, _ = self.collect(bodies)
        self.assertEqual(len(calls), 7); self.assertTrue(value['capture_complete'])
        self.assertEqual(value['fresh_run_meter']['usage_total_usd'], '0.7551')
        self.assertFalse(value['meter_gate']['strict_run_cap_passed'])
        self.assertTrue(value['meter_gate']['within_retained_allocation'])
        self.assertFalse(value['evidence_gates_passed']); self.assertEqual(value['hold_release_usd'], '0')

    def test_missing_invalid_and_zero_meters(self):
        for amount in (None, True, '0.7', -1):
            bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[6]); obj['data']['usageTotalUsd'] = amount
            bodies[6] = r.canonical(obj); value, _, _, _ = self.collect(bodies)
            self.assertEqual(value['meter_gate']['state'], 'unknown'); self.assertFalse(value['evidence_gates_passed'])
        bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[6]); obj['data']['usageTotalUsd'] = 0
        bodies[6] = r.canonical(obj); value, _, _, _ = self.collect(bodies)
        self.assertEqual(value['fresh_run_meter']['usage_total_usd'], '0'); self.assertTrue(value['meter_gate']['strict_run_cap_passed'])

    def test_public_output_excludes_native_ids_data_meter_headers_and_signing_secret(self):
        value, _, _, _ = self.collect()
        public = r.public_projection(value, {'plaintext_sha256': 'a' * 64, 'ciphertext_sha256': 'b' * 64})
        text = json.dumps(public)
        for forbidden in (TOKEN, self.target['id'], self.target['userId'], self.target['defaultDatasetId'],
                          self.target['defaultKeyValueStoreId'], self.target['defaultRequestQueueId'],
                          'NAMED_SYNTHETIC_SIGNING_SECRET', 'NAMED_SYNTHETIC_NATIVE_LOG',
                          'NAMED_SYNTHETIC_TIMEOUT', 'usage_total_usd', 'raw_row_count', 'headers'):
            self.assertNotIn(forbidden, text)
        self.assertFalse(public['ready_for_next_cell'])

    def test_access_denial_stops_at_each_stage_without_retry_or_error_body(self):
        for index in range(7):
            value, calls, _, _ = self.collect(failure_at=index)
            self.assertEqual(len(calls), index + 1); self.assertFalse(value['capture_complete'])
            self.assertEqual(value['capture_diagnostic']['category'], 'access_denied')
            self.assertNotIn('PRIVATE_BODY', json.dumps(value)); self.assertNotIn(TOKEN, json.dumps(value))

    def test_foreign_active_build_options_and_time_run_stop_before_dataset(self):
        for key, change in [('userId', 'F' * 17), ('status', 'RUNNING'), ('status', 'SUCCEEDED'),
                            ('buildNumber', '99.99'), ('finishedAt', '2026-01-01T00:00:11.000Z')]:
            bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[0]); obj['data'][key] = change
            bodies[0] = r.canonical(obj); value, calls, saved, _ = self.collect(bodies)
            self.assertEqual(len(calls), 1); self.assertFalse(value['capture_complete']); self.assertFalse(saved)
        bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[0]); obj['data']['options']['maxTotalChargeUsd'] = 1
        bodies[0] = r.canonical(obj); self.assertEqual(len(self.collect(bodies)[1]), 1)

    def test_foreign_named_or_boolean_count_store_stops_before_next_route(self):
        for index in (2, 3, 4):
            for key, change in [('name', 'NAMED_SYNTHETIC_STORE'), ('actRunId', 'F' * 17), ('userId', 'F' * 17)]:
                bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[index]); obj['data'][key] = change
                bodies[index] = r.canonical(obj); value, calls, _, _ = self.collect(bodies)
                self.assertEqual(len(calls), index + 1); self.assertFalse(value['capture_complete'])
        bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[2]); obj['data']['itemCount'] = True
        bodies[2] = r.canonical(obj); self.assertFalse(self.collect(bodies)[0]['capture_complete'])

    def test_wrong_final_scope_never_promoted_to_fresh_meter(self):
        bodies = copy.deepcopy(self.bodies); obj = json.loads(bodies[6]); obj['data']['id'] = 'F' * 17
        bodies[6] = r.canonical(obj); value, calls, _, _ = self.collect(bodies)
        self.assertEqual(len(calls), 7); self.assertFalse(value['capture_complete']); self.assertIsNone(value['fresh_run_meter'])

    def test_missing_or_truncated_pagination_never_passes_evidence_gate(self):
        for headers in ({}, {'X-Apify-Pagination-Offset': '0', 'X-Apify-Pagination-Limit': '3841',
                             'X-Apify-Pagination-Count': '2', 'X-Apify-Pagination-Total': '3'}):
            value, calls, _, _ = self.collect(headers=headers)
            self.assertEqual(len(calls), 7); self.assertTrue(value['capture_complete'])
            self.assertFalse(value['pagination_gate']['complete_single_page']); self.assertFalse(value['evidence_gates_passed'])

    def test_invalid_json_duplicate_nonfinite_and_raw_bound(self):
        for blob in (b'{"x":1,"x":2}', b'{"x":NaN}', b'broken'):
            with self.assertRaises(r.RecoveryError): r.strict(blob)
        self.assertEqual(r.strict(b'{"x":0.7551234567890123}')['x'], Decimal('0.7551234567890123'))
        bodies = copy.deepcopy(self.bodies); bodies[1] = r.canonical([{}] * 3842)
        self.assertEqual(len(self.collect(bodies)[1]), 2)

    def test_overflow_sentinel_is_preserved_but_not_accepted(self):
        bodies = copy.deepcopy(self.bodies); bodies[1] = r.canonical([{}] * 3841)
        obj = json.loads(bodies[2]); obj['data']['itemCount'] = 3841; bodies[2] = r.canonical(obj)
        h = {'X-Apify-Pagination-Offset': '0', 'X-Apify-Pagination-Limit': '3841',
             'X-Apify-Pagination-Count': '3841', 'X-Apify-Pagination-Total': '3841'}
        value, calls, _, _ = self.collect(bodies, headers=h)
        self.assertEqual(len(calls), 7); self.assertFalse(value['raw_within_assigned_bound']); self.assertFalse(value['evidence_gates_passed'])

    def test_invalid_order_extra_calls_and_failed_transport_never_open(self):
        def forbidden(*args, **kwargs): raise AssertionError('No network')
        with patch.object(r, 'RECOVERY_READY', True):
            t = r.Transport(TOKEN, self.target, opener=forbidden, clock=lambda: 0)
            for stage in ('raw', 'start', 'delete', 'list'):
                with self.assertRaises(r.RecoveryError): t.get(stage)
            self.assertEqual(t.calls, 0)
            t.calls = 7
            with self.assertRaises(r.RecoveryError): t.get('run')
            t.calls, t.failed = 0, True
            with self.assertRaises(r.RecoveryError): t.get('run')

    def test_body_limit_content_type_gzip_and_deadline_stop(self):
        for response in (Response(b'x' * (r.SMALL_LIMIT + 1)), Response(b'{}', 'text/html'),
                         Response(b'{}', headers={'Content-Encoding': 'gzip'})):
            with patch.object(r, 'RECOVERY_READY', True):
                t = r.Transport(TOKEN, self.target, opener=lambda *a, **k: response, clock=lambda: 0)
                with self.assertRaises(r.RecoveryError): t.get('run')
                self.assertTrue(response.closed); self.assertTrue(t.failed)
        clock = [0]
        class Slow(Response):
            def read1(self, count): clock[0] += 11; return b'x'
        response = Slow(b'{}')
        with patch.object(r, 'RECOVERY_READY', True):
            t = r.Transport(TOKEN, self.target, opener=lambda *a, **k: response, clock=lambda: clock[0])
            with self.assertRaises(r.RecoveryError) as e: t.get('run')
            self.assertEqual(e.exception.category, 'deadline_exceeded'); self.assertTrue(response.closed)

    def test_redirect_denied_and_no_redirect_handler(self):
        self.assertIsNone(r.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))
        def denied(request, **kwargs): raise HTTPError(request.full_url, 302, 'PRIVATE', {}, io.BytesIO(b'PRIVATE'))
        with patch.object(r, 'RECOVERY_READY', True):
            t = r.Transport(TOKEN, self.target, opener=denied, clock=lambda: 0)
            with self.assertRaises(r.RecoveryError) as e: t.get('run')
            self.assertEqual(e.exception.category, 'redirect_refused'); self.assertEqual(t.calls, 1)

    def test_encryption_failure_stops_before_next_get(self):
        calls = []
        def opener(request, **kwargs): calls.append(request); return Response(self.bodies[0])
        def denied(*args): raise r.RecoveryError('encryption_failed', 'evidence')
        with patch.object(r, 'RECOVERY_READY', True):
            t = r.Transport(TOKEN, self.target, opener=opener, clock=lambda: 0)
            value = r.collect(t, self.spec, self.cell, self.validators, denied)
        self.assertEqual(len(calls), 1); self.assertFalse(value['capture_complete'])

    def test_workflow_has_encrypted_only_allowlist_and_no_target_input(self):
        text = (r.ROOT.parents[1] / '.github/workflows/apify-web-evidence-recovery.yml').read_text()
        for label in r.STAGES + ('manifest',): self.assertIn('/recovery/' + label + '.age', text)
        self.assertIn('${{ secrets.APIFY_WEB_RECOVERY_TARGET }}', text)
        self.assertIn('github.run_attempt == 1', text); self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertNotIn('inputs.target', text); self.assertNotIn('controller.py --cell', text)
        self.assertNotIn('*.json', text); self.assertNotIn('recovery/*.age', text)

    @unittest.skipUnless(os.environ.get('WEB_RECOVERY_TEST_AGE_BIN') and os.environ.get('WEB_RECOVERY_TEST_AGE_IDENTITY'), 'existing local age identity not configured')
    def test_real_existing_age_verbatim_bytes_and_no_overwrite(self):
        binary = Path(os.environ['WEB_RECOVERY_TEST_AGE_BIN'])
        identity = Path(os.environ['WEB_RECOVERY_TEST_AGE_IDENTITY'])
        for blob in (b'NAMED_SYNTHETIC_LOG\n', b'{"named_synthetic_data":true}', b'x' * r.LOG_LIMIT):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'synthetic.age'
                proof = r.encrypt_raw(blob, path, binary, self.recipient, self.crypto)
                recovered = self.crypto.crypto(binary, ['--decrypt', '--identity', str(identity)], path.read_bytes())
                self.assertEqual(recovered, blob); self.assertEqual(r.sha(recovered), proof['plaintext_sha256'])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(r.RecoveryError): r.encrypt_raw(blob, path, binary, self.recipient, self.crypto)


if __name__ == '__main__': unittest.main()
