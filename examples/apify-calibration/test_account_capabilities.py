"""Synthetic account capability responses only; no real token, account or provider calls."""
import contextlib
import copy
from decimal import Decimal, localcontext
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import account_capabilities as a

SECRET = "SYNTHETIC_ACCOUNT_TOKEN"
PRIVATE = "SYNTHETIC_PRIVATE_FIELD"


def identity():
    return {"data": {"isPaying": True, "plan": {"tier": "STARTER", "id": PRIVATE,
            "monthlyBasePriceUsd": 19, "monthlyUsageCreditsUsd": 19, "description": PRIVATE},
            "effectivePlatformFeatures": {"ACTORS": {"isEnabled": True, "disabledReason": PRIVATE},
                                          "STORAGE": {"isEnabled": True, "disabledReason": SECRET}},
            "id": PRIVATE, "username": PRIVATE, "email": PRIVATE, "profile": {"name": PRIVATE},
            "proxy": {"password": SECRET}, "billing": {"balance": PRIVATE}}}


def limits():
    return {"data": {"limits": {"maxActorMemoryGbytes": 64, "maxConcurrentActorJobs": 32,
                               "maxMonthlyUsageUsd": 9999},
                     "current": {"actorMemoryGbytes": 0, "activeActorJobCount": 0,
                                 "monthlyUsageUsd": 12345},
                     "monthlyUsageCycle": {"startAt": PRIVATE, "endAt": PRIVATE}, "id": PRIVATE}}


class ForbiddenEnvironment:
    def get(self, *args):
        raise AssertionError("environment accessed before closed readiness guard")


class FakeTransport:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def get(self, url):
        self.calls.append(url)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception): raise reply
        return copy.deepcopy(reply)


class FakeResponse(io.BytesIO):
    def __init__(self, value, status=200, raw=False):
        super().__init__(value if raw else json.dumps(value).encode())
        self.status, self.sizes = status, []

    def read1(self, size):
        self.sizes.append(size)
        return super().read(size)


