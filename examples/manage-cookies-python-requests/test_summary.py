"""Do not publish a plausible summary of an incomplete or duplicated capture."""
import copy
import unittest
from summarize import summarize
from requests_matrix import run_matrix
from oracle import score


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = run_matrix(1)

    def test_derived_denominators(self):
        result = summarize(self.capture)
        self.assertEqual(result["extraction_observations"], 12)
        self.assertEqual(result["diagnostic_observations"], 6)
        self.assertEqual(result["matching_records"], 16)
        self.assertEqual(result["expected_record_comparisons"], 48)

    def test_duplicate_case_is_rejected(self):
        capture = copy.deepcopy(self.capture)
        capture["rounds"][0]["observations"][-1] = capture["rounds"][0]["observations"][0]
        with self.assertRaises(ValueError):
            summarize(capture)

    def test_missing_case_is_rejected(self):
        capture = copy.deepcopy(self.capture)
        capture["rounds"][0]["observations"].pop()
        with self.assertRaises(ValueError):
            summarize(capture)

    def test_stale_scores_cannot_override_records(self):
        capture = copy.deepcopy(self.capture)
        capture["rounds"][0]["observations"][1]["records"] *= 2
        with self.assertRaises(ValueError):
            summarize(capture)

    def test_updated_score_cannot_hide_extra_duplicate(self):
        capture = copy.deepcopy(self.capture)
        row = capture["rounds"][0]["observations"][1]
        row["records"].append(row["records"][0])
        row["row_count"] = 5
        row.update(score(row["records"]))
        with self.assertRaises(ValueError):
            summarize(capture)

    def test_inconsistent_expected_count_is_rejected(self):
        capture = copy.deepcopy(self.capture)
        capture["rounds"][0]["observations"][0]["expected_matching_records"] = 4
        with self.assertRaises(ValueError):
            summarize(capture)


if __name__ == "__main__":
    unittest.main()
