"""Checks the fixture and measured extraction contract, not network speed."""
import unittest
from requests import Session
from requests.cookies import CookieConflictError
from catalog_fixture import CatalogFixture


class CatalogTests(unittest.TestCase):
    def test_redirect_response_jar_is_not_accumulated_session(self):
        with CatalogFixture() as fixture, Session() as session:
            session.trust_env = False
            response = session.get(fixture.base_url + "/login", timeout=5)
            self.assertEqual(len(response.history), 1)
            self.assertEqual(sorted(c.name for c in response.cookies), ["region", "region"])
            self.assertEqual(sorted(c.name for c in session.cookies), ["region", "region", "sid"])
            with self.assertRaises(CookieConflictError):
                session.cookies.get("region")
            self.assertEqual(session.cookies.get("region", domain="127.0.0.1", path="/catalog/eu"), "EUR")
            session.cookies.clear(domain="127.0.0.1", path="/catalog/eu", name="region")
            self.assertEqual(session.cookies.get("region", domain="127.0.0.1", path="/catalog/us"), "USD")

    def test_path_scope_and_revocation_are_wire_observations(self):
        with CatalogFixture() as fixture, Session() as session:
            session.trust_env = False
            session.get(fixture.base_url + "/login", timeout=5)
            eu = session.get(fixture.base_url + "/catalog/eu/products", timeout=5).json()
            us = session.get(fixture.base_url + "/catalog/us/products", timeout=5).json()
            self.assertEqual(eu["records"][0], {"sku": "BK-101", "currency": "EUR", "price_minor": 1499})
            self.assertEqual(us["records"][0], {"sku": "BK-101", "currency": "USD", "price_minor": 1699})
            self.assertEqual(eu["wire"]["region_cookie_count"], 1)
            self.assertEqual(us["wire"]["region_cookie_count"], 1)
            fixture.revoke()
            revoked = session.get(fixture.base_url + "/catalog/eu/products", timeout=5).json()
            self.assertTrue(revoked["wire"]["session_cookie_received"])
            self.assertFalse(revoked["wire"]["active_member"])
            self.assertEqual(revoked["records"][0]["price_minor"], 1999)


if __name__ == "__main__":
    unittest.main()
