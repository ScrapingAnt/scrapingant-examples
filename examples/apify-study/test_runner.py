"""Offline smoke-runner tests. Every provider reply and clock is synthetic."""
import contextlib
import base64
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import html
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, parse_qs, quote, unquote

import runner as r

TOKEN = "OFFLINE_SECRET_NEVER_REAL"
STAMP = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
URLS = ["https://scrapingant.github.io/scrapingant-examples/fixtures/study/%s.html" % i for i in range(3)]
FIELDS = ["fixture", "sku", "name", "price_minor", "currency"]
RECORDS = [{"fixture": str(i), "sku": "AA101", "name": "Desk Lamp", "price_minor": 3499,
            "currency": "USD"} for i in range(3)]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def plan_fixture():
    cells = []
    for i in range(6):
        cells.append({"cell_id": "smoke-%s" % i, "actor_id": "PublicActor%s" % i,
                      "build": "3.0.%s" % (i + 1),
                      "input": {"startUrls": [{"url": u} for u in URLS], "maxConcurrency": 1},
                      "options": {"build": "3.0.%s" % (i + 1), "memoryMbytes": 4096,
                                  "timeoutSecs": 120, "maxTotalChargeUsd": "0.12",
                                  "restartOnError": False}, "ancillary_reserve_usd": "0.02",
                      "output": {"fields": FIELDS, "max_records": 3, "max_bytes": 65536,
                                 "expected_records": RECORDS, "allowed_urls": URLS}})
    return {"schema_version": 1, "stage": "SMOKE", "aggregate_reserved_usd": "0.84", "cells": cells}


def limited_plan_fixture():
    plan=plan_fixture()
    plan["cells"][0].update(cell_id="smoke-cheerio-scraper",actor="apify/cheerio-scraper",
                            actor_id="YrQuEkowkNCLdk4j2",force_permission_level="LIMITED_PERMISSIONS")
    return plan


def all_limited_plan_fixture():
    plan = plan_fixture()
    actors = (("cheerio-scraper", "YrQuEkowkNCLdk4j2"),
              ("web-scraper", "moJRLRc85AitArpNN"),
              ("playwright-scraper", "MpRbnNmVAoj5RC1Ma"),
              ("puppeteer-scraper", "YJCnS9qogi9XxDgLB"),
              ("website-content-crawler", "aYG0l9s7dbB7j3gbS"),
              ("rag-web-browser", "3ox4R101TgZz67sLr"))
    for spec, (name, actor_id) in zip(plan["cells"], actors):
        spec.update(cell_id="smoke-" + name, actor="apify/" + name, actor_id=actor_id,
                    force_permission_level="LIMITED_PERMISSIONS")
    return plan


def capability_plan_fixture():
    """Thirty-six synthetic cells; native input behavior is not simulated."""
    template = all_limited_plan_fixture()
    per_rep = [('cheerio-static', 0), ('cheerio-dynamic', 0), ('web-static', 1), ('web-dynamic', 1),
               ('playwright-static', 2), ('playwright-dynamic', 2), ('puppeteer-static', 3),
               ('puppeteer-dynamic', 3), ('website-content-crawler', 4),
               ('rag-web-browser-static', 5), ('rag-web-browser-dynamic', 5), ('rag-web-browser-formatting', 5)]
    cells = []
    for rep in range(1, 4):
        for name, index in per_rep:
            spec = copy.deepcopy(template['cells'][index])
            spec['cell_id'] = 'cap-r%s-%s' % (rep, name)
            spec['options']['maxTotalChargeUsd'] = '0.08'
            urls = [URLS[0].replace('0.html', '%s.html' % i) for i in range(30 if index < 5 else 1)]
            if index < 4:
                records = [dict(RECORDS[0], fixture=str(i)) for i in range(30)]
                spec['output'].update(max_records=30, max_bytes=16384, allowed_urls=urls, expected_records=records)
            else:
                spec['output'].update(fields=['url', 'text', 'markdown'], max_records=len(urls), max_bytes=524288,
                                      allowed_urls=urls, expected_records=None, content_contracts=[])
            cells.append(spec)
    return dict(schema_version=1, stage='CAPABILITY', aggregate_reserved_usd='3.60', cells=cells)


def response(status="SUCCEEDED", **changes):
    data = {"id": "PrivateRun", "userId": "PrivateOwner", "actId": "PublicActor0",
            "defaultDatasetId": "PrivateDataset", "defaultKeyValueStoreId": "PrivateKv",
            "defaultRequestQueueId": "PrivateQueue", "status": status,
            "buildNumber": "3.0.1", "startedAt": STAMP.isoformat(),
            "finishedAt": (STAMP + timedelta(seconds=30)).isoformat() if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED") else None,
            "options": {"build": "3.0.1", "memoryMbytes": 4096, "timeoutSecs": 120,
                        "maxTotalChargeUsd": 0.12, "restartOnError": False},
            "usageTotalUsd": 0.011, "usage": {"ACTOR_COMPUTE_UNITS": 0.01, "private-account": 19},
            "usageUsd": {"ACTOR_COMPUTE_UNITS": 0.002}, "chargedEventCounts": {"owned_event": 3},
            "stats": {"computeUnits": 0.01, "restartCount": 0, "urlSigningSecretKey": TOKEN},
            "urlSigningSecretKey": TOKEN, "statusMessage": TOKEN}
    data.update(changes)
    return {"data": data}


def metadata(kind, **changes):
    identity = {"dataset": "PrivateDataset", "kv": "PrivateKv", "queue": "PrivateQueue"}
    data = {"id": identity[kind], "userId": "PrivateOwner", "actId": "PublicActor0",
            "actRunId": "PrivateRun", "name": None, "createdAt": STAMP.isoformat(),
            "stats": {"storageBytes": 128, "readCount": 2, "writeCount": 3},
            "generalAccess": "FOLLOW_USER_SETTING", "urlSigningSecretKey": TOKEN}
    data.update(changes)
    return {"data": data}


class Clock:
    def __init__(self, value=100.0):
        self.value = value
    def __call__(self):
        return self.value
    def wait(self, seconds):
        self.value += seconds


class HttpReply:
    def __init__(self, status, body): self.status = status; self.stream = io.BytesIO(body)
    def read1(self, size): return self.stream.read(size)
    def close(self): pass


class ForbiddenEnvironment:
    def get(self, *args):
        raise AssertionError("environment access is forbidden in this offline test")


