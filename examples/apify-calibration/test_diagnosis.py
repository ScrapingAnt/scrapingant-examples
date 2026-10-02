"""Offline rejection and sanitization tests; no provider calls."""
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import diagnosis as d
from calibration import build_plan, PUBLIC_ACTOR_ID


class Fake:
    def __init__(self):
        self.calls = []
        self.identity = {"data": {"id": "fakeUser123", "username": "SENSITIVE_IDENTITY",
                                   "email": "SENSITIVE_EMAIL", "proxy": {"password": "SENSITIVE_PASSWORD"}}}
        self.run = {"id": "fakeRun123", "actId": PUBLIC_ACTOR_ID, "userId": "fakeUser123",
                    "buildNumber": d.BUILD, "startedAt": "2026-10-02T14:10:50.500Z",
                    "defaultKeyValueStoreId": "fakeKv123", "status": "SUCCEEDED",
                    "options": {"build": d.BUILD, "memoryMbytes": 1024, "timeoutSecs": 120,
                                "maxTotalChargeUsd": 0.1, "restartOnError": False}}
        self.listing = {"data": {"offset": 0, "limit": 5, "count": 1, "total": 1,
                                  "items": [deepcopy(self.run)]}}
        self.input = build_plan(d.BUILD)["input"]
        self.failure = None

    def get(self, stage, *, run_id=None, kv_id=None):
        self.calls.append(stage)
        if self.failure == stage: raise d.ReadFailure(403, "forbidden")
        return {"identity": self.identity, "runs": self.listing,
                "run": {"data": self.run}, "input": self.input}[stage]


