"""Offline guard tests. Only paid transport/account-counter boundaries are faked."""
import json
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from mcp_live import LiveRun, StopRun, call_plan, decode_rpc, check_snapshot, execute

class Response:
    status_code = 200
    headers = {"content-type": "application/json"}
    def __init__(self, value):
        self.text = json.dumps(value)

OK = {"jsonrpc": "2.0", "id": 10, "result": {"content": [{"type": "text", "text": "product $12"}], "isError": False}}

def snapshot(used=10, period="fixed"):
    return {"read_only_verified": True, "physical_standby": False, "matching_tokens": 1,
            "active_periods": 1, "period_ref": period, "used_credits": used, "total_credits": 100}

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run"

    def run_with(self, transport, **kwargs):
        return LiveRun(self.path, transport, "private-secret", ["product", "$12"], **kwargs)

    def test_cap_prevents_sixteenth_transport_and_persists_fifteen(self):
        requests = []
        run = self.run_with(lambda p: (requests.append(p), Response({**OK,"id":p["id"]}))[1])
        for i in range(15): run.observe("html", 0)
        with self.assertRaises(StopRun): run.observe("text", 0)
        self.assertEqual(len(requests), 15)
        self.assertEqual(len(json.loads((self.path / "ledger.json").read_text())["calls"]), 15)
        self.assertEqual(requests[0]["params"]["arguments"], {"url": "https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html", "browser": False, "proxy_type": "datacenter", "proxy_country": "US"})

    def test_timeout_is_reserved_and_not_retried(self):
        def timeout(p): raise TimeoutError("private-secret")
        run = self.run_with(timeout)
        with self.assertRaises(StopRun): run.observe("html", 0)
        with self.assertRaises(StopRun): run.observe("html", 0)
        ledger = (self.path / "ledger.json").read_text()
        self.assertNotIn("private-secret", ledger)
        self.assertEqual(json.loads(ledger)["calls"][0]["outcome"], "transport_unknown")
        self.assertEqual(json.loads(ledger)["reserved_credit_upper_bound"], 1)

    def test_transport_traceback_does_not_expose_exception_secret(self):
        secret = "private-secret"
        def timeout(p): raise TimeoutError(secret)
        run = self.run_with(timeout)
        try: run.observe("html",0)
        except StopRun:
            self.assertNotIn(secret, traceback.format_exc())
        else: self.fail("unknown transport must stop")

    def test_existing_run_is_never_overwritten_or_resumed(self):
        self.run_with(lambda p: Response(OK))
        with self.assertRaises(FileExistsError): self.run_with(lambda p: Response(OK))

    def test_secret_echo_redacted_and_stops(self):
        run = self.run_with(lambda p: Response({"result": {"content": [{"type":"text", "text":"private-secret"}]}}))
        with self.assertRaises(StopRun): run.observe("html", 0)
        for p in self.path.rglob("*"):
            if p.is_file(): self.assertNotIn("private-secret", p.read_text())
        self.assertEqual(run.ledger["calls"][0]["outcome"], "credential_echo_stopped")

    def test_tool_error_string_with_false_iserror_is_failure(self):
        run = self.run_with(lambda p: Response({"jsonrpc":"2.0","id":p["id"],"result": {"content": [{"type":"text", "text":"Failed to scrape page"}], "isError": False}}))
        run.observe("text", 0)
        self.assertEqual(run.ledger["calls"][0]["outcome"], "required_values_missing")
        self.assertFalse(run.ledger["calls"][0]["required_values_survive"])

    def test_rpc_error_is_retained_without_success(self):
        run = self.run_with(lambda p: Response({"jsonrpc":"2.0", "id":10,"error":{"code":-32603,"message":"tool failed"}}))
        run.observe("text", 0)
        self.assertEqual(run.ledger["calls"][0]["outcome"], "rpc_error")
        self.assertIn("tool failed", (self.path / "response-001.txt").read_text())

    def test_wrong_rpc_id_stops_before_another_attempt(self):
        run = self.run_with(lambda p: Response({**OK,"id":777}))
        with self.assertRaises(StopRun): run.observe("html",0)
        with self.assertRaises(StopRun): run.observe("text",0)
        self.assertEqual(len(run.ledger["calls"]),1)
        self.assertEqual(run.ledger["calls"][0]["outcome"],"rpc_id_mismatch")

    def test_malformed_result_and_blocks_are_retained_and_stop(self):
        for result in [[], {"content":[None]}, {"content":[{"type":"text","text":42}]}, {"content":[],"isError":"false"}]:
            with tempfile.TemporaryDirectory() as temp:
                run=LiveRun(Path(temp)/"run",lambda p:Response({"jsonrpc":"2.0","id":p["id"],"result":result}),"private-secret",["product"])
                with self.assertRaises(StopRun): run.observe("html",0)
                with self.assertRaises(StopRun): run.observe("html",0)
                self.assertEqual(run.ledger["calls"][0]["outcome"],"malformed_rpc")
                self.assertTrue((run.out/"response-001.txt").is_file())

    def test_discovery_wrong_identity_prevents_any_paid_attempt(self):
        class Session:
            trust_env=False
            def post(self,*args,**kwargs):
                return Response({"jsonrpc":"2.0","id":999,"result":{"protocolVersion":"2025-11-25","serverInfo":{"name":"fixture","version":"1"}}})
            def close(self): pass
        with patch("requests.Session",Session):
            with self.assertRaises(StopRun): execute(self.path,"private-secret")
        ledger=json.loads((self.path/"ledger.json").read_text())
        self.assertEqual(ledger["calls"],[])
        self.assertEqual(ledger["stop_reason"],"discovery_rpc_identity")

    def test_counter_debit_above_bound_stops_remaining_calls(self):
        values = iter([snapshot(), snapshot(12)])
        run = self.run_with(lambda p: Response(OK), usage=lambda: next(values))
        with self.assertRaises(StopRun): run.observe("html", 0)
        self.assertEqual(run.ledger["calls"][0]["observed_account_delta"], 2)
        self.assertEqual(run.ledger["stop_reason"], "usage_anomaly")

    def test_period_change_and_unknown_snapshot_never_mean_zero(self):
        for after in [snapshot(11, "changed"), None]:
            with tempfile.TemporaryDirectory() as temp:
                values = iter([snapshot(), after])
                run = LiveRun(Path(temp)/"run", lambda p: Response(OK), "private-secret", ["product"], usage=lambda:next(values))
                with self.assertRaises(StopRun): run.observe("html", 0)
                self.assertIsNone(run.ledger["calls"][0].get("observed_account_delta"))
                with self.assertRaises(StopRun): run.observe("html", 0)
                self.assertEqual(len(run.ledger["calls"]),1)

    def test_drift_is_recorded_not_disguised_as_identical_source(self):
        run = self.run_with(lambda p: Response(OK), expected_html_sha256="0" * 64)
        run.observe("html", 0)
        self.assertFalse(run.ledger["calls"][0]["matches_frozen_html"])

    def test_snapshot_rejects_write_role_standby_ambiguous_account(self):
        for key, value in [("read_only_verified", False), ("physical_standby", True), ("matching_tokens",2),("active_periods",0)]:
            data = snapshot(); data[key] = value
            with self.assertRaises(StopRun): check_snapshot(data)

    def test_plan_is_balanced_and_interleaved(self):
        plan = call_plan()
        self.assertEqual(len(plan),15)
        for r in range(5): self.assertEqual(sorted(arm for arm,repeat in plan if repeat==r), ["html","markdown","text"])

    def test_sse_multiline_json_is_decoded(self):
        data = 'event: message\ndata: {"result":\ndata: {"content":[]}}\n\n'
        self.assertEqual(decode_rpc(data, "text/event-stream"), {"result":{"content":[]}})

if __name__ == "__main__": unittest.main()
