import copy
import unittest
from contract import TRUTH, score, cost_per_correct


class ContractTests(unittest.TestCase):
    def test_literal_oracle_accepts_all_cases(self):
        for case in TRUTH:
            self.assertTrue(score(case, TRUTH[case])["accepted_page"])

    def test_wrong_and_invented_values_fail(self):
        for field in TRUTH["links"][0]:
            candidate = copy.deepcopy(TRUTH["links"])
            candidate[0][field] = "invented"
            self.assertFalse(score("links", candidate)["accepted_page"])

    def test_extra_missing_duplicate_and_reordered_records_fail(self):
        expected = copy.deepcopy(TRUTH["links"])
        for candidate in ([], expected[:1], expected + expected[:1], expected[::-1], expected[:1] * 2):
            self.assertFalse(score("links", candidate)["accepted_page"])

    def test_shape_type_and_extra_fields_fail(self):
        expected = copy.deepcopy(TRUTH["links"])
        for candidate in (None, {}, [1, 2], [{**expected[0], "extra": 0}, expected[1]]):
            self.assertFalse(score("links", candidate)["accepted_page"])

    def test_zero_correct_is_undefined_and_failures_stay_charged(self):
        self.assertIsNone(cost_per_correct(0.10, 0))
        self.assertEqual(cost_per_correct(0.10, 2), 0.05)

    def test_displayed_strings_are_not_numeric_coercions(self):
        candidate = copy.deepcopy(TRUTH["catalog"])
        candidate[0]["displayed_price"] = 1234.50
        self.assertFalse(score("catalog", candidate)["accepted_page"])


if __name__ == "__main__":
    unittest.main()
