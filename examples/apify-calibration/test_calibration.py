"""Offline boundary tests with an HTTP transport double; never provider execution."""
import contextlib
import copy
from datetime import datetime, timezone
from decimal import Decimal
import io
import json
import unittest
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import calibration as c

BUILD = "3.0.123"
COMPLETE = "https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/complete.html"
CHANGED = "https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/changed-layout.html"
TOKEN = "OFFLINE_TEST_SECRET_NEVER_REAL"
CLOSED_TEST_GUARD = {"ready": False, "public_build": None, "review_reference": None,
                     "all_in_upper_bound_usd": None, "retention_policy": None}


class ForbiddenEnvironment:
    def get(self, *args):
        raise AssertionError("environment read before closed cost guard")


def run_response(status="SUCCEEDED"):
    return {"data": {
        "id": "OfflineRunIdentifier", "userId": "OfflineAccountIdentifier",
        "defaultDatasetId": "OfflineDatasetIdentifier", "status": status,
        "defaultKeyValueStoreId": "OfflineKvIdentifier",
        "defaultRequestQueueId": "OfflineQueueIdentifier",
        "actId": "OfflineActorIdentifier",
        "startedAt": "2026-10-02T12:00:00.000Z",
        "finishedAt": "2026-10-02T12:00:30.000Z" if status in ("SUCCEEDED", "FAILED") else None,
        "buildNumber": BUILD,
        "options": {"build": BUILD, "memoryMbytes": 1024, "timeoutSecs": 120,
                    "maxTotalChargeUsd": 0.10},
        "usageTotalUsd": 0.012345, "usage": {"ACTOR_COMPUTE_UNITS": 0.01},
        "usageUsd": {"ACTOR_COMPUTE_UNITS": 0.002}, "chargedEventCounts": {},
        "stats": {"computeUnits": 0.01, "durationMillis": 30000, "restartCount": 0},
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
    def setUp(self):
        guard_patch = patch.object(c, "REVIEWED_GUARD", copy.deepcopy(CLOSED_TEST_GUARD))
        guard_patch.start()
        self.addCleanup(guard_patch.stop)

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
    def setUp(self):
        guard_patch = patch.object(c, "REVIEWED_GUARD", copy.deepcopy(CLOSED_TEST_GUARD))
        guard_patch.start()
        self.addCleanup(guard_patch.stop)

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
    def __init__(self, value, status=200):
        self.value = value
        self.status = status
        self.read_sizes = []
        self.offset = 0

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def read(self, size):
        self.read_sizes.append(size)
        result = self.value[self.offset:self.offset + size]
        self.offset += len(result)
        return result

    def read1(self, size): return self.read(size)

    def getcode(self): return self.status


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.response, Exception): raise self.response
        return self.response


def storage_response(kind):
    ids = {"dataset": "OfflineDatasetIdentifier", "kv": "OfflineKvIdentifier",
           "queue": "OfflineQueueIdentifier"}
    return {"data": {"id": ids[kind], "userId": "OfflineAccountIdentifier", "name": None,
                     "actId": "OfflineActorIdentifier", "actRunId": "OfflineRunIdentifier",
                     "generalAccess": "RESTRICTED", "createdAt": "2026-10-02T12:00:01.000Z",
                     "stats": {"storageBytes": 128, "readCount": 2, "writeCount": 1},
                     "urlSigningSecretKey": TOKEN, "consoleUrl": "https://example.invalid/" + TOKEN}}


class CleanupLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"mode": "cleanup", "upper_bound_hours": "0.25",
                       "review_reference": "OFFLINE_TEST_POLICY", "cleanup_approved": True}
        self.guard = copy.deepcopy(CLOSED_TEST_GUARD)
        self.guard["retention_policy"] = self.policy
        self.guard_patch = patch.object(c, "REVIEWED_GUARD", self.guard)
        self.guard_patch.start()
        self.addCleanup(self.guard_patch.stop)
        actor_patch = patch.object(c, "PUBLIC_ACTOR_ID", "OfflineActorIdentifier")
        actor_patch.start()
        self.addCleanup(actor_patch.stop)

    def replies(self, export=None, status="SUCCEEDED"):
        missing = HTTPError("https://api.apify.com/v2/datasets/OfflineDatasetIdentifier", 404,
                            TOKEN, {}, io.BytesIO(TOKEN.encode()))
        return ([run_response(status)] +
                ([export if export is not None else [record("complete"), record("changed-layout")]]
                 if status == "SUCCEEDED" else []) +
                [storage_response(kind) for kind in ("dataset", "kv", "queue")] +
                [None, None, None, missing, missing, missing])

    def invoke(self, transport):
        # The clock is synthetic. No token environment or provider call is used.
        with patch.object(c, "utc_now", return_value=datetime(2026, 10, 2, 12, 1, tzinfo=timezone.utc), create=True):
            return c.orchestrate(c.build_plan(BUILD), TOKEN, transport, persist=self.persist,
                                 emit=lambda value: self.saved.append(("stdout", copy.deepcopy(value))))

    def persist(self, receipt, phase):
        if not hasattr(self, "saved"): self.saved = []
        self.saved.append((phase, copy.deepcopy(receipt)))
        return c.digest(receipt)

    def test_all_receipts_and_expected_records_precede_three_deletes_then_absence_checks(self):
        transport = ScriptedTransport(self.replies())
        result = self.invoke(transport)
        self.assertEqual([x[0] for x in transport.requests], ["POST"] + ["GET"] * 4 + ["DELETE"] * 3 + ["GET"] * 3)
        self.assertTrue(result["cleanup"]["absence_confirmed"])
        self.assertEqual(result["accepted_output_count"], 2)
        self.assertEqual(result["receipts"]["storage"]["dataset"]["stats"]["storageBytes"], 128)
        self.assertEqual(result["receipts"]["usage"]["ACTOR_COMPUTE_UNITS"], "0.01")
        self.assertEqual(result["request_counts"]["delete"], 3)
        for value in (TOKEN, "OfflineRunIdentifier", "OfflineAccountIdentifier", "OfflineActorIdentifier",
                      "OfflineDatasetIdentifier", "OfflineKvIdentifier", "OfflineQueueIdentifier"):
            self.assertNotIn(value, json.dumps(result))
        self.assertFalse(result["all_in_cost_reconciled"])

    def test_export_and_extraction_failures_still_cleanup_and_keep_sanitized_receipt(self):
        for export in (RuntimeError(TOKEN), [record("complete"), record("complete")]):
            with self.subTest(export=type(export).__name__):
                transport = ScriptedTransport(self.replies(export))
                with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
                self.assertEqual(sum(x[0] == "DELETE" for x in transport.requests), 3)
                self.assertTrue(error.exception.receipt["cleanup"]["absence_confirmed"])
                self.assertNotIn(TOKEN, json.dumps(error.exception.receipt))

    def test_failed_terminal_run_cleans_without_export_or_restart(self):
        transport = ScriptedTransport(self.replies(status="FAILED"))
        with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
        self.assertEqual([x[0] for x in transport.requests], ["POST"] + ["GET"] * 3 + ["DELETE"] * 3 + ["GET"] * 3)
        self.assertEqual(error.exception.receipt["status"], "FAILED")

    def test_metadata_mismatch_means_no_deletion_of_any_store(self):
        for field, value in (("id", "DifferentOfflineIdentifier"), ("userId", "OtherOfflineOwner"),
                             ("name", "shared-or-named"), ("actRunId", None),
                             ("actId", "OtherOfflineActor"),
                             ("createdAt", "2026-10-01T12:00:00Z")):
            with self.subTest(field=field):
                replies = self.replies()
                replies[2]["data"][field] = value
                transport = ScriptedTransport(replies)
                with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
                self.assertTrue(all(x[0] != "DELETE" for x in transport.requests))
                self.assertTrue(error.exception.receipt["cleanup"]["owner_attention_required"])

    def test_one_delete_failure_does_not_stop_independent_stores_and_residual_is_explicit(self):
        replies = self.replies()
        replies[5] = RuntimeError(TOKEN)
        replies[8] = storage_response("dataset")
        transport = ScriptedTransport(replies)
        with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
        self.assertEqual(sum(x[0] == "DELETE" for x in transport.requests), 3)
        self.assertEqual(len(transport.requests), 11)
        receipt = error.exception.receipt
        self.assertFalse(receipt["cleanup"]["absence_confirmed"])
        self.assertTrue(receipt["cleanup"]["owner_attention_required"])
        self.assertFalse(receipt["all_in_cost_reconciled"])
        self.assertNotIn(TOKEN, json.dumps(receipt))

    def test_active_or_ambiguous_polling_never_deletes_or_aborts_and_reports_unknown_cost(self):
        for replies in ([run_response("RUNNING")] * 4,
                        [run_response("RUNNING"), RuntimeError(TOKEN)], [RuntimeError(TOKEN)]):
            with self.subTest(calls=len(replies)):
                transport = ScriptedTransport(replies)
                with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
                self.assertTrue(all(x[0] != "DELETE" and "abort" not in x[1] for x in transport.requests))
                self.assertTrue(error.exception.receipt["cleanup"]["owner_attention_required"])
                self.assertFalse(error.exception.receipt["all_in_cost_reconciled"])
                self.assertLessEqual(len(transport.requests), 4)

    def test_expired_cleanup_deadline_and_missing_approval_do_not_delete(self):
        for mutation in ("expired", "unapproved"):
            with self.subTest(mutation=mutation):
                self.guard["retention_policy"]["cleanup_approved"] = mutation != "unapproved"
                replies = self.replies()
                if mutation == "expired":
                    replies[0]["data"]["startedAt"] = "2026-10-02T11:00:00Z"
                    replies[0]["data"]["finishedAt"] = "2026-10-02T11:00:30Z"
                    for reply in replies[2:5]: reply["data"]["createdAt"] = "2026-10-02T11:00:01Z"
                transport = ScriptedTransport(replies)
                with self.assertRaises(c.PolicyError): self.invoke(transport)
                self.assertTrue(all(x[0] != "DELETE" for x in transport.requests))

    def test_access_setting_is_not_a_substitute_for_ownership_proof(self):
        for mode in ("RESTRICTED", "FOLLOW_USER_SETTING", "ANYONE_WITH_ID_CAN_READ", "ANYONE_WITH_NAME_CAN_READ", None):
            with self.subTest(mode=mode):
                replies = self.replies()
                for reply in replies[2:5]: reply["data"]["generalAccess"] = mode
                self.assertTrue(self.invoke(ScriptedTransport(replies))["cleanup"]["absence_confirmed"])

    def test_wall_deadline_skips_export_but_uses_reserved_cleanup_time(self):
        replies = self.replies()
        del replies[1]
        transport = ScriptedTransport(replies)
        with patch.object(c, "monotonic", side_effect=[0, 0] + [380] * 20):
            with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
        self.assertTrue(error.exception.receipt["wall_budget_exhausted"])
        self.assertEqual(error.exception.receipt["request_counts"]["export"], 0)
        self.assertTrue(error.exception.receipt["cleanup"]["absence_confirmed"])

    def test_wall_deadline_during_active_polling_stops_without_deletion(self):
        transport = ScriptedTransport([run_response("RUNNING")])
        with patch.object(c, "monotonic", side_effect=[0, 0, 400]):
            with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
        self.assertEqual(len(transport.requests), 1)
        self.assertTrue(error.exception.receipt["wall_budget_exhausted"])
        self.assertEqual(error.exception.receipt["status"], "RUNNING")
        self.assertTrue(error.exception.receipt["cleanup"]["owner_attention_required"])

    def test_insufficient_job_time_rejects_before_token_read_or_start(self):
        class DeadlineOnlyEnvironment:
            def get(self, key):
                if key == "APIFY_CALIBRATION_WALL_DEADLINE": return "359.99"
                raise AssertionError("token read with insufficient wall time")
        guard = copy.deepcopy(self.guard)
        guard.update(ready=True, public_build=BUILD, review_reference="OFFLINE_TEST_REVIEW", all_in_upper_bound_usd="0.90")
        transport = ScriptedTransport([])
        with patch.object(c, "REVIEWED_GUARD", guard), patch.object(c, "monotonic", return_value=0):
            with self.assertRaises(c.PolicyError):
                c.execute_live(BUILD, opt_in=True, environ=DeadlineOnlyEnvironment(), transport=transport)
        self.assertEqual(transport.requests, [])

    def test_persistence_verification_and_flushed_capture_precede_deletion(self):
        transport = ScriptedTransport(self.replies())
        original = self.persist
        def checked(receipt, phase):
            if phase == "pre_cleanup":
                self.assertTrue(all(x[0] != "DELETE" for x in transport.requests))
                self.assertEqual(receipt["request_counts"]["metadata"], 3)
                self.assertEqual(receipt["accepted_output_count"], 2)
            return original(receipt, phase)
        self.persist = checked
        result = self.invoke(transport)
        self.assertEqual([phase for phase, _ in self.saved], ["pre_cleanup", "stdout", "final"])
        self.assertTrue(result["pre_cleanup_evidence_verified"])
        self.assertEqual(result["pre_cleanup_capture_sha256"], c.digest(result["pre_cleanup_capture"]))
        self.assertEqual(result["pre_cleanup_capture"]["request_counts"]["delete"], 0)
        self.assertEqual(result["receipts"]["run"]["started_at"], "2026-10-02T12:00:00+00:00")
        self.assertEqual(result["receipts"]["cleanup"]["since_run_started_seconds"], "60.0")

    def test_persistence_failure_or_wrong_hash_blocks_every_delete(self):
        for failure in ("exception", "wrong_hash"):
            with self.subTest(failure=failure):
                transport = ScriptedTransport(self.replies())
                def save(receipt, phase):
                    if failure == "exception": raise OSError(TOKEN)
                    return "invalid_digest"
                self.persist = save
                with self.assertRaises(c.PolicyError) as error: self.invoke(transport)
                self.assertTrue(all(x[0] != "DELETE" for x in transport.requests))
                self.assertEqual(error.exception.receipt["cleanup"]["state"], "evidence_not_durable")
                self.assertTrue(error.exception.receipt["cleanup"]["owner_attention_required"])
                self.assertNotIn(TOKEN, json.dumps(error.exception.receipt))

    def test_final_evidence_is_retained_when_cleanup_fails(self):
        replies = self.replies()
        replies[8] = storage_response("dataset")
        with self.assertRaises(c.PolicyError): self.invoke(ScriptedTransport(replies))
        final = self.saved[-1][1]
        self.assertEqual(self.saved[-1][0], "final")
        self.assertTrue(final["pre_cleanup_evidence_verified"])
        self.assertFalse(final["cleanup"]["absence_confirmed"])
        self.assertTrue(final["cleanup"]["owner_attention_required"])

    def test_maximum_fourteen_calls_and_http_204_404_without_error_body_reads(self):
        missing = [HTTPError(c.API + "/" + route + "/" + run_response()["data"][field],
                             404, TOKEN, {}, io.BytesIO(TOKEN.encode()))
                   for field, route in c.STORE_FIELDS.values()]
        replies = [run_response("RUNNING")] * 3 + [run_response()] + [
            [record("complete"), record("changed-layout")]] + [storage_response(kind) for kind in c.STORE_FIELDS]
        responses = [FakeResponse(json.dumps(value).encode(), 201 if index == 0 else 200)
                     for index, value in enumerate(replies)]
        deleted = [FakeResponse(b"", 204) for _ in range(3)]
        opener = SequenceOpener(responses + deleted + missing)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
            transport = c.HttpTransport(BUILD, meter_wait=lambda _: self.fail("no fourth poll or wait permitted"))
            result = self.invoke(transport)
        self.assertEqual(len(opener.requests), 14)
        self.assertTrue(result["cleanup"]["absence_confirmed"])
        self.assertEqual([timeout for _, timeout in opener.requests], [30] + [65] * 3 + [10] * 10)
        self.assertTrue(all(request.get_header("Authorization") == "Bearer " + TOKEN for request, _ in opener.requests))
        self.assertTrue(all(TOKEN not in request.full_url for request, _ in opener.requests))
        self.assertTrue(all(response.read_sizes == [] for response in deleted))
        self.assertEqual(result["meter_refresh"]["state"], "preliminary_no_poll_slot")

    def test_ready_null_build_binds_initial_scope_then_polls_pinned_terminal_and_cleans(self):
        pending = run_response("READY")
        pending["data"]["buildNumber"] = None
        values = [pending, run_response(), [record("complete"), record("changed-layout")]] + [
            storage_response(kind) for kind in c.STORE_FIELDS]
        replies = [FakeResponse(json.dumps(value).replace('"maxTotalChargeUsd": 0.1',
                                                          '"maxTotalChargeUsd": 0.1000').encode(),
                                201 if index == 0 else 200) for index, value in enumerate(values)]
        replies += [FakeResponse(b"", 204) for _ in range(3)] + [
            HTTPError(c.API + "/" + route + "/" + pending["data"][field],
                      404, TOKEN, {}, io.BytesIO(TOKEN.encode())) for field, route in c.STORE_FIELDS.values()]
        opener = SequenceOpener(replies)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
            transport = c.HttpTransport(BUILD, refresh_terminal_meters=False)
            with patch.object(transport, "bind_run", wraps=transport.bind_run) as binding:
                result = self.invoke(transport)
        self.assertIsNone(transport.initial["buildNumber"])
        self.assertGreaterEqual(binding.call_count, 1)
        self.assertEqual(result["receipts"]["run"]["build_number"], BUILD)
        self.assertTrue(result["cleanup"]["absence_confirmed"])
        self.assertEqual(result["accepted_output_count"], 2)
        self.assertEqual(result["request_counts"], {"start": 1, "poll": 1, "export": 1,
                                                  "metadata": 3, "delete": 3, "absence": 3})
        self.assertEqual(len(opener.requests), 12)

    def meter_responses(self, refresh):
        values = [run_response(), refresh, [record("complete"), record("changed-layout")]] + [
            storage_response(kind) for kind in c.STORE_FIELDS]
        replies = [value if isinstance(value, Exception) else FakeResponse(json.dumps(value).encode(),
                   201 if index == 0 else 200) for index, value in enumerate(values)]
        return replies + [FakeResponse(b"", 204) for _ in range(3)] + [
            HTTPError(c.API + "/" + route + "/" + run_response()["data"][field],
                      404, TOKEN, {}, io.BytesIO(TOKEN.encode())) for field, route in c.STORE_FIELDS.values()]

    def test_meter_refresh_waits_once_then_replaces_only_verified_terminal_meters(self):
        refreshed = run_response()
        refreshed["data"]["usageTotalUsd"] = 0.025
        opener, waits = SequenceOpener(self.meter_responses(refreshed)), []
        def wait(seconds):
            self.assertEqual(len(opener.requests), 1)
            waits.append(seconds)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
            result = self.invoke(c.HttpTransport(BUILD, meter_wait=wait))
        self.assertEqual(waits, [10])
        self.assertEqual(result["meter_refresh"], {"state": "refreshed_after_wait", "capture_wait_seconds": 10,
                                                 "preliminary": False, "invoice_final": False, "diagnostic": None})
        self.assertEqual(result["receipts"]["run"]["usage_total_usd"], "0.025")
        self.assertEqual(result["pre_cleanup_capture"]["meter_refresh"], result["meter_refresh"])
        self.assertEqual(result["request_counts"]["poll"], 1)
        self.assertTrue(result["cleanup"]["absence_confirmed"])
        self.assertEqual(len(opener.requests), 12)

    def test_meter_refresh_failure_preserves_confirmed_terminal_for_cleanup(self):
        for mutation in ("connection", "http", "id", "userId", "actId", "defaultDatasetId",
                         "defaultKeyValueStoreId", "defaultRequestQueueId", "terminal_status", "build", "options"):
            with self.subTest(mutation=mutation):
                reply = run_response()
                if mutation == "connection": reply = URLError(TOKEN + " private provider message")
                elif mutation == "http": reply = HTTPError(c.API + "/" + TOKEN, 403, TOKEN,
                                                            {"Authorization": TOKEN}, io.BytesIO(TOKEN.encode()))
                elif mutation == "terminal_status": reply["data"]["status"] = "FAILED"
                elif mutation == "build": reply["data"]["buildNumber"] = "3.0.124"
                elif mutation == "options": reply["data"]["options"]["maxTotalChargeUsd"] = 0.2
                else: reply["data"][mutation] = "DifferentScopeValue"
                opener, waits = SequenceOpener(self.meter_responses(reply)), []
                with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
                    transport = c.HttpTransport(BUILD, meter_wait=waits.append)
                    result = self.invoke(transport)
                self.assertEqual(waits, [10])
                self.assertEqual(result["status"], "SUCCEEDED")
                self.assertEqual(transport.last_run["status"], "SUCCEEDED")
                self.assertEqual(result["receipts"]["run"]["usage_total_usd"], "0.012345")
                self.assertEqual(result["meter_refresh"]["state"], "preliminary_refresh_failed")
                self.assertTrue(result["meter_refresh"]["preliminary"])
                self.assertFalse(result["meter_refresh"]["invoice_final"])
                self.assertIsNotNone(result["meter_refresh"]["diagnostic"])
                self.assertTrue(result["cleanup"]["absence_confirmed"])
                self.assertEqual(result["request_counts"]["poll"], 1)
                self.assertEqual(len(opener.requests), 12)
                for private in (TOKEN, "OfflineRunIdentifier", "OfflineAccountIdentifier", "DifferentScopeValue"):
                    self.assertNotIn(private, json.dumps(result))

    def test_meter_refresh_latest_active_run_stops_export_and_all_cleanup(self):
        for status in ("READY", "RUNNING", "TIMING-OUT", "ABORTING"):
            for build_number in (BUILD, None):
                with self.subTest(status=status, build_number=build_number):
                    active = run_response(status)
                    active["data"]["buildNumber"] = build_number
                    active["data"]["usageTotalUsd"] = 0.099
                    opener, waits = SequenceOpener(self.meter_responses(active)), []
                    self.saved = []
                    with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
                        transport = c.HttpTransport(BUILD, meter_wait=waits.append)
                        with self.assertRaises(c.CalibrationFailure) as error:
                            self.invoke(transport)
                        with self.assertRaises(c.PolicyError):
                            transport.authorize_cleanup(transport.initial, run_response()["data"], {})
                    result = error.exception.receipt
                    self.assertEqual(result["status"], status)
                    self.assertEqual(transport.last_run["status"], "SUCCEEDED")
                    self.assertEqual(transport.latest_active_status, status)
                    self.assertEqual(waits, [10])
                    self.assertEqual(len(opener.requests), 2)
                    self.assertEqual(result["request_counts"], {"start": 1, "poll": 1, "export": 0,
                                                               "metadata": 0, "delete": 0, "absence": 0})
                    self.assertEqual(result["cleanup"]["state"], "latest_run_active")
                    self.assertTrue(result["cleanup"]["owner_attention_required"])
                    self.assertFalse(result["cleanup"]["absence_confirmed"])
                    self.assertEqual(result["meter_refresh"]["state"], "preliminary_latest_active")
                    self.assertTrue(result["meter_refresh"]["preliminary"])
                    self.assertFalse(result["meter_refresh"]["invoice_final"])
                    self.assertEqual(result["failure_diagnostic"], {"operation": "poll", "http_status": 200,
                        "category": "latest_run_active", "stage": "run_validation", "run_status": status})
                    self.assertEqual(result["extraction_outcome"], "not_attempted")
                    self.assertEqual(result["accepted_output_count"], 0)
                    self.assertIsNone(result["receipts"]["run"])
                    historical = result["historical_terminal_capture"]
                    self.assertEqual(historical["status"], "SUCCEEDED")
                    self.assertTrue(historical["preliminary"])
                    self.assertFalse(historical["invoice_final"])
                    self.assertEqual(historical["receipts"]["run"]["usage_total_usd"], "0.012345")
                    self.assertIsNone(result["pre_cleanup_capture"])
                    self.assertEqual([phase for phase, _ in self.saved], ["final"])
                    self.assertEqual(self.saved[0][1]["cleanup"]["state"], "latest_run_active")
                    for private in (TOKEN, "OfflineRunIdentifier", "OfflineAccountIdentifier", "OfflineActorIdentifier"):
                        self.assertNotIn(private, json.dumps(result))

    def test_meter_refresh_latest_active_mock_also_stops_without_cleanup(self):
        transport = ScriptedTransport([run_response(), run_response("RUNNING")] + self.replies()[1:])
        transport.refresh_terminal_meters, waits = True, []
        transport.meter_wait = waits.append
        with self.assertRaises(c.CalibrationFailure) as error:
            self.invoke(transport)
        result = error.exception.receipt
        self.assertEqual(result["status"], "RUNNING")
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(result["request_counts"]["delete"], 0)
        self.assertEqual(result["cleanup"]["state"], "latest_run_active")
        self.assertEqual(result["meter_refresh"]["diagnostic"]["run_status"], "RUNNING")
        self.assertEqual(result["historical_terminal_capture"]["receipts"]["run"]["usage_total_usd"], "0.012345")

    def conflicting_active(self, mutation):
        response = run_response("RUNNING")
        data = response["data"]
        if mutation == "build": data["buildNumber"] = "3.0.124"
        elif mutation == "cap": data["options"]["maxTotalChargeUsd"] = 0.2
        elif mutation == "missing_options": data.pop("options")
        elif mutation == "missing_owner": data.pop("userId")
        else: data[mutation] = TOKEN
        return response

    def test_active_original_id_with_conflicting_fields_revokes_http_cleanup(self):
        for mutation in ("build", "cap", "missing_options", "missing_owner", "userId", "actId",
                         "defaultDatasetId", "defaultKeyValueStoreId", "defaultRequestQueueId"):
            with self.subTest(mutation=mutation):
                opener = SequenceOpener(self.meter_responses(self.conflicting_active(mutation)))
                self.saved = []
                with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
                    transport = c.HttpTransport(BUILD, meter_wait=lambda _: None)
                    with self.assertRaises(c.CalibrationFailure) as error:
                        self.invoke(transport)
                    for method, route in (("GET", "/datasets/OfflineDatasetIdentifier/items?format=json&limit=2&fields=fixture%2Csku%2Cname%2Cprice_minor%2Ccurrency"),
                                          ("GET", "/datasets/OfflineDatasetIdentifier"),
                                          ("DELETE", "/datasets/OfflineDatasetIdentifier"),
                                          ("GET", "/actor-runs/OfflineRunIdentifier?waitForFinish=60")):
                        with self.assertRaises(c.PolicyError):
                            transport.request(method, c.API + route, None, TOKEN)
                result = error.exception.receipt
                self.assertEqual(result["status"], "RUNNING")
                self.assertEqual(result["cleanup"]["state"], "latest_run_active")
                self.assertTrue(result["cleanup"]["owner_attention_required"])
                self.assertEqual(result["request_counts"], {"start": 1, "poll": 1, "export": 0,
                                                           "metadata": 0, "delete": 0, "absence": 0})
                self.assertEqual(result["meter_refresh"]["diagnostic"]["category"], "latest_run_active")
                self.assertEqual(result["historical_terminal_capture"]["receipts"]["run"]["usage_total_usd"], "0.012345")
                self.assertIsNone(result["receipts"]["run"])
                self.assertEqual([phase for phase, _ in self.saved], ["final"])
                self.assertEqual(len(opener.requests), 2)
                for private in (TOKEN, "OfflineRunIdentifier", "OfflineAccountIdentifier"):
                    self.assertNotIn(private, json.dumps(result))

    def test_active_original_id_with_conflicting_fields_revokes_mock_cleanup(self):
        for mutation in ("build", "cap", "missing_options", "missing_owner", "userId", "actId",
                         "defaultDatasetId", "defaultKeyValueStoreId", "defaultRequestQueueId"):
            with self.subTest(mutation=mutation):
                transport = ScriptedTransport([run_response(), self.conflicting_active(mutation)] + self.replies()[1:])
                transport.refresh_terminal_meters = True
                transport.meter_wait = lambda _: None
                with self.assertRaises(c.CalibrationFailure) as error:
                    self.invoke(transport)
                result = error.exception.receipt
                self.assertEqual(result["status"], "RUNNING")
                self.assertEqual(result["cleanup"]["state"], "latest_run_active")
                self.assertEqual(result["request_counts"]["delete"], 0)
                self.assertEqual(result["request_counts"]["metadata"], 0)
                self.assertEqual(len(transport.requests), 2)
                self.assertNotIn(TOKEN, json.dumps(result))

    def test_conflicting_active_observation_revokes_previously_granted_deletion(self):
        values = [run_response()] + [storage_response(kind) for kind in c.STORE_FIELDS] + [self.conflicting_active("build")]
        opener = SequenceOpener([FakeResponse(json.dumps(value).encode(), 201 if index == 0 else 200)
                                 for index, value in enumerate(values)] + [FakeResponse(b"", 204)])
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener), \
                patch.object(c, "utc_now", return_value=datetime(2026, 10, 2, 12, 1, tzinfo=timezone.utc)):
            transport = c.HttpTransport(BUILD, meter_wait=lambda _: None)
            plan = c.build_plan(BUILD)
            transport.request("POST", c.API + "/actors/apify~web-scraper/runs?" + c.urlencode(plan["options"]), plan["input"], TOKEN)
            metadata = {kind: transport.request("GET", c.API + "/" + route + "/" + transport.initial[field], None, TOKEN)["data"]
                        for kind, (field, route) in c.STORE_FIELDS.items()}
            transport.authorize_cleanup(transport.initial, transport.last_run, metadata)
            with self.assertRaises(c.DiagnosticError) as error:
                transport.request("GET", c.API + "/actor-runs/OfflineRunIdentifier?waitForFinish=60", None, TOKEN)
            self.assertEqual(error.exception.diagnostic["category"], "latest_run_active")
            with self.assertRaises(c.PolicyError):
                transport.authorize_cleanup(transport.initial, transport.last_run, metadata)
            with self.assertRaises(c.PolicyError):
                transport.request("DELETE", c.API + "/datasets/OfflineDatasetIdentifier", None, TOKEN)
        self.assertEqual(len(opener.requests), 5)

    def test_meter_refresh_skips_wait_and_read_when_no_slot_or_reserved_time(self):
        for remaining in (174, 175):
            with self.subTest(remaining=remaining):
                refreshed = run_response()
                replies = self.meter_responses(refreshed)
                if remaining == 174: replies.pop(1)
                opener, waits, clock = SequenceOpener(replies), [], [0]
                def wait(seconds):
                    self.assertEqual(seconds, 10)
                    waits.append(seconds)
                    clock[0] += seconds
                with patch.object(c, "monotonic", side_effect=lambda: clock[0]), patch.object(c, "require_readiness"), \
                        patch.object(c, "build_opener", return_value=opener):
                    transport = c.HttpTransport(BUILD, meter_wait=wait)
                    real_request = transport.request
                    def request(method, url, payload, token):
                        reply = real_request(method, url, payload, token)
                        if method == "POST": clock[0] = 480 - remaining
                        return reply
                    with patch.object(transport, "request", side_effect=request):
                        result = self.invoke(transport)
                self.assertEqual(waits, [] if remaining == 174 else [10])
                self.assertEqual(result["meter_refresh"]["state"], "preliminary_insufficient_time"
                                 if remaining == 174 else "refreshed_after_wait")
                self.assertTrue(result["cleanup"]["absence_confirmed"])

    def test_meter_refresh_rechecks_deadline_after_wait_and_preserves_cleanup(self):
        replies = self.meter_responses(run_response())
        replies.pop(1)
        opener, clock = SequenceOpener(replies), [0]
        with patch.object(c, "monotonic", side_effect=lambda: clock[0]), patch.object(c, "require_readiness"), \
                patch.object(c, "build_opener", return_value=opener):
            def wait(seconds): clock[0] += seconds + 1
            transport = c.HttpTransport(BUILD, meter_wait=wait)
            real_request = transport.request
            def request(method, url, payload, token):
                reply = real_request(method, url, payload, token)
                if method == "POST": clock[0] = 305
                return reply
            with patch.object(transport, "request", side_effect=request):
                result = self.invoke(transport)
        self.assertEqual(result["meter_refresh"]["state"], "preliminary_refresh_failed")
        self.assertEqual(result["meter_refresh"]["diagnostic"]["category"], "deadline_exceeded")
        self.assertEqual(result["request_counts"]["poll"], 0)
        self.assertEqual(len(opener.requests), 11)
        self.assertTrue(result["cleanup"]["absence_confirmed"])

    def test_meter_refresh_wait_failure_never_reads_or_loses_terminal_cleanup_scope(self):
        replies = self.meter_responses(run_response())
        replies.pop(1)
        opener = SequenceOpener(replies)
        def wait(seconds): raise RuntimeError(TOKEN)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
            result = self.invoke(c.HttpTransport(BUILD, meter_wait=wait))
        self.assertEqual(result["meter_refresh"]["state"], "preliminary_refresh_failed")
        self.assertEqual(result["meter_refresh"]["capture_wait_seconds"], 0)
        self.assertEqual(result["request_counts"]["poll"], 0)
        self.assertTrue(result["cleanup"]["absence_confirmed"])
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_real_transport_deletion_requires_verified_terminal_scope_and_fixed_host(self):
        opener = SequenceOpener([FakeResponse(json.dumps(run_response("RUNNING")).encode(), 201)])
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
            transport = c.HttpTransport(BUILD)
            plan = c.build_plan(BUILD)
            url = c.API + "/actors/apify~web-scraper/runs?" + c.urlencode(plan["options"])
            transport.request("POST", url, plan["input"], TOKEN)
            for url in (c.API + "/datasets/OfflineDatasetIdentifier", c.API + "/datasets/OtherOfflineIdentifier",
                        "https://example.invalid/v2/datasets/OfflineDatasetIdentifier"):
                with self.subTest(url=url), self.assertRaises(c.PolicyError):
                    transport.request("DELETE", url, None, TOKEN)
        self.assertEqual(len(opener.requests), 1)


