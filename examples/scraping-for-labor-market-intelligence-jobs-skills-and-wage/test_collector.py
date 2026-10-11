import copy
from email.message import Message
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from collector import CollectionError, SourcePolicy, collect, direct_html, refresh
from fixture_server import FixtureServer, FIXTURES
from schema import validate_record
from scrapingant_transport import build_request, managed_html
from greenhouse_replay import CAPTURE_PATH, project_capture

STAMP = "2026-10-11T21:00:00Z"  # Controlled test input, not the capture observation time.


class CollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FixtureServer().__enter__()
        cls.policy = SourcePolicy(cls.server.url)
        # Literal oracle authored independently of HTML traversal and schema code.
        cls.oracle = json.loads((FIXTURES / "expected-records.json").read_text().replace(
            "__ORIGIN__", cls.server.origin))

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__()

    def setUp(self):
        self.server.mode = "baseline"
        self.server.requests.clear()

    def run_case(self, mode="baseline", max_pages=3):
        self.server.mode = mode
        return collect(self.policy, max_pages=max_pages, observed_utc=STAMP)

    def test_literal_oracle_and_duplicate(self):
        result = self.run_case()
        self.assertTrue(result["complete"])
        self.assertEqual(result["records"], self.oracle)
        self.assertEqual(result["counters"], {
            "requested_pages": 2, "fetched_pages": 2, "accepted_pages": 2,
            "cards_seen": 4, "valid_cards": 4, "duplicate_cards": 1,
            "conflicting_ids": 0, "rejected_cards": 0, "unique_records": 3, "failures": 0})

    def test_oracle_detects_semantically_wrong_title(self):
        result = collect(self.policy, observed_utc=STAMP,
                         fetch=lambda url: direct_html(url).replace("Data Analyst", "Wrong Analyst"))
        self.assertTrue(result["complete"])
        with self.assertRaises(AssertionError):
            self.assertEqual(result["records"], self.oracle)

    def test_conflict_excludes_id_and_marks_partial(self):
        result = self.run_case("conflict")
        self.assertFalse(result["complete"])
        self.assertEqual([row["jobID"] for row in result["records"]], ["NS-002", "NS-003"])
        self.assertEqual(result["counters"]["conflicting_ids"], 1)
        self.assertEqual(result["failures"][0]["code"], "conflicting_id")

    def test_missing_required_field(self):
        result = self.run_case("missing_location")
        self.assertFalse(result["complete"])
        self.assertEqual(result["counters"]["rejected_cards"], 1)
        self.assertEqual(result["failures"][0]["fields"], ["location"])

    def test_missing_source_date_stays_null(self):
        result = self.run_case()
        self.assertIsNone(result["records"][1]["sourcePostedDate"])
        self.assertNotEqual(result["records"][0]["observedUTC"][:10],
                            result["records"][0]["sourcePostedDate"])

    def test_source_url_must_match_record_id(self):
        result = self.run_case("source_mismatch")
        self.assertEqual(result["failures"][0]["fields"], ["sourceURL"])

    def test_application_url_must_match_approved_origin(self):
        result = self.run_case("application_external")
        self.assertEqual(result["failures"][0]["fields"], ["applicationURL"])

    def test_invalid_source_date_is_rejected(self):
        result = self.run_case("invalid_date")
        self.assertEqual(result["failures"][0]["fields"], ["sourcePostedDate"])

    def assert_rejected_next(self, mode):
        result = self.run_case(mode)
        self.assertFalse(result["complete"])
        self.assertEqual(result["counters"]["requested_pages"], 1)
        self.assertEqual(result["failures"][0]["code"], "next_url_rejected")
        self.assertEqual(self.server.requests, ["/careers/roles?page=1"])

    def test_hostile_next(self):
        self.assert_rejected_next("hostile_next")

    def test_wrong_next_path(self):
        self.assert_rejected_next("wrong_path")

    def test_wrong_next_page(self):
        self.assert_rejected_next("wrong_page")

    def test_changed_filter_rejected(self):
        self.assert_rejected_next("changed_filter")

    def test_duplicate_query_rejected(self):
        self.assert_rejected_next("duplicate_query")

    def test_fragment_next_rejected(self):
        self.assert_rejected_next("fragment_next")

    def test_loop_is_not_fetched_again(self):
        result = self.run_case("loop")
        self.assertEqual(result["failures"][0]["code"], "pagination_loop")
        self.assertEqual(result["counters"]["requested_pages"], 1)

    def test_page_budget(self):
        result = self.run_case(max_pages=1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["failures"], [{"page": 2, "code": "page_budget"}])
        self.assertEqual(len(result["records"]), 2)

    def test_bad_page_budget_prevents_acquisition(self):
        for limit in (0, -1, 21):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.run_case(max_pages=limit)
        self.assertEqual(self.server.requests, [])

    def test_missing_next_is_partial(self):
        result = self.run_case("missing_next")
        self.assertEqual(result["failures"][0]["code"], "pagination_shape")

    def test_changed_total_page_count(self):
        result = self.run_case("changed_total")
        self.assertEqual(result["failures"][0]["code"], "page_metadata")

    def test_valid_empty_and_unconfirmed_empty_are_distinct(self):
        good = self.run_case("empty")
        bad = self.run_case("empty_unconfirmed")
        self.assertTrue(good["complete"])
        self.assertEqual(good["records"], [])
        self.assertFalse(bad["complete"])
        self.assertEqual(bad["failures"][0]["code"], "unconfirmed_empty")

    def test_error_html_http200_is_not_empty(self):
        result = self.run_case("denied")
        self.assertFalse(result["complete"])
        self.assertEqual(result["failures"][0]["code"], "listing_envelope")
        self.assertEqual(len(result["records"]), 2)

    def test_http503_is_recorded_and_keeps_partial_records(self):
        result = self.run_case("http_fail")
        self.assertEqual(result["failures"], [{"page": 2, "code": "http_503"}])
        self.assertEqual(result["counters"]["fetched_pages"], 1)
        self.assertEqual(len(result["records"]), 1)

    def test_redirect_is_rejected_before_external_follow(self):
        result = self.run_case("redirect")
        self.assertEqual(result["failures"], [{"page": 1, "code": "http_302"}])
        self.assertEqual(len(self.server.requests), 1)

    def test_json_is_not_html(self):
        result = self.run_case("not_html")
        self.assertEqual(result["failures"][0]["code"], "not_html")

    def test_body_limit(self):
        result = self.run_case("oversized")
        self.assertEqual(result["failures"][0]["code"], "body_limit")

    def test_duplicate_envelope(self):
        result = self.run_case("duplicate_envelope")
        self.assertEqual(result["failures"][0]["code"], "listing_envelope")

    def test_invalid_observation_time_before_acquisition(self):
        with self.assertRaises(ValueError):
            collect(self.policy, observed_utc="2026-10-11T21:00:00+01:00")
        self.assertEqual(self.server.requests, [])

    def test_observation_time_and_provenance(self):
        result = self.run_case()
        self.assertTrue(all(row["observedUTC"] == STAMP for row in result["records"]))
        self.assertEqual(result["records"][2]["sourceURL"], self.server.origin + "/careers/jobs/NS-003")

    def test_all_required_fields_reject_null_or_blank(self):
        for field in ("jobID", "title", "employer", "location", "sourceURL", "applicationURL", "observedUTC"):
            for value in (None, "", " "):
                with self.subTest(field=field, value=value):
                    row = {**self.oracle[0], field: value}
                    self.assertIn(field, validate_record(row))

    def test_refresh_complete_add_change_absence(self):
        old = self.run_case()
        new = self.run_case("refresh")
        result = refresh(old, new)
        self.assertEqual(result["added_ids"], ["NS-004"])
        self.assertEqual(result["removed_ids"], ["NS-002"])
        self.assertEqual(result["changed"], [{"jobID": "NS-001", "fields": {
            "title": {"before": "Platform Engineer", "after": "Senior Platform Engineer"},
            "location": {"before": "Leeds, UK", "after": "Remote - UK"}}}])
        self.assertFalse(result["removals_suppressed"])

    def test_partial_refresh_suppresses_disappearance(self):
        old = self.run_case()
        new = self.run_case("http_fail")
        result = refresh(old, new)
        self.assertTrue(result["removals_suppressed"])
        self.assertEqual(result["removed_ids"], [])
        self.assertEqual(result["retained_previous_ids"], ["NS-002", "NS-003"])
        self.assertEqual([row["jobID"] for row in result["next_snapshot"]["records"]],
                         ["NS-001", "NS-002", "NS-003"])
        self.assertEqual(result["next_snapshot"]["records"][0]["title"], "Senior Platform Engineer")

    def test_timestamp_only_change_is_not_a_content_alert(self):
        old = self.run_case()
        new = copy.deepcopy(old)
        for row in new["records"]:
            row["observedUTC"] = "2026-10-12T21:00:00Z"
        self.assertEqual(refresh(old, new)["changed"], [])

    def test_partial_refresh_retains_original_observation_timestamps(self):
        old = self.run_case()
        self.server.mode = "http_fail"
        new = collect(self.policy, observed_utc="2026-10-12T21:00:00Z")
        rows = refresh(old, new)["next_snapshot"]["records"]
        self.assertEqual(rows[0]["observedUTC"], "2026-10-12T21:00:00Z")
        self.assertEqual(rows[1]["observedUTC"], STAMP)
        self.assertEqual(rows[2]["observedUTC"], STAMP)

    def test_refresh_rejects_forged_provenance_and_string_complete(self):
        old = self.run_case()
        for field, value in (("employer", "Other Employer"),
                             ("sourceURL", "https://unapproved.invalid/careers/jobs/NS-001"),
                             ("applicationURL", self.server.origin + "/careers/apply/NS-999")):
            new = copy.deepcopy(old)
            new["records"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                refresh(old, new)
        new = copy.deepcopy(old)
        new["complete"] = "false"
        with self.assertRaises(ValueError):
            refresh(old, new)

    def test_valid_empty_can_mark_source_absence(self):
        result = refresh(self.run_case(), self.run_case("empty"))
        self.assertEqual(result["removed_ids"], ["NS-001", "NS-002", "NS-003"])

    def test_refresh_rejects_other_source_and_duplicate_records(self):
        old = self.run_case()
        new = copy.deepcopy(old)
        new["source"] += "&department=other"
        with self.assertRaises(ValueError):
            refresh(old, new)
        new = copy.deepcopy(old)
        new["records"].append(new["records"][0])
        with self.assertRaises(ValueError):
            refresh(old, new)

    def test_cli_success_and_partial_exit(self):
        command = [sys.executable, str(Path(__file__).parent / "collector.py"), "--start-url", self.server.url]
        good = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)["complete"])
        self.server.mode = "http_fail"
        bad = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(bad.stdout)["complete"])


class GreenhouseReplayTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(CAPTURE_PATH.read_text())

    def test_literal_id_oracle_and_full_known_record(self):
        result = project_capture(self.payload, employer="Greenhouse")
        self.assertEqual(result["candidate_count"], 19)
        self.assertEqual([row["jobID"] for row in result["candidate_records"]],
                         json.loads((FIXTURES / "greenhouse-expected-ids.json").read_text()))
        self.assertEqual(result["candidate_records"][1], {
            "jobID": "8126988", "title": "Commercial Counsel", "employer": "Greenhouse",
            "location": "Eastern Timezone",
            "sourceURL": "https://job-boards.greenhouse.io/greenhouse/jobs/8126988?gh_jid=8126988",
            "applicationURL": None, "observedUTC": "2026-10-11T21:03:15Z",
            "sourcePostedDate": None, "source_updated_at": "2026-10-09T18:28:27-04:00"})
        self.assertFalse(result["validated_for_refresh"])
        self.assertEqual(result["missing_required_fields"], ["applicationURL"])

    def test_source_updated_at_is_not_posted_date(self):
        result = project_capture(self.payload, employer="Greenhouse")
        self.assertTrue(all(row["sourcePostedDate"] is None for row in result["candidate_records"]))
        self.assertTrue(all(row["source_updated_at"] for row in result["candidate_records"]))

    def test_bad_count_and_duplicate_id_rejected(self):
        self.payload["capture"]["source_meta"]["total"] = 20
        with self.assertRaises(ValueError):
            project_capture(self.payload, employer="Greenhouse")
        self.payload = json.loads(CAPTURE_PATH.read_text())
        self.payload["jobs"][1] = self.payload["jobs"][0]
        with self.assertRaises(ValueError):
            project_capture(self.payload, employer="Greenhouse")

    def test_bad_url_and_missing_field_rejected(self):
        self.payload["jobs"][0]["absolute_url"] = "https://unapproved.invalid/"
        with self.assertRaises(ValueError):
            project_capture(self.payload, employer="Greenhouse")
        self.payload = json.loads(CAPTURE_PATH.read_text())
        self.payload["jobs"][0]["location"] = {"name": ""}
        with self.assertRaises(ValueError):
            project_capture(self.payload, employer="Greenhouse")

    def test_empty_feed_distinct_from_failed_envelope(self):
        self.payload["jobs"] = []
        self.payload["capture"]["source_meta"]["total"] = 0
        self.payload["capture"]["jobs_count"] = 0
        self.assertEqual(project_capture(self.payload, employer="Greenhouse")["candidate_count"], 0)
        self.payload["capture"]["status"] = 503
        with self.assertRaises(ValueError):
            project_capture(self.payload, employer="Greenhouse")