class DiagnosisTests(unittest.TestCase):
    def test_exact_match_uses_four_reads_and_emits_no_private_values(self):
        fake = Fake(); result = d.diagnose(fake)
        self.assertTrue(result["exact_attempt_match"])
        self.assertTrue(result["run_token_identity_match"])
        self.assertIsNone(result["console_token_identity_match"])
        self.assertEqual(fake.calls, ["identity", "runs", "run", "input"])
        self.assertEqual(result["requests_attempted"], 4)
        for value in ("fakeRun123", "fakeUser123", "fakeKv123", "SENSITIVE_IDENTITY", "SENSITIVE_EMAIL", "SENSITIVE_PASSWORD"):
            self.assertNotIn(value, json.dumps(result))

    def test_empty_complete_list_is_no_match(self):
        fake = Fake(); fake.listing["data"].update(items=[], total=0, count=0)
        result = d.diagnose(fake)
        self.assertFalse(result["exact_attempt_match"])
        self.assertEqual(fake.calls, ["identity", "runs"])

    def test_identity_failure_stops_without_listing(self):
        fake = Fake(); fake.failure = "identity"
        result = d.diagnose(fake)
        self.assertIsNone(result["exact_attempt_match"])
        self.assertEqual(result["reads"], [{"stage": "identity", "http_status": 403, "category": "forbidden"}])
        self.assertEqual(fake.calls, ["identity"])

    def test_identity_missing_id_stops(self):
        fake = Fake(); del fake.identity["data"]["id"]
        self.assertEqual(d.diagnose(fake)["outcome"], "identity_invalid")
        self.assertEqual(fake.calls, ["identity"])

    def test_listing_failure_keeps_creation_unknown(self):
        fake = Fake(); fake.failure = "runs"
        self.assertIsNone(d.diagnose(fake)["exact_attempt_match"])

    def test_truncated_listing_is_unknown(self):
        fake = Fake(); fake.listing["data"]["total"] = 6
        self.assertEqual(d.diagnose(fake)["outcome"], "listing_incomplete")
        self.assertEqual(fake.calls, ["identity", "runs"])

    def test_ambiguous_candidates_are_not_followed(self):
        fake = Fake(); other=deepcopy(fake.run); other["id"]="fakeRun456"
        fake.listing["data"].update(items=[fake.run, other], count=2, total=2)
        self.assertEqual(d.diagnose(fake)["outcome"], "multiple_candidates")
        self.assertEqual(len(fake.calls), 2)

    def test_listing_wrong_actor_build_time_never_follows(self):
        for field, value in [("actId", "otherActor"), ("buildNumber", "3.0.26"),
                             ("startedAt", "2026-10-02T14:10:39Z"),
                             ("startedAt", "2026-10-02T14:11:01Z")]:
            with self.subTest(field=field, value=value):
                fake=Fake(); fake.listing["data"]["items"][0][field]=value
                self.assertFalse(d.diagnose(fake)["exact_attempt_match"])
                self.assertEqual(len(fake.calls), 2)

    def test_malformed_listing_rejected(self):
        for change in [{"offset": 1}, {"count": 0}, {"total": True}, {"limit": 1000}, {"items": "bad"}]:
            with self.subTest(change=change):
                fake=Fake(); fake.listing["data"].update(change)
                self.assertEqual(d.diagnose(fake)["outcome"], "listing_invalid")

    def test_run_reference_changes_are_not_followed(self):
        for field, value in [("id", "otherRun"), ("actId", "otherActor"),
                             ("userId", "otherUser"), ("buildNumber", "3.0.26"),
                             ("startedAt", "2026-10-02T14:11:01Z"),
                             ("defaultKeyValueStoreId", "../bad")]:
            with self.subTest(field=field):
                fake=Fake(); fake.run[field]=value
                self.assertEqual(d.diagnose(fake)["outcome"], "candidate_invalid")
                self.assertEqual(len(fake.calls), 3)

    def test_run_options_each_rejected(self):
        for field, value in [("build", "latest"), ("memoryMbytes", True), ("memoryMbytes", 2048),
                             ("timeoutSecs", 121), ("maxTotalChargeUsd", None),
                             ("maxTotalChargeUsd", 1), ("restartOnError", True)]:
            with self.subTest(field=field, value=value):
                fake=Fake(); fake.run["options"][field]=value
                self.assertEqual(d.diagnose(fake)["outcome"], "candidate_invalid")
                self.assertEqual(len(fake.calls), 3)

    def test_undocumented_restart_response_field_may_be_absent(self):
        fake=Fake(); del fake.run["options"]["restartOnError"]
        self.assertTrue(d.diagnose(fake)["exact_attempt_match"])

    def test_known_foreign_list_candidate_not_followed(self):
        fake=Fake(); fake.listing["data"]["items"][0]["userId"]="otherUser"
        result=d.diagnose(fake)
        self.assertEqual(result["outcome"],"candidate_owner_mismatch")
        self.assertFalse(result["run_token_identity_match"])
        self.assertEqual(len(fake.calls),2)

    def test_changed_kv_reference_not_followed(self):
        fake=Fake(); fake.run["defaultKeyValueStoreId"]="otherKv"
        self.assertEqual(d.diagnose(fake)["outcome"],"candidate_invalid")
        self.assertEqual(len(fake.calls),3)

    def test_input_exact_equality_including_no_extra_keys(self):
        for mutation in [lambda i: i.update(extra=True), lambda i: i.update(maxRequestRetries=1),
                         lambda i: i["startUrls"][0].update(url="https://example.com"),
                         lambda i: i.update(pageFunction="different"), lambda i: i.update(maxConcurrency=True)]:
            fake=Fake(); mutation(fake.input)
            self.assertFalse(d.diagnose(fake)["exact_attempt_match"])
            self.assertEqual(len(fake.calls), 4)

    def test_input_failure_is_unknown_not_no_match(self):
        fake=Fake(); fake.failure="input"
        self.assertIsNone(d.diagnose(fake)["exact_attempt_match"])


