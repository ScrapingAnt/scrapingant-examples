"""Offline model spend/scoring guards. No provider traffic or credential reads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model_run import ModelRun, StopRun, build_request, calculate_cost, model_plan
from contract import TRUTH

class Response:
    status_code=200
    headers={"content-type":"application/json"}
    def __init__(self,data): self.text=json.dumps(data)

def reply(case="catalog",**overrides):
    return {"id":"fake-completion", "model":"gpt-4.1-mini-2025-04-14", "service_tier":"default",
            "system_fingerprint":"fake-fingerprint", "choices":[{"index":0,"message":{"role":"assistant","content":json.dumps(TRUTH[case]),"refusal":None},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":100,"completion_tokens":200,"total_tokens":300,"prompt_tokens_details":{"cached_tokens":0}},**overrides}

class ModelGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)/"run"
        self.job={"phase":"offline","case":"catalog","arm":"html","repeat":0,"content":"product","source_url":"https://example.invalid/catalog"}
    def make(self,transport,**kwargs): return ModelRun(self.out,transport,"private-secret",**kwargs)

    def test_sixtieth_attempt_is_last_and_never_retried(self):
        calls=[];run=self.make(lambda p:(calls.append(p),Response(reply()))[1])
        for _ in range(60): run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertEqual(len(calls),60);self.assertEqual(len(run.ledger["calls"]),60)
        self.assertEqual(calls[0]["service_tier"],"default");self.assertFalse(calls[0]["store"])

    def test_full_request_input_cap_blocks_dispatch(self):
        run=self.make(lambda p:self.fail("oversized input dispatched"))
        with self.assertRaises(StopRun):run.observe({**self.job,"content":" token"*6000})
        self.assertEqual(run.ledger["calls"],[])

    def test_dollar_reservation_blocks_before_transport(self):
        run=self.make(lambda p:self.fail("overspend dispatched"))
        run.ledger["accounted_usd"]=0.248
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertEqual(run.ledger["calls"],[])

    def test_timeout_reserved_unknown_cost_stops_and_redacts(self):
        def transport(p): raise TimeoutError("private-secret")
        run=self.make(transport)
        with self.assertRaises(StopRun):run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertEqual(len(run.ledger["calls"]),1)
        self.assertIsNone(run.ledger["calls"][0]["actual_cost_usd"])
        self.assertAlmostEqual(run.ledger["accounted_usd"],0.0036)
        self.assertNotIn("private-secret",(self.out/"ledger.json").read_text())

    def test_missing_or_invalid_usage_stops_never_zero_cost(self):
        for usage in [None,{}, {"prompt_tokens":100,"completion_tokens":200,"total_tokens":299}, {"prompt_tokens":True,"completion_tokens":1,"total_tokens":2}]:
            with tempfile.TemporaryDirectory() as temp:
                run=ModelRun(Path(temp)/"run",lambda p:Response(reply(usage=usage)),"private-secret")
                with self.assertRaises(StopRun):run.observe(self.job)
                self.assertIsNone(run.ledger["calls"][0]["actual_cost_usd"])

    def test_wrong_model_and_paid_tier_stop(self):
        for values in [{"model":"gpt-4.1"},{"service_tier":"priority"}]:
            with tempfile.TemporaryDirectory() as temp:
                run=ModelRun(Path(temp)/"run",lambda p:Response(reply(**values)),"private-secret")
                with self.assertRaises(StopRun):run.observe(self.job)
                self.assertFalse(run.ledger["calls"][0]["score"]["accepted_page"])

    def test_http200_provider_error_can_never_be_accepted(self):
        run=self.make(lambda p:Response(reply(error={"message":"failed","type":"provider_error"})))
        with self.assertRaises(StopRun):run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertFalse(run.ledger["calls"][0]["score"]["accepted_page"])
        self.assertEqual(run.ledger["calls"][0]["outcome"],"provider_error")
        self.assertAlmostEqual(run.ledger["calls"][0]["actual_cost_usd"],0.00036)

    def test_run_freezes_task_text_even_if_source_file_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('model_run.py','contract.py','requirements.txt'): (root/name).write_text('test fixture')
            (root/'task.txt').write_text('Frozen original task.')
            with patch('model_run.ROOT',root):
                run=self.make(lambda p:Response(reply()))
                (root/'task.txt').write_text('Different later task.')
                row=run.observe(self.job)
            self.assertIn('Frozen original task.',row['request']['messages'][1]['content'])
            self.assertNotIn('Different later task.',row['request']['messages'][1]['content'])

    def test_truncation_refusal_and_wrong_records_remain_charged(self):
        for choice in [{"message":{"content":json.dumps(TRUTH['catalog']),"refusal":None},"finish_reason":"length"}, {"message":{"content":None,"refusal":"cannot"},"finish_reason":"stop"}, {"message":{"content":"[]","refusal":None},"finish_reason":"stop"}]:
            with tempfile.TemporaryDirectory() as temp:
                run=ModelRun(Path(temp)/"run",lambda p:Response(reply(choices=[choice])),"private-secret")
                run.observe(self.job)
                self.assertFalse(run.ledger["calls"][0]["score"]["accepted_page"])
                self.assertAlmostEqual(run.ledger["calls"][0]["actual_cost_usd"],0.00036)

    def test_correct_records_are_scored_without_prompt_oracle_leak(self):
        run=self.make(lambda p:Response(reply()))
        row=run.observe(self.job)
        self.assertTrue(row["score"]["accepted_page"])
        self.assertEqual(row["score"]["correct_slots"],18)
        self.assertNotIn("Ant Farm Deluxe",json.dumps(row["request"]))

    def test_secret_echo_stops_and_never_persists(self):
        run=self.make(lambda p:Response(reply(id="private-secret")))
        with self.assertRaises(StopRun):run.observe(self.job)
        for p in self.out.rglob('*'):
            if p.is_file():self.assertNotIn("private-secret",p.read_text())

    def test_existing_run_cannot_restart(self):
        self.make(lambda p:Response(reply()))
        with self.assertRaises(FileExistsError):self.make(lambda p:Response(reply()))

    def auth_failure(self):
        response=Response({'error':{'type':'invalid_request_error','code':'invalid_api_key'}})
        response.status_code=401
        run=self.make(lambda p:response)
        with self.assertRaises(StopRun):run.observe(self.job)
        return json.loads((self.out/'ledger.json').read_text())

    def test_authorized_continuation_preserves_failed_attempt_and_cap(self):
        original=self.auth_failure()
        calls=[]
        run=ModelRun.continue_after_auth_failure(self.out,lambda p:(calls.append(p),Response(reply()))[1],'replacement-test-binding')
        self.assertEqual(run.ledger['calls'],original['calls'])
        self.assertAlmostEqual(run.ledger['accounted_usd'],0.0036)
        for _ in range(59):run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertEqual(len(calls),59)
        self.assertEqual(run.ledger['calls'][0],original['calls'][0])
        self.assertEqual(run.ledger['calls'][-1]['attempt'],60)
        self.assertAlmostEqual(run.ledger['accounted_usd'],0.0036+59*0.00036)
        self.assertIsNone(run.ledger['calls'][0]['actual_cost_usd'])

    def test_continuation_cannot_reset_reservation_or_expand_limits(self):
        original=self.auth_failure()
        for changes in ({'accounted_usd':0.0},{'accounted_usd':float('nan')},{'maximum_attempts':61},{'usd_ceiling':1.0},{'stop_reason':'transport_outcome_unknown'}):
            (self.out/'ledger.json').write_text(json.dumps({**original,**changes}))
            with self.assertRaises(StopRun):ModelRun.continue_after_auth_failure(self.out,lambda p:self.fail('dispatch'),'replacement-test-binding')

    def test_repeated_auth_failure_stops_without_retry_and_retains_two_reservations(self):
        self.auth_failure()
        response=Response({'error':{'type':'invalid_request_error','code':'invalid_api_key'}});response.status_code=401
        calls=[]
        run=ModelRun.continue_after_auth_failure(self.out,lambda p:(calls.append(p),response)[1],'replacement-test-binding')
        with self.assertRaises(StopRun):run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertEqual(len(calls),1)
        self.assertAlmostEqual(run.ledger['accounted_usd'],0.0072)
        with self.assertRaises(StopRun):ModelRun.continue_after_auth_failure(self.out,lambda p:self.fail('second rebind'),'third-test-binding')

    def quota_failure_after_first_rebind(self):
        self.auth_failure()
        response=Response({'error':{'type':'insufficient_quota','code':'credit_balance_exhausted'}});response.status_code=429
        run=ModelRun.continue_after_auth_failure(self.out,lambda p:response,'second-test-binding')
        with self.assertRaises(StopRun):run.observe(self.job)
        return json.loads((self.out/'ledger.json').read_text())

    def test_explicit_two_attempt_rebind_retains_prefix_and_allows_only_58_jobs(self):
        original=self.quota_failure_after_first_rebind();calls=[]
        run=ModelRun.continue_after_auth_failure(self.out,lambda p:(calls.append(p),Response(reply()))[1],'third-test-binding',retained_attempts=2)
        self.assertEqual(run.ledger['calls'],original['calls'])
        self.assertAlmostEqual(run.ledger['accounted_usd'],0.0072)
        for _ in range(58):run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertEqual(len(calls),58);self.assertEqual(run.ledger['calls'][-1]['attempt'],60)
        self.assertEqual(run.ledger['calls'][:2],original['calls'])
        self.assertAlmostEqual(run.ledger['accounted_usd'],0.0072+58*0.00036)
        self.assertEqual(run.ledger['continuation_history'],[original['continuation']])

    def test_third_quota_failure_stops_and_cannot_rebind_again(self):
        self.quota_failure_after_first_rebind()
        response=Response({'error':{'type':'insufficient_quota','code':'credit_balance_exhausted'}});response.status_code=429
        run=ModelRun.continue_after_auth_failure(self.out,lambda p:response,'third-test-binding',retained_attempts=2)
        with self.assertRaises(StopRun):run.observe(self.job)
        with self.assertRaises(StopRun):run.observe(self.job)
        self.assertAlmostEqual(run.ledger['accounted_usd'],0.0108)
        with self.assertRaises(StopRun):ModelRun.continue_after_auth_failure(self.out,lambda p:self.fail('retry'),'fourth-test-binding',retained_attempts=2)

    def test_cached_price_and_unknown_details_are_conservative(self):
        self.assertAlmostEqual(calculate_cost({"prompt_tokens":1000,"completion_tokens":100,"total_tokens":1100,"prompt_tokens_details":{"cached_tokens":800}}),0.00032)
        self.assertAlmostEqual(calculate_cost({"prompt_tokens":1000,"completion_tokens":100,"total_tokens":1100}),0.00056)

    def test_45_same_capture_jobs_are_balanced(self):
        plan=model_plan()
        self.assertEqual(len(plan),45)
        for case in ("catalog","links","attributes"):
            for arm in ("html","markdown","text"):
                self.assertEqual(sum(x["case"]==case and x["arm"]==arm for x in plan),5)

if __name__=='__main__':unittest.main()
