"""Corruption tests created before the summary implementation."""
import copy
import unittest

from spec import EXTRACTION, DIAGNOSTICS, JSON_PAYLOAD
from state import EXPECTED_EU, EXPECTED_US, score_records
from summarize import summarize_captures


STAMP = '2026-09-27T12:00:00+00:00'
ORIGINS = {'primary': 'http://127.0.0.1:12345', 'secondary': 'http://127.0.0.1:12346'}


def capture(browser='chromium'):
    cases = []
    for name, (region, stored, query, label) in EXTRACTION.items():
        records = [dict(zip(('sku', 'currency', 'price'), row))
                   for row in (EXPECTED_EU if region == 'eu' else EXPECTED_US)]
        origin = ORIGINS[label]
        cases.append(dict(case=name, kind='extraction', captured_at=STAMP,
                          mode='browser_dom', page_url=origin + '/' + ('?region=eu' if name == 'query_only_without_storage' else ''),
                          origin=origin, request_url=origin + '/api/catalog' + (f'?region={query}' if query else ''),
                          page_status=200, request_status=200, response_region=region,
                          storage_region=stored, records=records, api_records=copy.deepcopy(records),
                          **score_records(records), check_passed=True))
    observations = {
        'json_argument_round_trip': {'input': JSON_PAYLOAD, 'parsed': JSON_PAYLOAD,
                                    'raw': __import__('json').dumps(JSON_PAYLOAD), 'stored_type': 'string'},
        'storage_crud': {'initial': None, 'after_set': 'first', 'after_update': 'second',
                         'after_remove': None, 'count_before_clear': 2, 'count_after_clear': 0},
        'session_storage_not_restored': {'original_local': 'eu', 'original_session': 'tab-only',
            'new_page_local': 'eu', 'new_page_session': None, 'restored_local': 'eu',
            'restored_session': None, 'snapshot': {'cookies': [], 'origins': [
                {'origin': ORIGINS['primary'], 'localStorage': [{'name': 'region', 'value': 'eu'}]}]}},
        'storage_event_other_page': {'writer_events': [], 'reader_events': [
            {'key': 'region', 'oldValue': None, 'newValue': 'eu', 'storageArea': 'localStorage'}],
            'writer_value': 'eu', 'reader_value': 'eu'},
    }
    cases += [dict(case=name, kind='diagnostic', captured_at=STAMP, observed=observations[name],
                   check_passed=True) for name in sorted(DIAGNOSTICS)]
    return {'schema_version': 1, 'browser': browser, 'environment': {'python': '3.12.10',
        'platform': 'test', 'machine': 'test', 'playwright': '1.63.0', 'browser': '1.0'},
        'started_at': STAMP, 'completed_at': STAMP, 'fixture_origins': ORIGINS,
        'rounds': 3, 'runs': [{'round': index, 'cases': copy.deepcopy(cases)} for index in range(1, 4)]}


class SummaryTests(unittest.TestCase):
    def test_complete_two_browser_denominators(self):
        summary = summarize_captures([capture(), capture('firefox')], ['chromium', 'firefox'])
        self.assertEqual(summary['extraction_observations'], 72)
        self.assertEqual(summary['diagnostic_observations'], 24)
        self.assertEqual(summary['passed_checks'], 96)
        self.assertEqual(summary['matching_record_observations'], 144)
        self.assertEqual(summary['record_opportunities'], 288)

    def test_missing_duplicate_extra_cases_and_rounds_rejected(self):
        mutations = [lambda d: d['runs'][0]['cases'].pop(),
                     lambda d: d['runs'][0]['cases'].append(copy.deepcopy(d['runs'][0]['cases'][0])),
                     lambda d: d['runs'][0]['cases'][0].update(case='unknown'),
                     lambda d: d['runs'].pop(),
                     lambda d: d['runs'][1].update(round=1),
                     lambda d: d.update(rounds=2),
                     lambda d: d['runs'][0].update(round=True)]
        for mutation in mutations:
            data = capture()
            mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                summarize_captures([data], ['chromium'])

    def test_browser_identity_coverage_and_duplicates_rejected(self):
        for captures, expected in (([capture()], ['chromium', 'firefox']),
                                   ([capture(), capture()], ['chromium']),
                                   ([capture('webkit')], ['webkit']),
                                   ([capture('firefox')], ['chromium'])):
            with self.assertRaises(ValueError):
                summarize_captures(captures, expected)

    def test_tampered_records_scores_flags_requests_diagnostics_rejected(self):
        mutations = [lambda c: c['records'][0].update(price='0.00'),
                     lambda c: c.update(matching_records=0),
                     lambda c: c.update(check_passed='yes'),
                     lambda c: c.update(request_url='https://example.com/api/catalog?region=eu'),
                     lambda c: c.update(storage_region='us'),
                     lambda c: c.update(mode='invented'),
                     lambda c: c.update(captured_at='not-a-timestamp')]
        for mutation in mutations:
            data = capture()
            mutation(data['runs'][0]['cases'][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                summarize_captures([data], ['chromium'])
        data = capture()
        target = next(c for c in data['runs'][0]['cases'] if c['case'] == 'storage_crud')
        target['observed']['count_after_clear'] = 1
        with self.assertRaises(ValueError):
            summarize_captures([data], ['chromium'])

    def test_rescored_wrong_control_never_accepts_arbitrary_zero_match_rows(self):
        data = capture()
        case = data['runs'][0]['cases'][1]
        case['records'][0]['sku'] = 'UNKNOWN'
        case['api_records'] = copy.deepcopy(case['records'])
        # The control still scores 0/4 but must match the independent US oracle.
        with self.assertRaises(ValueError):
            summarize_captures([data], ['chromium'])

    def test_wrong_kind_cannot_change_denominators_even_with_false_flag(self):
        data = capture()
        data['runs'][0]['cases'][0].update(kind='diagnostic', check_passed=False)
        with self.assertRaises(ValueError):
            summarize_captures([data], ['chromium'])

    def test_report_can_represent_an_honest_failed_observation(self):
        data = capture()
        case = data['runs'][0]['cases'][0]
        case['request_status'] = 500
        case['check_passed'] = False
        self.assertEqual(summarize_captures([data], ['chromium'])['passed_checks'], 47)


if __name__ == '__main__':
    unittest.main()
