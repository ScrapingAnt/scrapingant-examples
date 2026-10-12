"""Offline literal-oracle and boundary checks for one published job page."""
import importlib
import hashlib
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
import unittest
import subprocess
import sys
from unittest.mock import patch
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
STAMP = "2026-10-12T08:26:43Z"
SOURCE_URL = "https://job-boards.greenhouse.io/greenhouse/jobs/8126988?gh_jid=8126988"


class AdapterTests(unittest.TestCase):
    def setUp(self):
        try:
            self.helper = importlib.import_module("greenhouse_single_post")
        except ModuleNotFoundError:
            self.fail("The source-specific adapter has not been implemented")
        self.body = (ROOT / "fixtures/greenhouse-single-post.html").read_text()
        self.expected = json.loads((ROOT / "fixtures/greenhouse-single-post-expected-record.json").read_text())

    def collect(self, body):
        return self.helper.collect_one(fetch=lambda url: body, observed_utc=STAMP)

    def test_literal_record_and_single_post_completeness_scope(self):
        result = self.collect(self.body)
        self.assertEqual(result["records"], [self.expected])
        self.assertTrue(result["complete"])
        self.assertEqual(result["completeness_scope"], "one_selected_posting_page")
        self.assertFalse(result["board_inventory_complete"])
        self.assertEqual(result["counters"]["requested_pages"], 1)
        self.assertEqual(result["counters"]["accepted_pages"], 1)

    def test_error_or_empty_html_is_failed_not_legitimate_empty(self):
        for body in ["", "<html><body>No jobs found</body></html>"]:
            with self.subTest(body=body):
                result = self.collect(body)
                self.assertFalse(result["complete"])
                self.assertEqual(result["records"], [])
                self.assertEqual(result["failures"][0]["code"], "html_contract")

    def test_application_form_must_be_present(self):
        body = self.body.replace('id="application-form"', 'id="other-form"')
        self.assertFalse(self.collect(body)["complete"])

    def test_application_url_must_match_this_post(self):
        body = self.body.replace('action="/greenhouse/jobs/8126988?gh_jid=8126988"',
                                 'action="https://example.org/apply"')
        self.assertFalse(self.collect(body)["complete"])

    def test_application_action_must_not_be_missing(self):
        body = self.body.replace('action="/greenhouse/jobs/8126988?gh_jid=8126988" ', '')
        self.assertFalse(self.collect(body)["complete"])

    def test_duplicate_title_marker_is_rejected(self):
        body = self.body.replace("</body>", "<h1>Other job</h1></body>")
        self.assertFalse(self.collect(body)["complete"])

    def test_metadata_title_disagreement_is_rejected(self):
        body = self.body.replace('property="og:title" content="Commercial Counsel"',
                                 'property="og:title" content="Sales Associate"')
        self.assertFalse(self.collect(body)["complete"])

    def test_employer_identity_cannot_drift(self):
        body = self.body.replace(" at Greenhouse</title>", " at Other Employer</title>")
        self.assertFalse(self.collect(body)["complete"])

    def test_location_marker_must_be_present(self):
        body = self.body.replace('class="job__location"', 'class="other-location"')
        self.assertFalse(self.collect(body)["complete"])

    def test_source_id_mismatch_is_rejected(self):
        body = self.body.replace("8126988", "8234044")
        self.assertFalse(self.collect(body)["complete"])

    def test_http_canonical_discrepancy_is_recorded_without_changing_dispatch_url(self):
        result = self.collect(self.body)
        self.assertEqual(result["source_metadata"]["canonical_url"], SOURCE_URL.replace("https:", "http:", 1))
        self.assertTrue(result["source_metadata"]["canonical_scheme_differs"])
        self.assertEqual(result["records"][0]["sourceURL"], SOURCE_URL)
        self.assertEqual(result["records"][0]["applicationURL"], SOURCE_URL)

    def test_optional_date_stays_null(self):
        result = self.collect(self.body)
        self.assertIsNone(result["records"][0]["sourcePostedDate"])

    def test_invalid_observation_stamp_prevents_acquisition(self):
        def forbidden_fetch(url):
            self.fail("An invalid caller timestamp must not reach acquisition")
        with self.assertRaises(ValueError):
            self.helper.collect_one(fetch=forbidden_fetch, observed_utc="2026-10-12")

    def test_literal_oracle_catches_plausible_semantic_wrong_title(self):
        wrong = self.body.replace("Commercial Counsel", "Senior Legal Assistant")
        result = self.collect(wrong)
        self.assertTrue(result["complete"])
        self.assertNotEqual(result["records"], [self.expected])