class FakeTransport:
    def __init__(self, replies, settle=False):
        self.replies = list(replies)
        self.requests = []
        self.enable_terminal_settling = settle
        self.authorized = False
    def request(self, operation, identity, timeout):
        self.requests.append((operation, copy.deepcopy(identity), timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)
    def bind_run(self, identity):
        self.bound = copy.deepcopy(identity)
    def authorize_cleanup(self, identity):
        self.authorized = True


class TestTools:
    def setUp(self):
        self.assertTrue(callable(getattr(r, "prepare_cell", None)), "reviewed-plan validation is missing")
        self.plan = plan_fixture()
        self.pin = hashlib.sha256(canonical(self.plan)).hexdigest()
        for name, value in (("RUNNER_READY", True), ("REVIEWED_PLAN_SHA256", self.pin)):
            p = patch.object(r, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.cell = r.prepare_cell(self.plan, "smoke-0")
        self.clock = Clock()
        self.saved = []
    def persist(self, payload):
        self.saved.append(payload)
        return {"plaintext_sha256": hashlib.sha256(payload).hexdigest(), "ciphertext_sha256": "c" * 64,
                "remote_file_readback_verified": True}
    def capture(self, transport, **kwargs):
        return r.run_until_capture(transport, self.cell, self.persist, budget=r.StudyBudget(self.plan),
                                   clock=self.clock, utcnow=lambda: STAMP + timedelta(seconds=40),
                                   wait=self.clock.wait, **kwargs)
    def normal(self, status="SUCCEEDED", export=None, settle=False):
        replies = [r.Reply(201, response(status))]
        if status == "SUCCEEDED":
            replies.append(r.Reply(200, RECORDS if export is None else export))
        replies += [r.Reply(200, metadata(k)) for k in ("dataset", "kv", "queue")]
        return FakeTransport(replies, settle=settle)
    def approval(self, state):
        return {"plaintext_sha256": state.plaintext_sha256, "ciphertext_sha256": state.ciphertext_sha256,
                "scope_approved": True}
    def cleanup(self, transport, state, approval=None, verifier=lambda *args: True, **kwargs):
        return r.cleanup_verified_capture(transport, state, self.approval(state) if approval is None else approval,
                                         verify_local_approval=verifier, clock=self.clock,
                                         utcnow=lambda: STAMP + timedelta(minutes=1), **kwargs)
    def cleanup_transport(self, latest=None, metas=None, statuses=None):
        replies = [r.Reply(200, response() if latest is None else latest)]
        replies += [r.Reply(200, metadata(k)) for k in ("dataset", "kv", "queue")] if metas is None else metas
        for status in statuses or [(204, 404)] * 3:
            replies += [r.Reply(status[0], None), r.Reply(status[1], None)]
        return FakeTransport(replies)


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.plan = capability_plan_fixture()
        self.raw = json.dumps(self.plan, indent=2).encode()
        for key, value in [('RUNNER_READY', True), ('REVIEWED_CAPABILITY_PLAN_SHA256', r.sha(canonical(self.plan))),
                           ('REVIEWED_CAPABILITY_PLAN_FILE_SHA256', r.sha(self.raw))]:
            guard = patch.object(r, key, value, create=True)
            guard.start(); self.addCleanup(guard.stop)

    def cell(self, index=0):
        return r.prepare_cell(self.plan, self.plan['cells'][index]['cell_id'])

    def test_capability_bytes_and_canonical_pin_are_separate_from_smoke(self):
        self.assertEqual(r.load_reviewed_plan(self.raw), self.plan)
        with self.assertRaises(r.Fault): r.load_reviewed_plan(canonical(self.plan))
        smoke = plan_fixture()
        with patch.object(r, 'REVIEWED_PLAN_SHA256', r.sha(canonical(smoke))):
            self.assertEqual(r.validate_plan(smoke), smoke)
        with patch.object(r, 'REVIEWED_CAPABILITY_PLAN_FILE_SHA256', None):
            with self.assertRaises(r.Fault): r.load_reviewed_plan(self.raw)

    def test_exact_repeated_actor_cells_reserve_all_thirty_six_and_never_repeat(self):
        budget = r.StudyBudget(self.plan)
        for spec in self.plan['cells']: budget.claim(r.prepare_cell(self.plan, spec['cell_id']))
        self.assertEqual(budget.reserved_usd, Decimal('3.60'))
        self.assertEqual(len(budget.claimed), 36)
        with self.assertRaises(r.Fault): budget.claim(self.cell())

    def test_capability_rehashed_wrong_order_actor_permission_and_caps_still_fail(self):
        for key, value in [('cell_id', 'cap-r1-other-static'), ('actor_id', 'ForeignActor'),
                           ('force_permission_level', 'FULL_PERMISSIONS')]:
            bad = copy.deepcopy(self.plan); bad['cells'][0][key] = value
            with self.subTest(key=key), patch.object(r, 'REVIEWED_CAPABILITY_PLAN_SHA256', r.sha(canonical(bad))):
                with self.assertRaises(r.Fault): r.validate_plan(bad)
        for change in ('order', 'cap', 'count'):
            bad = copy.deepcopy(self.plan)
            if change == 'order': bad['cells'][0], bad['cells'][1] = bad['cells'][1], bad['cells'][0]
            elif change == 'cap': bad['cells'][0]['options']['maxTotalChargeUsd'] = '0.12'
            else: bad['cells'].pop()
            with self.subTest(change=change), patch.object(r, 'REVIEWED_CAPABILITY_PLAN_SHA256', r.sha(canonical(bad))):
                with self.assertRaises(r.Fault): r.validate_plan(bad)

    def test_spec_cap_is_sent_and_response_equivalence_is_checked(self):
        cell = self.cell(); seen = []
        data = response(actId=cell.spec['actor_id'])
        data['data']['options']['maxTotalChargeUsd'] = 0.08
        def opener(req, timeout):
            seen.append(req); return HttpReply(201, canonical(data))
        transport = r.HttpTransport(cell, TOKEN, opener=opener, clock=Clock(), deadline=500)
        self.assertEqual(transport.request('start', {}, 30).status, 201)
        self.assertEqual(parse_qs(urlsplit(seen[0].full_url).query)['maxTotalChargeUsd'], ['0.08'])
        data['data']['options']['maxTotalChargeUsd'] = Decimal('0.08000')
        self.assertEqual(r.validate_run(data['data'], cell)['options']['maxTotalChargeUsd'], '0.08')
        for bad in (Decimal('0.12'), '0.08', None, True):
            data['data']['options']['maxTotalChargeUsd'] = bad
            with self.assertRaises(r.Fault): r.validate_run(data['data'], cell)

    def test_large_content_export_state_roundtrip_and_sentinel_keep_exact_scope(self):
        cell = self.cell(8); spec = cell.spec; clock = Clock()
        rows = [dict(url=u, text='Owned ' + 'x' * 10000, markdown='Owned') for u in spec['output']['allowed_urls']]
        run = response(actId=spec['actor_id'], buildNumber=spec['build'])
        run['data']['options'] = dict(spec['options'], maxTotalChargeUsd=Decimal('0.08'))
        transport = FakeTransport([r.Reply(201, run), r.Reply(200, rows)] +
                                  [r.Reply(200, metadata(k, actId=spec['actor_id'])) for k in r.STORES])
        persist = lambda blob: dict(plaintext_sha256=r.sha(blob), ciphertext_sha256='c'*64, remote_file_readback_verified=True)
        state = r.run_until_capture(transport, cell, persist, budget=r.StudyBudget(self.plan), clock=clock,
                                    wait=clock.wait, utcnow=lambda: STAMP + timedelta(seconds=40))
        self.assertTrue(state.capture_verified)
        self.assertEqual(state.evidence['stage'], 'CAPABILITY')
        self.assertEqual(len(state.evidence['records']), 30)
        self.assertEqual(r.public_result(state)['stage'], 'CAPABILITY')
        raw = r.serialize_private_state(state)
        self.assertGreater(len(raw), 262144)
        self.assertEqual(r.restore_private_state(raw, self.plan).evidence, state.evidence)
        with self.assertRaises(r.OutputFault) as extra: r.validate_output(rows + [rows[0]], cell)
        self.assertLessEqual(len(extra.exception.records), 31)
        tampered = json.loads(raw); tampered['evidence']['stage'] = 'SMOKE'
        tampered['plaintext_sha256'] = r.sha(canonical(tampered['evidence']))
        with self.assertRaises(r.Fault): r.restore_private_state(canonical(tampered), self.plan)

    def test_export_http_larger_bound_does_not_widen_provider_metadata(self):
        cell = self.cell(8); body = canonical([dict(url=u, text='x'*10000, markdown='Owned') for u in cell.spec['output']['allowed_urls']])
        seen=[]
        def opener(req, timeout): seen.append(req); return HttpReply(200, body)
        transport = r.HttpTransport(cell, TOKEN, opener=opener, clock=Clock(), deadline=500)
        identity = response(actId=cell.spec['actor_id'], buildNumber=cell.spec['build'])['data']
        identity['options'] = dict(cell.spec['options'], maxTotalChargeUsd=Decimal('0.08'))
        transport.bind_run(r.validate_run(identity, cell))
        self.assertEqual(len(transport.request('export', transport.identity, 10).body), 30)
        self.assertEqual(parse_qs(urlsplit(seen[0].full_url).query)['limit'], ['31'])
        with self.assertRaises(r.Fault) as error: transport.request('metadata_dataset', transport.identity, 10)
        self.assertEqual(error.exception.category, 'response_too_large')

    def test_billing_projection_stays_private_and_distinguishes_null_zero(self):
        cell = self.cell(); data = response()['data']
        data.update(pricingInfo={'pricingModel':'PAY_PER_EVENT'}, platformUsageBillingModel='USER', usageTotalUsd=0, usage=None)
        receipt = r.run_receipt(data, cell)
        self.assertIn('billing_evidence', receipt)
        self.assertEqual(receipt['billing_evidence'], __import__('billing_projection').project_run_billing(data, []))
        state = r.PrivateState(cell); state.evidence = {'run':receipt}
        public = canonical(r.public_result(state)).decode()
        self.assertNotIn('billing_evidence', public)
        self.assertNotIn('PAY_PER_EVENT', public)

    def test_missing_capability_pin_and_closed_guard_precede_environment(self):
        with patch.object(r, 'RUNNER_READY', False), self.assertRaises(r.Fault) as error:
            r.execute(self.plan, self.plan['cells'][0]['cell_id'], opt_in=True, environ=ForbiddenEnvironment())
        self.assertEqual(error.exception.category, 'guard_closed')
        with patch.object(r, 'REVIEWED_CAPABILITY_PLAN_SHA256', None), self.assertRaises(r.Fault):
            r.execute(self.plan, self.plan['cells'][0]['cell_id'], opt_in=True, environ=ForbiddenEnvironment())

    def test_revoked_capability_pin_blocks_cached_transport_before_any_request(self):
        called=[]
        transport=r.HttpTransport(self.cell(),TOKEN,opener=lambda *args,**kwargs:called.append(True),clock=Clock(),deadline=500)
        with patch.object(r,'REVIEWED_CAPABILITY_PLAN_SHA256',None), self.assertRaises(r.Fault):
            transport.request('start',{},30)
        self.assertEqual(called,[])
        self.assertEqual(transport.counts['total'],0)


class ContractTests(TestTools, unittest.TestCase):

    def test_all_six_pinned_actor_overrides_accept_only_limited(self):
        plan = all_limited_plan_fixture()
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(plan)).hexdigest()):
            self.assertEqual(r.validate_plan(plan), plan)
        for index in range(6):
            for key, value in (("force_permission_level", "FULL_PERMISSIONS"),
                               ("force_permission_level", None), ("actor_id", "ForeignActor"),
                               ("actor", "apify/foreign-actor"), ("cell_id", "smoke-foreign")):
                bad = copy.deepcopy(plan); bad["cells"][index][key] = value
                with self.subTest(index=index, key=key), patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(bad)).hexdigest()):
                    with self.assertRaises(r.Fault): r.validate_plan(bad)
        swapped = copy.deepcopy(plan); swapped["cells"][4], swapped["cells"][5] = swapped["cells"][5], swapped["cells"][4]
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(swapped)).hexdigest()):
            with self.assertRaises(r.Fault): r.validate_plan(swapped)

    def test_permission_override_rejects_other_modes_cells_or_actor_identities(self):
        cases=[]
        for value in (None,"FULL_PERMISSIONS","limited_permissions",True,"LIMITED_PERMISSIONS "):
            plan=limited_plan_fixture();plan["cells"][0]["force_permission_level"]=value;cases.append(plan)
        for key,value in (("cell_id","other-cheerio"),("actor","apify/web-scraper"),("actor_id","OtherPublicActor")):
            plan=limited_plan_fixture();plan["cells"][0][key]=value;cases.append(plan)
        plan=limited_plan_fixture();plan["cells"][0],plan["cells"][1]=plan["cells"][1],plan["cells"][0];cases.append(plan)
        plan=limited_plan_fixture();plan["cells"][1]["force_permission_level"]="LIMITED_PERMISSIONS";cases.append(plan)
        for index,plan in enumerate(cases):
            with self.subTest(case=index),patch.object(r,"REVIEWED_PLAN_SHA256",hashlib.sha256(canonical(plan)).hexdigest()):
                with self.assertRaises(r.Fault):r.validate_plan(plan)

    def test_permission_request_intent_is_private_and_observed_level_remains_unknown(self):
        plan=limited_plan_fixture()
        with patch.object(r,"REVIEWED_PLAN_SHA256",hashlib.sha256(canonical(plan)).hexdigest()):
            cell=r.prepare_cell(plan,"smoke-cheerio-scraper")
            replies=[r.Reply(201,response(actId=cell.spec["actor_id"],permissionLevel="FULL_PERMISSIONS")),r.Reply(200,RECORDS)]
            replies += [r.Reply(200,metadata(k,actId=cell.spec["actor_id"])) for k in r.STORES]
            state=r.run_until_capture(FakeTransport(replies),cell,self.persist,budget=r.StudyBudget(plan),
                                      clock=self.clock,utcnow=lambda:STAMP+timedelta(seconds=40),wait=self.clock.wait)
            receipt=state.evidence["run"]
            self.assertEqual(receipt.get("requested_permission_level"),"LIMITED_PERMISSIONS")
            self.assertIn("observed_permission_level",receipt)
            self.assertIsNone(receipt["observed_permission_level"])
            self.assertNotIn("permission_level",json.dumps(r.public_result(state)))
            self.assertNotIn("LIMITED_PERMISSIONS",json.dumps(r.public_result(state)))
        legacy=r.run_receipt(response()["data"],self.cell)
        self.assertIsNone(legacy.get("requested_permission_level"))

    def test_unreviewed_permission_override_changes_plan_commitment(self):
        plan=limited_plan_fixture()
        with self.assertRaises(r.Fault):r.prepare_cell(plan,"smoke-cheerio-scraper")
        raw=canonical(plan)
        with patch.object(r,"REVIEWED_PLAN_FILE_SHA256",hashlib.sha256(raw).hexdigest()):
            with self.assertRaises(r.Fault):r.load_reviewed_plan(raw)
            with patch.object(r,"REVIEWED_PLAN_SHA256",hashlib.sha256(raw).hexdigest()):
                self.assertEqual(r.load_reviewed_plan(raw),plan)

    def test_private_json_state_roundtrip_preserves_original_scope_and_counts(self):
        self.assertTrue(callable(getattr(r, "private_state_bytes", None)), "bounded state serialization is missing")
        state = self.capture(self.normal())
        raw = r.private_state_bytes(state)
        self.assertIn(b"PrivateOwner", raw)  # Root keeps this only in 0600 temporary state.
        restored = r.restore_private_state(raw, self.plan)
        self.assertEqual(restored.identity, state.identity)
        self.assertEqual(restored.request_counts, state.request_counts)
        self.assertEqual(restored.plaintext_sha256, state.plaintext_sha256)
        result = self.cleanup(self.cleanup_transport(), restored)
        self.assertEqual(result["cleanup_state"], "complete")

    def test_private_state_restore_rejects_scope_receipt_plan_counts_and_non_json(self):
        self.assertTrue(callable(getattr(r, "private_state_bytes", None)), "bounded state serialization is missing")
        state = self.capture(self.normal()); raw = r.private_state_bytes(state)
        for mutate in (lambda v: v["identity"].update(userId="ForeignOwner"),
                       lambda v: v["evidence"].update(records=[]),
                       lambda v: v.update(plan_sha256="0" * 64),
                       lambda v: v["request_counts"].update(start=0),
                       lambda v: v.update(diagnostic={"category": TOKEN})):
            value = json.loads(raw); mutate(value)
            with self.assertRaises(r.Fault):
                r.restore_private_state(canonical(value), self.plan)
        for invalid in (b"not JSON", b"x" * 262145, b'{"status":NaN}', b'{"status":1,"status":2}'):
            with self.assertRaises(r.Fault):
                r.restore_private_state(invalid, self.plan)

    def test_failure_state_can_roundtrip_but_remains_impossible_to_clean(self):
        self.assertTrue(callable(getattr(r, "private_state_bytes", None)), "bounded state serialization is missing")
        state = self.capture(FakeTransport([r.Fault("connection_error", "request")]))
        restored = r.restore_private_state(r.private_state_bytes(state), self.plan)
        t = FakeTransport([])
        self.assertEqual(self.cleanup(t, restored)["cleanup_state"], "blocked")
        self.assertEqual(t.requests, [])

    def test_three_normal_polls_plus_settling_and_two_phase_metadata_stay_at_nineteen(self):
        replies = [r.Reply(201, response("READY")), r.Reply(200, response("RUNNING")),
                   r.Reply(200, response("RUNNING")), r.Reply(200, response()), r.Reply(200, response()),
                   r.Reply(200, RECORDS)] + [r.Reply(200, metadata(k)) for k in ("dataset", "kv", "queue")]
        state = self.capture(FakeTransport(replies, settle=True))
        self.assertEqual(self.cleanup(self.cleanup_transport(), state)["cleanup_state"], "complete")
        self.assertEqual(state.request_counts["total"], 19)
        self.assertEqual(state.request_counts["poll"] + state.request_counts["settle"], 4)

    def test_public_projection_discards_hostile_diagnostic_fields(self):
        state = self.capture(self.normal())
        state.diagnostic = {"category": TOKEN, "stage": TOKEN, "http_status": TOKEN, "body": TOKEN}
        state.request_counts["raw"] = TOKEN
        public = json.dumps(r.public_result(state))
        self.assertNotIn(TOKEN, public)
        self.assertNotIn("raw", json.loads(public)["request_counts"])

    def test_final_cleanup_result_has_no_raw_provider_references(self):
        state = self.capture(self.normal()); result = self.cleanup(self.cleanup_transport(), state)
        encoded = json.dumps(result)
        for raw in (TOKEN, "PrivateOwner", "PrivateRun", "PrivateDataset", "PrivateKv", "PrivateQueue"):
            self.assertNotIn(raw, encoded)

    def test_partial_owned_records_survive_acceptance_failure_without_debug_fields(self):
        rows = copy.deepcopy(RECORDS[:2]); rows[0]["price_minor"] = 1; rows[0]["#debug"] = TOKEN
        state = self.capture(self.normal(export=rows))
        self.assertEqual(state.evidence["extraction_state"], "invalid")
        self.assertEqual(state.evidence["records"], [{k:v for k,v in row.items() if k != "#debug"} for row in rows])
        self.assertNotIn(TOKEN, self.saved[-1].decode())

    def test_rag_metadata_url_adapter_drops_other_metadata_and_preserves_partial_text(self):
        p = plan_fixture(); out = p["cells"][0]["output"]
        out.update(fields=["url", "text", "markdown"], expected_records=None, url_source="metadata.url",
                   content_contracts=[{"url":u} for u in URLS])
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(p)).hexdigest()):
            cell = r.prepare_cell(p, "smoke-0")
            rows = [{"metadata":{"url":u, "userId":"PrivateOwner", "headers":{"Authorization":TOKEN}},
                     "text":"Owned", "markdown":"Owned"} for u in URLS]
            self.assertEqual(r.validate_output(rows,cell), [{"url":u,"text":"Owned","markdown":"Owned"} for u in URLS])

    def test_sentinel_extra_record_is_detected_not_silently_accepted(self):
        state = self.capture(self.normal(export=RECORDS + [RECORDS[0]]))
        self.assertEqual(state.evidence["extraction_state"], "invalid")
        self.assertEqual(len(state.evidence["records"]), 4)

    def test_metadata_item_count_is_captured_without_defaulting_missing_to_zero(self):
        t=self.normal(); t.replies[2]=r.Reply(200,metadata("dataset",itemCount=3))
        state=self.capture(t)
        self.assertEqual(state.evidence["storage"]["dataset"]["itemCount"],3)
        self.assertIsNone(state.evidence["storage"]["kv"].get("itemCount"))

    def test_root_serializer_name_and_cleanup_fresh_scalar_receipts(self):
        self.assertTrue(callable(getattr(r,"serialize_private_state",None)),"root private-state interface is missing")
        state=self.capture(self.normal()); before=canonical(state.evidence)
        fresh=response();fresh["data"]["usageTotalUsd"]=0.012
        result=self.cleanup(self.cleanup_transport(latest=fresh),state)
        self.assertEqual(result["refreshed_run"]["usage_total_usd"],"0.012")
        self.assertEqual(result["refreshed_storage"]["queue"]["storageBytes"],128)
        self.assertEqual(result["cleaned_at"],(STAMP+timedelta(minutes=1)).isoformat())
        self.assertEqual(canonical(state.evidence),before)
        self.assertEqual(r.restore_private_state(r.serialize_private_state(state),self.plan).cleanup_state,"complete")

    def test_cleanup_active_revocation_preserves_approved_initial_evidence_immutable(self):
        state=self.capture(self.normal());before=canonical(state.evidence)
        result=self.cleanup(FakeTransport([r.Reply(200,response("RUNNING",options={}))]),state)
        self.assertEqual(result["cleanup_state"],"blocked")
        self.assertEqual(canonical(state.evidence),before)
        self.assertTrue(state.latest_active)

    def test_session_late_original_active_reply_revokes_before_deadline_check(self):
        state=self.capture(self.normal());before=canonical(state.evidence)
        t=FakeTransport([r.Reply(200,response("RUNNING",options={},userId=None))])
        original=t.request
        def late(operation,identity,timeout):
            reply=original(operation,identity,timeout)
            self.clock.wait(121)
            return reply
        t.request=late
        result=self.cleanup(t,state)
        self.assertEqual(result["diagnostic"]["category"],"latest_run_active")
        self.assertTrue(state.latest_active)
        self.assertFalse(state.capture_verified)
        self.assertEqual(canonical(state.evidence),before)
        self.assertEqual([q[0] for q in t.requests],["fresh_terminal"])

    def test_session_late_settling_active_reply_never_uses_old_terminal_for_capture(self):
        t=FakeTransport([r.Reply(201,response()),r.Reply(200,response("RUNNING",options={}))],settle=True)
        original=t.request
        def late(operation,identity,timeout):
            reply=original(operation,identity,timeout)
            if operation=="settle":self.clock.wait(471)
            return reply
        t.request=late
        state=self.capture(t)
        self.assertTrue(state.latest_active)
        self.assertFalse(state.capture_verified)
        self.assertIsNone(state.evidence["run"])
        self.assertEqual(state.evidence["historical_terminal_capture"]["status"],"SUCCEEDED")
        self.assertEqual([q[0] for q in t.requests],["start","settle"])

    def test_dataset_item_count_mismatch_marks_extraction_invalid_and_keeps_records(self):
        t=self.normal();t.replies[2]=r.Reply(200,metadata("dataset",itemCount=4))
        state=self.capture(t)
        self.assertEqual(state.evidence["extraction_state"],"invalid")
        self.assertEqual(state.evidence["records"],RECORDS)
        self.assertFalse(state.evidence["dataset_item_count_matches_capture"])

    def test_file_and_canonical_plan_pins_are_separately_verified(self):
        self.assertTrue(callable(getattr(r, "load_reviewed_plan", None)), "fixed-file plan verification is missing")
        raw = json.dumps(self.plan, indent=2).encode()
        with patch.object(r, "REVIEWED_PLAN_FILE_SHA256", hashlib.sha256(raw).hexdigest()):
            self.assertEqual(r.load_reviewed_plan(raw), self.plan)
            with self.assertRaises(r.Fault):
                r.load_reviewed_plan(canonical(self.plan))

    def test_real_schema_case_id_and_full_content_manifest_contract(self):
        p = plan_fixture()
        records = [{"case_id": v["fixture"], **{k: value for k, value in v.items() if k != "fixture"}} for v in RECORDS]
        p["cells"][0]["output"].update(fields=["case_id", "sku", "name", "price_minor", "currency"], expected_records=records)
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(p)).hexdigest()):
            cell = r.prepare_cell(p, "smoke-0")
            self.assertEqual(r.validate_output(records, cell), records)
        p["cells"][0]["output"].update(fields=["url", "text", "markdown"], expected_records=None,
                                     content_contracts=[{"url": u, "case_id": str(i), "expected_sentences": {"S1": "Owned"}}
                                                        for i, u in enumerate(URLS)])
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(p)).hexdigest()):
            cell = r.prepare_cell(p, "smoke-0")
            rows = [{"url": u, "text": "Owned content", "markdown": "Owned markdown"} for u in URLS]
            self.assertEqual(r.validate_output(rows, cell), rows)

    def test_capture_requires_encryption_callback_before_start(self):
        t = FakeTransport([])
        with self.assertRaises(r.Fault):
            r.run_until_capture(t, self.cell, None, budget=r.StudyBudget(self.plan), clock=self.clock,
                                utcnow=lambda: STAMP, wait=self.clock.wait)
        self.assertEqual(t.requests, [])

    def test_six_cell_ledger_uses_exact_aggregate_and_rejects_repeated_cell(self):
        budget = r.StudyBudget(self.plan)
        for c in self.plan["cells"]:
            budget.claim(r.prepare_cell(self.plan, c["cell_id"]))
        self.assertEqual(budget.reserved_usd, Decimal("0.84"))
        with self.assertRaises(r.Fault):
            budget.claim(self.cell)

    def test_poll_validation_diagnostic_retains_successful_http_status(self):
        t = FakeTransport([r.Reply(201, response("READY")), r.Reply(200, response(buildNumber="wrong"))])
        state = self.capture(t)
        self.assertEqual(state.diagnostic["category"], "build_mismatch")
        self.assertEqual(state.diagnostic["http_status"], 200)

    def test_numeric_cap_rejects_nonfinite_boolean_negative_missing_and_string(self):
        for value in (Decimal("NaN"), float("inf"), True, -1, None, "0.12"):
            data = response()["data"]; data["options"]["maxTotalChargeUsd"] = value
            with self.subTest(value=value), self.assertRaises(r.Fault):
                r.validate_run(data, self.cell)

    def test_local_approval_time_is_included_in_cleanup_phase_deadline(self):
        state = self.capture(self.normal())
        t = FakeTransport([])
        def slow_approval(*args):
            self.clock.wait(30)
            return True
        result = self.cleanup(t, state, verifier=slow_approval)
        self.assertEqual(result["cleanup_state"], "blocked")
        self.assertEqual(t.requests, [])

    def test_cleanup_expiry_checked_again_before_each_delete(self):
        state = self.capture(self.normal())
        t = self.cleanup_transport()
        times = iter([STAMP + timedelta(minutes=1), STAMP + timedelta(minutes=31),
                      STAMP + timedelta(minutes=31), STAMP + timedelta(minutes=31), STAMP + timedelta(minutes=31)])
        result = r.cleanup_verified_capture(t, state, self.approval(state), verify_local_approval=lambda *a: True,
                                            clock=self.clock, utcnow=lambda: next(times))
        self.assertEqual(result["cleanup_state"], "residual")
        self.assertFalse(any(q[0].startswith("delete") for q in t.requests))

    def test_slow_export_never_spends_reserved_cleanup_time_on_metadata(self):
        t = self.normal()
        original = t.request
        def request(operation, identity, timeout):
            result = original(operation, identity, timeout)
            if operation == "export":
                self.clock.wait(390)
            return result
        t.request = request
        state = self.capture(t)
        self.assertFalse(state.capture_verified)
        self.assertEqual([q[0] for q in t.requests], ["start", "export"])

    def test_typed_transport_active_fault_moves_prior_numbers_to_historical_only(self):
        t = FakeTransport([r.Reply(201, response()), r.Fault("latest_run_active", "run_validation", 200)], settle=True)
        t.latest_active_status = "RUNNING"
        state = self.capture(t)
        self.assertTrue(state.latest_active)
        self.assertIsNone(state.evidence["run"])
        self.assertEqual(state.evidence["historical_terminal_capture"]["status"], "SUCCEEDED")
        self.assertEqual(state.status, "RUNNING")

    def test_content_foreign_duplicate_url_and_oversized_text_are_rejected(self):
        p = plan_fixture(); p["cells"][0]["output"].update(fields=["url", "text", "markdown"], expected_records=None,
            content_contracts=[{"url": u, "case_id": str(i)} for i,u in enumerate(URLS)])
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(p)).hexdigest()):
            cell = r.prepare_cell(p, "smoke-0")
            base = [{"url": u, "text": "Owned", "markdown": "Owned"} for u in URLS]
            for replacement in ({"url": "https://foreign.invalid", "text": "Owned", "markdown": "Owned"},
                                base[1], {"url": URLS[0], "text": "x"*65537, "markdown": "Owned"}):
                items = copy.deepcopy(base); items[0] = replacement
                with self.assertRaises(r.Fault):
                    r.validate_output(items, cell)

    def test_closed_guard_blocks_before_token_or_transport(self):
        with patch.object(r, "RUNNER_READY", False):
            with self.assertRaises(r.Fault):
                r.execute(self.plan, "smoke-0", opt_in=True, environ=ForbiddenEnvironment(),
                          persist_encrypted=self.persist, transport_factory=lambda *args, **kw: self.fail("transport created"))

    def test_missing_opt_in_blocks_before_token(self):
        with self.assertRaises(r.Fault):
            r.execute(self.plan, "smoke-0", opt_in=False, environ=ForbiddenEnvironment(), persist_encrypted=self.persist)

    def test_modified_plan_rejected_before_token(self):
        self.plan["cells"][0]["build"] = "unreviewed"
        with self.assertRaises(r.Fault):
            r.execute(self.plan, "smoke-0", opt_in=True, environ=ForbiddenEnvironment(), persist_encrypted=self.persist)

    def test_missing_pin_bad_budget_and_low_deadline_block_start(self):
        for mutation in (lambda p: p["cells"][0].pop("build"),
                         lambda p: p.update(aggregate_reserved_usd="0.83"),
                         lambda p: p["cells"][0]["options"].update(maxTotalChargeUsd="0.13")):
            p = plan_fixture(); mutation(p)
            with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(p)).hexdigest()), self.assertRaises(r.Fault):
                r.prepare_cell(p, "smoke-0")
        with self.assertRaises(r.Fault):
            r.execute(self.plan, "smoke-0", opt_in=True, environ=ForbiddenEnvironment(),
                      persist_encrypted=self.persist, clock=self.clock, deadline=self.clock() + 359)

    def test_budget_retains_full_reserve_after_ambiguous_start_and_cannot_repeat(self):
        budget = r.StudyBudget(self.plan)
        t = FakeTransport([r.Fault("connection_error", "request")])
        state = r.run_until_capture(t, self.cell, self.persist, budget=budget, clock=self.clock,
                                   utcnow=lambda: STAMP + timedelta(seconds=40), wait=self.clock.wait)
        self.assertEqual(state.status, "UNKNOWN")
        self.assertEqual(budget.reserved_usd, Decimal("0.14"))
        self.assertEqual([q[0] for q in t.requests], ["start"])
        with self.assertRaises(r.Fault):
            r.run_until_capture(t, self.cell, self.persist, budget=budget, clock=self.clock,
                                utcnow=lambda: STAMP, wait=self.clock.wait)

    def test_capture_receipt_is_private_redacted_and_performs_no_delete(self):
        t = self.normal()
        state = self.capture(t)
        evidence = json.loads(self.saved[0])
        self.assertEqual(state.status, "SUCCEEDED")
        self.assertEqual([q[0] for q in t.requests], ["start", "export", "metadata_dataset", "metadata_kv", "metadata_queue"])
        self.assertEqual(evidence["records"], RECORDS)
        self.assertTrue(evidence["owner_association_verified"])
        self.assertFalse(evidence["invoice_finality"])
        self.assertEqual(evidence["storage"]["kv"]["storageBytes"], 128)
        self.assertEqual(evidence["recovery_identity"], {"schema_version": 1, "identity": state.identity})
        for secret in (TOKEN, "urlSigningSecretKey", "private-account"):
            self.assertNotIn(secret, self.saved[0].decode())
        for secret in (TOKEN, "PrivateRun", "PrivateOwner", "PrivateDataset", "PrivateKV", "PrivateQueue", "urlSigningSecretKey", "private-account"):
            self.assertNotIn(secret, json.dumps(r.public_result(state)))
            self.assertNotIn(secret, repr(state))

    def test_nullable_pending_build_and_numeric_equivalence_are_accepted(self):
        t = self.normal()
        initial = response("READY", buildNumber=None)
        initial["data"]["options"]["maxTotalChargeUsd"] = Decimal("0.12000")
        t.replies.insert(0, r.Reply(201, initial)); t.replies[1] = r.Reply(200, response())
        state = self.capture(t)
        self.assertEqual(state.status, "SUCCEEDED")
        self.assertEqual([q[0] for q in t.requests].count("start"), 1)
        self.assertEqual([q[0] for q in t.requests].count("poll"), 1)

    def test_initial_missing_identity_foreign_actor_bad_build_or_options_never_polls(self):
        bads = [response(userId=None), response(actId="ForeignActor"), response(buildNumber=None),
                response(buildNumber="9.9.9"), response(defaultDatasetId="../../evil")]
        bad = response(); bad["data"]["options"]["memoryMbytes"] = True; bads.append(bad)
        for initial in bads:
            with self.subTest(initial=initial):
                t = FakeTransport([r.Reply(201, initial)])
                state = self.capture(t)
                self.assertEqual(state.status, "UNKNOWN")
                self.assertEqual([q[0] for q in t.requests], ["start"])
                self.assertTrue(r.public_result(state)["owner_attention_required"])

    def test_three_active_polls_leave_owner_attention_without_export_or_cleanup(self):
        t = FakeTransport([r.Reply(201, response("READY"))] + [r.Reply(200, response("RUNNING"))] * 3)
        state = self.capture(t)
        self.assertTrue(state.latest_active)
        self.assertEqual(len(t.requests), 4)
        self.assertNotIn("export", [q[0] for q in t.requests])

    def test_settling_uses_one_spare_poll_and_no_fourth_normal_poll(self):
        t = self.normal()
        t.enable_terminal_settling = True
        t.replies.insert(1, r.Reply(200, response()))
        state = self.capture(t)
        self.assertEqual(state.status, "SUCCEEDED")
        self.assertEqual([q[0] for q in t.requests].count("settle"), 1)
        self.assertEqual(self.clock(), 110)

    def test_latest_same_id_active_even_malformed_revokes_terminal_capture_permission(self):
        for key, value in (("buildNumber", "9.9.9"), ("options", {}), ("userId", None), ("actId", "ForeignActor")):
            with self.subTest(key=key):
                t = FakeTransport([r.Reply(201, response()), r.Reply(200, response("RUNNING", **{key: value}))], settle=True)
                state = self.capture(t)
                self.assertTrue(state.latest_active)
                self.assertEqual([q[0] for q in t.requests], ["start", "settle"])
                self.assertEqual(state.evidence["historical_terminal_capture"]["status"], "SUCCEEDED")

    def test_export_failure_still_captures_all_metadata_for_approved_cleanup(self):
        t = self.normal(export=[{"arbitrary": TOKEN}])
        state = self.capture(t)
        self.assertEqual(state.evidence["extraction_state"], "invalid")
        self.assertTrue(state.capture_verified)
        self.assertEqual([q[0] for q in t.requests][-3:], ["metadata_dataset", "metadata_kv", "metadata_queue"])

    def test_every_metadata_must_be_owned_unnamed_and_associated_before_capture_verified(self):
        for changes in ({"userId": "ForeignOwner"}, {"name": "shared"}, {"name": ""},
                        {"actRunId": "ForeignRun"}, {"actId": "ForeignActor"}, {"id": "ForeignStore"},
                        {"createdAt": (STAMP - timedelta(seconds=6)).isoformat()}):
            t = self.normal(); t.replies[2] = r.Reply(200, metadata("dataset", **changes))
            state = self.capture(t)
            self.assertFalse(state.capture_verified)
            self.assertEqual([q[0] for q in t.requests][-3:], ["metadata_dataset", "metadata_kv", "metadata_queue"])

    def test_persistence_exception_or_unverified_hash_never_authorizes_cleanup(self):
        for callback in (lambda payload: (_ for _ in ()).throw(RuntimeError(TOKEN)),
                         lambda payload: {"plaintext_sha256": "0" * 64, "ciphertext_sha256": "c" * 64,
                                          "remote_file_readback_verified": True},
                         lambda payload: {"plaintext_sha256": hashlib.sha256(payload).hexdigest(), "ciphertext_sha256": "c" * 64,
                                          "remote_file_readback_verified": False}):
            state = r.run_until_capture(self.normal(), self.cell, callback, budget=r.StudyBudget(self.plan),
                                        clock=self.clock, utcnow=lambda: STAMP + timedelta(seconds=40), wait=self.clock.wait)
            t = FakeTransport([])
            result = self.cleanup(t, state)
            self.assertEqual(t.requests, [])
            self.assertEqual(result["cleanup_state"], "blocked")

    def test_cleanup_requires_matching_approval_and_local_readback_callback_before_get(self):
        state = self.capture(self.normal())
        for approval, verifier in (({}, lambda *a: True), (self.approval(state), None),
                                   (self.approval(state), lambda *a: False)):
            t = FakeTransport([])
            result = self.cleanup(t, state, approval=approval, verifier=verifier)
            self.assertEqual(result["cleanup_state"], "blocked")
            self.assertEqual(t.requests, [])

    def test_cleanup_uses_fresh_terminal_then_all_three_metadata_then_exact_deletes(self):
        state = self.capture(self.normal())
        t = self.cleanup_transport()
        result = self.cleanup(t, state)
        self.assertEqual(result["cleanup_state"], "complete")
        self.assertEqual([q[0] for q in t.requests], ["fresh_terminal", "metadata_dataset", "metadata_kv", "metadata_queue",
                          "delete_dataset", "absence_dataset", "delete_kv", "absence_kv", "delete_queue", "absence_queue"])
        self.assertTrue(t.authorized)
        self.assertEqual(state.request_counts["total"], 15)

    def test_terminal_failed_run_can_be_cleaned_after_durable_failure_receipt(self):
        state = self.capture(self.normal(status="FAILED"))
        t = self.cleanup_transport(latest=response("FAILED"))
        result = self.cleanup(t, state)
        self.assertEqual(result["cleanup_state"], "complete")
        self.assertEqual(state.evidence["extraction_state"], "terminal_failure")

    def test_cleanup_fresh_active_malformed_revokes_without_any_metadata_or_delete(self):
        state = self.capture(self.normal())
        for changes in ({"buildNumber": "wrong"}, {"options": {}}, {"userId": None}):
            t = FakeTransport([r.Reply(200, response("RUNNING", **changes))])
            result = self.cleanup(t, state)
            self.assertEqual(result["cleanup_state"], "blocked")
            self.assertTrue(result["owner_attention_required"])
            self.assertEqual([q[0] for q in t.requests], ["fresh_terminal"])
            # A revoked state cannot recover permission from its earlier receipt.
            self.assertTrue(state.latest_active)
            break

    def test_cleanup_fresh_foreign_refs_or_build_options_status_prevent_all_deletion(self):
        for changes in ({"id": "ForeignRun"}, {"userId": "ForeignOwner"}, {"actId": "ForeignActor"},
                        {"defaultDatasetId": "ForeignStore"}, {"buildNumber": None},
                        {"buildNumber": "9.9.9"}, {"options": {}}, {"status": "FAILED"}):
            state = self.capture(self.normal())
            t = FakeTransport([r.Reply(200, response(**changes))])
            result = self.cleanup(t, state)
            self.assertEqual(result["cleanup_state"], "blocked")
            self.assertFalse(any(q[0].startswith("delete") for q in t.requests))

    def test_phase2_all_metadata_checks_precede_any_delete_even_last_store_bad(self):
        state = self.capture(self.normal())
        metas = [r.Reply(200, metadata("dataset")), r.Reply(200, metadata("kv")),
                 r.Reply(200, metadata("queue", name="existing-shared"))]
        t = self.cleanup_transport(metas=metas)
        result = self.cleanup(t, state)
        self.assertEqual(result["cleanup_state"], "blocked")
        self.assertEqual([q[0] for q in t.requests], ["fresh_terminal", "metadata_dataset", "metadata_kv", "metadata_queue"])

    def test_delete_failure_continues_independent_stores_and_reports_residual(self):
        state = self.capture(self.normal())
        t = self.cleanup_transport(statuses=[(500, 404), (204, 404), (204, 404)])
        # A failed DELETE has no absence verification call.
        t.replies.pop(5)
        result = self.cleanup(t, state)
        self.assertEqual(result["cleanup_state"], "residual")
        self.assertEqual([q[0] for q in t.requests].count("delete_queue"), 1)
        self.assertTrue(result["owner_attention_required"])

    def test_only_typed_http_404_proves_absence_not_json_body(self):
        state = self.capture(self.normal())
        t = self.cleanup_transport(statuses=[(204, 200), (204, 404), (204, 404)])
        t.replies[5] = r.Reply(200, {"statusCode": 404})
        result = self.cleanup(t, state)
        self.assertEqual(result["cleanup_state"], "residual")
        self.assertEqual(result["stores"]["dataset"], "absence_unconfirmed")

    def test_approval_age_and_short_cleanup_deadline_block_before_requests(self):
        state = self.capture(self.normal())
        t = FakeTransport([])
        result = r.cleanup_verified_capture(t, state, self.approval(state), verify_local_approval=lambda *a: True,
                                            clock=self.clock, utcnow=lambda: STAMP + timedelta(minutes=26))
        self.assertEqual(result["cleanup_state"], "blocked"); self.assertEqual(t.requests, [])
        result = self.cleanup(t, state, deadline=self.clock() + 99)
        self.assertEqual(result["cleanup_state"], "blocked"); self.assertEqual(t.requests, [])

    def test_tampered_raw_state_scope_cannot_use_approved_receipt(self):
        state = self.capture(self.normal())
        state.identity["userId"] = "ForeignOwner"
        t = FakeTransport([])
        result = self.cleanup(t, state)
        self.assertEqual(result["cleanup_state"], "blocked")
        self.assertEqual(t.requests, [])

    def test_content_contract_keeps_only_owned_bounded_text_and_fixed_urls(self):
        p = plan_fixture()
        p["cells"][0]["output"].update(fields=["url", "text", "markdown"], expected_records=None,
                                     content_contracts={u: {"expected_sentence": "Owned fixture sentence."} for u in URLS})
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(p)).hexdigest()):
            cell = r.prepare_cell(p, "smoke-0")
            items = [{"url": u, "text": "Owned fixture sentence.", "markdown": "# Owned\nOwned fixture sentence.",
                      "headers": {"Authorization": TOKEN}, "#debug": TOKEN} for u in URLS]
            t = FakeTransport([r.Reply(201, response()), r.Reply(200, items)] + [r.Reply(200, metadata(k)) for k in ("dataset", "kv", "queue")])
            state = r.run_until_capture(t, cell, self.persist, budget=r.StudyBudget(p), clock=self.clock,
                                        utcnow=lambda: STAMP + timedelta(seconds=40), wait=self.clock.wait)
            self.assertEqual(state.evidence["extraction_state"], "accepted")
            self.assertNotIn(TOKEN, self.saved[-1].decode())


