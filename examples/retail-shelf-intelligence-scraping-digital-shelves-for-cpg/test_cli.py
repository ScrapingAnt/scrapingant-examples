"""Run public commands against owned local files or in-memory acquisitions."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import collector

ROOT = Path(__file__).parent

class CLI(unittest.TestCase):
    def test_replay_command_emits_normalized_JSON_without_environment_key_dispatch(self):
        env = dict(os.environ, SCRAPINGANT_API_KEY="owned-env-key-no-dispatch")
        result = subprocess.run([sys.executable, "collector.py", "replay", "fixtures/baseline.html",
                                 "--observed-at", "2026-10-13T11:00:00Z"], cwd=ROOT, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["complete"])
        self.assertEqual(output["acquisition"]["transport"], "offline_replay")
        self.assertIsNone(output["acquisition"]["api_http_status"])
        self.assertEqual([r["price"] for r in output["records"]], ["8.25", "24.00"])
        self.assertNotIn("owned-env-key", result.stdout + result.stderr)

    def test_partial_replay_returns_nonzero_and_does_not_invent_OOS(self):
        result = subprocess.run([sys.executable, "collector.py", "replay", "fixtures/partial.html",
                                 "--observed-at", "2026-10-13T12:00:00Z"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        output = json.loads(result.stdout)
        self.assertFalse(output["complete"])
        self.assertEqual([r["sku"] for r in output["records"]], ["000701002"])

    def test_HTTP200_error_shell_is_failed_collection_with_receipt_cost(self):
        acquisition = {"usable":True,"body":b'<html>Access denied</html>',"receipt":{
            "api_http_status":200,"target_http_status":200,"actual_receipt_credits":1,"credit_receipt_state":"known"}}
        result = collector.collection(acquisition, source=collector.SOURCE, observed_at_utc="2026-10-13T12:00:00Z")
        self.assertFalse(result["complete"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["cost"]["actual_receipt_credits"], 1)
        self.assertIsNone(result["cost"]["credits_per_accepted_record"])

    def test_projection_replay_is_not_a_live_HTML_transport_receipt(self):
        result = collector.replay_projection(ROOT / "fixtures/adagio-field-projection.json")
        self.assertTrue(result["complete"])
        self.assertEqual(result["acquisition"]["transport"], "field_projection_replay")
        self.assertEqual(result["acquisition"]["source_body_sha256"], "8b1400da3561c1861ebdd3d087e6c2455daa68ce626c9a7de5b5c25a186a4c50")
        self.assertEqual([r["sku"] for r in result["records"]], ["001036002", "001036004"])
        self.assertEqual([r["price"] for r in result["records"]], ["9.00", "29.00"])
        self.assertEqual([r["availability"] for r in result["records"]], ["out_of_stock", "out_of_stock"])
        self.assertIsNone(result["acquisition"]["api_http_status"])

    def test_managed_CLI_reads_only_header_key_and_emits_no_body(self):
        calls = []
        def fake_acquire(url, **options):
            calls.append((url, options))
            return {"usable":False,"body":b"","receipt":{
                "api_http_status":423,"target_http_status":None,"actual_receipt_credits":None,"credit_receipt_state":"unknown"}}
        stdout = StringIO()
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY":"owned-key"}), patch.object(collector,"acquire",fake_acquire), redirect_stdout(stdout):
            exit_code = collector.main(["managed", "--browser", "false"])
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], collector.SOURCE)
        self.assertEqual(calls[0][1], {"managed":True,"browser":False,"key":"owned-key"})
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["cost"]["unknown_charge_requests"], 1)
        self.assertNotIn("owned-key", stdout.getvalue())
        self.assertNotIn("body", result)

    def test_recorded_managed_fields_match_independent_source_oracle(self):
        path = ROOT / "expected_output/managed-2026-10-13/collection.json"
        result = json.loads(path.read_text()) if path.exists() else {"complete":False}
        self.assertTrue(result["complete"])
        self.assertEqual(result["cost"], {"accepted_records":2,"actual_receipt_credits":1,
            "credits_per_accepted_record":"0.50","unknown_charge_requests":0})
        receipt = result["acquisition"]
        self.assertEqual(receipt["requests"], 1)
        self.assertEqual(receipt["api_http_status"], 200)
        self.assertEqual(receipt["target_http_status"], 200)
        self.assertEqual(receipt["target_media_type"], "text/html")
        self.assertEqual(receipt["collector_sha256"], "73c30dd543306c96f452de9b1c5a8441d22e477ef25945623c76a2e1a0fc4e2f")
        oracle = json.loads((ROOT / "fixtures/adagio-source-oracle.json").read_text())
        for actual, expected in zip(result["records"], oracle, strict=True):
            self.assertEqual(actual["product_id"], expected["product_group_id"])
            self.assertEqual(actual["sku"], expected["sku"])
            self.assertEqual(actual["variant"], expected["size_literal"])
            self.assertIsNone(actual["variant_id"])
            self.assertEqual(actual["pack_quantity"], expected["pack_size"])
            self.assertEqual(actual["pack_unit"], "ounce")
            self.assertEqual(actual["price"], expected["price_decimal"])
            self.assertEqual(actual["currency"], expected["currency"])
            self.assertEqual(actual["availability"], "out_of_stock")
            self.assertEqual(actual["source_evidence"]["availability_token"], expected["availability_literal"])
            self.assertEqual(actual["market"], expected["market"])
            self.assertEqual(actual["fulfilment"], expected["fulfilment"])
            self.assertEqual(actual["purchase_basis"], expected["purchase_basis"])
            self.assertEqual(actual["offer_kind"], expected["offer_basis"])
            self.assertEqual(actual["observed_at_utc"], "2026-10-13T10:59:39Z")
            self.assertEqual(actual["requested_source_url"], collector.SOURCE)
            self.assertEqual(actual["observed_source_url"], collector.SOURCE)

if __name__ == "__main__":
    unittest.main(verbosity=2)
