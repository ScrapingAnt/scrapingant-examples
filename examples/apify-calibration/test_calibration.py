"""Offline boundary tests with an HTTP transport double; never provider execution."""
import contextlib
import copy
from decimal import Decimal
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import calibration as c

BUILD = "3.0.123"
COMPLETE = "https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/complete.html"
CHANGED = "https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/changed-layout.html"
TOKEN = "OFFLINE_TEST_SECRET_NEVER_REAL"


class ForbiddenEnvironment:
    def get(self, *args):
        raise AssertionError("environment read before closed cost guard")


def run_response(status="SUCCEEDED"):
    return {"data": {
        "id": "OfflineRunIdentifier", "userId": "OfflineAccountIdentifier",
        "defaultDatasetId": "OfflineDatasetIdentifier", "status": status,
        "buildNumber": BUILD,
        "options": {"build": BUILD, "memoryMbytes": 1024, "timeoutSecs": 120,
                    "maxTotalChargeUsd": 0.10},
        "usageTotalUsd": 0.012345, "usage": {"ACTOR_COMPUTE_UNITS": 0.01},
    }}


def record(fixture):
    return {"fixture": fixture, "sku": "AA101", "name": "Desk Lamp",
            "price_minor": 3499, "currency": "USD",
            "#debug": {"account": "OfflineAccountIdentifier"}}


