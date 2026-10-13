"""Missing observations must never turn into stock or disappearance assertions."""
import copy
import json
from pathlib import Path
import unittest
import collector

ROOT = Path(__file__).parent

def snapshot(name, at):
    return collector.parse_page((ROOT / f"fixtures/{name}.html").read_bytes(),
                                requested_source_url=collector.OWNED_SOURCE, observed_at_utc=at)

class Changes(unittest.TestCase):
    def setUp(self):
        self.before = snapshot("baseline", "2026-10-13T11:00:00Z")
        self.after = snapshot("changed", "2026-10-13T12:00:00Z")
        self.partial = snapshot("partial", "2026-10-13T12:00:00Z")

    def test_changed_and_partial_snapshots_match_literal_oracles(self):
        for name, result in (("changed", self.after), ("partial", self.partial)):
            with self.subTest(name=name):
                self.assertEqual(result["records"], json.loads((ROOT / f"fixtures/{name}-records.json").read_text()))
        self.assertTrue(self.after["complete"])
        self.assertFalse(self.partial["complete"])

    def test_comparable_changes_report_only_the_selected_offers(self):
        report = collector.change_report(self.before, self.after)
        self.assertEqual(report["changes"], [
            {"sku":"000701002", "variant":"3oz", "fields":{
                "price":{"before":"8.25", "after":"8.75"},
                "availability":{"before":"in_stock", "after":"out_of_stock"}}},
            {"sku":"000701004", "variant":"16oz", "fields":{
                "availability":{"before":"out_of_stock", "after":"unknown"}}}])
        self.assertEqual(report["unobserved_prior_records"], [])

    def test_partial_omission_retains_prior_record_and_original_time(self):
        report = collector.change_report(self.before, self.partial)
        self.assertFalse(report["current_complete"])
        self.assertEqual(report["changes"], [{"sku":"000701002", "variant":"3oz", "fields":{
            "price":{"before":"8.25", "after":"8.50"}}}])
        self.assertEqual(report["unobserved_prior_records"], [self.before["records"][1]])
        self.assertEqual(report["unobserved_prior_records"][0]["observed_at_utc"], "2026-10-13T11:00:00Z")
        self.assertNotIn("removed", report)

    def test_failed_acquisition_does_not_report_every_prior_SKU_out_of_stock(self):
        failed = {"records":[], "rejected":[{"sku":None,"reason":"HTTP_failure"}], "complete":False}
        report = collector.change_report(self.before, failed)
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["unobserved_prior_records"], self.before["records"])

    def test_even_complete_selected_omission_is_not_inventory_disappearance(self):
        current = copy.deepcopy(self.partial)
        current["complete"] = True
        report = collector.change_report(self.before, current)
        self.assertEqual(len(report["unobserved_prior_records"]), 1)

    def test_pack_change_is_rejected_and_previous_pack_is_retained(self):
        current = snapshot("changed-pack", "2026-10-13T12:00:00Z")
        self.assertFalse(current["complete"])
        self.assertEqual(current["rejected"], [{"sku":"000701004", "reason":"pack_identity_changed"}])
        report = collector.change_report(self.before, current)
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["unobserved_prior_records"], [self.before["records"][1]])

    def test_currency_market_offer_fulfilment_changes_are_not_price_comparisons(self):
        for field, value in (("currency","EUR"), ("market","GB"), ("fulfilment","pickup"),
                             ("offer_kind","subscription"), ("variant","12oz"), ("pack_quantity",12)):
            with self.subTest(field=field):
                current = copy.deepcopy(self.after)
                current["records"][0][field] = value
                report = collector.change_report(self.before, current)
                self.assertEqual([c["sku"] for c in report["changes"]], ["000701004"])
                self.assertEqual(len(report["unobserved_prior_records"]), 1)
                self.assertEqual(len(report["new_observations"]), 1)

    def test_same_or_older_observation_cannot_overwrite_a_newer_record(self):
        for time in ("2026-10-13T10:00:00Z", "2026-10-13T11:00:00Z"):
            with self.subTest(time=time):
                current = copy.deepcopy(self.after)
                for r in current["records"]:
                    r["observed_at_utc"] = time
                with self.assertRaises(ValueError):
                    collector.change_report(self.before, current)

    def test_duplicate_snapshot_ID_is_rejected_instead_of_last_write_wins(self):
        current = copy.deepcopy(self.after)
        current["records"].append(copy.deepcopy(current["records"][0]))
        with self.assertRaises(ValueError):
            collector.change_report(self.before, current)

    def test_literal_oracle_detects_every_material_field_tamper(self):
        expected = json.loads((ROOT / "fixtures/baseline-records.json").read_text())
        collector.verify_oracle(self.before["records"], expected)
        bad_fields = {"sku":"other", "variant":"16oz", "variant_id":"invented", "price":"2.00",
                      "currency":"EUR", "pack_quantity":16, "pack_unit":"gram", "availability":"out_of_stock",
                      "requested_source_url":"https://wrong.example/", "observed_source_url":"https://wrong.example/",
                      "observed_at_utc":"2026-10-13T13:00:00Z", "market":"GB", "fulfilment":"pickup",
                      "offer_kind":"subscription", "product_id":"701"}
        for field, value in bad_fields.items():
            with self.subTest(field=field):
                wrong = copy.deepcopy(self.before["records"])
                wrong[0][field] = value
                with self.assertRaises(ValueError):
                    collector.verify_oracle(wrong, expected)

    def test_receipt_cost_and_accepted_record_denominator_are_separate(self):
        self.assertEqual(collector.cost_summary({"actual_receipt_credits":1,"credit_receipt_state":"known"}, 2),
                         {"actual_receipt_credits":1,"unknown_charge_requests":0,"accepted_records":2,"credits_per_accepted_record":"0.50"})
        no_records = collector.cost_summary({"actual_receipt_credits":10,"credit_receipt_state":"known"}, 0)
        self.assertEqual(no_records["actual_receipt_credits"], 10)
        self.assertIsNone(no_records["credits_per_accepted_record"])
        unknown = collector.cost_summary({"actual_receipt_credits":None,"credit_receipt_state":"unknown"}, 2)
        self.assertEqual(unknown["unknown_charge_requests"], 1)
        self.assertIsNone(unknown["credits_per_accepted_record"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
