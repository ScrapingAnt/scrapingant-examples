"""Adversarial offline checks; no credentials, network, or model required."""
import copy
import json
import unittest

from validate import ORACLE, validate_json, validate_records

URL = 'https://example.invalid/owned/complete.html'


def example(case='complete'):
    rows = [{k: v for k, v in r.items() if k != 'status'} for r in ORACLE[case]]
    for r in rows:
        r['source_url'] = URL
    return {'records': rows}, '\n\n'.join(r['evidence'] for r in rows)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.payload, self.markdown = example()

    def check(self, payload=None, markdown=None, case='complete'):
        return validate_records(self.payload if payload is None else payload,
                                self.markdown if markdown is None else markdown,
                                URL, case)

    def test_complete(self):
        r = self.check()
        self.assertEqual(len(r['accepted']), 2)
        self.assertEqual(r['precision'], 1)
        self.assertEqual(r['recall'], 1)
        self.assertTrue(r['complete_run_success'])

    def test_changed_layout_same_values(self):
        p, md = example('changed-layout')
        self.assertEqual(self.check(p, md, 'changed-layout')['exact_match_count'], 2)

    def test_malformed_json(self):
        for raw in ['{', '{"records": [], "records": []}', '{"records": [NaN]}']:
            with self.subTest(raw=raw):
                r = validate_json(raw, self.markdown, URL, 'complete')
                self.assertTrue(r['errors'])
                self.assertEqual(r['accepted'], [])
                self.assertIsNone(r['precision'])

    def test_missing_keys(self):
        for field in self.payload['records'][0]:
            with self.subTest(field=field):
                p = copy.deepcopy(self.payload)
                del p['records'][0][field]
                r = self.check(p)
                self.assertEqual(r['schema_valid_count'], 1)
                self.assertEqual(len(r['accepted']), 1)

    def test_wrong_types_without_coercion(self):
        for value in ['3499', 3499.0, True, [], {}]:
            with self.subTest(value=value):
                self.payload['records'][0]['price_minor'] = value
                self.assertEqual(self.check()['schema_valid_count'], 1)

    def test_extra_keys(self):
        self.payload['records'][0]['debug'] = 'yes'
        self.assertEqual(self.check()['schema_valid_count'], 1)

    def test_invalid_envelope(self):
        self.payload['extra'] = True
        r = self.check()
        self.assertEqual(r['schema_valid_count'], 2)
        self.assertEqual(r['accepted'], [])
        for p in [[], {}, {'records': 'wrong'}]:
            self.assertTrue(self.check(p)['errors'])

    def test_valid_looking_fabrication(self):
        self.payload['records'][0]['price_minor'] = 1
        r = self.check()
        self.assertEqual(r['schema_valid_count'], 2)
        self.assertEqual(r['exact_match_count'], 1)
        self.assertIn('oracle_mismatch:price_minor', r['quarantine'][0]['reasons'])

    def test_wrong_evidence_and_source(self):
        for field, value, reason in [('evidence', 'fabricated quote', 'evidence_not_in_source'),
                                     ('source_url', 'https://wrong.invalid', 'source_url_mismatch'),
                                     ('evidence', self.payload['records'][1]['evidence'], 'evidence_does_not_support_record')]:
            with self.subTest(field=field, value=value):
                p = copy.deepcopy(self.payload)
                p['records'][0][field] = value
                self.assertIn(reason, self.check(p)['quarantine'][0]['reasons'])

    def test_line_wrapping_does_not_change_evidence_support(self):
        original = self.payload['records'][0]['evidence']
        wrapped = original.replace(' | Price:', ' |\nPrice:')
        self.payload['records'][0]['evidence'] = wrapped
        markdown = self.markdown.replace(original, wrapped)
        self.assertEqual(self.check(markdown=markdown)['accepted_count'], 2)
        self.assertEqual(self.check()['accepted_count'], 1)

    def test_value_accuracy_does_not_imply_provenance_acceptance(self):
        self.payload['records'][0]['source_url'] = 'https://wrong.invalid'
        result = self.check()
        self.assertEqual(result['oracle_value_match_count'], 2)
        self.assertEqual(result['accepted_count'], 1)

    def test_duplicate_id_quarantines_all_copies(self):
        self.payload['records'].append(copy.deepcopy(self.payload['records'][0]))
        r = self.check()
        self.assertEqual(r['schema_valid_count'], 3)
        self.assertEqual(len(r['accepted']), 1)
        self.assertEqual(len(r['quarantine']), 2)
        self.assertEqual(r['duplicate_ids'], ['AA101'])

    def test_missing_or_ambiguous_oracle_values_never_accepted(self):
        for case, reason in [('missing-price', 'oracle_unavailable'), ('conflicting-value', 'oracle_ambiguous')]:
            with self.subTest(case=case):
                p, md = example(case)
                r = self.check(p, md, case)
                self.assertEqual(r['schema_valid_count'], 2)
                self.assertEqual(len(r['accepted']), 1)
                self.assertIn(reason, r['quarantine'][0]['reasons'])
                self.assertFalse(r['complete_run_success'])
                self.assertEqual(r['oracle_value_match_count'], 2)
                self.assertEqual(r['accepted_count'], 1)
                self.assertEqual(r['recall'], 1)

    def test_omission(self):
        self.payload['records'].pop()
        r = self.check()
        self.assertEqual(r['omissions'], ['BB202'])
        self.assertEqual(r['recall'], .5)
        self.assertEqual(r['precision'], 1)
        self.assertFalse(r['complete_run_success'])

    def test_empty_output(self):
        r = self.check({'records': []})
        self.assertIsNone(r['schema_pass_rate'])
        self.assertEqual(len(r['omissions']), 2)

    def test_injected_fabrication_and_unknown_id(self):
        self.payload['records'][0]['id'] = 'XX999'
        r = self.check(case='untrusted-instruction')
        self.assertEqual(r['hallucinated_ids'], ['XX999'])
        self.assertEqual(r['omissions'], ['AA101'])
        self.assertEqual(len(r['accepted']), 1)


class ToolBoundaryTests(unittest.TestCase):
    def test_injected_tool_failures(self):
        from live import unpack
        for envelope, reason in [({'isError': True}, 'tool_error'),
                                  ({'content': []}, 'empty_result'),
                                  ({'content': [{'type': 'text', 'text': 'Error: injected'}]}, 'error_looking_text')]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                unpack(envelope)

    def test_plain_and_wrapped_results(self):
        from live import unpack
        for envelope in [{'content': [{'type': 'text', 'text': '# Catalog'}]},
                         {'content': [{'type': 'text', 'text': json.dumps({'result': '# Catalog'})}]},
                         {'structuredContent': {'result': '# Catalog'}}]:
            self.assertEqual(unpack(envelope), '# Catalog')


if __name__ == '__main__':
    unittest.main(verbosity=2)
