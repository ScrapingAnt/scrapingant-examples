"""Literal-oracle and adverse-input tests. All acquisition transport is mocked."""
import copy
import io
import json
import os
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from acquire import AcquisitionError, fetch_html
from acquire import main as acquire_main
from budget import workload
from snapshot import compare, parse_snapshot

ROOT = Path(__file__).resolve().parent
ORACLE = json.loads((ROOT / "fixtures/oracle.json").read_text())


def fixture(name):
    return (ROOT / "fixtures" / (name + ".html")).read_text()


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.baseline = parse_snapshot(fixture("baseline"))
        self.changed = parse_snapshot(fixture("changed"))

    def test_literal_record_oracle_all_three_snapshots(self):
        for name in ("baseline", "changed", "truncated"):
            with self.subTest(name=name):
                snapshot, expected = parse_snapshot(fixture(name)), ORACLE[name]
                self.assertEqual(snapshot["context"], {**ORACLE["provenance"], "observed_utc": expected["observed_utc"]})
                self.assertEqual(snapshot["complete"], expected["complete"])
                self.assertEqual(snapshot["issues"], expected["issues"])
                self.assertEqual([[r[c] for c in expected["record_columns"]] for r in snapshot["records"]], expected["records"])
                for record in snapshot["records"]:
                    self.assertEqual({k: record[k] for k in snapshot["context"]}, snapshot["context"])

    def test_literal_changed_diff_oracle(self):
        self.assertEqual(compare(self.baseline, self.changed), ORACLE["changed_diff"])

    def test_literal_truncated_diff_oracle(self):
        self.assertEqual(compare(self.baseline, parse_snapshot(fixture("truncated"))), ORACLE["truncated_diff"])

    def test_sponsored_organic_unknown_are_distinct(self):
        self.assertEqual([r["sponsored_status"] for r in self.baseline["records"][:4]], ["sponsored", "organic", "organic", "unknown"])
        self.assertEqual(self.changed["records"][3]["sponsored_status"], "unknown")

    def test_conflicting_sponsored_labels_are_unknown(self):
        html = fixture("baseline").replace("<span data-role=\"placement-label\">Sponsored</span>", "<span data-role=\"placement-label\">Sponsored</span><span data-role=\"placement-label\">Organic</span>", 1)
        self.assertEqual(parse_snapshot(html)["records"][0]["sponsored_status"], "unknown")

    def test_duplicate_asin_ad_and_organic_placements_preserved(self):
        records = [r for r in self.baseline["records"] if r["asin"] == "B000000001"]
        self.assertEqual([(r["observed_position"], r["sponsored_status"]) for r in records], [(1, "sponsored"), (3, "organic")])

    def test_same_class_duplicate_is_not_arbitrarily_matched(self):
        baseline = parse_snapshot(fixture("baseline").replace("Sponsored", "Organic"))
        changed = parse_snapshot(fixture("changed").replace("Sponsored", "Organic"))
        result = compare(baseline, changed)
        self.assertEqual(result["ambiguous_placements"], [{"asin": "B000000001", "sponsored_status": "organic", "before_count": 2, "after_count": 2}])
        self.assertFalse(any(c["asin"] == "B000000001" for c in result["changes"]))

    def test_missing_asin_is_null_and_suppresses_comparison(self):
        changed = parse_snapshot(fixture("changed").replace('data-asin="B000000002"', 'data-asin=""'))
        self.assertIsNone(changed["records"][0]["asin"])
        self.assertEqual(compare(self.baseline, changed)["changes"], [])
        self.assertIn("missing_or_invalid_asin", changed["issues"])

    def test_invalid_asin_is_not_a_join_key(self):
        changed = parse_snapshot(fixture("changed").replace('data-asin="B000000002"', 'data-asin="short"'))
        self.assertIsNone(changed["records"][0]["asin"])
        self.assertFalse(changed["complete"])

    def test_missing_title_and_price_are_null_not_zero(self):
        record = self.baseline["records"][4]
        self.assertIsNone(record["title"])
        self.assertIsNone(record["price"])
        self.assertTrue(self.baseline["complete"])

    def test_missing_or_ambiguous_price_emits_no_price_change(self):
        for replacement in ("", "$27–30", "$1,000.00"):
            with self.subTest(price=replacement):
                changed = parse_snapshot(fixture("changed").replace("$27.00", replacement))
                self.assertIsNone(changed["records"][0]["price"])
                self.assertFalse(any(c["kind"] == "observed_price_change" for c in compare(self.baseline, changed)["changes"]))

    def test_currency_mismatch_is_not_silently_converted(self):
        changed = parse_snapshot(fixture("changed").replace('data-currency="USD"', 'data-currency="EUR"'))
        result = compare(self.baseline, changed)
        self.assertEqual(result["status"], "suppressed")
        self.assertIn("mismatch_currency", result["reasons"])
        self.assertEqual(result["changes"], [])

    def test_price_currency_mismatch_is_unknown(self):
        changed = parse_snapshot(fixture("changed").replace('class="a-offscreen" data-currency="USD">$27.00', 'class="a-offscreen" data-currency="EUR">$27.00'))
        self.assertIsNone(changed["records"][0]["price"])

    def test_count_page_and_end_signal_mismatches_suppress(self):
        mutations = [
            ('data-expected-count="6"', 'data-expected-count="7"'),
            ('data-page="1"', 'data-page="2"'),
            ('id="snapshot-end" data-count="6"', 'id="snapshot-end" data-count="5"'),
            ('<div id="snapshot-end" data-count="6" data-page="1"></div>', ''),
        ]
        for old, new in mutations:
            with self.subTest(mutation=old):
                changed = parse_snapshot(fixture("changed").replace(old, new))
                self.assertFalse(changed["complete"])
                self.assertEqual(compare(self.baseline, changed)["changes"], [])

    def test_premature_and_duplicate_end_signals_suppress(self):
        end = '<div id="snapshot-end" data-count="6" data-page="1"></div>'
        for html in (fixture("changed").replace(end, '').replace('<div data-component-type=', end + '<div data-component-type=', 1), fixture("changed").replace(end, end + end)):
            self.assertFalse(parse_snapshot(html)["complete"])

    def test_cross_query_marketplace_and_source_suppress(self):
        for old, new, reason in [('data-query="desk lamp"', 'data-query="floor lamp"', "mismatch_query"), ('data-marketplace="amazon.com"', 'data-marketplace="amazon.co.uk"', "mismatch_marketplace"), ('fixtures.invalid/amazon-us/', 'other.invalid/amazon-us/', "mismatch_source_url")]:
            with self.subTest(reason=reason):
                result = compare(self.baseline, parse_snapshot(fixture("changed").replace(old, new)))
                self.assertIn(reason, result["reasons"])
                self.assertEqual(result["changes"], [])

    def test_missing_product_partial_window_never_raises_delist(self):
        line = next(line for line in fixture("changed").splitlines() if 'data-asin="B000000006"' in line)
        result = compare(self.baseline, parse_snapshot(fixture("changed").replace(line, '')))
        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(result["changes"], [])

    def test_complete_window_absence_is_only_not_observed(self):
        absent = [c for c in compare(self.baseline, self.changed)["changes"] if c["asin"] == "B000000005"]
        self.assertEqual(absent, [{"asin": "B000000005", "sponsored_status": "organic", "kind": "not_observed_in_window"}])
        self.assertNotIn("rank", json.dumps(compare(self.baseline, self.changed)))
        self.assertNotIn("delist", json.dumps(compare(self.baseline, self.changed)))

    def test_block_and_error_envelopes_suppress(self):
        for status in ("blocked", "error"):
            changed = parse_snapshot(fixture("changed").replace('data-capture-status="ok"', 'data-capture-status="' + status + '"'))
            self.assertEqual(compare(self.baseline, changed)["changes"], [])

    def test_incomplete_baseline_and_changed_window_suppress(self):
        baseline = parse_snapshot(fixture("truncated"))
        self.assertIn("baseline_incomplete", compare(baseline, self.changed)["reasons"])
        changed = copy.deepcopy(self.changed)
        changed["expected_count"] = 7
        self.assertIn("mismatch_window", compare(self.baseline, changed)["reasons"])

    def test_missing_provenance_and_invalid_utc_rejected(self):
        for old, new in [('data-query="desk lamp"', 'data-query=""'), ('2026-10-11T11:00:00Z', '2026-10-11T11:00:00')]:
            self.assertFalse(parse_snapshot(fixture("changed").replace(old, new))["complete"])

    def test_old_or_identical_timestamp_suppresses(self):
        changed = copy.deepcopy(self.changed)
        changed["context"]["observed_utc"] = self.baseline["context"]["observed_utc"]
        self.assertIn("non_increasing_observation_time", compare(self.baseline, changed)["reasons"])

    def test_subsecond_utc_time_orders_as_time_not_text(self):
        changed = copy.deepcopy(self.changed)
        changed["context"]["observed_utc"] = "2026-10-11T10:00:00.001Z"
        self.assertEqual(compare(self.baseline, changed)["status"], "compared")

    def test_unrecognized_live_html_is_not_a_complete_snapshot(self):
        with self.assertRaises(ValueError):
            parse_snapshot("<html><body>Robot check</body></html>")

    def test_conflicting_completion_attributes_never_override_incomplete(self):
        changed = parse_snapshot(fixture("changed").replace('data-complete="true"', 'data-complete="false" data-complete="true"'))
        self.assertFalse(changed["complete"])
        self.assertIn("duplicate_attributes", changed["issues"])
        self.assertEqual(compare(self.baseline, changed)["changes"], [])

    def test_conflicting_asin_attributes_never_create_a_join(self):
        changed = parse_snapshot(fixture("changed").replace('data-asin="B000000002"', 'data-asin="B000000099" data-asin="B000000002"'))
        self.assertFalse(changed["complete"])
        self.assertIn("duplicate_attributes", changed["issues"])
        self.assertEqual(compare(self.baseline, changed)["changes"], [])

    def test_duplicate_noncritical_and_self_closing_attributes_rejected(self):
        for html in (fixture("changed").replace('<h2>', '<h2 class="title" class="title">', 1), fixture("changed").replace('</main>', '<img alt="a" alt="b" /></main>'), fixture("changed").replace('<body>', '<body id="a" ID="b">')):
            with self.subTest(html=html[:50]):
                changed = parse_snapshot(html)
                self.assertFalse(changed["complete"])
                self.assertIn("duplicate_attributes", changed["issues"])
                self.assertEqual(compare(self.baseline, changed)["changes"], [])