class SequenceOpener:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception): raise reply
        return reply


class HttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        guard_patch = patch.object(c, "REVIEWED_GUARD", copy.deepcopy(CLOSED_TEST_GUARD))
        guard_patch.start()
        self.addCleanup(guard_patch.stop)
        actor_patch = patch.object(c, "PUBLIC_ACTOR_ID", "OfflineActorIdentifier")
        actor_patch.start()
        self.addCleanup(actor_patch.stop)

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
        response = FakeResponse(json.dumps(run_response()).encode("utf-8"), 201)
        opener = FakeOpener(response)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener) as factory:
            transport = c.HttpTransport(BUILD)
            plan = c.build_plan(BUILD)
            url = c.API + "/actors/apify~web-scraper/runs?build=" + BUILD + (
                "&memory=1024&timeout=120&maxTotalChargeUsd=0.10&restartOnError=false")
            reply = transport.request("POST", url, plan["input"], TOKEN)
            self.assertEqual(reply["data"]["buildNumber"], BUILD)
            self.assertEqual(reply["data"]["usageTotalUsd"], Decimal("0.012345"))
            self.assertIsInstance(factory.call_args.args[0], c.NoRedirect)
        self.assertEqual(len(opener.requests), 1)
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, request.full_url)
        self.assertEqual(timeout, 30)
        self.assertTrue(all(size <= 65536 for size in response.read_sizes))
        self.assertEqual(response.offset, len(response.value))

    def test_http_error_body_and_oversize_response_are_sanitized_without_retry(self):
        provider_error = HTTPError(c.API + "/actor-runs/OfflineRunIdentifier", 500,
                                   TOKEN, {"Authorization": TOKEN}, io.BytesIO(TOKEN.encode()))
        for response in (provider_error, FakeResponse(b"x" * (c.RESPONSE_LIMIT + 1), 201)):
            with self.subTest(response=type(response).__name__):
                opener = FakeOpener(response)
                with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
                    transport = c.HttpTransport(BUILD)
                    with self.assertRaises(c.PolicyError) as error:
                        plan = c.build_plan(BUILD)
                        transport.request("POST", c.API + "/actors/apify~web-scraper/runs?" + c.urlencode(plan["options"]), plan["input"], TOKEN)
                self.assertEqual(len(opener.requests), 1)
                self.assertNotIn(TOKEN, str(error.exception))
                self.assertNotIn("OfflineRunIdentifier", str(error.exception))

    def test_redirect_is_rejected_without_echoing_destination(self):
        with self.assertRaises(c.PolicyError) as error:
            c.NoRedirect().redirect_request(None, None, 302, TOKEN, {}, "https://example.invalid/" + TOKEN)
        self.assertNotIn(TOKEN, str(error.exception))

    def test_response_reader_checks_deadline_between_chunks(self):
        response = FakeResponse(b"x" * 100000)
        with patch.object(c, "monotonic", side_effect=[0, 2]), self.assertRaises(c.WallDeadline):
            c.read_bounded(response, deadline=1)
        self.assertEqual(response.read_sizes, [65536])


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("REVIEWED_GUARD", copy.deepcopy(CLOSED_TEST_GUARD)),
                            ("PUBLIC_ACTOR_ID", "OfflineActorIdentifier")):
            changed = patch.object(c, name, value)
            changed.start()
            self.addCleanup(changed.stop)

    def failure(self, replies):
        opener, saved = SequenceOpener(replies), []
        def persist(receipt, phase):
            saved.append(copy.deepcopy(receipt))
            return c.digest(receipt)
        with patch.object(c, "require_readiness"), patch.object(c, "build_opener", return_value=opener):
            with self.assertRaises(c.CalibrationFailure) as error:
                c.orchestrate(c.build_plan(BUILD), TOKEN, c.HttpTransport(BUILD), persist=persist)
        receipt = error.exception.receipt
        self.assertEqual(receipt["request_counts"]["start"], 1)
        for kind in ("export", "metadata", "delete", "absence"):
            self.assertEqual(receipt["request_counts"][kind], 0)
        self.assertEqual(len(opener.requests), 1 + receipt["request_counts"]["poll"])
        self.assertEqual(saved[-1]["failure_diagnostic"], receipt["failure_diagnostic"])
        serialized = json.dumps(receipt) + str(error.exception)
        for private in (TOKEN, "OfflineRunIdentifier", "OfflineAccountIdentifier",
                        "OfflineDatasetIdentifier", "OfflineKvIdentifier", "OfflineQueueIdentifier",
                        "https://example.invalid", "Authorization", "private provider"):
            self.assertNotIn(private, serialized)
        return receipt

    def test_http_rejections_retain_only_numeric_status_and_fixed_category(self):
        for status in (401, 403, 400):
            with self.subTest(status=status):
                error = HTTPError("https://example.invalid/" + TOKEN, status, TOKEN,
                                  {"Authorization": TOKEN}, io.BytesIO(TOKEN.encode()))
                receipt = self.failure([error])
                self.assertEqual(receipt["failure_diagnostic"], {
                    "operation": "start", "http_status": status, "category": "http_error",
                    "stage": "response_status", "run_status": None})
                self.assertEqual(receipt["status"], "UNKNOWN")
                self.assertIsNone(receipt["receipts"]["run"])

    def test_successful_http_status_survives_bounded_read_and_json_failures(self):
        for body, category, stage in ((b"x" * (c.RESPONSE_LIMIT + 1), "response_too_large", "response_read"),
                                      (TOKEN.encode(), "invalid_json", "json_decode"),
                                      (b"\xff" + TOKEN.encode(), "invalid_json", "json_decode")):
            with self.subTest(category=category, body_length=len(body)):
                receipt = self.failure([FakeResponse(body, 201)])
                self.assertEqual(receipt["failure_diagnostic"], {
                    "operation": "start", "http_status": 201, "category": category,
                    "stage": stage, "run_status": None})

    def test_build_options_and_identifier_validation_have_distinct_stages(self):
        for field, value, category, stage in (
                ("buildNumber", TOKEN, "build_mismatch", "build_validation"),
                ("memoryMbytes", 2048, "options_mismatch", "options_validation"),
                ("id", TOKEN + "/", "invalid_identifier", "identifier_validation"),
                ("userId", None, "invalid_identifier", "identifier_validation"),
                ("actId", "DifferentPublicActor", "scope_mismatch", "scope_validation")):
            with self.subTest(field=field):
                response = run_response()
                target = response["data"]["options"] if field == "memoryMbytes" else response["data"]
                target[field] = value
                receipt = self.failure([FakeResponse(json.dumps(response).encode(), 201)])
                self.assertEqual(receipt["failure_diagnostic"], {
                    "operation": "start", "http_status": 201, "category": category,
                    "stage": stage, "run_status": "SUCCEEDED"})

    def test_invalid_response_and_run_status_do_not_copy_untrusted_values(self):
        for response, category in (({"data": None}, "invalid_response"),
                                   (dict(run_response(), data={"status": TOKEN}), "invalid_run_status")):
            with self.subTest(category=category):
                receipt = self.failure([FakeResponse(json.dumps(response).encode(), 201)])
                self.assertEqual(receipt["failure_diagnostic"], {
                    "operation": "start", "http_status": 201, "category": category,
                    "stage": "run_validation", "run_status": None})

    def test_unexpected_success_status_is_distinct_from_connection_failure(self):
        for response, status, category, stage in (
                (FakeResponse(TOKEN.encode(), 202), 202, "unexpected_http_status", "response_status"),
                (URLError(TOKEN + " private provider message"), None, "connection_error", "request"),
                (RuntimeError(TOKEN + " private provider message"), None, "transport_error", "request")):
            with self.subTest(category=category):
                receipt = self.failure([response])
                self.assertEqual(receipt["failure_diagnostic"], {
                    "operation": "start", "http_status": status, "category": category,
                    "stage": stage, "run_status": None})

    def test_poll_failure_keeps_current_status_without_reusing_start_http_status(self):
        for reply, http_status, category, stage, run_status in (
                (URLError(TOKEN), None, "connection_error", "request", None),
                (HTTPError(c.API, 403, TOKEN, {}, io.BytesIO(TOKEN.encode())),
                 403, "http_error", "response_status", None)):
            with self.subTest(category=category):
                receipt = self.failure([FakeResponse(json.dumps(run_response("RUNNING")).encode(), 201), reply])
                self.assertEqual(receipt["status"], "RUNNING")
                self.assertEqual(receipt["failure_diagnostic"], {
                    "operation": "poll", "http_status": http_status, "category": category,
                    "stage": stage, "run_status": run_status})

    def test_successful_poll_http_status_survives_local_scope_validation(self):
        changed = run_response()
        changed["data"]["userId"] = "DifferentOwner"
        receipt = self.failure([FakeResponse(json.dumps(run_response("RUNNING")).encode(), 201),
                                FakeResponse(json.dumps(changed).encode(), 200)])
        self.assertEqual(receipt["failure_diagnostic"], {
            "operation": "poll", "http_status": 200, "category": "scope_mismatch",
            "stage": "scope_validation", "run_status": "SUCCEEDED"})

    def test_unresolved_terminal_build_never_exports_or_deletes(self):
        for status in c.TERMINAL:
            for in_poll in (False, True):
                with self.subTest(status=status, in_poll=in_poll):
                    terminal = run_response(status)
                    terminal["data"]["buildNumber"] = None
                    replies = ([FakeResponse(json.dumps(run_response("RUNNING")).encode(), 201)]
                               if in_poll else [])
                    replies.append(FakeResponse(json.dumps(terminal).encode(), 200 if in_poll else 201))
                    receipt = self.failure(replies)
                    self.assertEqual(receipt["failure_diagnostic"]["category"], "build_mismatch")


