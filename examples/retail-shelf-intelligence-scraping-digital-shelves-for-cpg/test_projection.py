"""A saved factual projection must not invent common capture provenance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import collector

ROOT = Path(__file__).parent

class Projection(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((ROOT / "fixtures/adagio-field-projection.json").read_text())

    def replay(self, value):
        with tempfile.TemporaryDirectory(prefix="retail-projection-") as directory:
            path = Path(directory) / "facts.json"
            path.write_text(json.dumps(value))
            return collector.replay_projection(path)

    def test_valid_zero_offset_source_time_is_normalized_to_UTC_seconds(self):
        result = self.replay(self.original)
        self.assertTrue(result["complete"])
        self.assertEqual([r["observed_at_utc"] for r in result["records"]], ["2026-10-13T10:37:02Z"] * 2)
        self.assertEqual([r["source_evidence"]["product_path"] for r in result["records"]],
                         ["projection.records[0]","projection.records[1]"])

    def test_reversed_input_preserves_actual_field_locator_after_SKU_sort(self):
        value = copy.deepcopy(self.original)
        value["records"].reverse()
        result = self.replay(value)
        self.assertTrue(result["complete"])
        self.assertEqual([r["sku"] for r in result["records"]], ["001036002","001036004"])
        self.assertEqual([r["source_evidence"]["product_path"] for r in result["records"]],
                         ["projection.records[1]","projection.records[0]"])
        self.assertEqual([r["source_evidence"]["offer_path"] for r in result["records"]],
                         ["projection.records[1].price_decimal","projection.records[0].price_decimal"])

    def test_each_record_requires_valid_UTC_calendar_time(self):
        for index in (0,1):
            for invalid in ("not-time", "2026-02-30T10:00:00Z", "2026-10-13T10:37:02",
                            "2026-10-13T10:37:02+02:00", "2026-10-13T10:37:02-01:00"):
                with self.subTest(index=index, time=invalid):
                    wrong = copy.deepcopy(self.original)
                    wrong["records"][index]["observed_at_utc"] = invalid
                    with self.assertRaises(ValueError):
                        self.replay(wrong)

    def test_different_full_capture_times_cannot_be_collapsed_to_one_second(self):
        wrong = copy.deepcopy(self.original)
        wrong["records"][1]["observed_at_utc"] = "2026-10-13T10:37:02.999999+00:00"
        with self.assertRaises(ValueError):
            self.replay(wrong)

    def test_different_body_hashes_do_not_become_shared_provenance(self):
        wrong = copy.deepcopy(self.original)
        wrong["records"][1]["source_sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            self.replay(wrong)

    def test_each_body_hash_is_bounded_canonical_SHA256(self):
        for index in (0,1):
            for bad in ("", "a" * 63, "g" * 64, "A" * 64, None, ["a" * 64]):
                with self.subTest(index=index, hash=bad):
                    wrong = copy.deepcopy(self.original)
                    wrong["records"][index]["source_sha256"] = bad
                    with self.assertRaises(ValueError):
                        self.replay(wrong)

    def test_every_selected_identity_pack_and_context_input_is_validated(self):
        mutations = {"source_url":"https://wrong.example/", "product_group_id":"1036", "sku":"001036006",
            "size_literal":"6oz", "pack_size":6, "pack_unit":"gram", "pack_measure":"count",
            "currency":"EUR", "offer_basis":"subscription", "purchase_basis":"one_time", "fulfilment":"pickup",
            "market":"GB", "market_basis":"proxy_country=us"}
        for index in (0,1):
            for field,bad in mutations.items():
                with self.subTest(index=index, field=field):
                    wrong = copy.deepcopy(self.original)
                    wrong["records"][index][field] = bad
                    with self.assertRaises(ValueError):
                        self.replay(wrong)

    def test_pack_boolean_and_wrong_numeric_type_are_not_valid_quantities(self):
        for bad in (True, "3", 3.0):
            with self.subTest(pack=bad):
                wrong = copy.deepcopy(self.original)
                wrong["records"][0]["pack_size"] = bad
                with self.assertRaises(ValueError):
                    self.replay(wrong)

    def test_normalized_price_field_is_a_canonical_decimal_string(self):
        for bad in (9, True, "9", "9.0", "NaN", "-9.00"):
            with self.subTest(price=bad):
                wrong = copy.deepcopy(self.original)
                wrong["records"][0]["price_decimal"] = bad
                with self.assertRaises(ValueError):
                    self.replay(wrong)

    def test_duplicate_missing_and_extra_records_are_rejected(self):
        for rows in ([self.original["records"][0]] * 2, self.original["records"][:1], self.original["records"] * 2):
            with self.subTest(count=len(rows)):
                wrong = copy.deepcopy(self.original)
                wrong["records"] = rows
                with self.assertRaises(ValueError):
                    self.replay(wrong)

    def test_required_capture_or_material_field_cannot_be_omitted(self):
        for field in ("observed_at_utc","source_sha256","product_group_id","pack_size","offer_basis","price_decimal"):
            with self.subTest(field=field):
                wrong = copy.deepcopy(self.original)
                del wrong["records"][1][field]
                with self.assertRaises(ValueError):
                    self.replay(wrong)

    def test_wrong_version_and_oversized_projection_are_rejected(self):
        wrong = copy.deepcopy(self.original)
        wrong["version"] = 2
        with self.assertRaises(ValueError):
            self.replay(wrong)
        wrong = copy.deepcopy(self.original)
        wrong["scope"] = "x" * 262145
        with self.assertRaises(ValueError):
            self.replay(wrong)

    def test_direct_and_managed_source_kinds_cannot_be_mixed(self):
        for index in (0,1):
            wrong = copy.deepcopy(self.original)
            wrong["records"][index]["source_kind"] = "managed_html_observation"
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.replay(wrong)
        wrong = copy.deepcopy(self.original)
        wrong["source_kind"] = "managed_html_observation"
        with self.assertRaises(ValueError):
            self.replay(wrong)

if __name__ == "__main__":
    unittest.main(verbosity=2)
