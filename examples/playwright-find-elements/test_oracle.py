"""Regression contracts: reject malformed records and tampered capture matrices."""
import copy
import unittest

from oracle import CATALOG, CASE_IDS, DIAGNOSTIC_IDS, validate_records, summarize


class RecordTests(unittest.TestCase):
    def test_literal_catalog_is_accepted(self):
        self.assertEqual(validate_records(copy.deepcopy(CATALOG), CATALOG), CATALOG)

    def test_missing_record_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_records(CATALOG[:2], CATALOG)

    def test_duplicate_record_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_records([CATALOG[0], CATALOG[0], CATALOG[2]], CATALOG)

    def test_wrong_price_is_rejected(self):
        records = copy.deepcopy(CATALOG)
        records[1]["price"] = "12.01"
        with self.assertRaises(ValueError):
            validate_records(records, CATALOG)

    def test_unknown_field_is_rejected(self):
        records = copy.deepcopy(CATALOG)
        records[0]["debug"] = "unexpected"
        with self.assertRaises(ValueError):
            validate_records(records, CATALOG)

    def test_null_and_numeric_price_are_rejected(self):
        for value in (None, 24.5, "", "NaN"):
            records = copy.deepcopy(CATALOG)
            records[0]["price"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_records(records, CATALOG)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        from expectations import expected_cases, expected_diagnostics
        self.docs = []
        for browser in ("chromium", "firefox"):
            rows = []
            for round_id in (1, 2, 3):
                for case, observation in expected_cases().items():
                    rows.append({"round": round_id, "case": case, "observation": copy.deepcopy(observation)})
            self.docs.append({
                "schema": 1,
                "environment": {"browser": browser, "browser_version": "test-1", "python": "3.12.10", "playwright": "1.63.0", "os": "test-os", "architecture": "test-arch"},
                "observations": rows,
                "diagnostics": [{"round": r, "case": c, "observation": copy.deepcopy(o)} for r in (1, 2, 3) for c, o in expected_diagnostics().items()],
            })

    def test_complete_matrix_has_exact_denominators(self):
        result = summarize(self.docs)
        self.assertEqual(result["extraction_observations"], 72)
        self.assertEqual(result["diagnostic_observations"], 24)
        self.assertEqual(result["passed"], 96)

    def test_missing_case_is_rejected(self):
        self.docs[0]["observations"].pop()
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_duplicate_case_is_rejected(self):
        self.docs[0]["observations"][-1] = copy.deepcopy(self.docs[0]["observations"][0])
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_unexpected_case_is_rejected(self):
        self.docs[0]["observations"][0]["case"] = "invented"
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_missing_round_is_rejected(self):
        self.docs[0]["observations"] = [row for row in self.docs[0]["observations"] if row["round"] != 3]
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_changed_record_rejected_even_if_pass_flag_added(self):
        row = next(row for row in self.docs[0]["observations"] if row["case"] == "scoped_records")
        row["observation"]["records"][0]["sku"] = "FORGED"
        row["passed"] = True
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_environment_missing_or_wrong_version_rejected(self):
        for field, value in (("browser_version", ""), ("playwright", "0.0.0")):
            docs = copy.deepcopy(self.docs)
            docs[0]["environment"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): summarize(docs)

    def test_duplicate_browser_rejected(self):
        self.docs[1]["environment"]["browser"] = "chromium"
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_changed_diagnostic_rejected(self):
        self.docs[0]["diagnostics"][0]["observation"] = {"outcome": "found"}
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_wrong_schema_rejected(self):
        for schema in (2, True, 1.0, "1"):
            self.docs[0]["schema"] = schema
            with self.subTest(schema=schema), self.assertRaises(ValueError): summarize(self.docs)

    def test_boolean_count_is_not_accepted_as_one(self):
        row = next(row for row in self.docs[0]["observations"] if row["case"] == "eager_count_all")
        row["observation"]["count"] = True
        with self.assertRaises(ValueError): summarize(self.docs)

    def test_inconsistent_runtime_between_browsers_rejected(self):
        self.docs[1]["environment"]["os"] = "another-os"
        with self.assertRaises(ValueError): summarize(self.docs)
