"""Synthetic deterministic tests only; every transport is injected."""
import copy, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import controller as c

PLAN = c.load_plan()
CELL = next(x for x in PLAN['cells'] if x['actor'] == 'apify/ai-web-scraper')

class ForbiddenEnvironment:
    def get(self, *_): raise AssertionError('environment accessed before authorization')

class Response:
    def __init__(self, body=b'{"data":{}}', status=201):
        self.body, self.status, self.closed = io.BytesIO(body), status, False
    def read1(self, n): return self.body.read(n)
    def close(self): self.closed = True

def identity():
    return {'id': 'SYNTHRUN000000001', 'userId': 'SYNTHUSR000000001',
            'actId': CELL['actor_id'], 'defaultDatasetId': 'SYNTHDAT000000001',
            'defaultKeyValueStoreId': 'SYNTHKVS000000001',
            'defaultRequestQueueId': 'SYNTHQUE000000001'}

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(c, 'ACTIVE_CELL', CELL['cell_id'])
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def transport(self, opener=None, clock=lambda: 0):
        return c.Transport(CELL, 'synthetic-token', opener=opener or (lambda *a, **k: Response()), clock=clock)

    def test_closed_guard_before_environment_and_paths(self):
        with patch.object(c, 'ACTIVE_CELL', None), patch.object(c, 'load_plan', side_effect=AssertionError()):
            with self.assertRaises(c.Stopped) as e:
                c.execute(CELL['cell_id'], opt_in=True, environ=ForbiddenEnvironment())
            self.assertEqual(e.exception.category, 'guard_closed')

    def test_opt_in_before_environment(self):
        with self.assertRaises(c.Stopped) as e:
            c.execute(CELL['cell_id'], environ=ForbiddenEnvironment())
        self.assertEqual(e.exception.category, 'opt_in_required')

    def test_wrong_cell_before_environment(self):
        with self.assertRaises(c.Stopped) as e:
            c.execute('foreign', opt_in=True, environ=ForbiddenEnvironment())
        self.assertEqual(e.exception.category, 'invalid_cell')

    def test_plan_pin_and_source_pins(self):
        self.assertEqual(c.sha((c.ROOT / 'continuation-plan.json').read_bytes()), c.PLAN_SHA256)
        validators, crypto = c.load_sources()
        self.assertFalse(validators.RUNNER_READY)
        self.assertEqual(crypto.MAX_PLAINTEXT_BYTES, 8388608)

    def test_changed_plan_before_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'continuation-plan.json').write_bytes((c.ROOT / 'continuation-plan.json').read_bytes() + b' ')
            with patch.object(c, 'ROOT', root):
                with self.assertRaises(c.Stopped) as e:
                    c.execute(CELL['cell_id'], opt_in=True, environ=ForbiddenEnvironment())
                self.assertEqual(e.exception.category, 'source_mismatch')

    def test_deferred_Article_old_cell_ids_refused_before_environment(self):
        for repetition in range(1, 4):
            name = 'breadth-r' + str(repetition) + '-article'
            with patch.object(c, 'ACTIVE_CELL', name):
                with self.assertRaises(c.Stopped) as e:
                    c.execute(name, opt_in=True, environ=ForbiddenEnvironment())
                self.assertEqual(e.exception.category, 'invalid_cell')

    def test_disguised_Article_ID_or_actor_cannot_construct_transport(self):
        for field, value in [('actor_id', 'hy5TYiCBwQ9o8uRKG'),
                ('actor', 'lukaskrivka/article-extractor-smart'),
                ('actor_id', c.ALLOWED_ACTORS['apify/google-search-scraper'])]:
            spec = copy.deepcopy(CELL); spec[field] = value
            with self.assertRaises(c.Stopped) as e:
                c.Transport(spec, None, opener=lambda *a, **k: self.fail('network touched'))
            self.assertEqual(e.exception.category, 'invalid_cell')

    def test_rehashed_hostile_plan_Article_rejected_before_environment(self):
        spec = copy.deepcopy(CELL)
        spec.update(actor='lukaskrivka/article-extractor-smart', actor_id='hy5TYiCBwQ9o8uRKG')
        blob = c.canonical({'cells': [spec]})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'continuation-plan.json').write_bytes(blob)
            with patch.object(c, 'ROOT', root), patch.object(c, 'PLAN_SHA256', c.sha(blob)):
                with self.assertRaises(c.Stopped) as e:
                    c.execute(CELL['cell_id'], opt_in=True, environ=ForbiddenEnvironment())
                self.assertEqual(e.exception.category, 'invalid_cell')

    def test_injected_plan_and_mutated_transport_Article_refused(self):
        spec = copy.deepcopy(CELL); spec['actor_id'] = 'hy5TYiCBwQ9o8uRKG'
        with patch.object(c, 'load_plan', return_value={'cells': [spec]}):
            with self.assertRaises(c.Stopped) as e:
                c.execute(CELL['cell_id'], opt_in=True, environ=ForbiddenEnvironment())
            self.assertEqual(e.exception.category, 'invalid_cell')
        t = self.transport(lambda *a, **k: self.fail('network touched'))
        t.cell = spec
        with self.assertRaises(c.Stopped): t.request('start')
        self.assertEqual(t.counts, {})

    def test_successful_start_consumes_only_start_and_auth_header(self):
        sent = []
        def opener(request, **kw):
            sent.append(request)
            return Response()
        t = self.transport(opener)
        t.request('start')
        self.assertEqual(t.counts, {'start': 1})
        self.assertEqual(sent[0].method, 'POST')
        self.assertIn('forcePermissionLevel=LIMITED_PERMISSIONS', sent[0].full_url)
        self.assertNotIn('synthetic-token', sent[0].full_url)
        self.assertEqual(sent[0].get_header('Authorization'), 'Bearer synthetic-token')
        self.assertEqual(json.loads(sent[0].data), CELL['input'])
        self.assertNotIn('synthetic-token', repr(t))

    def test_second_start_refused(self):
        t = self.transport()
        t.request('start')
        with self.assertRaises(c.Stopped): t.request('start')
        self.assertEqual(t.counts['start'], 1)

    def test_ambiguous_start_is_never_retried(self):
        sent = []
        def fail(request, **kw):
            sent.append(request)
            raise OSError('synthetic-token must not escape')
        t = self.transport(fail)
        with self.assertRaises(c.Stopped) as e: t.request('start')
        self.assertEqual(e.exception.safe(), {'category': 'connection_error', 'http_status': None})
        with self.assertRaises(c.Stopped): t.request('start')
        self.assertEqual(len(sent), 1)

    def test_http_error_body_not_read_or_logged(self):
        error = HTTPError('https://api.apify.com', 403, 'synthetic-token', {}, io.BytesIO(b'synthetic-token'))
        t = self.transport(lambda *a, **k: (_ for _ in ()).throw(error))
        with self.assertRaises(c.Stopped) as e: t.request('start')
        self.assertEqual(e.exception.safe(), {'category': 'http_error', 'http_status': 403})
        self.assertNotIn('synthetic-token', str(e.exception))
        self.assertTrue(t.failed)

    def test_redirect_refused(self):
        t = self.transport(lambda *a, **k: (_ for _ in ()).throw(HTTPError('u', 302, 'x', {}, io.BytesIO())))
        with self.assertRaises(c.Stopped) as e: t.request('start')
        self.assertEqual(e.exception.category, 'redirect_refused')
        self.assertIsNone(c.NoRedirect().redirect_request(None, None, None, None, None, None))

    def test_oversized_start_stops_and_consumes_attempt(self):
        t = self.transport(lambda *a, **k: Response(b'A' * 131073))
        with self.assertRaises(c.Stopped) as e: t.request('start')
        self.assertEqual(e.exception.category, 'response_too_large')
        self.assertEqual(t.counts['start'], 1)
        self.assertTrue(t.failed)

    def test_deadline_before_start(self):
        now = [0]
        t = self.transport(clock=lambda: now[0])
        now[0] = 6290
        with self.assertRaises(c.Stopped): t.request('start')
        self.assertEqual(t.counts, {})

    def test_response_read_deadline(self):
        now = [0]
        class Slow(Response):
            def read1(self, n):
                now[0] = 31
                return super().read1(n)
        t = self.transport(lambda *a, **k: Slow(), clock=lambda: now[0])
        with self.assertRaises(c.Stopped) as e: t.request('start')
        self.assertEqual(e.exception.category, 'deadline_exceeded')

    def test_foreign_identity_rejected(self):
        bad = identity()
        bad['actId'] = 'FOREIGNACTOR00001'
        with self.assertRaises(c.Stopped): self.transport().bind(bad)

    def test_default_routes_bound_to_new_identity(self):
        t = self.transport()
        t.bind(identity())
        for op, field in [('dataset', 'defaultDatasetId'), ('kv', 'defaultKeyValueStoreId'),
                          ('queue', 'defaultRequestQueueId'), ('log', 'id'), ('meter', 'id')]:
            method, url, *_ = t.route(op)
            self.assertEqual(method, 'GET')
            self.assertIn(identity()[field], url)

    def test_no_arbitrary_routes_or_delete(self):
        t = self.transport()
        t.bind(identity())
        for op in ['delete', 'abort', 'profile', 'limits', 'list', 'https://foreign.example']:
            with self.subTest(op=op), self.assertRaises(c.Stopped): t.request(op)
        self.assertEqual(t.counts, {})

    def test_export_retains_errors_with_one_sentinel(self):
        t = self.transport()
        t.bind(identity())
        url = t.route('export')[1]
        for value in ('clean=false', 'skipHidden=false', 'skipEmpty=false', 'limit=7'):
            self.assertIn(value, url)

    def test_poll_and_export_limits(self):
        t = self.transport(lambda *a, **k: Response(status=200))
        t.bind(identity())
        for _ in range(7): t.request('poll')
        with self.assertRaises(c.Stopped): t.request('poll')
        t.request('export')
        with self.assertRaises(c.Stopped): t.request('export')
        self.assertEqual(t.counts, {'poll': 7, 'export': 1})

    def test_strict_json_and_exact_decimal(self):
        self.assertEqual(str(c.strict(b'{"usd":0.1234567890123456789}')['usd']), '0.1234567890123456789')
        for blob in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff'):
            with self.subTest(blob=blob), self.assertRaises(c.Stopped): c.strict(blob)

    def test_native_scope_options_rejected(self):
        v, _ = c.load_sources()
        data = {**identity(), 'status': 'SUCCEEDED', 'buildNumber': CELL['build'],
                'options': copy.deepcopy(CELL['options']), 'startedAt': '2026-10-04T00:00:00Z',
                'finishedAt': '2026-10-04T00:01:00Z'}
        data['options']['maxTotalChargeUsd'] = c.Decimal(CELL['options']['maxTotalChargeUsd'])
        from types import SimpleNamespace
        v.validate_run(data, SimpleNamespace(spec=CELL))
        for field, value in [('memoryMbytes', 1024), ('maxTotalChargeUsd', '0.74'), ('restartOnError', True)]:
            bad = copy.deepcopy(data)
            bad['options'][field] = value
            with self.subTest(field=field), self.assertRaises(v.Fault): v.validate_run(bad, SimpleNamespace(spec=CELL))

    def test_workflow_default_main_attempt_one_no_deletes(self):
        workflow = (c.ROOT.parents[1] / '.github/workflows/apify-continuation-study.yml').read_text()
        self.assertIn('default: false', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('github.run_attempt == 1', workflow)
        self.assertNotIn('strategy:', workflow[workflow.index('  capture:'):])
        self.assertNotIn('workflow_run:', workflow)
        self.assertIn('persist-credentials: false', workflow)

    def test_meter_budget_boundary_and_missing(self):
        c.validate_meter_budget({'usage_total_usd': '0.20'}, CELL)
        c.validate_meter_budget({'usage_total_usd': '0'}, CELL)
        for value in (None, 0.5, 'NaN', '-1'):
            with self.subTest(value=value), self.assertRaises(c.Stopped) as e:
                c.validate_meter_budget({'usage_total_usd': value}, CELL)
            self.assertEqual(e.exception.category, 'meter_unavailable')
        with self.assertRaises(c.Stopped) as e:
            c.validate_meter_budget({'usage_total_usd': '0.20000000000000001'}, CELL)
        self.assertEqual(e.exception.category, 'budget_exceeded')

    def test_native_zero_meter_is_known_not_missing(self):
        validators, _ = c.load_sources()
        data = {'status': 'SUCCEEDED', 'startedAt': '2026-10-04T00:00:00Z',
                'finishedAt': '2026-10-04T00:01:00Z', 'usageTotalUsd': 0}
        meter = c.project_run_meter(validators, data, CELL)
        self.assertEqual(meter['usage_total_usd'], '0')
        c.validate_meter_budget(meter, CELL)
        data['usageTotalUsd'] = True
        self.assertIsNone(c.project_run_meter(validators, data, CELL)['usage_total_usd'])

if __name__ == '__main__': unittest.main()
