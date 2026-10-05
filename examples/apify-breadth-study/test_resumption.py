"""Synthetic/offline checks of prospective admission and counter sequencing."""
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import controller as c
import recover_existing as recovery

PLAN = c.load_plan()


class ResumptionTests(unittest.TestCase):
    def transport(self, now, **overrides):
        cell = next(x for x in PLAN['cells'] if x['cell_id'] == 'breadth-r1-playwright')
        return SimpleNamespace(cell=cell, failed=False, counts={'export': 1},
                               clock=lambda: now[0], deadline=100, **overrides)

    def test_every_future_browser_case_is_in_finite_admission_range(self):
        revised = PLAN['resumption_revision']['corrected_browser_cells']
        self.assertEqual(len(revised), 8)
        for cell in PLAN['cells']:
            if cell['cell_id'] not in revised:
                continue
            hook = cell['input']['preNavigationHooks']
            count = int(re.search(r'count=(\d+);', hook)[1])
            self.assertEqual(count, cell['assigned_case_count'])
            self.assertEqual(cell['maximum_owned_resource_admissions'], count * 3)
            self.assertEqual(len(cell['input']['startUrls']), count)
            self.assertEqual(sum(cell['mode_distribution'].values()), count)
            self.assertEqual(sum(cell['layout_distribution'].values()), count)
            self.assertEqual({int(x['userData']['case_id'][3:]) for x in cell['input']['startUrls']}, set(range(count)))
            self.assertIn('maximum:3', hook)
            self.assertIn('last+200-performance.now()', hook)
            self.assertIn("request.method()!=='GET'", hook)
            self.assertIn('used.has(request.url())', hook)
            self.assertNotIn('count=3600;', hook)

    def test_historical_first_cell_input_commitment_remains_unchanged(self):
        first = next(x for x in PLAN['cells'] if x['cell_id'] == 'breadth-r1-web')
        self.assertEqual(first['native_input_sha256'], 'b38d8c371afc6893246783cdad57e998235083235eb36f0c104a2e268e636600')
        self.assertEqual(c.sha(c.canonical(first['input'])), first['native_input_sha256'])
        self.assertIn('count=3600;', first['input']['preNavigationHooks'])
        self.assertFalse(PLAN['resumption_revision']['first_cell_rerun_authorized'])

    def test_readiness_retries_concurrency_and_spending_caps_preserved(self):
        for cell in PLAN['cells']:
            if cell['task'] == 'browser-products':
                self.assertIn('timeout:8000', cell['input']['postNavigationHooks'])
                self.assertEqual(cell['input']['maxRequestRetries'], 0)
                self.assertEqual(cell['input']['maxConcurrency'], 5)
                self.assertEqual(cell['options']['maxTotalChargeUsd'], '0.75')
                self.assertEqual(cell['options']['timeoutSecs'], 5400)
                self.assertFalse(cell['options']['restartOnError'])
                self.assertEqual(cell['input']['proxyConfiguration'], {'useApifyProxy': True})

    def test_settle_finishes_before_one_existing_metadata_request(self):
        now = [0]
        transport = self.transport(now)
        seen = []
        def sleep(seconds):
            seen.append(seconds)
            now[0] += seconds
        with patch.object(c, 'ACTIVE_CELL', transport.cell['cell_id']):
            self.assertEqual(c.settle_metadata(transport, sleeper=sleep), 6)
        self.assertEqual(seen, [6])
        self.assertEqual(transport.counts, {'export': 1})

    def test_no_settle_or_request_before_closed_guard(self):
        t = self.transport([0])
        with patch.object(c, 'ACTIVE_CELL', None), self.assertRaises(c.Stopped):
            c.settle_metadata(t, sleeper=lambda _: self.fail('sleep'))

    def test_deadline_is_reserved_before_sleep(self):
        t = self.transport([80])
        with patch.object(c, 'ACTIVE_CELL', t.cell['cell_id']), self.assertRaises(c.Stopped) as stopped:
            c.settle_metadata(t, sleeper=lambda _: self.fail('sleep'))
        self.assertEqual(stopped.exception.category, 'deadline_exceeded')

    def test_early_wake_and_backward_clock_fail_without_metadata(self):
        for ended in (0, 5.999, -1):
            now = [0]
            t = self.transport(now)
            with self.subTest(ended=ended), patch.object(c, 'ACTIVE_CELL', t.cell['cell_id']), self.assertRaises(c.Stopped):
                c.settle_metadata(t, sleeper=lambda _: now.__setitem__(0, ended))
            self.assertEqual(t.counts, {'export': 1})

    def test_oversleep_cannot_extend_deadline(self):
        now = [0]
        t = self.transport(now)
        with patch.object(c, 'ACTIVE_CELL', t.cell['cell_id']), self.assertRaises(c.Stopped):
            c.settle_metadata(t, sleeper=lambda _: now.__setitem__(0, 86))

    def test_repeated_or_failed_capture_cannot_settle(self):
        for counts, failed in (({}, False), ({'export': 1, 'dataset': 1}, False), ({'export': 1}, True)):
            t = self.transport([0]); t.counts = counts; t.failed = failed
            with self.subTest(counts=counts, failed=failed), patch.object(c, 'ACTIVE_CELL', t.cell['cell_id']), self.assertRaises(c.Stopped):
                c.settle_metadata(t, sleeper=lambda _: self.fail('sleep'))

    def test_native_charge_cap_still_diagnoses_excess(self):
        cell = next(x for x in PLAN['cells'] if x['cell_id'] == 'breadth-r1-playwright')
        with self.assertRaises(c.Stopped) as stopped:
            c.validate_meter_budget({'usage_total_usd': '0.751'}, cell)
        self.assertEqual(stopped.exception.category, 'budget_exceeded')

    def test_closed_recovery_pin_normalizes_only_reviewed_guard_assignments(self):
        name = 'apify-breadth-study/controller.py'
        closed = re.sub(rb'^ACTIVE_CELL = .*$', b'ACTIVE_CELL = None', (c.ROOT / 'controller.py').read_bytes(), flags=re.MULTILINE)
        expected = recovery.sha(closed)
        activated = closed.replace(b'ACTIVE_CELL = None', b"ACTIVE_CELL = 'breadth-r1-playwright'")
        self.assertEqual(recovery.dependency_digest(name, activated), expected)
        changed = activated.replace(b'METADATA_SETTLE_SECONDS = 6', b'METADATA_SETTLE_SECONDS = 7')
        self.assertNotEqual(recovery.dependency_digest(name, changed), expected)
        foreign = closed.replace(b'ACTIVE_CELL = None', b"ACTIVE_CELL = 'breadth-r1-article'")
        with self.assertRaises(ValueError):
            recovery.dependency_digest(name, foreign)

    def test_live_recovery_refuses_an_active_paid_cell(self):
        with patch.object(c, 'ACTIVE_CELL', 'breadth-r1-playwright'), self.assertRaises(recovery.RecoveryError):
            recovery.load_reviewed()


if __name__ == '__main__':
    unittest.main()