class ManagedContractTests(unittest.TestCase):
    @staticmethod
    def response(body, *, target_type=None, outer_type=None):
        class Response(io.BytesIO):
            status = 200
        response = Response(body.encode())
        response.headers = Message()
        response.headers["Ant-page-status-code"] = "200"
        if target_type is not None:
            response.headers["Ant-original-header-content-type"] = target_type
        if outer_type is not None:
            response.headers["Content-Type"] = outer_type
        return response

    def test_source_shaped_html_without_outer_content_type(self):
        outer = self
        class Opener:
            def open(self, request, timeout):
                target = parse_qs(urlsplit(request.full_url).query)["url"][0]
                page = parse_qs(urlsplit(target).query)["page"][0]
                return outer.response((FIXTURES / f"page-{page}.html").read_text(),
                                      target_type="text/html; charset=utf-8")
        policy = SourcePolicy("https://owned.example/careers/roles?page=1")
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "fixture-secret"}):
            result = collect(policy, observed_utc=STAMP,
                             fetch=lambda url: managed_html(url, browser="false", opener=Opener()))
        expected = json.loads((FIXTURES / "expected-records.json").read_text().replace(
            "__ORIGIN__", "https://owned.example"))
        self.assertTrue(result["complete"])
        self.assertEqual(result["records"], expected)

    def test_explicit_non_html_target_rejected_despite_outer_html(self):
        outer = self
        class Opener:
            def open(self, request, timeout):
                return outer.response("<html>not a permitted HTML target</html>",
                                      target_type="application/json", outer_type="text/html")
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "fixture-secret"}):
            with self.assertRaisesRegex(CollectionError, "not_html"):
                managed_html("https://owned.example/", browser="false", opener=Opener())

    def test_missing_target_type_does_not_replace_listing_schema_guard(self):
        outer = self
        class Opener:
            def open(self, request, timeout):
                return outer.response('{"jobs": []}')
        policy = SourcePolicy("https://owned.example/careers/roles?page=1")
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "fixture-secret"}):
            result = collect(policy, observed_utc=STAMP,
                             fetch=lambda url: managed_html(url, browser="false", opener=Opener()))
        self.assertFalse(result["complete"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["failures"][0]["code"], "listing_envelope")

    def test_explicit_request_parameters_and_header_secret(self):
        for browser in ("false", "true"):
            request = build_request("https://owned.example/careers/roles?page=1", browser=browser, key="fixture-secret")
            self.assertEqual(urlsplit(request.full_url).path, "/v2/general")
            self.assertEqual(parse_qs(urlsplit(request.full_url).query), {
                "url": ["https://owned.example/careers/roles?page=1"], "browser": [browser],
                "proxy_type": ["datacenter"], "proxy_country": ["us"], "timeout": ["30"],
                "return_page_source": ["false"]})
            self.assertNotIn("fixture-secret", request.full_url)
            self.assertEqual(request.get_header("X-api-key"), "fixture-secret")

    def test_environment_key_and_invalid_mode(self):
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "fixture-secret"}):
            self.assertEqual(build_request("https://owned.example/", browser="false").get_header("X-api-key"), "fixture-secret")
        with self.assertRaises(ValueError):
            build_request("https://owned.example/", browser=None, key="fixture-secret")

    def test_http_target_not_sent_to_managed_api(self):
        with self.assertRaises(ValueError):
            build_request("http://127.0.0.1:8873/", browser="false", key="fixture-secret")

    def test_response_acceptance_and_target_status(self):
        class FakeResponse(io.BytesIO):
            status = 200
            headers = Message()
        response = FakeResponse(b"<html>Owned fixture</html>")
        response.headers["Content-Type"] = "text/html"
        response.headers["Ant-page-status-code"] = "200"
        class Opener:
            def open(self, request, timeout):
                return response
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "fixture-secret"}):
            self.assertEqual(managed_html("https://owned.example/", browser="false", opener=Opener()),
                             "<html>Owned fixture</html>")
            response = FakeResponse(b"unavailable")
            response.headers.replace_header("Ant-page-status-code", "404")
            with self.assertRaisesRegex(CollectionError, "target_status_unaccepted"):
                managed_html("https://owned.example/", browser="true", opener=Opener())

    def test_error_message_has_no_request_url_or_key(self):
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 403, "fixture-secret", {}, None)
        with patch.dict(os.environ, {"SCRAPINGANT_API_KEY": "fixture-secret"}):
            with self.assertRaises(CollectionError) as caught:
                managed_html("https://owned.example/", browser="false", opener=Opener())
        self.assertEqual(str(caught.exception), "api_http_403")


if __name__ == "__main__":
    unittest.main(verbosity=2)
