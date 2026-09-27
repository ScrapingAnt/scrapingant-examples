"""Boundary tests for the independently written oracle and safe initializer."""
import json
import unittest

from state import EXPECTED_EU, EXPECTED_US, init_script, score_records, validate_origin


class OracleTests(unittest.TestCase):
    def rows(self, tuples=EXPECTED_EU):
        return [dict(zip(('sku', 'currency', 'price'), row)) for row in tuples]

    def test_literal_oracle_and_permutation(self):
        self.assertEqual(EXPECTED_EU[0], ('ATLAS-01', 'EUR', '12.50'))
        self.assertTrue(score_records(self.rows()[::-1])['exact_match'])
        self.assertEqual(score_records(self.rows(EXPECTED_US))['matching_records'], 0)

    def test_duplicates_missing_extra_and_wrong_price_fail_exact(self):
        rows = self.rows()
        for changed in (rows[:-1], rows + [rows[0]], [rows[0]] * 4,
                        rows[:-1] + [dict(rows[-1], price='0.01')]):
            with self.subTest(changed=changed):
                self.assertFalse(score_records(changed)['exact_match'])
        self.assertEqual(score_records([rows[0]] * 4)['matching_records'], 1)

    def test_wrong_schema_and_types_rejected(self):
        for value in (None, {}, [None], [{'sku': 'ATLAS-01'}],
                      [dict(self.rows()[0], price=12.5)],
                      [dict(self.rows()[0], extra=True)]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                score_records(value)


class InitializerTests(unittest.TestCase):
    def test_origin_rejects_paths_credentials_non_loopback(self):
        for bad in ('https://example.com', 'http://localhost:9000', 'http://127.0.0.1:9/path',
                    'http://user@127.0.0.1:9', 'http://127.0.0.1:9?x=1', 'file:fixture.html',
                    'http://127.0.0.1', 'http://127.0.0.1:0', 'http://127.0.0.1:65536'):
            with self.subTest(origin=bad), self.assertRaises(ValueError):
                validate_origin(bad)

    def test_initializer_exact_guard_and_missing_only(self):
        script = init_script('http://127.0.0.1:1234')
        self.assertIn('location.origin !== config.origin', script)
        self.assertIn('localStorage.getItem(config.key) === null', script)
        self.assertIn('"missing_only": true', script)
        self.assertIn('"missing_only": false', init_script('http://127.0.0.1:1234', missing_only=False))

    def test_only_known_regions_and_boolean_mode(self):
        for kwargs in ({'region': "eu';throw 1;//"}, {'missing_only': 'false'}):
            with self.assertRaises(ValueError):
                init_script('http://127.0.0.1:1234', **kwargs)


if __name__ == '__main__':
    unittest.main()
