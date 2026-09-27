"""Regression tests attack record meaning, origin guards and capture integrity."""
import copy
import contextlib
import io
import sys
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from oracle import EXPECTED_EU, desired_matches, exact_dataset
from storage_state import (SPECIAL_KEY, SPECIAL_VALUE, canonical_origin, origin_of,
                           restore, set_item, validate_snapshot)
from summarize import read_capture, summarize


class FakeDriver:
    current_url = 'http://127.0.0.1:8123/blank'
    def __init__(self):
        self.calls = []
    def execute_script(self, script, *args):
        if script == 'return location.origin;':
            return getattr(self, 'frame_origin', origin_of(self.current_url))
        self.calls.append((script, args))


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(sku=s, currency=c, price_minor=p) for s, c, p in EXPECTED_EU]

    def test_literal_expected_and_order_independent(self):
        self.assertTrue(exact_dataset(list(reversed(self.rows))))
        self.assertEqual(desired_matches(self.rows), 4)

    def test_reject_duplicate_missing_extra_and_wrong_price(self):
        for rows in (self.rows[:-1], self.rows+[self.rows[0]], self.rows[:3]+[self.rows[0]],
                     [dict(self.rows[0], price_minor=826)]+self.rows[1:]):
            with self.subTest(rows=rows):
                self.assertFalse(exact_dataset(rows))

    def test_reject_malformed_schema_and_boolean_number(self):
        for row in (dict(self.rows[0], price_minor=True), dict(self.rows[0], extra=1), {'sku': 'SKU-1'}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                exact_dataset([row]+self.rows[1:])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.driver = FakeDriver()
        self.state = {'schema_version': 1, 'origin': 'http://127.0.0.1:8123', 'items': [['demo_region', 'eu']]}

    def test_arguments_are_not_interpolated(self):
        set_item(self.driver, SPECIAL_KEY, SPECIAL_VALUE)
        script, args = self.driver.calls[0]
        self.assertNotIn(SPECIAL_KEY, script); self.assertNotIn(SPECIAL_VALUE, script)
        self.assertEqual(args, (SPECIAL_KEY, SPECIAL_VALUE))

    def test_origin_port_and_scheme_are_part_of_identity(self):
        self.assertEqual(origin_of('https://EXAMPLE.test:443/path?q=1'), 'https://example.test')
        self.assertNotEqual(origin_of('http://127.0.0.1:8123'), origin_of('http://127.0.0.1:8124'))
        for url in ('data:text/html,hello', 'file:///demo', 'https://user:pass@example.test'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                origin_of(url)

    def test_reject_paths_queries_fragments_and_opaque_snapshot_origins(self):
        for value in ('http://example.test/path', 'http://example.test?q=1', 'http://example.test#frag', 'null'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_origin(value)

    def test_restore_checks_current_origin_before_mutation(self):
        for current in ('http://127.0.0.1:8124/blank', 'https://127.0.0.1:8123/blank', 'http://localhost:8123/blank'):
            self.driver.current_url = current
            with self.subTest(current=current), self.assertRaises(ValueError):
                restore(self.driver, self.state, self.state['origin'])
            self.assertEqual(self.driver.calls, [])

    def test_restore_checks_selected_script_document_not_only_top_url(self):
        self.driver.frame_origin = 'http://127.0.0.1:8124'
        with self.assertRaises(ValueError):
            restore(self.driver, self.state, self.state['origin'])
        self.assertEqual(self.driver.calls, [])

    def test_restore_checks_snapshot_origin_before_mutation(self):
        wrong = dict(self.state, origin='http://127.0.0.1:8124')
        with self.assertRaises(ValueError):
            restore(self.driver, wrong, self.state['origin'])
        self.assertEqual(self.driver.calls, [])

    def test_snapshot_rejects_duplicate_nonstring_and_bad_schema_before_writing(self):
        for items in ([['a', '1'], ['a', '2']], [['a', 3]], [['a']], {'a': '1'}):
            with self.subTest(items=items), self.assertRaises(ValueError):
                restore(self.driver, dict(self.state, items=items), self.state['origin'])
        for value in (dict(self.state, schema_version=True), dict(self.state, extra=1)):
            with self.assertRaises(ValueError):
                validate_snapshot(value)
        self.assertEqual(self.driver.calls, [])

    def test_restore_passes_pairs_as_arguments(self):
        self.state['items'].append([SPECIAL_KEY, SPECIAL_VALUE])
        self.assertEqual(restore(self.driver, self.state, self.state['origin']), 2)
        self.assertEqual(self.driver.calls[0][1], (self.state['items'],))


class PartialCaptureTests(unittest.TestCase):
    def test_failed_round_preserves_observations_without_exception_text(self):
        import browser_matrix
        def failed_round(kind, index, server, base, second_server, second_base, run):
            run['cases'].append({'case': 'partial', 'assertion_passed': True})
            raise RuntimeError('sensitive-local-path-must-not-appear')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'failed.json'
            with patch.object(sys, 'argv', ['browser_matrix.py', '--output', str(output)]), patch.object(browser_matrix, 'one_round', failed_round), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(browser_matrix.main(), 1)
            text = output.read_text(); capture = json.loads(text)
            self.assertEqual(capture['failure'], {'error_type': 'RuntimeError'})
            self.assertEqual(capture['assertions'], 1)
            self.assertNotIn('sensitive-local-path', text)
            with self.assertRaises(ValueError):
                summarize([capture])


class DirectRequestTests(unittest.TestCase):
    def test_loopback_request_ignores_poisoned_proxy_environment(self):
        from catalog_fixture import fixture_server
        from local_http import fetch_catalog
        poisoned = {name: 'http://127.0.0.1:1' for name in
                    ('http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY')}
        poisoned.update({'no_proxy': '', 'NO_PROXY': ''})
        with fixture_server() as (_, base), patch.dict(os.environ, poisoned):
            self.assertTrue(exact_dataset(fetch_catalog(base+'/api/catalog?region=eu')['records']))

    def test_direct_request_rejects_non_fixture_urls(self):
        from local_http import fetch_catalog
        for url in ('https://example.test/api/catalog', 'http://127.0.0.1/api/catalog',
                    'http://user:pass@127.0.0.1:8123/api/catalog', 'http://127.0.0.1:8123/other'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch_catalog(url)


class WaitTests(unittest.TestCase):
    def test_storage_alone_does_not_satisfy_wait(self):
        from browser_support import wait_catalog
        from oracle import EXPECTED_US
        stale = {'stored_region': 'eu', 'rendered_region': 'eu', 'ready': True, 'error': None,
                 'records': [dict(sku=s, currency=c, price_minor=p) for s, c, p in EXPECTED_US]}
        current = dict(stale, records=[dict(sku=s, currency=c, price_minor=p) for s, c, p in EXPECTED_EU])
        class DeterministicWait:
            def __init__(self, driver, *args, **kwargs):
                self.driver = driver
            def until(self, predicate):
                first = predicate(self.driver)
                if first is not False:
                    raise AssertionError('storage-only predicate accepted stale records')
                return predicate(self.driver)
        with patch('browser_support.WebDriverWait', DeterministicWait), patch('browser_support.read_page', side_effect=[stale, current]):
            self.assertEqual(wait_catalog(object(), 'eu', 'eu'), current)


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parent/'expected_output/chrome.json'
        cls.original = read_capture(path)

    def setUp(self):
        self.report = copy.deepcopy(self.original)

    def test_recompute_complete_capture(self):
        summary = summarize([self.report])
        self.assertEqual(summary['extraction_observations'], 36)
        self.assertEqual(summary['diagnostic_observations'], 24)

    def test_reject_missing_round_missing_case_duplicate_case(self):
        mutations = (
            lambda r: r['runs'].pop(),
            lambda r: r['runs'][0]['cases'].pop(),
            lambda r: r['runs'][0]['cases'].__setitem__(0, copy.deepcopy(r['runs'][0]['cases'][1])),
        )
        for mutate in mutations:
            report = copy.deepcopy(self.original); mutate(report)
            with self.assertRaises(ValueError):
                summarize([report])

    def test_reject_tampered_records_despite_passing_flags(self):
        for alteration in ('price', 'duplicate', 'missing', 'extra', 'boolean'):
            report = copy.deepcopy(self.original)
            case = next(c for c in report['runs'][0]['cases'] if c['case'] == 'bootstrap_seed')
            if alteration == 'price': case['records'][0]['price_minor'] += 1
            if alteration == 'duplicate': case['records'][1] = copy.deepcopy(case['records'][0])
            if alteration == 'missing': case['records'].pop()
            if alteration == 'extra': case['records'].append(copy.deepcopy(case['records'][0]))
            if alteration == 'boolean': case['records'][0]['price_minor'] = True
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                summarize([report])

    def test_reject_forged_counts_environment_diagnostics_and_request(self):
        for field, value in [('matching_records', 0), ('stored_region', 'us'), ('page_path', '/catalog?region=eu'),
                             ('assertion_passed', 1), ('ready', False), ('kind', 'diagnostic')]:
            report = copy.deepcopy(self.original)
            case = next(c for c in report['runs'][0]['cases'] if c['case'] == 'bootstrap_seed')
            case[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize([report])
        for mutate in (
            lambda r: r.__setitem__('passed', 999),
            lambda r: r['runs'][0]['environment'].__setitem__('browser', 'firefox'),
            lambda r: r['runs'][0]['cases'][0].__setitem__('error', 'OtherError'),
            lambda r: next(c for c in r['runs'][0]['cases'] if c['kind'] == 'extraction')['request_event'].__setitem__('status', 201),
        ):
            report = copy.deepcopy(self.original); mutate(report)
            with self.assertRaises(ValueError):
                summarize([report])

    def test_reject_duplicate_browser_and_empty_capture(self):
        for reports in ([], [self.report, self.report], [{}]):
            with self.assertRaises(ValueError):
                summarize(reports)

    def test_reject_cross_diagnostic_origin_contradiction(self):
        case = next(c for c in self.report['runs'][0]['cases'] if c['case'] == 'snapshot_restore_contents')
        for snapshot in (case['exported_snapshot'], case['restored_snapshot']):
            snapshot['origin'] = 'http://127.0.0.1:1'
        with self.assertRaises(ValueError):
            summarize([self.report])

    def test_json_reader_rejects_duplicates_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'capture.json'
            for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{bad}'):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    read_capture(path)


if __name__ == '__main__':
    unittest.main()