class Response(io.BytesIO):
    status = 200

    def __init__(self, body=b"<html>owned response</html>", **headers):
        super().__init__(body)
        self.headers = Message()
        for name, value in {"Ant-page-status-code": "200", "Content-Type": "text/html; charset=utf-8", "Ant-credits-cost": "1", **headers}.items():
            if value is not None:
                self.headers[name] = value


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "OFFLINE_TEST_TOKEN"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_explicit_request_contract_key_header_and_raw_cost(self):
        seen = []
        def opener(request, timeout):
            seen.append((request, timeout))
            return Response()
        body, meta = fetch_html("https://fixtures.invalid/?q=private+query", False, max_credits=1, opener=opener)
        request, timeout = seen[0]
        query = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(query, {"url": ["https://fixtures.invalid/?q=private+query"], "browser": ["false"], "proxy_type": ["datacenter"], "proxy_country": ["us"], "timeout": ["30"], "return_page_source": ["false"]})
        self.assertNotIn("OFFLINE_TEST_TOKEN", request.full_url)
        self.assertEqual(request.get_header("X-api-key"), "OFFLINE_TEST_TOKEN")
        self.assertEqual(timeout, 35)
        self.assertEqual(meta["credits_recorded"], 1)
        self.assertFalse(meta["accepted_snapshot"])
        self.assertIn("owned response", body)

    def test_rendered_credit_reserve_and_contract(self):
        def opener(request, timeout):
            self.assertEqual(parse_qs(urlsplit(request.full_url).query)["browser"], ["true"])
            return Response(**{"Ant-credits-cost": "10"})
        _, meta = fetch_html("https://fixtures.invalid/", True, max_credits=10, opener=opener)
        self.assertEqual(meta["credit_reserve"], 10)

    def test_transient_api_500_retries_once_with_attempt_cap(self):
        calls, waits = [], []
        def opener(request, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 500, "secret private query", {}, None)
            return Response()
        _, meta = fetch_html("https://fixtures.invalid/", False, max_attempts=2, max_credits=2, opener=opener, pause=waits.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(meta["attempts"], 2)
        self.assertEqual(waits, [1])

    def test_persistent_transient_failure_stops_after_two_and_is_sanitized(self):
        calls = []
        def opener(request, timeout):
            calls.append(1)
            raise HTTPError(request.full_url, 500, "OFFLINE_TEST_TOKEN private query", {}, None)
        with self.assertRaises(AcquisitionError) as error:
            fetch_html("https://fixtures.invalid/?secret=query", False, 2, 2, opener=opener, pause=lambda _: None)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("query", str(error.exception))
        self.assertNotIn("OFFLINE_TEST_TOKEN", str(error.exception))

    def test_auth_quota_validation_and_concurrency_do_not_retry(self):
        for status in (403, 409, 422, 423):
            calls = []
            def opener(request, timeout):
                calls.append(1)
                raise HTTPError(request.full_url, status, "upstream secret", {}, None)
            with self.assertRaises(AcquisitionError):
                fetch_html("https://fixtures.invalid/", False, 2, 2, opener=opener)
            self.assertEqual(len(calls), 1)

    def test_network_timeout_does_not_start_unknown_remote_duplicate(self):
        calls = []
        def opener(request, timeout):
            calls.append(1)
            raise URLError("OFFLINE_TEST_TOKEN private query")
        with self.assertRaises(AcquisitionError) as error:
            fetch_html("https://fixtures.invalid/", False, 2, 2, opener=opener)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private", str(error.exception))

    def test_insufficient_reserve_prevents_any_request(self):
        with self.assertRaises(AcquisitionError):
            fetch_html("https://fixtures.invalid/", True, 2, 10, opener=lambda *a, **k: self.fail("unexpected transport"))

    def test_missing_key_prevents_any_request(self):
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": ""}):
            with self.assertRaises(AcquisitionError):
                fetch_html("https://fixtures.invalid/", False, opener=lambda *a, **k: self.fail("unexpected transport"))

    def test_error_target_missing_receipt_and_json_never_become_snapshot(self):
        for headers in ({"Ant-page-status-code": "404"}, {"Ant-page-status-code": None}, {"Ant-credits-cost": None}, {"Content-Type": "application/json"}, {"Ant-credits-cost": "-1"}, {"Ant-credits-cost": "99"}):
            with self.subTest(headers=headers):
                with self.assertRaises(AcquisitionError):
                    fetch_html("https://fixtures.invalid/", False, max_credits=1, opener=lambda *a, **k: Response(**headers))

    def test_oversized_and_invalid_encoding_capture_rejected(self):
        for body in (b"x" * 2_000_001, b"\xff"):
            with self.assertRaises(AcquisitionError):
                fetch_html("https://fixtures.invalid/", False, opener=lambda *a, **k: Response(body))

    def test_source_shaped_html_original_header_without_outer_type_accepted(self):
        response = Response(**{"Content-Type": None, "Ant-original-header-content-type": "text/html; charset=utf-8"})
        html, meta = fetch_html("https://fixtures.invalid/", False, opener=lambda *a, **k: response)
        self.assertIn("owned response", html)
        self.assertFalse(meta["accepted_snapshot"])

    def test_original_non_html_type_overrides_outer_html_and_is_rejected(self):
        with self.assertRaises(AcquisitionError):
            fetch_html("https://fixtures.invalid/", False, opener=lambda *a, **k: Response(**{"Ant-original-header-content-type": "application/json"}))

    def test_no_original_or_outer_content_type_is_unknown_and_rejected(self):
        with self.assertRaises(AcquisitionError):
            fetch_html("https://fixtures.invalid/", False, opener=lambda *a, **k: Response(**{"Content-Type": None}))


class AcquisitionDestinationTests(unittest.TestCase):
    def run_cli(self, destination):
        args = ["acquire.py", "--url", "https://fixtures.invalid/", "--browser", "false", "--permitted", "--out", str(destination)]
        with patch("sys.argv", args), patch("sys.stdout", new_callable=io.StringIO) as output:
            status = acquire_main()
        return status, output.getvalue()

    def test_valid_destination_is_reserved_before_fetch_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "new-capture"
            def offline_fetch(*args):
                self.assertTrue((destination / "capture.html").is_file())
                self.assertTrue((destination / "provenance.json").is_file())
                return "<html>owned capture</html>", {"accepted_snapshot": False}
            with patch("acquire.fetch_html", side_effect=offline_fetch) as fetch:
                status, _ = self.run_cli(destination)
                self.assertEqual(status, 0)
                fetch.assert_called_once()
            self.assertEqual((destination / "capture.html").read_text(), "<html>owned capture</html>")
            self.assertEqual(json.loads((destination / "provenance.json").read_text()), {"accepted_snapshot": False})

    def test_existing_destination_prevents_any_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "existing"
            destination.mkdir()
            (destination / "keep.txt").write_text("retain existing capture")
            with patch("acquire.fetch_html", return_value=("owned capture", {})) as fetch:
                status, message = self.run_cli(destination)
                self.assertEqual(status, 1)
                fetch.assert_not_called()
            self.assertEqual((destination / "keep.txt").read_text(), "retain existing capture")
            self.assertNotIn(str(destination), message)

    def test_missing_parent_prevents_any_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "missing-parent" / "capture"
            with patch("acquire.fetch_html", return_value=("owned capture", {})) as fetch:
                status, _ = self.run_cli(destination)
                self.assertEqual(status, 1)
                fetch.assert_not_called()
            self.assertFalse(destination.parent.exists())

    def test_file_destination_prevents_any_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "existing-file"
            destination.write_text("retain file")
            with patch("acquire.fetch_html", return_value=("owned capture", {})) as fetch:
                status, _ = self.run_cli(destination)
                self.assertEqual(status, 1)
                fetch.assert_not_called()
            self.assertEqual(destination.read_text(), "retain file")

    def test_open_error_prevents_any_fetch_and_redacts_path(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "new-capture"
            with patch.object(Path, "open", side_effect=PermissionError("private path")), patch("acquire.fetch_html", return_value=("owned capture", {})) as fetch:
                status, message = self.run_cli(destination)
                self.assertEqual(status, 1)
                fetch.assert_not_called()
            self.assertNotIn("private path", message)

    def test_mkdir_error_prevents_any_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "new-capture"
            with patch.object(Path, "mkdir", side_effect=PermissionError("private path")), patch("acquire.fetch_html", return_value=("owned capture", {})) as fetch:
                status, _ = self.run_cli(destination)
                self.assertEqual(status, 1)
                fetch.assert_not_called()


class BudgetTests(unittest.TestCase):
    def test_hourly_workload_literal_denominators(self):
        result = workload(5, 1, 1, 24, 30, 2)
        self.assertEqual((result["snapshots"], result["initial_calls"], result["attempted_calls_cap"]), (3600, 3600, 7200))
        self.assertEqual((result["raw_datacenter_credits_at_cap"], result["rendered_datacenter_credits_at_cap"]), (7200, 72000))

    def test_queries_marketplaces_pages_and_retries_all_multiply(self):
        result = workload(2, 3, 4, 6, 7, 2)
        self.assertEqual(result["snapshots"], 252)
        self.assertEqual(result["initial_calls"], 1008)
        self.assertEqual(result["attempted_calls_cap"], 2016)

    def test_invalid_workload_is_rejected(self):
        for n in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                workload(n, 1, 1, 1, 1)


if __name__ == "__main__":
    unittest.main()