class Opener:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception): raise reply
        return reply


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        units = patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", None)
        units.start(); self.addCleanup(units.stop)

    def test_whitelist_discards_private_financial_and_arbitrary_fields(self):
        result = a.project(identity(), limits())
        self.assertIs(result["paying"], True)
        self.assertEqual(result["plan_tier"], "STARTER")
        self.assertEqual(result["features"], {"ACTORS": True, "STORAGE": True})
        self.assertEqual(result["technical"], {"maxActorMemoryGbytes": 64, "maxConcurrentActorJobs": 32,
                                               "actorMemoryGbytes": 0, "activeActorJobCount": 0})
        self.assertEqual(result["headroom"], {"actorMemoryGbytes": 64, "concurrentActorJobs": 32})
        self.assertTrue(result["schema_complete"])
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["feasibility"], {"one_job_at_memoryMbytes_8192": None,
                                                "one_job_at_memoryMbytes_32768": None})
        output = json.dumps(result)
        for forbidden in (SECRET, PRIVATE, "Usd", "billing", "profile", "proxy", "email", "password"):
            self.assertNotIn(forbidden, output)

    def test_missing_values_are_null_and_do_not_default_to_zero_or_a_plan(self):
        result = a.project({"data": {}}, {"data": {"limits": {}, "current": {}}})
        self.assertFalse(result["schema_complete"])
        self.assertIsNone(result["paying"])
        self.assertIsNone(result["plan_tier"])
        self.assertTrue(all(value is None for value in result["technical"].values()))
        self.assertTrue(all(value is None for value in result["headroom"].values()))
        self.assertTrue(all(value is None for value in result["feasibility"].values()))

    def test_boolean_and_plan_types_do_not_coerce_or_emit_arbitrary_strings(self):
        for value in (None, "true", 1, {}, [], SECRET):
            with self.subTest(value=value):
                user = identity()
                user["data"]["isPaying"] = value
                user["data"]["plan"]["tier"] = value
                user["data"]["effectivePlatformFeatures"]["ACTORS"]["isEnabled"] = value
                result = a.project(user, limits())
                self.assertIsNone(result["paying"])
                self.assertIsNone(result["plan_tier"])
                self.assertIsNone(result["features"]["ACTORS"])
                self.assertFalse(result["schema_complete"])
                self.assertNotIn(SECRET, json.dumps(result))
        user = identity()
        user["data"]["plan"]["tier"] = "PRIVATE_UNKNOWN_PLAN"
        self.assertIsNone(a.project(user, limits())["plan_tier"])

    def test_memory_and_integer_job_fields_require_bounded_nonnegative_numbers(self):
        for field, group in (("maxActorMemoryGbytes", "limits"), ("actorMemoryGbytes", "current"),
                             ("maxConcurrentActorJobs", "limits"), ("activeActorJobCount", "current")):
            invalid = (None, True, "64", -1, float("nan"), float("inf"), 10 ** 9, {}, [],
                       Decimal("0." + "1" * 48))
            if "Job" in field: invalid += (1.5, Decimal("1.0"))
            for value in invalid:
                with self.subTest(field=field, value=value):
                    account = limits()
                    account["data"][group][field] = value
                    result = a.project(identity(), account)
                    self.assertIsNone(result["technical"][field])
                    self.assertFalse(result["schema_complete"])

    def test_reviewed_conversion_compares_exact_headroom_and_job_slots(self):
        for maximum, current, jobs, active, expected in (
                (8, 0, 1, 0, (True, False)), (32, 0, 1, 0, (True, True)),
                (32, 24, 1, 0, (True, False)), (32, 24.000001, 1, 0, (False, False)),
                (64, 0, 32, 32, (False, False)), (0, 0, 0, 0, (False, False))):
            with self.subTest(values=(maximum, current, jobs, active)):
                account = limits()
                account["data"]["limits"].update(maxActorMemoryGbytes=maximum, maxConcurrentActorJobs=jobs)
                account["data"]["current"].update(actorMemoryGbytes=current, activeActorJobCount=active)
                with patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", 1024):
                    result = a.project(identity(), account)
                self.assertEqual(tuple(result["feasibility"].values()), expected)

    def test_unverified_units_and_response_unit_hints_never_claim_feasibility(self):
        account = limits()
        account["data"]["memoryUnit"] = "GiB"
        account["data"]["limits"]["maxActorMemoryMbytes"] = 65536
        for unit in (None, True, "1024", 1024.0, 1, 1023):
            with self.subTest(unit=unit), patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", unit):
                result = a.project(identity(), account)
                self.assertIsNone(result["memory_conversion_Mbytes_per_Gbyte"])
                self.assertTrue(all(value is None for value in result["feasibility"].values()))
        with patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", 1000):
            account["data"]["limits"]["maxActorMemoryGbytes"] = 8
            self.assertFalse(a.project(identity(), account)["feasibility"]["one_job_at_memoryMbytes_8192"])

    def test_disabled_features_or_incomplete_schema_cannot_claim_feasibility(self):
        for changed in (False, None, SECRET):
            user = identity()
            user["data"]["effectivePlatformFeatures"]["STORAGE"]["isEnabled"] = changed
            with patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", 1024): result = a.project(user, limits())
            self.assertTrue(all(value is (False if changed is False else None)
                                for value in result["feasibility"].values()))

    def test_exact_decimal_capacity_never_rounds_a_shortfall_up_to_feasible(self):
        for maximum, target in ((8, "one_job_at_memoryMbytes_8192"), (32, "one_job_at_memoryMbytes_32768")):
            with self.subTest(maximum=maximum):
                account = limits()
                account["data"]["limits"]["maxActorMemoryGbytes"] = maximum
                account["data"]["current"]["actorMemoryGbytes"] = Decimal("1e-30")
                with patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", 1024): result = a.project(identity(), account)
                self.assertFalse(result["feasibility"][target])
        account = limits()
        account["data"]["limits"]["maxActorMemoryGbytes"] = Decimal("8.191")
        with localcontext() as context, patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", 1000):
            context.prec = 1
            result = a.project(identity(), account)
        self.assertFalse(result["feasibility"]["one_job_at_memoryMbytes_8192"])

    def test_conservative_inference_uses_1000_and_preserves_capacity_shortfalls(self):
        for maximum, expected in ((Decimal("4.0959"), (False, False, False)),
                                  (Decimal("4.096"), (True, False, False)),
                                  (Decimal("8.1919"), (True, False, False)),
                                  (Decimal("8.192"), (True, True, False)),
                                  (Decimal("32.768"), (True, True, True))):
            with self.subTest(maximum=maximum):
                account = limits()
                account["data"]["limits"]["maxActorMemoryGbytes"] = maximum
                result = a.project(identity(), account)
                self.assertEqual(tuple(result["conservative_feasibility"].values()), expected)
        account = limits()
        account["data"]["limits"]["maxActorMemoryGbytes"] = Decimal("8.192")
        account["data"]["current"]["actorMemoryGbytes"] = Decimal("1e-30")
        self.assertFalse(a.project(identity(), account)["conservative_feasibility"]["one_job_at_memoryMbytes_8192"])


