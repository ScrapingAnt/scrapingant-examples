"""The captured cases must expose different state at the actual server boundary."""
import unittest
from requests_matrix import run_round


class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_round(1)
        cls.cases = {row["case"]: row for row in cls.result["observations"]}

    def test_literal_extraction_outcomes(self):
        expected = {
            "independent_requests": 0, "persistent_session": 4,
            "per_call_cookies": 4, "per_call_followup": 0,
            "final_response_cookies_only": 0, "lwp_full_restore": 4,
            "get_dict_roundtrip": 0, "request_prepare": 0,
            "session_prepare_request": 4, "expired_session": 0,
            "clear_session": 0, "server_revocation": 0,
        }
        self.assertEqual({name: row["matching_records"] for name, row in self.cases.items()}, expected)
        self.assertTrue(all(row["check_passed"] for group in ("observations", "diagnostics") for row in self.result[group]))

    def test_flattened_jar_changes_actual_request_currency(self):
        self.assertTrue(self.cases["lwp_full_restore"]["wire"]["region_is_eur"])
        self.assertTrue(self.cases["get_dict_roundtrip"]["wire"]["region_is_usd"])
        self.assertEqual(self.cases["get_dict_roundtrip"]["records"][0],
                         {"sku": "BK-101", "currency": "USD", "price_minor": 1699})

    def test_per_call_cookies_are_not_saved_to_session(self):
        self.assertEqual(self.cases["per_call_cookies"]["stored_cookie_count"], 0)
        self.assertTrue(self.cases["per_call_cookies"]["wire"]["active_member"])
        self.assertFalse(self.cases["per_call_followup"]["wire"]["session_cookie_received"])

    def test_revocation_is_distinct_from_expiry_and_clear(self):
        self.assertTrue(self.cases["server_revocation"]["wire"]["session_cookie_received"])
        self.assertFalse(self.cases["server_revocation"]["wire"]["active_member"])
        self.assertFalse(self.cases["expired_session"]["wire"]["session_cookie_received"])
        self.assertFalse(self.cases["clear_session"]["wire"]["session_cookie_received"])


if __name__ == "__main__":
    unittest.main()
