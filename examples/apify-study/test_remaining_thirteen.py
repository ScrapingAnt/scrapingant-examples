"""Exact finite continuation and encrypted future scope, synthetic offline only."""
import copy
import json
import unittest
from unittest.mock import patch

import runner as r
import workflow_driver as driver
import test_runner as fixture
import test_transport as age_tests

EXPECTED = ('cap-r2-rag-web-browser-dynamic', 'cap-r2-rag-web-browser-formatting',
    'cap-r3-cheerio-static', 'cap-r3-cheerio-dynamic', 'cap-r3-web-static',
    'cap-r3-web-dynamic', 'cap-r3-playwright-static', 'cap-r3-playwright-dynamic',
    'cap-r3-puppeteer-static', 'cap-r3-puppeteer-dynamic', 'cap-r3-rag-web-browser-static',
    'cap-r3-rag-web-browser-dynamic', 'cap-r3-rag-web-browser-formatting')


class RemainingThirteenTests(unittest.TestCase):
    def test_manifest_and_execution_allowlist_are_exact_thirteen_and_secret_free(self):
        with patch.object(driver.os, 'environ', fixture.ForbiddenEnvironment()), \
                patch.object(driver, 'plan', side_effect=AssertionError('manifest read source')):
            self.assertEqual(tuple(driver.smoke_manifest('capability-unstarted-thirteen')), EXPECTED)
        self.assertEqual(tuple(driver.EXECUTION_CELL_ALLOWLIST), EXPECTED)
        self.assertEqual(len(set(EXPECTED)), 13)
        self.assertIn('capability-unstarted-thirteen', driver.MANIFEST_SCOPES)
        workflow = (driver.ROOT.parents[1]/'.github/workflows/apify-study-smoke.yml').read_text()
        self.assertIn('          - capability-unstarted-thirteen', workflow)

    def test_completed_and_deferred_cells_cannot_read_plan_or_environment_even_when_open(self):
        all_cells = list(driver.ALLOWED_CELLS) + list(driver.CAPABILITY_CELLS)
        excluded = [cell for cell in all_cells if cell not in EXPECTED]
        for phase in (driver.capture, driver.cleanup):
            for cell in excluded:
                with self.subTest(phase=phase.__name__, cell=cell), \
                        patch.object(r, 'RUNNER_READY', True), \
                        patch.object(driver, 'plan', side_effect=AssertionError('excluded cell read plan')):
                    with self.assertRaises(r.Fault) as error:
                        phase(cell, environ=fixture.ForbiddenEnvironment())
                self.assertEqual(error.exception.category, 'invalid_cell')

    def test_original_plan_and_native_contracts_remain_pinned(self):
        raw = (driver.ROOT/'capability-plan.json').read_bytes()
        self.assertEqual(r.sha(raw), 'b1b409024d3391bc9a73a506e8722c5227861083907cb98e4441b7b3dc557bcc')
        plan = r.load_reviewed_plan(raw)
        self.assertEqual(len(plan['cells']), 36)
        selected = [c for c in plan['cells'] if c['cell_id'] in EXPECTED]
        self.assertEqual(tuple(c['cell_id'] for c in selected), EXPECTED)
        for cell in selected:
            self.assertEqual(cell['force_permission_level'], 'LIMITED_PERMISSIONS')
            self.assertEqual(cell['options']['timeoutSecs'], 120)
            self.assertEqual(cell['options']['maxTotalChargeUsd'], '0.08')
            self.assertIs(cell['options']['restartOnError'], False)
        self.assertFalse(any(c.endswith('-website-content-crawler') for c in EXPECTED))


class FutureIdentityTests(fixture.TestTools, unittest.TestCase):
    def test_full_and_partial_identity_survive_standard_age_readback_privately(self):
        transports = [self.normal(), fixture.FakeTransport([
            r.Reply(201, fixture.response('READY')),
            r.Fault('unexpected_http_status', 'response_status', 403)])]
        for transport in transports:
            with self.subTest(partial=len(transport.replies) == 2):
                state = self.capture(transport)
                value = json.loads(self.saved[-1])
                self.assertEqual(value['recovery_identity'], {'schema_version': 1, 'identity': state.identity})
                self.assertEqual(set(state.identity), set(r.IDENTITY_FIELDS) |
                    {'startedAt', 'finishedAt', 'build', 'options', 'status'})
                self.assertEqual(value['scope_association_sha256'], r.scope_commitment(state.identity))
                helper = age_tests.AgeTransportTests('test_standard_age_roundtrip_requires_durable_readback')
                helper.setUpClass(); helper.setUp(); self.addCleanup(helper.doCleanups)
                helper.payload = self.saved[-1]
                encrypted = helper.encrypt()
                helper.verify(encrypted, validate_payload=lambda v:
                    v['recovery_identity'] == {'schema_version': 1, 'identity': state.identity})
                self.assertEqual(helper.private.read_bytes(), self.saved[-1])
                for key in r.IDENTITY_FIELDS:
                    self.assertNotIn(state.identity[key].encode(), helper.cipher.read_bytes())
                    if key != 'actId':
                        self.assertNotIn(state.identity[key], json.dumps(r.public_result(state)))
                self.assertNotIn(fixture.TOKEN, self.saved[-1].decode())

    def test_missing_validated_identity_is_null_and_never_imputed(self):
        bad = fixture.response(); del bad['data']['defaultRequestQueueId']
        for reply in (r.Fault('transport_error', 'request'), r.Reply(201, bad)):
            state = self.capture(fixture.FakeTransport([reply]))
            self.assertIn('recovery_identity', state.evidence)
            self.assertIsNone(state.evidence['recovery_identity'])
            self.assertNotIn('PrivateOwner', self.saved[-1].decode())

    def test_mutated_encrypted_identity_cannot_restore_as_the_original_private_state(self):
        state = self.capture(self.normal())
        self.assertIsNotNone(state.evidence.get('recovery_identity'))
        for field, wrong in [('id', 'ForeignRun'), ('userId', 'ForeignOwner'),
                             ('status', 'RUNNING'), ('build', '9.9.9')]:
            raw = json.loads(r.serialize_private_state(state))
            raw['evidence']['recovery_identity']['identity'][field] = wrong
            raw['plaintext_sha256'] = r.sha(r.canonical(raw['evidence']))
            with self.subTest(field=field), self.assertRaises(r.Fault):
                r.restore_private_state(r.canonical(raw), self.plan)


if __name__ == '__main__':
    unittest.main()
