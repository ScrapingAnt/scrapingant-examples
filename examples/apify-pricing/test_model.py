"""Hand-derived acceptance tests; synthetic inputs, never provider output."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from model import reconcile

PACKET = Path(__file__).resolve().parent
RATES = json.loads((PACKET / "rates.json").read_text())
SOURCE = {
    "url": "https://docs.apify.com/actors/publishing/monetize/pay-per-event",
    "checked_on": "2026-10-02",
    "note": "Synthetic Actor configured with documented default start-event price",
}


def fixture(model="event_included"):
    # Every meter is explicitly zero unless the test supplies a quantity.
    zero = {name: {"quantity": "0", "unit": spec["unit"]}
            for name, spec in RATES["meters"].items()}
    post = {name: row for name, row in zero.items()
            if name.startswith(("dataset_", "kv_", "queue_", "transfer_"))}
    return {
        "schema_version": 1, "label": "Synthetic charge-reconciliation acceptance case",
        "input_type": "synthetic", "currency": "USD", "cadence": "monthly",
        "period_start": "2026-10-02", "period_end": "2026-11-02",
        "plan": "starter", "other_account_usage_usd": "0",
        "extra_cash_charges_usd": "0", "unresolved_items": [],
        "actors": [{
            "id": "synthetic/start-event-case", "version": "synthetic-v1",
            "pricing_model": model, "price_source": copy.deepcopy(SOURCE),
            "events": ([] if model == "usage_only" else [{
                "name": "apify-actor-start", "charged_count": "400000",
                "unit": "event", "unit_price_usd": "0.00005", "price_per": "1",
                "currency": "USD", "source": copy.deepcopy(SOURCE),
            }]),
            "run_usage": copy.deepcopy(zero), "post_run_usage": copy.deepcopy(post),
        }],
        "accepted_outputs": {
            "count": "800", "unit": "record",
            "definition": "Synthetic unique records passing required-field validation",
        },
    }


class ReconciliationTests(unittest.TestCase):
    def test_included_event_charge_is_not_replaced_with_platform_usage(self):
        # Break caught: treating included event charges as free or usage-only.
        m = fixture()
        m["actors"][0]["run_usage"]["compute"]["quantity"] = "50"
        result = reconcile(m, RATES)
        self.assertEqual(result["known_workload_usage_usd"], "20")

    def test_extra_usage_adds_compute_and_proxy_exactly_once(self):
        m = fixture("event_plus_usage")
        m["actors"][0]["run_usage"]["compute"]["quantity"] = "50"
        m["actors"][0]["run_usage"]["residential_proxy"]["quantity"] = "1"
        r = reconcile(m, RATES)
        self.assertEqual(r["known_workload_usage_usd"], "38")
        self.assertEqual(r["overage_next_invoice_usd"], "19")
        self.assertEqual(r["cycle_cash_cost_usd"], "38")

    def test_post_run_writes_are_billable_even_when_run_usage_is_included(self):
        m = fixture()
        m["actors"][0]["post_run_usage"]["dataset_writes"]["quantity"] = "200000"
        self.assertEqual(reconcile(m, RATES)["known_workload_usage_usd"], "21")

    def test_usage_only_has_no_developer_event_charge(self):
        m = fixture("usage_only")
        m["actors"][0]["run_usage"]["compute"]["quantity"] = "150"
        self.assertEqual(reconcile(m, RATES)["cycle_cash_cost_usd"], "30")

    def test_allowance_is_applied_once_across_two_actors(self):
        m = fixture()
        m["actors"].append(copy.deepcopy(m["actors"][0]))
        m["actors"][1]["id"] = "synthetic/second-actor"
        r = reconcile(m, RATES)
        self.assertEqual(r["known_account_usage_usd"], "40")
        self.assertEqual(r["prepaid_applied_usd"], "19")
        self.assertEqual(r["overage_next_invoice_usd"], "21")
        self.assertEqual(r["cycle_cash_cost_usd"], "40")

    def test_other_account_usage_consumes_allowance_before_incremental_bill(self):
        m = fixture()
        m["other_account_usage_usd"] = "15"
        r = reconcile(m, RATES)
        self.assertEqual(r["cycle_cash_cost_usd"], "35")
        self.assertEqual(r["incremental_workload_cash_usd"], "16")
        self.assertEqual(r["workload_usage_per_accepted_output_usd"], "0.025")

    def test_paid_fee_is_floor_below_and_exactly_at_allowance(self):
        for count, unused in [("100000", "14"), ("380000", "0")]:
            with self.subTest(count=count):
                m = fixture()
                m["actors"][0]["events"][0]["charged_count"] = count
                r = reconcile(m, RATES)
                self.assertEqual(r["cycle_cash_cost_usd"], "19")
                self.assertEqual(r["overage_next_invoice_usd"], "0")
                self.assertEqual(r["unused_prepaid_usd"], unused)

    def test_free_plan_is_a_blocking_allowance_instead_of_paid_overage(self):
        m = fixture()
        m["plan"] = "free"
        r = reconcile(m, RATES)
        self.assertEqual(r["status"], "free_allowance_exceeded")
        self.assertIsNone(r["cycle_cash_cost_usd"])
        self.assertIsNone(r["overage_next_invoice_usd"])
        self.assertEqual(r["free_allowance_shortfall_usd"], "15")
        m["actors"][0]["events"][0]["charged_count"] = "100000"
        self.assertEqual(reconcile(m, RATES)["cycle_cash_cost_usd"], "0")

    def test_free_excess_does_not_report_a_feasible_unit_cost_or_cash_bound(self):
        m = fixture()
        m["plan"] = "free"
        r = reconcile(m, RATES)
        self.assertIsNone(r["workload_usage_per_accepted_output_usd"])
        self.assertIsNone(r["known_cash_lower_bound_usd"])

    def test_fractional_operation_counts_cannot_be_used_as_gigabytes(self):
        m = fixture("usage_only")
        m["actors"][0]["run_usage"]["dataset_writes"]["quantity"] = "0.5"
        with self.assertRaises(ValueError):
            reconcile(m, RATES)

    def test_month_end_billing_cycle_uses_explicit_dates(self):
        m = fixture()
        m["period_start"], m["period_end"] = "2027-01-31", "2027-02-28"
        self.assertEqual(reconcile(m, RATES)["cycle_cash_cost_usd"], "20")

    def test_missing_billable_meter_leaves_total_unknown_not_zero(self):
        m = fixture("event_plus_usage")
        del m["actors"][0]["run_usage"]["residential_proxy"]
        r = reconcile(m, RATES)
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["known_workload_usage_usd"], "20")
        self.assertEqual(r["known_cash_lower_bound_usd"], "20")
        self.assertIsNone(r["cycle_cash_cost_usd"])
        self.assertIsNone(r["workload_usage_per_accepted_output_usd"])
        self.assertTrue(any("residential_proxy" in x for x in r["unresolved"] ))

    def test_missing_included_run_usage_is_only_a_memo_gap(self):
        m = fixture()
        m["actors"][0]["run_usage"] = {}
        r = reconcile(m, RATES)
        self.assertEqual(r["status"], "complete")
        self.assertEqual(r["cycle_cash_cost_usd"], "20")
        self.assertTrue(r["memo_unknown"])

    def test_missing_post_run_transfer_blocks_total(self):
        m = fixture()
        m["actors"][0]["post_run_usage"]["transfer_external"]["quantity"] = None
        self.assertIsNone(reconcile(m, RATES)["cycle_cash_cost_usd"])

    def test_missing_event_count_or_price_or_source_blocks_total(self):
        for key in ("charged_count", "unit_price_usd", "price_per", "source"):
            with self.subTest(key=key):
                m = fixture()
                m["actors"][0]["events"][0][key] = None
                self.assertIsNone(reconcile(m, RATES)["cycle_cash_cost_usd"])

    def test_unknown_model_is_unresolved_not_assumed_usage_only(self):
        m = fixture()
        m["actors"][0]["pricing_model"] = None
        self.assertIsNone(reconcile(m, RATES)["cycle_cash_cost_usd"])

    def test_missing_other_account_usage_does_not_block_workload_unit_cost(self):
        m = fixture()
        m["other_account_usage_usd"] = None
        r = reconcile(m, RATES)
        self.assertIsNone(r["cycle_cash_cost_usd"])
        self.assertEqual(r["workload_usage_per_accepted_output_usd"], "0.025")
        self.assertIsNone(r["incremental_workload_cash_usd"])

    def test_missing_or_zero_accepted_count_has_undefined_unit_cost(self):
        for count in (None, "0"):
            with self.subTest(count=count):
                m = fixture()
                m["accepted_outputs"]["count"] = count
                r = reconcile(m, RATES)
                self.assertEqual(r["cycle_cash_cost_usd"], "20")
                self.assertIsNone(r["workload_usage_per_accepted_output_usd"])
                self.assertIsNone(r["account_cash_per_accepted_output_usd"])

    def test_accepted_output_count_does_not_change_billed_events(self):
        m = fixture()
        m["accepted_outputs"]["count"] = "1"
        r = reconcile(m, RATES)
        self.assertEqual(r["cycle_cash_cost_usd"], "20")
        self.assertEqual(r["workload_usage_per_accepted_output_usd"], "20")

    def test_rates_keep_thousand_unit_divisors_and_hour_integrals(self):
        m = fixture("usage_only")
        u = m["actors"][0]["run_usage"]
        for name, quantity in [("dataset_storage", "24000"), ("dataset_reads", "1000"),
                               ("dataset_writes", "1000"), ("serp_proxy", "1000"),
                               ("transfer_external", "2"), ("transfer_internal", "2")]:
            u[name]["quantity"] = quantity
        self.assertEqual(reconcile(m, RATES)["known_workload_usage_usd"], "27.0054")

    def test_scale_and_business_rates_apply_to_resources_not_generic_event_discounts(self):
        for plan, want in [("scale", "28"), ("business", "26.5")]:
            with self.subTest(plan=plan):
                m = fixture("event_plus_usage")
                m["plan"] = plan
                m["actors"][0]["run_usage"]["compute"]["quantity"] = "50"
                self.assertEqual(reconcile(m, RATES)["known_workload_usage_usd"], want)

    def test_rounding_occurs_only_on_final_display_and_preserves_subcent_events(self):
        m = fixture()
        m["other_account_usage_usd"] = "19"
        m["actors"][0]["events"][0]["charged_count"] = "100"
        r = reconcile(m, RATES)
        self.assertEqual(r["known_workload_usage_usd"], "0.005")
        self.assertEqual(r["cycle_cash_cost_usd"], "19.005")
        self.assertEqual(r["display_cycle_cash_cost_usd"], "19.01")
        self.assertEqual(r["overage_next_invoice_usd"], "0.005")

    def test_extra_cash_charges_do_not_use_prepaid_allowance(self):
        m = fixture()
        m["actors"][0]["events"][0]["charged_count"] = "100000"
        m["extra_cash_charges_usd"] = "7"
        r = reconcile(m, RATES)
        self.assertEqual(r["cycle_cash_cost_usd"], "26")
        self.assertEqual(r["unused_prepaid_usd"], "14")

    def test_declared_unresolved_addon_blocks_a_precise_bill(self):
        m = fixture()
        m["unresolved_items"] = ["Datacenter IP add-on amount/allowance eligibility unknown"]
        self.assertIsNone(reconcile(m, RATES)["cycle_cash_cost_usd"])

    def test_duplicate_actors_and_event_names_are_rejected(self):
        for duplicate in ("actor", "event"):
            with self.subTest(duplicate=duplicate):
                m = fixture()
                if duplicate == "actor":
                    m["actors"].append(copy.deepcopy(m["actors"][0]))
                else:
                    m["actors"][0]["events"].append(copy.deepcopy(m["actors"][0]["events"][0]))
                with self.assertRaises(ValueError):
                    reconcile(m, RATES)

    def test_usage_only_rejects_event_rows(self):
        m = fixture()
        m["actors"][0]["pricing_model"] = "usage_only"
        with self.assertRaises(ValueError):
            reconcile(m, RATES)

    def test_invalid_currency_cadence_dates_and_units_are_rejected(self):
        for key, value in [("currency", "EUR"), ("cadence", "annual"),
                           ("period_end", "2026-10-03"), ("plan", "enterprise")]:
            with self.subTest(key=key):
                m = fixture()
                m[key] = value
                with self.assertRaises(ValueError):
                    reconcile(m, RATES)
        for field, value in [("unit", "MB"), ("quantity", "-1"),
                             ("quantity", "NaN"), ("quantity", "Infinity"),
                             ("quantity", 0.1), ("quantity", True)]:
            with self.subTest(field=field, value=value):
                m = fixture("event_plus_usage")
                m["actors"][0]["run_usage"]["compute"][field] = value
                with self.assertRaises(ValueError):
                    reconcile(m, RATES)

    def test_event_currency_units_and_fractional_counts_are_rejected(self):
        for key, value in [("currency", "EUR"), ("unit", "record"),
                           ("charged_count", "1.2"), ("price_per", "0")]:
            with self.subTest(key=key):
                m = fixture()
                m["actors"][0]["events"][0][key] = value
                with self.assertRaises(ValueError):
                    reconcile(m, RATES)

    def test_unknown_meter_keys_are_rejected_instead_of_silently_ignored(self):
        m = fixture()
        m["actors"][0]["run_usage"]["datacentre_proxy"] = {"quantity": "5", "unit": "IP"}
        with self.assertRaises(ValueError):
            reconcile(m, RATES)

    def test_accepted_counts_require_integer_and_named_definition(self):
        for key, value in [("count", "-1"), ("count", "1.5"),
                           ("definition", ""), ("unit", "")]:
            with self.subTest(key=key):
                m = fixture()
                m["accepted_outputs"][key] = value
                with self.assertRaises(ValueError):
                    reconcile(m, RATES)

    def test_missing_completeness_attestation_blocks_total(self):
        m = fixture()
        del m["unresolved_items"]
        self.assertIsNone(reconcile(m, RATES)["cycle_cash_cost_usd"])

    def test_cli_rejects_duplicate_json_keys_and_reports_unknowns(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text('{"plan":"starter", "plan":"free"}')
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("model.py")),
                                   str(p)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("duplicate", proc.stderr.lower())
            m = fixture("event_plus_usage")
            m["actors"][0]["run_usage"]["compute"]["quantity"] = None
            p.write_text(json.dumps(m))
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("model.py")),
                                   str(p)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout)["status"], "partial")

    def test_saved_named_synthetic_examples_match_hand_reconciled_amounts(self):
        # Changed inclusion, allowance, rate units or unknown handling must fail.
        cases = [
            ("s1-event-included.json", "0.632", "19", "complete"),
            ("s2-event-plus-usage.json", "22.272", "22.272", "complete"),
            ("s3-usage-only.json", "22.224", "22.224", "complete"),
            ("s4-missing-usage.json", "14.272", None, "partial"),
            ("s5-zero-accepted.json", "22.272", "22.272", "complete"),
            ("s6-shared-allowance.json", "44.544", "59.544", "complete"),
            ("s7-free-limit.json", "22.272", None, "free_allowance_exceeded"),
        ]
        for filename, usage, cash, status in cases:
            with self.subTest(filename=filename):
                r = reconcile(json.loads((PACKET / "fixtures" / filename).read_text()), RATES)
                self.assertEqual(r["input_type"], "synthetic")
                self.assertEqual(r["known_workload_usage_usd"], usage)
                self.assertEqual(r["cycle_cash_cost_usd"], cash)
                self.assertEqual(r["status"], status)

    def test_csv_exposes_included_rows_and_blank_unknown_amounts(self):
        import csv
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "ledger.csv"
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("model.py")),
                                   str(PACKET / "fixtures/s4-missing-usage.json"),
                                   "--csv", str(csv_path)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with csv_path.open() as f:
                rows = list(csv.DictReader(f))
            proxy = next(x for x in rows if x["scope"] == "run_usage" and x["item"] == "residential_proxy")
            self.assertEqual(proxy["billed_amount_usd"], "")
            self.assertEqual(proxy["treatment"], "unknown")
            included = reconcile(json.loads((PACKET / "fixtures/s1-event-included.json").read_text()), RATES)
            compute = next(x for x in included["lines"] if x["scope"] == "run_usage" and x["item"] == "compute")
            self.assertEqual(compute["rated_amount_usd"], "12")
            self.assertEqual(compute["billed_amount_usd"], "0")
            self.assertEqual(compute["treatment"], "included_in_event_price")

    def test_unknown_template_has_no_precise_bill_or_unit_cost(self):
        r = reconcile(json.loads((PACKET / "fixtures/worksheet-template.json").read_text()), RATES)
        self.assertEqual(r["status"], "partial")
        self.assertIsNone(r["cycle_cash_cost_usd"])
        self.assertIsNone(r["workload_usage_per_accepted_output_usd"])

    def test_rate_snapshot_requires_dated_official_provenance(self):
        for key, value in [("checked_on", None), ("checked_on", "not-a-date"),
                           ("source_url", "https://example.invalid/unverified")]:
            with self.subTest(key=key, value=value):
                rates = copy.deepcopy(RATES)
                rates[key] = value
                with self.assertRaises(ValueError):
                    reconcile(fixture(), rates)

    def test_rate_plan_overage_flag_requires_real_boolean(self):
        rates = copy.deepcopy(RATES)
        rates["plans"]["free"]["overage_available"] = "false"
        m = fixture()
        m["plan"] = "free"
        with self.assertRaises(ValueError):
            reconcile(m, rates)

    def test_accepted_output_metadata_requires_trimmed_nonempty_strings(self):
        for key, value in [("unit", {"invalid": "object"}), ("definition", "   ")]:
            with self.subTest(key=key):
                m = fixture()
                m["accepted_outputs"][key] = value
                with self.assertRaises(ValueError):
                    reconcile(m, RATES)


if __name__ == "__main__":
    unittest.main()
