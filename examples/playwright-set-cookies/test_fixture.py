"""Exercise server boundaries without relying on the browser or oracle."""
import json
import unittest
from urllib.request import Request, ProxyHandler, build_opener

from catalog_fixture import serve_catalog

# Loopback fixture reads must not inherit an ambient outbound proxy.
urlopen = build_opener(ProxyHandler({})).open


class FixtureTests(unittest.TestCase):
    def test_cookie_and_region_are_independent_inputs(self):
        with serve_catalog() as fixture:
            def read(path, cookie=None):
                req = Request(fixture.origin + path, headers={'Cookie': cookie} if cookie else {})
                with urlopen(req) as response:
                    return response.status, json.load(response)
            status, retail = read('/api/catalog?region=EU')
            self.assertEqual(status, 200)
            self.assertEqual(retail['records'][0], {'sku': 'SKU-101', 'currency': 'EUR', 'price': '10.80'})
            _, member_us = read('/api/catalog', 'demo_session=member-v1')
            self.assertEqual(member_us['records'][0], {'sku': 'SKU-101', 'currency': 'USD', 'price': '9.00'})
            _, member_eu = read('/api/catalog?region=EU', 'demo_session=member-v1')
            self.assertEqual(member_eu['records'][-1], {'sku': 'SKU-404', 'currency': 'EUR', 'price': '32.40'})
            self.assertEqual(fixture.hit_count('/api/catalog'), 3)

    def test_seed_and_mutation_supply_scoped_cookies(self):
        with serve_catalog() as fixture:
            with urlopen(fixture.origin + '/seed') as response:
                cookie = response.headers.get('Set-Cookie')
                self.assertIsNotNone(cookie)
                self.assertIn('demo_session=member-v1', cookie)
                self.assertIn('HttpOnly', cookie)
                self.assertIn('Path=/', cookie)
            with urlopen(fixture.origin + '/session/guest') as response:
                self.assertIn('demo_session=guest-v1', response.headers.get('Set-Cookie'))


if __name__ == '__main__':
    unittest.main()