class FixtureResponse:
    def __init__(self, body, *, status=200, target="200", credits="1"):
        self.status = status
        self.headers = Message()
        if target is not None:
            self.headers["Ant-page-status-code"] = target
        if credits is not None:
            self.headers["Ant-credits-cost"] = credits
        self.headers["Ant-original-header-content-type"] = "text/html; charset=utf-8"
        self.body = BytesIO(body)

    def read(self, n): return self.body.read(n)
    def __enter__(self): return self
    def __exit__(self, *args): self.body.close()


class FixtureOpener:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error

    def open(self, request, timeout):
        if self.error:
            raise self.error
        return self.response


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.helper = importlib.import_module("greenhouse_single_post")
        self.assertTrue(hasattr(self.helper, "OneDispatchObserver"), "The one-dispatch receipt observer is missing")
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.body = (ROOT / "fixtures/greenhouse-single-post.html").read_bytes()

    def observer(self, body=None, **kwargs):
        return self.helper.OneDispatchObserver(Path(self.temp.name),
                  delegate=FixtureOpener(FixtureResponse(self.body if body is None else body, **kwargs)))

    def managed(self, observer, key="offline-placeholder"):
        real_builder = self.helper.transport.build_request
        with patch.object(self.helper.transport, "build_request",
                          side_effect=lambda url, browser: real_builder(url, browser=browser, key=key)):
            return self.helper.managed_collection(observer, observed_utc=STAMP)

    def test_receipt_and_body_exist_before_adapter_rejects_bad_html(self):
        bad = b"<html><body>Public error page</body></html>"
        observer = self.observer(body=bad)
        real_record = self.helper.SinglePostParser.record
        def verify_persisted_before_acceptance(parser, stamp):
            receipt_path = Path(self.temp.name) / "receipt.json"
            self.assertTrue(receipt_path.exists())
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["response_sha256"], hashlib.sha256(bad).hexdigest())
            self.assertEqual((Path(self.temp.name) / "response.html").read_bytes(), bad)
            return real_record(parser, stamp)
        with patch.object(self.helper.SinglePostParser, "record", verify_persisted_before_acceptance):
            result = self.managed(observer)
        self.assertFalse(result["complete"])
        receipt = json.loads((Path(self.temp.name) / "receipt.json").read_text())
        self.assertEqual(receipt["actual_credits"], 1)
        self.assertEqual(receipt["http_status"], 200)
        self.assertEqual(receipt["target_status"], "200")
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(bad).hexdigest())
        self.assertEqual((Path(self.temp.name) / "response.html").read_bytes(), bad)
        self.assertEqual(receipt["provider_dispatches"], 1)

    def test_raw_managed_path_returns_literal_record_with_missing_outer_type(self):
        observer = self.observer()
        result = self.managed(observer)
        expected = json.loads((ROOT / "fixtures/greenhouse-single-post-expected-record.json").read_text())
        self.assertEqual(result["records"], [expected])
        self.assertEqual(observer.receipt["actual_credits"], 1)
        self.assertIsNone(observer.receipt["outer_content_type"])
        self.assertEqual(observer.calls, 1)

    def test_second_dispatch_is_rejected_without_retry(self):
        observer = self.observer()
        request = self.helper.transport.build_request(SOURCE_URL, browser="false", key="offline-placeholder")
        with observer.open(request, timeout=35): pass
        with self.assertRaises(self.helper.CollectionError):
            observer.open(request, timeout=35)
        self.assertEqual(observer.calls, 1)
        self.assertEqual(observer.receipt["provider_dispatches"], 1)

    def test_wrong_source_is_rejected_before_dispatch(self):
        observer = self.observer()
        request = self.helper.transport.build_request("https://example.org/jobs", browser="false", key="offline-placeholder")
        with self.assertRaises(self.helper.CollectionError):
            observer.open(request, timeout=35)
        self.assertEqual(observer.calls, 0)

    def test_rendered_mode_cannot_be_used_as_fallback(self):
        observer = self.observer()
        request = self.helper.transport.build_request(SOURCE_URL, browser="true", key="offline-placeholder")
        with self.assertRaises(self.helper.CollectionError):
            observer.open(request, timeout=35)
        self.assertEqual(observer.calls, 0)

    def test_echoed_request_fields_are_not_job_html(self):
        echo = json.dumps({"url": SOURCE_URL, "title": "Commercial Counsel", "location": "Eastern Timezone"}).encode()
        observer = self.observer(body=echo)
        result = self.managed(observer)
        self.assertFalse(result["complete"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["failures"][0]["code"], "html_contract")
        self.assertEqual(observer.receipt["actual_credits"], 1)

    def test_oversized_body_hash_is_labeled_bounded_prefix_and_rejected(self):
        observer = self.observer(body=b"x" * 1_000_002)
        result = self.managed(observer)
        self.assertFalse(result["complete"])
        self.assertEqual(result["failures"][0]["code"], "body_limit")
        self.assertFalse(observer.receipt["full_body_captured"])
        self.assertEqual(observer.receipt["response_bytes"], 1_000_001)
        self.assertEqual(observer.receipt.get("body_hash_scope"), "bounded prefix; full body unavailable")

    def test_api_redirect_receipt_is_recorded_as_failed_without_following(self):
        headers = Message()
        headers["Location"] = "https://example.org/redirect"
        observer = self.helper.OneDispatchObserver(Path(self.temp.name), delegate=FixtureOpener(
            error=HTTPError("https://api.scrapingant.com/v2/general", 302, "redirect", headers, BytesIO(b"redirect"))))
        result = self.managed(observer)
        self.assertFalse(result["complete"])
        self.assertEqual(result["failures"][0]["code"], "api_http_302")
        self.assertEqual(observer.calls, 1)
        self.assertEqual(observer.receipt["http_status"], 302)

    def test_target_failure_preserves_receipt_before_rejection(self):
        observer = self.observer(target="403")
        result = self.managed(observer)
        self.assertFalse(result["complete"])
        self.assertEqual(result["failures"][0]["code"], "target_status_unaccepted")
        self.assertEqual(observer.receipt["target_status"], "403")
        self.assertEqual(observer.receipt["actual_credits"], 1)

    def test_missing_or_unexpected_credit_receipt_prevents_record_acceptance(self):
        for credits in [None, "10", "bad"]:
            with self.subTest(credits=credits):
                observer = self.observer(credits=credits)
                result = self.managed(observer)
                self.assertFalse(result["complete"])
                self.assertEqual(result["failures"][0]["code"], "credit_receipt_unaccepted")

    def test_transport_failure_counts_attempt_and_leaves_charge_unknown(self):
        observer = self.helper.OneDispatchObserver(Path(self.temp.name),
            delegate=FixtureOpener(error=URLError("unavailable")))
        result = self.managed(observer)
        self.assertFalse(result["complete"])
        self.assertEqual(observer.receipt["provider_dispatches"], 1)
        self.assertIsNone(observer.receipt["actual_credits"])
        self.assertEqual(observer.receipt["error"], "api_transport_failed")

    def echo_variants(self, key):
        return [key, "".join(f"&#x{ord(char):x};" for char in key),
                "".join(f"\\u{ord(char):04x}" for char in key)]

    def test_credential_echo_in_plain_entity_json_body_is_never_persisted(self):
        key = 'synthetic<&"secret-20261012'
        for echo in self.echo_variants(key):
            with self.subTest(echo=echo), TemporaryDirectory() as temp:
                body = self.body + ("<!--" + echo + "-->").encode()
                observer = self.helper.OneDispatchObserver(Path(temp), delegate=FixtureOpener(FixtureResponse(body)))
                result = self.managed(observer, key=key)
                self.assertFalse(result["complete"])
                self.assertEqual(result["failures"][0]["code"], "credential_echo_detected")
                self.assertFalse((Path(temp) / "response.html").exists())
                receipt = json.loads((Path(temp) / "receipt.json").read_text())
                self.assertFalse(receipt["body_retained"])
                self.assertEqual(receipt["actual_credits"], 1)
                self.assertNotIn(key, (Path(temp) / "receipt.json").read_text())

    def test_credential_echo_in_allowlisted_headers_and_receipt_is_never_persisted(self):
        key = 'synthetic<&"secret-20261012'
        fields = {"Ant-original-header-content-type": "target_content_type",
                  "Content-Type": "outer_content_type", "Ant-credits-cost": "credit_receipt",
                  "Ant-page-status-code": "target_status"}
        for header, field in fields.items():
            for echo in self.echo_variants(key):
                with self.subTest(header=header, echo=echo), TemporaryDirectory() as temp:
                    response = FixtureResponse(self.body)
                    if header in response.headers:
                        del response.headers[header]
                    response.headers[header] = echo
                    observer = self.helper.OneDispatchObserver(Path(temp), delegate=FixtureOpener(response))
                    result = self.managed(observer, key=key)
                    self.assertFalse(result["complete"])
                    self.assertEqual(result["failures"][0]["code"], "credential_echo_detected")
                    self.assertFalse((Path(temp) / "response.html").exists())
                    receipt = json.loads((Path(temp) / "receipt.json").read_text())
                    self.assertIsNone(receipt[field])
                    self.assertFalse(receipt["body_retained"])
                    self.assertNotIn(key, (Path(temp) / "receipt.json").read_text())

    def test_receipt_success_schema_uses_observed_credit_and_one_request(self):
        observer = self.observer()
        self.managed(observer)
        receipt = json.loads((Path(self.temp.name) / "receipt.json").read_text())
        self.assertEqual(receipt.get("actual_receipt_credits"), 1)
        self.assertEqual(receipt.get("requests"), 1)
        self.assertIs(receipt.get("accepted"), True)
        self.assertIs(type(receipt["requests"]), int)

    def test_receipt_parse_failure_preserves_known_credit(self):
        observer = self.observer(body=b"<html><body>Unavailable</body></html>")
        self.managed(observer)
        receipt = json.loads((Path(self.temp.name) / "receipt.json").read_text())
        self.assertEqual(receipt.get("actual_receipt_credits"), 1)
        self.assertEqual(receipt.get("requests"), 1)
        self.assertIs(receipt.get("accepted"), False)

    def test_receipt_transport_failure_keeps_credit_unknown(self):
        observer = self.helper.OneDispatchObserver(Path(self.temp.name), delegate=FixtureOpener(error=URLError("unavailable")))
        self.managed(observer)
        receipt = json.loads((Path(self.temp.name) / "receipt.json").read_text())
        self.assertIn("actual_receipt_credits", receipt)
        self.assertIsNone(receipt["actual_receipt_credits"])
        self.assertEqual(receipt.get("requests"), 1)
        self.assertIs(receipt.get("accepted"), False)

    def test_receipt_initial_schema_precedes_any_dispatch(self):
        self.observer()
        receipt_path = Path(self.temp.name) / "receipt.json"
        self.assertTrue(receipt_path.exists())
        receipt = json.loads(receipt_path.read_text())
        self.assertIn("actual_receipt_credits", receipt)
        self.assertIsNone(receipt["actual_receipt_credits"])
        self.assertEqual(receipt.get("requests"), 0)
        self.assertIs(receipt.get("accepted"), False)

    def test_duplicate_credit_receipts_are_unknown_and_unaccepted(self):
        for duplicate in ["1", "10"]:
            with self.subTest(duplicate=duplicate), TemporaryDirectory() as temp:
                response = FixtureResponse(self.body)
                response.headers["Ant-credits-cost"] = duplicate
                observer = self.helper.OneDispatchObserver(Path(temp), delegate=FixtureOpener(response))
                self.managed(observer)
                receipt = json.loads((Path(temp) / "receipt.json").read_text())
                self.assertIs(receipt["accepted"], False)
                self.assertIsNone(receipt["actual_receipt_credits"])
                self.assertEqual(receipt["requests"], 1)

    def test_second_credit_header_echo_is_guarded_before_persistence(self):
        key = 'synthetic<&"secret-20261012'
        for echo in self.echo_variants(key):
            with self.subTest(echo=echo), TemporaryDirectory() as temp:
                response = FixtureResponse(self.body)
                response.headers["Ant-credits-cost"] = echo
                observer = self.helper.OneDispatchObserver(Path(temp), delegate=FixtureOpener(response))
                result = self.managed(observer, key=key)
                receipt = json.loads((Path(temp) / "receipt.json").read_text())
                self.assertIs(receipt["accepted"], False)
                self.assertTrue(result["failures"])
                self.assertEqual(result["failures"][0]["code"], "credential_echo_detected")
                self.assertFalse((Path(temp) / "response.html").exists())
                self.assertIsNone(receipt["actual_receipt_credits"])
                self.assertIs(receipt["accepted"], False)

    def test_live_consistent_title_drift_retains_record_and_cost_but_is_unaccepted(self):
        body = self.body.replace(b"Commercial Counsel", b"Senior Legal Assistant")
        observer = self.observer(body=body)
        result = self.managed(observer)
        self.assertEqual(result["records"][0]["title"], "Senior Legal Assistant")
        self.assertEqual(observer.receipt["actual_receipt_credits"], 1)
        self.assertIs(observer.receipt["accepted"], False)
        self.assertFalse(result["semantic_oracle_matches"])

    def test_live_oracle_ignores_only_actual_observation_time(self):
        observer = self.observer()
        real_builder = self.helper.transport.build_request
        with patch.object(self.helper.transport, "build_request",
                          side_effect=lambda url, browser: real_builder(url, browser=browser, key="offline-placeholder")):
            result = self.helper.managed_collection(observer, observed_utc="2026-10-12T09:20:01Z")
        self.assertEqual(result["records"][0]["observedUTC"], "2026-10-12T09:20:01Z")
        self.assertIs(observer.receipt["accepted"], True)


class ControllerInterfaceTests(unittest.TestCase):
    def run_helper(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "greenhouse_single_post.py"), *args],
                              capture_output=True, text=True, env={})

    def test_verify_source_accepts_semantic_contract_despite_full_hash_difference(self):
        run = self.run_helper("--verify-source", str(ROOT / "fixtures/greenhouse-single-post.html"))
        try:
            result = json.loads(run.stdout)
        except json.JSONDecodeError:
            self.fail("The offline --verify-source controller interface is missing")
        self.assertEqual(run.returncode, 0)
        self.assertTrue(result["semantic_preflight"]["accepted"])
        self.assertFalse(result["semantic_preflight"]["matches_frozen_full_body"])
        self.assertEqual(result["execution"]["provider_dispatches"], 0)


    def test_live_flag_is_not_offered_by_offline_example(self):
        run = self.run_helper("--live")
        self.assertEqual(run.returncode, 2)
        self.assertIn("unrecognized arguments", run.stderr)

    def test_default_cli_is_owned_fixture_only(self):
        run = self.run_helper()
        self.assertEqual(run.returncode, 0)
        result = json.loads(run.stdout)
        self.assertEqual(result["execution"]["mode"], "owned_source_shaped_fixture")
        self.assertEqual(result["execution"]["provider_dispatches"], 0)

    def test_verify_source_rejects_empty_page_with_nonzero_exit(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "empty.html"
            path.write_text("<html><body>No jobs</body></html>")
            run = self.run_helper("--verify-source", str(path))
            self.assertEqual(run.returncode, 2)
            self.assertFalse(json.loads(run.stdout)["semantic_preflight"]["accepted"])

class SourceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.helper = importlib.import_module("greenhouse_single_post")
        self.body = (ROOT / "fixtures/greenhouse-single-post.html").read_bytes()

    def verify(self, body):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "captured.html"
            path.write_bytes(body)
            return self.helper.verify_source(path)

    def test_harmless_wrapper_and_tracking_nonce_drift_is_semantically_accepted(self):
        wrapped = self.body.replace(b"<body>", b'<body><div data-wrapper="changed"><script nonce="changed-nonce"></script>').replace(b"</body>", b"</div></body>")
        result = self.verify(wrapped)
        self.assertTrue(result["semantic_preflight"]["accepted"])
        self.assertTrue(result["semantic_preflight"]["literal_oracle_matches"])
        self.assertFalse(result["semantic_preflight"]["matches_frozen_full_body"])
        self.assertEqual(result["records"], [json.loads((ROOT / "fixtures/greenhouse-single-post-expected-record.json").read_text())])

    def test_coherent_field_drift_is_rejected_by_independent_oracle(self):
        body = self.body.replace(b"Commercial Counsel", b"Senior Legal Assistant")
        result = self.verify(body)
        self.assertFalse(result["semantic_preflight"]["accepted"])
        self.assertFalse(result["semantic_preflight"]["literal_oracle_matches"])
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["title"], "Senior Legal Assistant")

    def test_truncated_page_is_rejected(self):
        result = self.verify(self.body.replace(b"</html>", b""))
        self.assertFalse(result["semantic_preflight"]["accepted"])
        self.assertEqual(result["failures"][0]["code"], "html_contract")

    def test_unclosed_form_with_appended_html_closing_is_rejected(self):
        result = self.verify(self.body.replace(b"</form>", b""))
        self.assertFalse(result["semantic_preflight"]["accepted"])
        self.assertEqual(result["failures"][0]["code"], "html_contract")

    def test_mismatched_form_closing_tag_is_rejected_even_if_depth_balances(self):
        result = self.verify(self.body.replace(b"</form>", b"</div>"))
        self.assertFalse(result["semantic_preflight"]["accepted"])
        self.assertEqual(result["failures"][0]["code"], "html_contract")

    def test_challenge_or_echo_is_rejected(self):
        for body in [b"<html><body>Verify you are human</body></html>", json.dumps({"source":SOURCE_URL,"title":"Commercial Counsel"}).encode()]:
            with self.subTest(body=body):
                result = self.verify(body)
                self.assertFalse(result["semantic_preflight"]["accepted"])
                self.assertEqual(result["records"], [])

    def test_oversized_prefix_is_rejected_without_claiming_full_hash(self):
        result = self.verify(b"x" * 1_000_002)
        self.assertFalse(result["semantic_preflight"]["accepted"])
        self.assertEqual(result["failures"][0]["code"], "body_limit")
        self.assertEqual(result["semantic_preflight"]["input_hash_scope"], "bounded prefix; full file exceeds body limit")



if __name__ == "__main__":
    unittest.main(verbosity=2)