class EntryTests(unittest.TestCase):
    def test_public_projection_has_only_starter_confirmation_not_plan_label(self):
        for tier,expected in [('STARTER',True),('FREE',False),('SCALE',False),('BUSINESS',False),(None,None),('hostile',None)]:
            with self.subTest(tier=tier):
                result=a.public_result({'plan_tier':tier})
                self.assertNotIn('plan_tier',result)
                self.assertIs(result['starter_plan_confirmed'],expected)
    def setUp(self):
        guard = patch.object(a, "CAPABILITIES_READY", False)
        guard.start(); self.addCleanup(guard.stop)
        units = patch.object(a, "REVIEWED_MBYTES_PER_GBYTE", None)
        units.start(); self.addCleanup(units.stop)

    def test_default_plan_and_closed_execution_do_not_read_token_or_build_transport(self):
        for argv, expected in (([], 0), (["--plan"], 0), (["--execute"], 2)):
            with self.subTest(argv=argv), patch.object(a, "AccountTransport") as transport, \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(a.main(argv, environ=ForbiddenEnvironment()), expected)
                transport.assert_not_called()
                self.assertEqual(json.loads(out.getvalue())["requests_attempted"], 0)

    def test_execution_requires_opt_in_even_when_guard_is_reviewed(self):
        with patch.object(a, "CAPABILITIES_READY", True), self.assertRaises(a.ProbeError):
            a.execute(opt_in=False, environ=ForbiddenEnvironment())

    def test_invalid_token_or_arguments_are_sanitized_before_requests(self):
        for token in (None, "", True, "bad\n" + SECRET, "x" * 4097):
            with self.subTest(token=token), patch.object(a, "CAPABILITIES_READY", True), \
                    patch.object(a, "AccountTransport") as transport, contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(a.main(["--execute"], environ={"APIFY_TOKEN": token}), 2)
                transport.assert_not_called()
                self.assertNotIn(SECRET, out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(a.main(["--token=" + SECRET], environ=ForbiddenEnvironment()), 2)
        self.assertNotIn(SECRET, out.getvalue() + err.getvalue())

    def test_two_reads_succeed_with_unverified_units_without_execution_readiness(self):
        fake = FakeTransport([identity(), limits()])
        with patch.object(a, "CAPABILITIES_READY", True):
            result = a.execute(opt_in=True, environ={"APIFY_TOKEN": SECRET}, transport=fake)
        self.assertEqual(fake.calls, ["https://api.apify.com/v2/users/me", "https://api.apify.com/v2/users/me/limits"])
        self.assertEqual(result["requests_attempted"], 2)
        self.assertEqual(result["outcome"], "complete")
        self.assertFalse(result["execution_ready"])
        self.assertTrue(all(value is True for value in result["feasibility"].values()))
        self.assertEqual(result["conservative_conversion_Mbytes_per_Gbyte"], 1000)
        self.assertEqual(result["memory_unit_mapping"], "unverified")

    def test_execute_and_main_expose_only_public_derived_fields(self):
        for entry in ("execute", "main"):
            with self.subTest(entry=entry):
                account = limits()
                account["data"]["limits"]["maxActorMemoryGbytes"] = 73.125
                account["data"]["current"]["actorMemoryGbytes"] = 1.125
                account["data"]["limits"]["maxConcurrentActorJobs"] = 37
                fake = FakeTransport([identity(), account])
                with patch.object(a, "CAPABILITIES_READY", True):
                    if entry == "execute":
                        result = a.execute(opt_in=True, environ={"APIFY_TOKEN": SECRET}, transport=fake)
                    else:
                        with patch.object(a, "AccountTransport", return_value=fake), contextlib.redirect_stdout(io.StringIO()) as out:
                            self.assertEqual(a.main(["--execute"], environ={"APIFY_TOKEN": SECRET}), 0)
                        result = json.loads(out.getvalue())
                for field in ("technical", "headroom", "maxActorMemoryGbytes", "actorMemoryGbytes",
                              "maxConcurrentActorJobs", "activeActorJobCount"):
                    self.assertNotIn(field, json.dumps(result))
                for private in (SECRET, PRIVATE, "73.125", "1.125", "37", "Usd", "profile", "proxy"):
                    self.assertNotIn(private, json.dumps(result))
                self.assertEqual(result["requests_attempted"], 2)
                self.assertTrue(all(value is True for value in result["feasibility"].values()))

    def test_missing_schema_and_hostile_transport_errors_are_safe_failures_without_retry(self):
        for replies, attempts, outcome in (([{}, limits()], 2, "incomplete_schema"),
                                          ([RuntimeError(SECRET + PRIVATE)], 1, "read_failed")):
            fake = FakeTransport(replies)
            result = a.probe(fake)
            self.assertEqual(result["outcome"], outcome)
            self.assertEqual(result["requests_attempted"], attempts)
            self.assertEqual(len(fake.calls), attempts)
            self.assertNotIn(SECRET, json.dumps(result))
            self.assertNotIn(PRIVATE, json.dumps(result))


class HttpTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(a, "CAPABILITIES_READY", True)
        guard.start(); self.addCleanup(guard.stop)

    def test_real_transport_guard_blocks_construction_without_network(self):
        with patch.object(a, "CAPABILITIES_READY", False), patch.object(a, "build_opener") as opener:
            with self.assertRaises(a.ProbeError): a.AccountTransport(SECRET)
            opener.assert_not_called()

    def test_exact_two_fixed_gets_use_header_auth_and_bounded_reads(self):
        replies = [FakeResponse(identity()), FakeResponse(limits())]
        opener = Opener(replies)
        result = a.probe(a.AccountTransport(SECRET, opener=opener))
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(len(opener.calls), 2)
        for request, timeout in opener.calls:
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.get_header("Authorization"), "Bearer " + SECRET)
            self.assertNotIn(SECRET, request.full_url)
            self.assertIsNone(request.data)
            self.assertGreater(timeout, 0); self.assertLessEqual(timeout, 10)
        self.assertTrue(all(0 < size <= 8192 for reply in replies for size in reply.sizes))

    def test_wrong_host_route_query_order_and_third_get_are_rejected_before_opener(self):
        opener = Opener([FakeResponse(identity()), FakeResponse(limits())])
        transport = a.AccountTransport(SECRET, opener=opener)
        for url in ("https://evil.invalid/v2/users/me", "http://api.apify.com/v2/users/me",
                    "https://api.apify.com/v2/users/me?token=" + SECRET,
                    "https://api.apify.com/v2/users/me#fragment", "https://api.apify.com/v2/users/other",
                    "https://api.apify.com/v2/users/me/limits"):
            with self.subTest(url=url), self.assertRaises(a.ProbeError): transport.get(url)
        self.assertEqual(len(opener.calls), 0)
        transport.get("https://api.apify.com/v2/users/me")
        with self.assertRaises(a.ProbeError): transport.get("https://api.apify.com/v2/users/me")
        transport.get("https://api.apify.com/v2/users/me/limits")
        with self.assertRaises(a.ProbeError): transport.get("https://api.apify.com/v2/users/me/limits")
        self.assertEqual(len(opener.calls), 2)

    def test_http_failures_never_read_error_bodies_follow_redirects_or_retry(self):
        for status in (301, 400, 401, 403, 429, 500):
            with self.subTest(status=status):
                body = io.BytesIO((SECRET + PRIVATE).encode())
                error = HTTPError("https://evil.invalid/" + SECRET, status, PRIVATE,
                                  {"Location": "https://evil.invalid/" + SECRET}, body)
                opener = Opener([error])
                result = a.probe(a.AccountTransport(SECRET, opener=opener))
                self.assertEqual(result["reads"][0]["http_status"], status)
                self.assertEqual(result["requests_attempted"], 1)
                self.assertEqual(len(opener.calls), 1)
                self.assertNotIn(SECRET, json.dumps(result))
                self.assertTrue(body.closed)
        self.assertIsNone(a.NoRedirect().redirect_request(None, None, 302, PRIVATE, {}, "https://evil.invalid"))

    def test_invalid_json_nonfinite_duplicate_keys_oversize_and_connection_are_bounded(self):
        for reply, category in ((FakeResponse(b"{" + SECRET.encode(), raw=True), "invalid_json"),
                                (FakeResponse(b'{"data":{"isPaying":NaN}}', raw=True), "invalid_json"),
                                (FakeResponse(b'{"data":{},"data":{}}', raw=True), "invalid_json"),
                                (FakeResponse(b"x" * 131073, raw=True), "response_too_large"),
                                (URLError(SECRET + PRIVATE), "connection_error")):
            with self.subTest(category=category):
                opener = Opener([reply])
                result = a.probe(a.AccountTransport(SECRET, opener=opener))
                self.assertEqual(result["reads"][0]["category"], category)
                self.assertEqual(len(opener.calls), 1)
                self.assertNotIn(SECRET, json.dumps(result))
                if isinstance(reply, FakeResponse): self.assertLessEqual(sum(reply.sizes), 139264)

    def test_wall_and_route_deadlines_stop_before_extra_calls(self):
        clock = [0]
        opener = Opener([FakeResponse(identity()), FakeResponse(limits())])
        with patch.object(a, "monotonic", side_effect=lambda: clock[0]):
            transport = a.AccountTransport(SECRET, opener=opener)
            clock[0] = 31
            with self.assertRaises(a.ProbeError): transport.get("https://api.apify.com/v2/users/me")
        self.assertEqual(len(opener.calls), 0)
        class SlowResponse(FakeResponse):
            def read1(self, size):
                clock[0] += 11
                return super().read1(size)
        clock[0] = 0
        opener = Opener([SlowResponse(identity())])
        with patch.object(a, "monotonic", side_effect=lambda: clock[0]):
            result = a.probe(a.AccountTransport(SECRET, opener=opener))
        self.assertEqual(result["reads"][0]["category"], "deadline_exceeded")
        self.assertEqual(len(opener.calls), 1)

    def test_json_decoding_deadline_prevents_the_second_get(self):
        clock = [0]
        opener = Opener([FakeResponse(identity()), FakeResponse(limits())])
        original_loads = json.loads
        def slow_decode(*args, **kwargs):
            clock[0] += 11
            return original_loads(*args, **kwargs)
        with patch.object(a, "monotonic", side_effect=lambda: clock[0]), patch.object(a.json, "loads", side_effect=slow_decode):
            result = a.probe(a.AccountTransport(SECRET, opener=opener))
        self.assertEqual(result["outcome"], "read_failed")
        self.assertEqual(result["reads"][0]["category"], "deadline_exceeded")
        self.assertEqual(len(opener.calls), 1)


if __name__ == "__main__": unittest.main()