class RunSchemaTests(unittest.TestCase):
    def test_numeric_equivalence_preserves_exact_effective_limits(self):
        for literal in ("0.1", "0.10", "0.1000", "1e-1"):
            with self.subTest(literal=literal):
                encoded = json.dumps(run_response()).replace('"maxTotalChargeUsd": 0.1',
                                                              '"maxTotalChargeUsd": ' + literal)
                response = json.loads(encoded, parse_float=Decimal)
                self.assertEqual(c.validate_run(response, BUILD)["options"]["maxTotalChargeUsd"], Decimal("0.10"))

    def test_non_numeric_nonfinite_negative_missing_or_wrong_limit_rejected(self):
        for value in (None, True, False, Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1"),
                      "0.1", Decimal("0.1001"), Decimal("0.09")):
            with self.subTest(value=str(value)):
                response = run_response()
                response["data"]["options"]["maxTotalChargeUsd"] = value
                with self.assertRaises(c.PolicyError): c.validate_run(response, BUILD)
        response = run_response()
        del response["data"]["options"]["maxTotalChargeUsd"]
        with self.assertRaises(c.PolicyError): c.validate_run(response, BUILD)

    def test_null_build_allowed_only_nonterminal_and_wrong_nonnull_never_allowed(self):
        for status in c.RUN_STATUSES:
            for build_number in (None, "3.0.124", "latest", False):
                with self.subTest(status=status, build_number=build_number):
                    response = run_response(status)
                    response["data"]["buildNumber"] = build_number
                    if build_number is None and status not in c.TERMINAL:
                        c.validate_run(response, BUILD)
                    else:
                        with self.assertRaises(c.PolicyError): c.validate_run(response, BUILD)

    def test_pending_run_still_requires_pinned_options_build_and_safe_original_identity(self):
        for value in (None, "latest", "3.0.124"):
            with self.subTest(options_build=value):
                response = run_response("READY")
                response["data"]["buildNumber"] = None
                response["data"]["options"]["build"] = value
                with self.assertRaises(c.PolicyError): c.validate_run(response, BUILD)
        for field in ("id", "userId", "actId", "defaultDatasetId", "defaultKeyValueStoreId", "defaultRequestQueueId"):
            with self.subTest(field=field):
                response = run_response("READY")
                response["data"]["buildNumber"] = None
                response["data"][field] = TOKEN + "/"
                with patch.object(c, "PUBLIC_ACTOR_ID", "OfflineActorIdentifier"), self.assertRaises(c.PolicyError):
                    c.verify_initial_references(c.validate_run(response, BUILD))


class EvidencePersistenceTests(unittest.TestCase):
    def test_atomic_fixed_file_fsync_and_exact_readback_digest(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                receipt = {"evidence_type": "offline_synthetic_test", "records": [], "all_in_cost_reconciled": False}
                with patch.object(c.os, "fsync", wraps=c.os.fsync) as sync:
                    checksum = c.persist_receipt_atomic(receipt, "pre_cleanup")
                self.assertEqual(checksum, c.digest(receipt))
                self.assertEqual(Path("calibration-receipt.json").read_bytes(), c.canonical_bytes(receipt))
                self.assertEqual(sync.call_count, 2)
                self.assertEqual(list(Path(directory).iterdir()), [Path(directory) / "calibration-receipt.json"])
                with patch.object(c.Path, "read_bytes", return_value=b"mismatch"), self.assertRaises(c.PolicyError):
                    c.persist_receipt_atomic(receipt, "final")
            finally:
                os.chdir(previous)

    def test_receipt_stdout_is_flushed(self):
        with patch("builtins.print") as output:
            c.emit_receipt({"phase": "offline_synthetic_test", "records": []})
        self.assertTrue(output.call_args.kwargs["flush"])


if __name__ == "__main__":
    unittest.main()