class TransportTests(unittest.TestCase):
    def transport(self, opener):
        return d.ReadOnlyTransport("FAKE_TOKEN", opener=opener)

    def test_identity_then_list_urls_fixed_and_get_only(self):
        class Opener:
            def __init__(self): self.requests=[]
            def open(self, request, timeout):
                self.requests.append(request)
                response=io.BytesIO(b'{"data":{"id":"fakeUser123"}}'); response.status=200
                return response
        opener=Opener(); transport=self.transport(opener)
        transport.get("identity"); transport.get("runs")
        self.assertTrue(all(r.get_method()=="GET" for r in opener.requests))
        self.assertEqual(opener.requests[0].full_url, d.API+"/users/me")
        self.assertIn("limit=5", opener.requests[1].full_url)
        self.assertNotIn("FAKE_TOKEN", opener.requests[1].full_url)

    def test_http_errors_do_not_read_or_expose_body(self):
        class Body:
            def read(self, *args): raise AssertionError("must not read error body")
            def close(self): pass
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 401, "SENSITIVE_PROVIDER_TEXT", {}, Body())
        with self.assertRaises(d.ReadFailure) as cm: self.transport(Opener()).get("identity")
        self.assertEqual(cm.exception.status, 401)
        self.assertEqual(cm.exception.category, "authentication_rejected")
        self.assertNotIn("SENSITIVE", str(cm.exception))

    def test_network_error_is_sanitized_and_never_retried(self):
        class Opener:
            calls=0
            def open(self, request, timeout):
                self.calls+=1; raise URLError("SENSITIVE_TOKEN_URL")
        opener=Opener()
        with self.assertRaises(d.ReadFailure) as cm: self.transport(opener).get("identity")
        self.assertIsNone(cm.exception.status)
        self.assertEqual(cm.exception.category, "transport_error")
        self.assertEqual(opener.calls, 1)

    def test_bad_json_oversize_nonfinite_and_non200_rejected(self):
        for raw, status, category in [(b'bad',200,"invalid_json"), (b'{"x": NaN}',200,"invalid_json"),
                                      (b'x'*(d.RESPONSE_LIMIT+1),200,"response_too_large"),
                                      (b'{}',201,"unexpected_status")]:
            with self.subTest(category=category):
                class Opener:
                    def open(self, request, timeout):
                        response=io.BytesIO(raw); response.status=status; return response
                with self.assertRaises(d.ReadFailure) as cm: self.transport(Opener()).get("identity")
                self.assertEqual(cm.exception.category, category)

    def test_route_order_repeat_arbitrary_method_and_ids_rejected_before_network(self):
        class Opener:
            def open(self, *args, **kwargs): raise AssertionError("unexpected call")
        for stage, kw in [("run", {"run_id":"anything"}), ("input", {"kv_id":"anything"}),
                          ("delete", {}), ("https://example.com", {}), ("POST", {})]:
            with self.subTest(stage=stage):
                with self.assertRaises(d.ReadFailure): self.transport(Opener()).get(stage, **kw)

    def test_no_execute_means_no_environment_or_transport_access(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(d,"ReadOnlyTransport",side_effect=AssertionError):
            self.assertEqual(d.main([]), 0)

    def test_redirect_handler_refuses_follow(self):
        self.assertIsNone(d.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.test"))

    def test_real_transport_four_reads_then_rejects_any_fifth(self):
        fake=Fake()
        payloads=[fake.identity, fake.listing, {"data":fake.run}, fake.input]
        class Opener:
            calls=0
            def open(self, request, timeout):
                response=io.BytesIO(json.dumps(payloads[self.calls]).encode()); response.status=200
                self.calls+=1; return response
        opener=Opener(); transport=self.transport(opener)
        self.assertTrue(d.diagnose(transport)["exact_attempt_match"])
        for stage in ("identity", "input", "delete", "run"):
            with self.assertRaises(d.ReadFailure): transport.get(stage)
        self.assertEqual(opener.calls, 4)

    def test_guard_open_blocks_before_token_read(self):
        def forbid_token(key, *args):
            if key == "APIFY_TOKEN": raise AssertionError("token read")
            return None
        with patch.dict(d.REVIEWED_GUARD, {"ready":True}), patch.object(d.os.environ,"get",side_effect=forbid_token):
            self.assertEqual(d.main(["--execute-read-only"]), 1)

    def test_arbitrary_run_or_kv_rejected_after_legitimate_preceding_reads(self):
        fake=Fake(); payloads=[fake.identity, fake.listing, {"data":fake.run}]
        class Opener:
            calls=0
            def open(self, request, timeout):
                response=io.BytesIO(json.dumps(payloads[self.calls]).encode()); response.status=200
                self.calls+=1; return response
        opener=Opener(); transport=self.transport(opener)
        transport.get("identity"); transport.get("runs")
        with self.assertRaises(d.ReadFailure): transport.get("run",run_id="otherRun")
        transport.get("run",run_id=fake.run["id"])
        with self.assertRaises(d.ReadFailure): transport.get("input",kv_id="otherKv")
        self.assertEqual(opener.calls,3)

    def test_closed_diagnostic_gate_blocks_before_token_read(self):
        def forbid_token(key, *args):
            if key == "APIFY_TOKEN": raise AssertionError("token read")
            return None
        with patch.object(d,"DIAGNOSTIC_OPEN",False), patch.object(d.os.environ,"get",side_effect=forbid_token):
            self.assertEqual(d.main(["--execute-read-only"]),1)


if __name__ == "__main__": unittest.main()