class ScriptedTransport:
    """Records the real runner's boundary requests and returns synthetic replies."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def request(self, method, url, payload, token):
        self.requests.append((method, url, copy.deepcopy(payload), token))
        if not self.replies:
            raise AssertionError("unexpected additional HTTP request")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)


class PlannerTests(unittest.TestCase):
    def test_default_plan_never_reads_environment_or_connects(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(c.main([], environ=ForbiddenEnvironment(),
                                    transport=ScriptedTransport([])), 0)
        p = json.loads(out.getvalue())
        self.assertFalse(p["readiness"]["ready"])
        self.assertIsNone(p["all_in_upper_bound_usd"])
        self.assertEqual(p["provider_calls_performed"], 0)
        self.assertEqual(p["evidence_type"], "unexecuted_plan")

    def test_execution_blocks_before_environment_access_or_http(self):
        for argv in (["--execute", "--build", BUILD],
                     ["--check-readiness", "--build", BUILD]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(c.main(argv, environ=ForbiddenEnvironment(),
                                        transport=ScriptedTransport([])), 2)

    def test_execute_function_requires_opt_in_and_a_reviewed_guard(self):
        for opt_in in (False, True):
            with self.subTest(opt_in=opt_in), self.assertRaises(c.PolicyError):
                c.execute_live(BUILD, opt_in=opt_in, environ=ForbiddenEnvironment(),
                               transport=ScriptedTransport([]))

    def test_reviewed_finite_retention_does_not_require_deletion_approval(self):
        guard = {"ready": True, "public_build": BUILD, "review_reference": "OFFLINE_TEST_REVIEW",
                 "all_in_upper_bound_usd": "0.90",
                 "retention_policy": {"mode": "finite_retention", "upper_bound_hours": "168",
                                      "review_reference": "OFFLINE_TEST_POLICY"}}
        with patch.object(c, "REVIEWED_GUARD", guard):
            c.require_readiness(BUILD)

    def test_cleanup_policy_requires_approval_and_a_known_duration(self):
        policy = {"mode": "cleanup", "upper_bound_hours": "1",
                  "review_reference": "OFFLINE_TEST_POLICY", "cleanup_approved": False}
        guard = {"ready": True, "public_build": BUILD, "review_reference": "OFFLINE_TEST_REVIEW",
                 "all_in_upper_bound_usd": "0.90", "retention_policy": policy}
        for mutation in ("unapproved", "unknown_duration", "unknown_mode"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(guard)
                if mutation == "unknown_duration": changed["retention_policy"]["upper_bound_hours"] = None
                elif mutation == "unknown_mode": changed["retention_policy"]["mode"] = "assume_seven_days"
                with patch.object(c, "REVIEWED_GUARD", changed), self.assertRaises(c.PolicyError):
                    c.execute_live(BUILD, opt_in=True, environ=ForbiddenEnvironment(), transport=ScriptedTransport([]))
        guard["retention_policy"]["cleanup_approved"] = True
        with patch.object(c, "REVIEWED_GUARD", guard):
            c.require_readiness(BUILD)

    def test_build_requires_immutable_public_number_not_tag_or_query(self):
        for build in ("latest", "main", "3.0", "3.0.0", "3.0.123?token=x", " 3.0.123", True):
            with self.subTest(build=build), self.assertRaises(c.PolicyError):
                c.build_plan(build)

    def test_payload_constrains_owned_pages_and_resource_options(self):
        p = c.build_plan(BUILD)
        self.assertEqual(p["actor"], "apify/web-scraper")
        self.assertEqual(p["input"]["startUrls"], [{"url": COMPLETE}, {"url": CHANGED}])
        self.assertEqual(p["options"], {"build": BUILD, "memory": "1024", "timeout": "120",
                                       "maxTotalChargeUsd": "0.10", "restartOnError": "false"})
        for key, want in {"runMode": "PRODUCTION", "maxConcurrency": 1,
                          "maxPagesPerCrawl": 2, "maxResultsPerCrawl": 2,
                          "maxRequestRetries": 0, "linkSelector": "",
                          "injectJQuery": False, "downloadMedia": False,
                          "downloadCss": False, "maxScrollHeightPixels": 0,
                          "debugLog": False, "browserLog": False}.items():
            self.assertEqual(p["input"][key], want, key)
        self.assertEqual(p["input"]["proxyConfiguration"], {"useApifyProxy": False})
        self.assertEqual(p["fixture_body_bytes"], {"complete": 290, "changed-layout": 422})
        self.assertEqual(p["nominal_compute_only_usd"], "0.006666666666666666666666666667")
        self.assertFalse(p["nominal_compute_is_all_in_bound"])

    def test_storage_math_preserves_gb_hour_rates_and_unknowns(self):
        self.assertEqual(c.storage_cost_usd("1", "2", "0.5", "168"), Decimal("0.840"))
        self.assertEqual(c.storage_cost_usd("0", "0", "0", "168"), Decimal("0"))
        for values in ((None, "0", "0", "168"), ("-1", "0", "0", "168"),
                       (0.5, "0", "0", "168"), ("0", "NaN", "0", "168")):
            with self.subTest(values=values), self.assertRaises(c.PolicyError):
                c.storage_cost_usd(*values)


class OrchestrationTests(unittest.TestCase):
    def test_one_start_bounded_polling_and_one_filtered_export(self):
        transport = ScriptedTransport([run_response("RUNNING"), run_response(),
                                       [record("complete"), record("changed-layout")]])
        result = c.orchestrate(c.build_plan(BUILD), TOKEN, transport)
        self.assertEqual(result["accepted_output_count"], 2)
        self.assertEqual(result["returned_output_count"], 2)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual([x[0] for x in transport.requests], ["POST", "GET", "GET"])
        self.assertEqual(urlsplit(transport.requests[0][1]).path, "/v2/actors/apify~web-scraper/runs")
        query = parse_qs(urlsplit(transport.requests[-1][1]).query)
        self.assertEqual(query["limit"], ["2"])
        self.assertEqual(query["fields"], ["fixture,sku,name,price_minor,currency"])
        self.assertNotIn("unwind", query)
        serialized = json.dumps(result)
        for secret in (TOKEN, "OfflineRunIdentifier", "OfflineDatasetIdentifier", "OfflineAccountIdentifier"):
            self.assertNotIn(secret, serialized)
        self.assertTrue(all(TOKEN not in x[1] and "token=" not in x[1] for x in transport.requests))

    def test_ambiguous_start_error_never_retries_or_exposes_provider_body(self):
        transport = ScriptedTransport([RuntimeError(TOKEN + " private provider error body account-id")])
        with self.assertRaises(c.PolicyError) as error:
            c.orchestrate(c.build_plan(BUILD), TOKEN, transport)
        self.assertEqual(len(transport.requests), 1)
        self.assertNotIn(TOKEN, str(error.exception))
        self.assertNotIn("private provider", str(error.exception))

    def test_effective_option_mismatch_stops_without_second_start(self):
        for field, value in (("maxTotalChargeUsd", None), ("memoryMbytes", 1024.0),
                             ("timeoutSecs", 120.0), ("buildNumber", "3.0.124")):
            with self.subTest(field=field):
                response = run_response()
                if field == "buildNumber": response["data"][field] = value
                else: response["data"]["options"][field] = value
                transport = ScriptedTransport([response])
                with self.assertRaises(c.PolicyError):
                    c.orchestrate(c.build_plan(BUILD), TOKEN, transport)
                self.assertEqual(len(transport.requests), 1)

    def test_poll_limit_does_not_restart_abort_or_delete(self):
        transport = ScriptedTransport([run_response("RUNNING")] * 4)
        with self.assertRaises(c.PolicyError):
            c.orchestrate(c.build_plan(BUILD), TOKEN, transport)
        self.assertEqual([x[0] for x in transport.requests], ["POST", "GET", "GET", "GET"])
        self.assertTrue(all("abort" not in x[1] and "delete" not in x[1] for x in transport.requests))

    def test_altered_fixture_or_actor_payload_rejected_before_start(self):
        for mutation in ("actor", "url", "retry"):
            with self.subTest(mutation=mutation):
                p = c.build_plan(BUILD)
                if mutation == "actor": p["actor"] = "someone/other-actor"
                elif mutation == "url": p["input"]["startUrls"][0]["url"] = "https://example.invalid/"
                else: p["input"]["maxRequestRetries"] = 1
                transport = ScriptedTransport([])
                with self.assertRaises(c.PolicyError): c.orchestrate(p, TOKEN, transport)
                self.assertEqual(transport.requests, [])

    def test_failed_run_does_not_export_or_rerun(self):
        transport = ScriptedTransport([run_response("FAILED")])
        with self.assertRaises(c.PolicyError):
            c.orchestrate(c.build_plan(BUILD), TOKEN, transport)
        self.assertEqual(len(transport.requests), 1)

    def test_untrusted_output_must_match_fixture_contract(self):
        for bad in ([record("complete"), record("complete")],
                    [dict(record("complete"), name=TOKEN)],
                    [dict(record("complete"), price_minor=True)],
                    [record("complete")] * 3):
            with self.subTest(bad=bad):
                transport = ScriptedTransport([run_response(), bad])
                with self.assertRaises(c.PolicyError) as error:
                    c.orchestrate(c.build_plan(BUILD), TOKEN, transport)
                self.assertNotIn(TOKEN, str(error.exception))


class FakeResponse:
    def __init__(self, value):
        self.value = value
        self.read_sizes = []

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def read(self, size):
        self.read_sizes.append(size)
        return self.value[:size]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.response, Exception): raise self.response
        return self.response


class HttpBoundaryTests(unittest.TestCase):
    def test_real_transport_cannot_be_constructed_while_guard_is_closed(self):
        with patch.object(c, "build_opener") as opener:
            with self.assertRaises(c.PolicyError): c.HttpTransport(BUILD)
            opener.assert_not_called()

    def test_route_payload_and_query_tampering_stops_before_opener(self):
        plan = c.build_plan(BUILD)
        start = c.API + "/actors/apify~web-scraper/runs?build=" + BUILD + (
            "&memory=1024&timeout=120&maxTotalChargeUsd=0.10&restartOnError=false")
        bad = [
            ("DELETE", c.API + "/actor-runs/OfflineRunIdentifier", None),
            ("GET", c.API + "/users/me", None),
            ("POST", start.replace("apify~web-scraper", "someone~other"), plan["input"]),
            ("POST", start + "&token=" + TOKEN, plan["input"]),
            ("POST", start + "&webhooks=anything", plan["input"]),
            ("POST", start.replace("memory=1024", "memory=2048"), plan["input"]),
            ("POST", start, dict(plan["input"], maxRequestRetries=1)),
            ("GET", c.API + "/actor-runs/OfflineRunIdentifier?waitForFinish=60&extra=1", None),
            ("GET", c.API + "/datasets/OfflineDatasetIdentifier/items?format=json&limit=3", None),
        ]
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener") as opener:
            transport = c.HttpTransport(BUILD)
            for method, url, payload in bad:
                with self.subTest(method=method, url=url), self.assertRaises(c.PolicyError):
                    transport.request(method, url, payload, TOKEN)
            opener.assert_not_called()

    def test_mock_http_uses_header_auth_and_bounded_reads_without_redirect_or_retry(self):
        response = FakeResponse(json.dumps(run_response()).encode("utf-8"))
        opener = FakeOpener(response)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener) as factory:
            transport = c.HttpTransport(BUILD)
            plan = c.build_plan(BUILD)
            url = c.API + "/actors/apify~web-scraper/runs?build=" + BUILD + (
                "&memory=1024&timeout=120&maxTotalChargeUsd=0.10&restartOnError=false")
            self.assertEqual(transport.request("POST", url, plan["input"], TOKEN), run_response())
            self.assertIsInstance(factory.call_args.args[0], c.NoRedirect)
        self.assertEqual(len(opener.requests), 1)
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, request.full_url)
        self.assertEqual(timeout, 65)
        self.assertEqual(response.read_sizes, [c.RESPONSE_LIMIT + 1])

    def test_http_error_body_and_oversize_response_are_sanitized_without_retry(self):
        provider_error = HTTPError(c.API + "/actor-runs/OfflineRunIdentifier", 500,
                                   TOKEN, {"Authorization": TOKEN}, io.BytesIO(TOKEN.encode()))
        for response in (provider_error, FakeResponse(b"x" * (c.RESPONSE_LIMIT + 1))):
            with self.subTest(response=type(response).__name__):
                opener = FakeOpener(response)
                with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
                    transport = c.HttpTransport(BUILD)
                    with self.assertRaises(c.PolicyError) as error:
                        transport.request("GET", c.API + "/actor-runs/OfflineRunIdentifier?waitForFinish=60", None, TOKEN)
                self.assertEqual(len(opener.requests), 1)
                self.assertNotIn(TOKEN, str(error.exception))
                self.assertNotIn("OfflineRunIdentifier", str(error.exception))

    def test_redirect_is_rejected_without_echoing_destination(self):
        with self.assertRaises(c.PolicyError) as error:
            c.NoRedirect().redirect_request(None, None, 302, TOKEN, {}, "https://example.invalid/" + TOKEN)
        self.assertNotIn(TOKEN, str(error.exception))


if __name__ == "__main__":
    unittest.main()