class TransportTests(TestTools, unittest.TestCase):
    def test_each_pinned_actor_start_sends_only_explicit_limited_override(self):
        plan = all_limited_plan_fixture(); seen = []
        def opener(req, timeout):
            seen.append((req.full_url, req.data, req.get_method(), timeout))
            raise URLError(TOKEN)
        with patch.object(r, "REVIEWED_PLAN_SHA256", hashlib.sha256(canonical(plan)).hexdigest()):
            for spec in plan["cells"]:
                with self.subTest(cell=spec["cell_id"]):
                    cell = r.prepare_cell(plan, spec["cell_id"])
                    transport = r.HttpTransport(cell, TOKEN, opener=opener, clock=self.clock, deadline=self.clock()+480)
                    with self.assertRaises(r.Fault): transport.request("start", None, 30)
                    query = parse_qs(urlsplit(seen[-1][0]).query)
                    self.assertEqual(query["forcePermissionLevel"], ["LIMITED_PERMISSIONS"])
                    self.assertEqual(query["maxTotalChargeUsd"], ["0.12"])
                    self.assertEqual(query["restartOnError"], ["false"])
                    self.assertEqual(seen[-1][1:], (canonical(spec["input"]), "POST", 30))
                    self.assertEqual(urlsplit(seen[-1][0]).path, "/v2/acts/"+spec["actor_id"]+"/runs")
                    previous = len(seen)
                    with self.assertRaises(r.Fault): transport.request("start", None, 30)
                    self.assertEqual(len(seen), previous)
        self.assertEqual(len(seen), 6)

    def http(self, opener):
        return r.HttpTransport(self.cell, TOKEN, opener=opener, clock=self.clock, deadline=self.clock() + 480)

    def error_transport(self, body, content_type="application/json", status=403, slow=None):
        class ErrorBody:
            def __init__(inner):inner.stream=io.BytesIO(body);inner.closed=False;inner.read_sizes=[]
            def read(inner,size):raise AssertionError("buffered error body read is forbidden")
            def read1(inner,size):
                inner.read_sizes.append(size)
                if slow:self.clock.wait(slow)
                return inner.stream.read(min(size,1) if slow else size)
            def close(inner):inner.closed=True
        stream=ErrorBody()
        def opener(req,timeout):
            raise HTTPError(req.full_url,status,TOKEN,{"Content-Type":content_type},stream)
        return self.http(opener),stream

    def test_limited_permission_is_only_one_post_query_parameter_with_unchanged_caps_input_and_options(self):
        plan=limited_plan_fixture();seen=[]
        def opener(req,timeout):
            seen.append((req.full_url,req.get_method(),req.data,timeout))
            raise URLError(TOKEN)
        with patch.object(r,"REVIEWED_PLAN_SHA256",hashlib.sha256(canonical(plan)).hexdigest()):
            cell=r.prepare_cell(plan,"smoke-cheerio-scraper")
            transport=r.HttpTransport(cell,TOKEN,opener=opener,clock=self.clock,deadline=self.clock()+480)
            with self.assertRaises(r.Fault):transport.request("start",None,30)
            self.assertEqual(len(seen),1)
            self.assertEqual(transport.counts["start"],1)
            self.assertEqual(transport.counts["total"],1)
            query=parse_qs(urlsplit(seen[0][0]).query)
            self.assertEqual(query,{"build":["3.0.1"],"memory":["4096"],"timeout":["120"],
                                    "maxTotalChargeUsd":["0.12"],"restartOnError":["false"],
                                    "forcePermissionLevel":["LIMITED_PERMISSIONS"]})
            self.assertEqual(seen[0][1],"POST")
            self.assertEqual(seen[0][2],canonical(cell.spec["input"]))
            self.assertEqual(seen[0][3],30)
            self.assertNotIn("forcePermissionLevel",cell.spec["options"])
            self.assertNotIn("force_permission_level",cell.spec["options"])
            with self.assertRaises(r.Fault):transport.request("start",None,30)
            self.assertEqual(len(seen),1)
            for spec in plan["cells"][1:]:
                other=r.HttpTransport(r.prepare_cell(plan,spec["cell_id"]),TOKEN,opener=opener,clock=self.clock,deadline=self.clock()+480)
                with self.assertRaises(r.Fault):other.request("start",None,30)
                self.assertNotIn("forcePermissionLevel",parse_qs(urlsplit(seen[-1][0]).query))

    def test_json_403_body_preserved_redacted_privately_with_only_known_machine_type_public(self):
        body={"error":{"type":"full-permission-actor-not-approved","message":"Review required " + TOKEN,
                       "details":{"password":"password-value","Authorization":"Bearer auth-value",
                                  "Cookie":"session=cookie-value; second=another-value","api-key":"api-value",
                                  "url":"https://example.invalid/object?token=url-value&X-Amz-Signature=signed-value",
                                  "elsewhere":"apify_api_" + "A"*40,"userId":"PrivateOwner"}}}
        t,stream=self.error_transport(canonical(body))
        state=self.capture(t)
        self.assertIn("http_error_response",state.evidence)
        error=state.evidence["http_error_response"]
        self.assertEqual(error["read_state"],"complete")
        self.assertFalse(error["truncated"])
        self.assertFalse(error["malformed"])
        self.assertEqual(error["response_format"],"json")
        self.assertIn("Review required",error["body_redacted"])
        self.assertEqual(state.diagnostic["machine_error_type"],"full-permission-actor-not-approved")
        self.assertEqual(state.diagnostic["response_format"],"json")
        private=self.saved[0].decode();public=json.dumps(r.public_result(state))
        for secret in (TOKEN,"password-value","auth-value","cookie-value","another-value","api-value","url-value","signed-value","A"*40,"PrivateOwner"):
            self.assertNotIn(secret,private)
            self.assertNotIn(secret,public)
        self.assertNotIn("Review required",public)
        self.assertNotIn("body_redacted",public)
        self.assertTrue(stream.closed)
        self.assertEqual(state.request_counts["start"],1)

    def test_html_error_body_secret_fields_and_signed_queries_never_reach_public_output(self):
        body=("<html><h1>Forbidden</h1><input name='api_key' value='hidden-value'>"
              "<div data-password=attribute-value>Authorization: Bearer bearer-value</div>"
              "<a href='https://example.invalid/a?signature=signature-value&amp;token=query-value'>link</a>"
              "<p>"+TOKEN+"</p></html>").encode()
        t,stream=self.error_transport(body,"text/html; charset=utf-8")
        state=self.capture(t)
        self.assertIn("http_error_response",state.evidence)
        error=state.evidence["http_error_response"]
        self.assertEqual(error["response_format"],"html")
        self.assertIn("Forbidden",error["body_redacted"])
        for secret in (TOKEN,"hidden-value","attribute-value","bearer-value","signature-value","query-value"):
            self.assertNotIn(secret,self.saved[0].decode())
        self.assertNotIn("Forbidden",json.dumps(r.public_result(state)))
        self.assertTrue(stream.closed)

    def test_unknown_error_type_and_unknown_content_type_remain_private(self):
        t,stream=self.error_transport(canonical({"error":{"type":TOKEN,"message":"private explanation"}}),"application/x-"+TOKEN)
        state=self.capture(t)
        self.assertIn("http_error_response",state.evidence)
        self.assertIsNone(state.diagnostic.get("machine_error_type"))
        self.assertEqual(state.diagnostic["response_format"],"unknown")
        self.assertIn("private explanation",state.evidence["http_error_response"]["body_redacted"])
        self.assertNotIn(TOKEN,self.saved[0].decode())
        self.assertNotIn("private explanation",json.dumps(r.public_result(state)))

    def test_malformed_json_keeps_redacted_bounded_text_and_malformed_label(self):
        t,stream=self.error_transport(b'{"error":{"type":"unknown","api_key":"broken-value","message":"'+TOKEN.encode())
        state=self.capture(t)
        self.assertIn("http_error_response",state.evidence)
        self.assertTrue(state.evidence["http_error_response"]["malformed"])
        self.assertIsNone(state.diagnostic.get("machine_error_type"))
        self.assertNotIn(TOKEN,self.saved[0].decode())
        self.assertNotIn("broken-value",self.saved[0].decode())

    def test_error_body_limit_and_route_deadline_preserve_only_bounded_received_prefix(self):
        self.assertTrue(hasattr(r,"ERROR_RESPONSE_LIMIT"),"bounded HTTP error preservation is missing")
        t,stream=self.error_transport(b"x"*(r.ERROR_RESPONSE_LIMIT+50),"text/plain")
        state=self.capture(t);error=state.evidence["http_error_response"]
        self.assertTrue(error["truncated"])
        self.assertLessEqual(len(error["body_redacted"]),r.ERROR_RESPONSE_LIMIT)
        self.assertLessEqual(sum(stream.read_sizes),r.ERROR_RESPONSE_LIMIT+1)
        t,stream=self.error_transport(b"secret body not yet received","text/plain",slow=11)
        state=self.capture(t);error=state.evidence["http_error_response"]
        self.assertEqual(error["read_state"],"deadline")
        self.assertTrue(error["truncated"])
        self.assertEqual(state.diagnostic["category"],"deadline_exceeded")
        self.assertEqual(state.diagnostic["http_status"],403)
        self.assertLessEqual(len(stream.read_sizes),3)
        self.assertTrue(stream.closed)

    def test_error_exception_string_and_safe_mapping_never_contain_private_body(self):
        t,stream=self.error_transport(canonical({"error":{"type":"insufficient-permissions","message":"private secret response " + TOKEN}}))
        with self.assertRaises(r.Fault) as error:t.request("start",None,30)
        self.assertEqual(error.exception.safe().get("machine_error_type"),"insufficient-permissions")
        self.assertNotIn("private secret response",str(error.exception))
        self.assertNotIn(TOKEN,str(error.exception))
        self.assertNotIn("body_redacted",json.dumps(error.exception.safe()))

    def test_only_verified_403_error_codes_are_public_other_statuses_do_not_infer(self):
        for status,code,expected in ((403,"full-permission-actor-blocked-for-admin","full-permission-actor-blocked-for-admin"),
                                     (400,"full-permission-actor-not-approved",None),(402,"payment-required",None)):
            t,stream=self.error_transport(canonical({"error":{"type":code,"message":"private details"}}),status=status)
            state=self.capture(t)
            self.assertEqual(state.diagnostic.get("machine_error_type"),expected)
            self.assertEqual(state.diagnostic["http_status"],status)
            self.assertNotIn("private details",json.dumps(r.public_result(state)))

    def test_escaped_json_keys_nested_secret_values_and_encoded_signed_url_are_redacted(self):
        body=(b'{"error":{"type":"insufficient-permissions","api\\u005fkey":{"nested":"nested-value"},'
              b'"cookie":["list-value"],"message":"https://example.invalid/a?%74oken=encoded-token&%73ignature=encoded-signature"}}')
        t,stream=self.error_transport(body)
        state=self.capture(t)
        for secret in ("nested-value","list-value","encoded-token","encoded-signature"):
            self.assertNotIn(secret,self.saved[0].decode())
        self.assertEqual(state.diagnostic["machine_error_type"],"insufficient-permissions")

    def test_reversibly_encoded_token_and_known_id_values_cannot_survive_private_redaction(self):
        def encoded(value):return "".join("%%%02X"%ord(char) for char in value)
        def recovered(value):
            for _ in range(12):
                value=html.unescape(unquote(value))
            return value
        vectors=["https://example.invalid/?context="+encoded(TOKEN),
                 "https://example.invalid/?context="+quote(encoded(TOKEN),safe=""),
                 "https://example.invalid/?context="+encoded(TOKEN).lower(),
                 "https://api.apify.com/v2/actor-runs/"+encoded("PrivateRun"),
                 "https://example.invalid/?runId="+encoded("PrivateRun"),
                 "&#79;"+TOKEN[1:],
                 "https://example.invalid/?context="+html.escape(encoded(TOKEN)).replace("%","&#37;")]
        for value in vectors:
            with self.subTest(vector=vectors.index(value)):
                raw=canonical({"error":{"type":"insufficient-permissions","message":value}})
                text,machine,malformed,truncated=r.redacted_error_body(raw,TOKEN,["PrivateRun"],"json")
                self.assertNotIn(TOKEN,recovered(text))
                self.assertNotIn("PrivateRun",recovered(text))
                self.assertEqual(machine,"insufficient-permissions")

    def test_malformed_json_fallback_normalizes_encoded_tokens_ids_and_secret_keys(self):
        encoded=lambda value:"".join("%%%02X"%ord(char) for char in value)
        values=[encoded(TOKEN),quote(encoded(TOKEN),safe=""),"&#79;"+TOKEN[1:],
                "https://api.apify.com/v2/actor-runs/"+encoded("PrivateRun")]
        for value in values:
            raw=('{"error":{"api\\u005fkey":"generic-value","message":"'+value).encode()
            text,machine,malformed,truncated=r.redacted_error_body(raw,TOKEN,["PrivateRun"],"json")
            for _ in range(12):text=html.unescape(unquote(text))
            self.assertNotIn(TOKEN,text)
            self.assertNotIn("PrivateRun",text)
            self.assertNotIn("generic-value",text)
            self.assertTrue(malformed)

    def test_normalization_depth_and_invalid_encoding_fail_closed_without_private_value(self):
        self.assertTrue(hasattr(r,"ERROR_NORMALIZATION_PASSES"),"bounded encoding normalization is missing")
        value="".join("%%%02X"%ord(char) for char in TOKEN)
        for _ in range(r.ERROR_NORMALIZATION_PASSES+3):value=quote(value,safe="")
        for payload in (value,"unsupported %u004F"+TOKEN[1:],"invalid %FF "+TOKEN):
            text,machine,malformed,truncated=r.redacted_error_body(canonical({"error":{"type":"insufficient-permissions","message":payload}}),TOKEN,[],"json")
            self.assertIn("REDACTED_UNRESOLVED_ENCODING",text)
            for _ in range(12):text=html.unescape(unquote(text))
            self.assertNotIn(TOKEN,text)
            self.assertTrue(malformed)

    def test_known_token_and_ids_base64_variants_are_redacted(self):
        for value in (TOKEN,"PrivateRun"):
            for encoder in (base64.b64encode,base64.urlsafe_b64encode):
                encoded=encoder(value.encode()).decode()
                for variant in (encoded,encoded.rstrip("="),quote(encoded,safe="")):
                    text,_,_,_=r.redacted_error_body(canonical({"message":"context="+variant}),TOKEN,["PrivateRun"],"json")
                    self.assertNotIn(encoded,text)
                    self.assertNotIn(encoded.rstrip("="),text)

    def test_truncated_encoded_known_secret_and_id_prefixes_are_masked(self):
        for value in (TOKEN,"PrivateRun"):
            for encoder in (base64.b64encode,base64.urlsafe_b64encode):
                partial=encoder(value.encode()).decode()[:-4]
                raw=('{"message":"https://example.invalid/?context='+partial).encode()
                text,_,malformed,_=r.redacted_error_body(raw,TOKEN,["PrivateRun"],"json")
                self.assertNotIn(partial,text)
                self.assertIn("REDACTED",text)
                self.assertTrue(malformed)

    def test_unbound_private_resource_route_and_identifier_query_values_are_redacted(self):
        values=["https://api.apify.com/v2/actor-runs/ForeignRun999",
                "https://api.apify.com/v2/datasets/ForeignDataset999/items",
                "/v2/key-value-stores/ForeignKv999/records/INPUT",
                "https://api.apify.com/v2/request-queues/ForeignQueue999",
                "https://example.invalid/?userId=ForeignOwner999&runId=ForeignRun999"]
        text,_,_,_=r.redacted_error_body(canonical({"message":values}),TOKEN,[],"json")
        for value in ("ForeignRun999","ForeignDataset999","ForeignKv999","ForeignQueue999","ForeignOwner999"):
            self.assertNotIn(value,text)

    def test_invalid_utf8_and_nul_interleaved_bodies_are_dropped_privately(self):
        for raw in ((TOKEN+" PrivateRun").encode("utf-16-le"),(TOKEN+" PrivateRun").encode("utf-16-be"),
                    b"\xff"+TOKEN.encode()):
            text,machine,malformed,truncated=r.redacted_error_body(raw,TOKEN,["PrivateRun"],"unknown")
            self.assertIn("REDACTED_UNRESOLVED_ENCODING",text)
            self.assertNotIn(TOKEN,text.replace("\x00",""))
            self.assertNotIn("PrivateRun",text.replace("\x00",""))
            self.assertTrue(malformed)
            self.assertIsNone(machine)

    def test_cleanup_http_faults_retained_separately_without_mutating_approved_evidence(self):
        for target in ("fresh_terminal","metadata_dataset","delete_dataset"):
            with self.subTest(operation=target):
                state=self.capture(self.normal())
                approved=canonical(state.evidence);digest=state.plaintext_sha256
                called=[]
                def opener(req,timeout):
                    called.append(req.get_method())
                    if len(called)==1 and target!="fresh_terminal":body=response()
                    elif len(called)<=4 and target=="delete_dataset":body=metadata(tuple(r.STORES)[len(called)-2])
                    else:raise HTTPError(req.full_url,403,TOKEN,{"Content-Type":"application/json"},io.BytesIO(canonical({"error":{"type":"insufficient-permissions","message":"cleanup detail "+TOKEN+" PrivateRun"}})))
                    class Body(io.BytesIO):
                        status=200
                    return Body(canonical(body))
                transport=r.HttpTransport(self.cell,TOKEN,mode="cleanup",identity=state.identity,request_counts=state.request_counts,
                                          opener=opener,clock=self.clock,deadline=self.clock()+120)
                result=self.cleanup(transport,state)
                self.assertIn("http_error_responses",result)
                errors=result["http_error_responses"]
                self.assertEqual(errors[0]["operation"],target)
                self.assertIn("cleanup detail",errors[0]["body_redacted"])
                self.assertNotIn(TOKEN,json.dumps(result))
                self.assertNotIn("PrivateRun",json.dumps(result))
                self.assertEqual(canonical(state.evidence),approved)
                self.assertEqual(state.plaintext_sha256,digest)
                self.assertNotIn("cleanup detail",json.dumps(r.public_result(state)))
                if target!="delete_dataset":self.assertNotIn("DELETE",called)

    def test_private_error_state_roundtrip_retains_machine_type_and_redacted_body(self):
        t,stream=self.error_transport(canonical({"error":{"type":"full-permission-actor-not-approved","message":"preserved detail"}}))
        state=self.capture(t)
        restored=r.restore_private_state(r.serialize_private_state(state),self.plan)
        self.assertEqual(restored.diagnostic,state.diagnostic)
        self.assertEqual(restored.evidence["http_error_response"],state.evidence["http_error_response"])
        self.assertNotIn("preserved detail",json.dumps(r.public_result(restored)))

    def test_error_redaction_decode_deadline_is_labeled_without_losing_received_redacted_body(self):
        t,stream=self.error_transport(canonical({"error":{"type":"insufficient-permissions","message":TOKEN}}))
        self.assertTrue(callable(getattr(r,"redacted_error_body",None)),"redacted body capture is missing")
        original=r.redacted_error_body
        def slow(*args,**kwargs):
            answer=original(*args,**kwargs)
            self.clock.wait(31)
            return answer
        with patch.object(r,"redacted_error_body",side_effect=slow):state=self.capture(t)
        self.assertEqual(state.diagnostic["category"],"deadline_exceeded")
        self.assertEqual(state.diagnostic["stage"],"json_decode")
        self.assertEqual(state.evidence["http_error_response"]["read_state"],"deadline")
        self.assertNotIn(TOKEN,self.saved[0].decode())

    def test_error_reader_failure_retains_partial_safe_body_and_explicit_read_failed(self):
        class Broken:
            closed=False
            calls=0
            def read1(inner,size):
                inner.calls+=1
                if inner.calls==1:return b"safe prefix " + TOKEN.encode()
                raise OSError(TOKEN)
            def close(inner):inner.closed=True
        stream=Broken()
        def opener(req,timeout):raise HTTPError(req.full_url,403,TOKEN,{"Content-Type":"text/plain"},stream)
        state=self.capture(self.http(opener))
        self.assertEqual(state.evidence["http_error_response"]["read_state"],"read_failed")
        self.assertTrue(state.evidence["http_error_response"]["truncated"])
        self.assertIn("safe prefix",state.evidence["http_error_response"]["body_redacted"])
        self.assertNotIn(TOKEN,self.saved[0].decode())
        self.assertTrue(stream.closed)

    def test_typed_absence_404_still_never_reads_error_body_or_adds_http_calls(self):
        state=self.capture(self.normal())
        class ForbiddenBody:
            closed=False
            def read1(inner,size):raise AssertionError("absence proof must not read a response body")
            def close(inner):inner.closed=True
        body=ForbiddenBody()
        def opener(req,timeout):raise HTTPError(req.full_url,404,TOKEN,{"Content-Type":"application/json"},body)
        t=r.HttpTransport(self.cell,TOKEN,mode="cleanup",identity=state.identity,request_counts=state.request_counts,
                          opener=opener,clock=self.clock,deadline=self.clock()+120)
        t.authorize_cleanup(state.identity)
        reply=t.request("absence_dataset",state.identity,10)
        self.assertEqual((reply.status,reply.body),(404,None))
        self.assertTrue(body.closed)
        self.assertEqual(t.counts["absence_dataset"],1)

    def test_export_uses_extra_record_sentinel_and_fixed_fields(self):
        seen=[]
        def opener(req,timeout):
            seen.append(req.full_url);raise URLError(TOKEN)
        state=self.capture(self.normal());t=self.http(opener);t.bind_run(state.identity)
        with self.assertRaises(r.Fault):
            t.request("export",state.identity,10)
        q=parse_qs(urlsplit(seen[0]).query)
        self.assertEqual(q["limit"],["4"])
        self.assertEqual(q["fields"],[",".join(FIELDS)])

    def test_trickling_response_uses_read1_and_stops_at_route_deadline(self):
        class Trickle:
            status=201
            def __init__(inner):
                inner.body=io.BytesIO(canonical(response()));inner.buffered_reads=0;inner.chunk_reads=0;inner.closed=False
            def read(inner,size):
                inner.buffered_reads+=1
                self.clock.wait(11)
                return inner.body.read(size)
            def read1(inner,size):
                inner.chunk_reads+=1
                self.clock.wait(11)
                return inner.body.read(min(size,1))
            def close(inner):inner.closed=True
        body=Trickle();t=self.http(lambda *a,**kw:body)
        with self.assertRaises(r.Fault) as error:
            t.request("start",None,30)
        self.assertEqual(error.exception.category,"deadline_exceeded")
        self.assertEqual(body.buffered_reads,0)
        self.assertEqual(body.chunk_reads,3)
        self.assertTrue(body.closed)
        self.assertEqual(t.counts["start"],1)

    def test_route_deadline_includes_connection_time_and_json_decode(self):
        class Body:
            status=201
            def __init__(inner):inner.body=io.BytesIO(canonical(response()));inner.closed=False
            def read(inner,size):return inner.body.read(size)
            def read1(inner,size):return inner.body.read(size)
            def close(inner):inner.closed=True
        body=Body();t=self.http(lambda *a,**kw:body)
        original_loads=r.json.loads
        def slow_decode(value,*args,**kwargs):
            result=original_loads(value,*args,**kwargs)
            self.clock.wait(31)
            return result
        with patch.object(r.json,"loads",side_effect=slow_decode):
            with self.assertRaises(r.Fault) as error:t.request("start",None,30)
        self.assertEqual(error.exception.category,"deadline_exceeded")
        self.assertTrue(body.closed)

    def test_http_late_decoded_original_active_revokes_before_time_and_scope_checks(self):
        state=self.capture(self.normal())
        class Body:
            status=200
            def __init__(inner):inner.body=io.BytesIO(canonical(response("RUNNING",options={},actId="ForeignActor")))
            def read(inner,size):return inner.body.read(size)
            def read1(inner,size):return inner.body.read(size)
            def close(inner):pass
        t=r.HttpTransport(self.cell,TOKEN,mode="cleanup",identity=state.identity,request_counts=state.request_counts,
                          opener=lambda *a,**kw:Body(),clock=self.clock,deadline=self.clock()+120)
        original_loads=r.json.loads
        def slow_decode(value,*args,**kwargs):
            result=original_loads(value,*args,**kwargs)
            self.clock.wait(121)
            return result
        with patch.object(r.json,"loads",side_effect=slow_decode):
            with self.assertRaises(r.Fault) as error:t.request("fresh_terminal",state.identity,10)
        self.assertEqual(error.exception.category,"latest_run_active")
        self.assertTrue(t.latest_active)
        self.assertEqual(t.latest_active_status,"RUNNING")
        with self.assertRaises(r.Fault):t.authorize_cleanup(state.identity)
        with self.assertRaises(r.Fault):t.request("metadata_dataset",state.identity,10)
        self.assertEqual(t.counts["total"],6)

    def test_late_http_404_cannot_bypass_absence_route_deadline(self):
        state=self.capture(self.normal())
        def opener(req,timeout):
            self.clock.wait(11)
            raise HTTPError(req.full_url,404,TOKEN,{},io.BytesIO(TOKEN.encode()))
        t=r.HttpTransport(self.cell,TOKEN,mode="cleanup",identity=state.identity,request_counts=state.request_counts,
                          opener=opener,clock=self.clock,deadline=self.clock()+120)
        t.authorize_cleanup(state.identity)
        with self.assertRaises(r.Fault) as error:t.request("absence_dataset",state.identity,10)
        self.assertEqual(error.exception.category,"deadline_exceeded")
        self.assertEqual(error.exception.http_status,404)
        self.assertEqual(t.counts["absence_dataset"],1)

    def test_connection_setup_overrun_stops_before_any_body_read(self):
        class Body:
            status=201
            def read1(inner,size):raise AssertionError("body read after route expired")
            def close(inner):inner.closed=True
        body=Body();body.closed=False
        def opener(req,timeout):
            self.clock.wait(31)
            return body
        t=self.http(opener)
        with self.assertRaises(r.Fault) as error:t.request("start",None,30)
        self.assertEqual(error.exception.category,"deadline_exceeded")
        self.assertEqual(error.exception.http_status,201)
        self.assertTrue(body.closed)

    def test_http_routes_fixed_auth_header_only_and_no_automatic_retry(self):
        seen = []
        def opener(req, timeout):
            seen.append((req.full_url, req.get_method(), req.headers, timeout))
            raise URLError(TOKEN)
        t = self.http(opener)
        with self.assertRaises(r.Fault) as ctx:
            t.request("start", None, 30)
        self.assertEqual(ctx.exception.category, "connection_error")
        self.assertEqual(len(seen), 1)
        self.assertNotIn(TOKEN, seen[0][0])
        self.assertEqual(urlsplit(seen[0][0]).hostname, "api.apify.com")
        self.assertEqual(seen[0][2]["Authorization"], "Bearer " + TOKEN)
        self.assertEqual(parse_qs(urlsplit(seen[0][0]).query)["restartOnError"], ["false"])
        with self.assertRaises(r.Fault):
            t.request("start", None, 30)
        with self.assertRaises(r.Fault):
            t.request("https://foreign.invalid", None, 30)
        self.assertEqual(len(seen), 1)

    def test_unreadable_http_error_body_is_labeled_and_numeric_status_is_preserved(self):
        class BadBody:
            def read(self, *args):
                raise AssertionError("buffered reads are forbidden")
            def read1(self,*args):
                raise OSError(TOKEN)
            def close(self):
                pass
        for status in (400, 401, 403, 302):
            def opener(req, timeout, status=status):
                raise HTTPError("https://api.apify.com/v2/acts/x/runs", status, TOKEN, {}, BadBody())
            t = self.http(opener)
            with self.assertRaises(r.Fault) as ctx:
                t.request("start", None, 30)
            self.assertEqual(ctx.exception.http_status, status)
            self.assertEqual(ctx.exception.error_response["read_state"],"read_failed")
            self.assertNotIn(TOKEN, str(ctx.exception))

    def test_http_body_limit_json_failures_and_private_error_sanitization(self):
        class Body:
            status = 201
            def __init__(self, body):
                self.body = io.BytesIO(body)
            def read(self, n):
                return self.body.read(n)
            def read1(self, n):
                return self.body.read(n)
            def close(self):
                pass
        for body, category in ((b"x" * 131073, "response_too_large"), (TOKEN.encode(), "invalid_json"),
                               (b'{"value":NaN}', "invalid_json"), (b'{"a":1,"a":2}', "invalid_json")):
            t = self.http(lambda req, timeout, body=body: Body(body))
            with self.assertRaises(r.Fault) as ctx:
                t.request("start", None, 30)
            self.assertEqual(ctx.exception.category, category)
            self.assertEqual(ctx.exception.http_status, 201)
            self.assertNotIn(TOKEN, str(ctx.exception))

    def test_cleanup_transport_has_no_start_and_restores_total_call_budget(self):
        state = self.capture(self.normal())
        counts = {**r.OP_LIMITS, "total": sum(r.OP_LIMITS.values())}
        t = r.HttpTransport(self.cell, TOKEN, mode="cleanup", identity=state.identity,
                            request_counts=counts,
                            opener=lambda *a, **kw: self.fail("HTTP after exhausted budget"),
                            clock=self.clock, deadline=self.clock() + 120)
        for operation in ("start", "fresh_terminal", "delete_dataset"):
            with self.assertRaises(r.Fault):
                t.request(operation, state.identity, 10)

    def test_raw_http_active_original_id_revokes_even_with_wrong_options(self):
        state = self.capture(self.normal())
        payload = canonical(response("RUNNING", options={}))
        class Body:
            status = 200
            def read(self, n):
                nonlocal payload
                chunk, payload = payload[:n], payload[n:]
                return chunk
            def read1(self,n):
                return self.read(n)
            def close(self):
                pass
        t = r.HttpTransport(self.cell, TOKEN, mode="cleanup", identity=state.identity,
                            request_counts=state.request_counts, opener=lambda *a, **kw: Body(),
                            clock=self.clock, deadline=self.clock() + 120)
        with self.assertRaises(r.Fault) as ctx:
            t.request("fresh_terminal", state.identity, 10)
        self.assertEqual(ctx.exception.category, "latest_run_active")
        with self.assertRaises(r.Fault):
            t.authorize_cleanup(state.identity)
        with self.assertRaises(r.Fault):
            t.request("delete_dataset", state.identity, 10)


class AvailabilityTests(unittest.TestCase):
    def test_closed_runner_module_exists_for_review(self):
        self.assertTrue(Path(__file__).with_name("runner.py").is_file(),
                        "the separately guarded study runner has not been implemented")


if __name__ == "__main__":
    unittest.main()
