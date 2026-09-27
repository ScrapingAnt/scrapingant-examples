import unittest
from catalog_fixture import catalog_response
from state import score_records


class FixtureTests(unittest.TestCase):
    def test_query_contract_independently_scored(self):
        status, payload = catalog_response('/api/catalog?region=eu')
        self.assertEqual(status, 200)
        self.assertTrue(score_records(payload['records'])['exact_match'])
        status, payload = catalog_response('/api/catalog')
        self.assertEqual((status, payload['region']), (200, 'us'))
        self.assertEqual(score_records(payload['records'])['matching_records'], 0)

    def test_ambiguous_unknown_and_empty_query_rejected(self):
        for path in ('/api/catalog?region=', '/api/catalog?region=eu&region=us',
                     '/api/catalog?region=zz', '/api/catalog?unexpected=eu', '/elsewhere'):
            with self.subTest(path=path):
                self.assertNotEqual(catalog_response(path)[0], 200)


if __name__ == '__main__':
    unittest.main()
