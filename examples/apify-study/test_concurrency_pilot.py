"""Synthetic finite pilot regressions. No network, real environment or provider."""
import contextlib
import copy
from datetime import timedelta
from decimal import Decimal
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import runner as r
import workflow_driver as driver
import test_runner as f


RAW = (Path(__file__).parent / 'concurrency-plan.json').read_bytes()
PLAN = json.loads(RAW)
IDS = tuple('concurrency-pilot-playwright-c%d' % n for n in (1, 5, 10))
COUNTERS = ('native_active_tasks_start', 'native_active_tasks_end',
            'native_desired_tasks_start', 'native_desired_tasks_end')


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.plan = copy.deepcopy(PLAN)
        for key, value in (('RUNNER_READY', True),
                           ('CONCURRENCY_READY', True),
                           ('REVIEWED_CONCURRENCY_PLAN_SHA256', r.sha(r.canonical(self.plan))),
                           ('REVIEWED_CONCURRENCY_PLAN_FILE_SHA256', r.sha(RAW))):
            p = patch.object(r, key, value, create=True); p.start(); self.addCleanup(p.stop)
        self.clock = f.Clock()

    def cell(self, index=0):
        return r.prepare_cell(self.plan, IDS[index])

    def response(self, status='SUCCEEDED', index=0):
        spec = self.cell(index).spec
        value = f.response(status, actId=spec['actor_id'], buildNumber=spec['build'])
        value['data']['options'] = dict(spec['options'], maxTotalChargeUsd=0.20)
        return value

    def metas(self):
        return [r.Reply(200, f.metadata(k, actId=self.cell().spec['actor_id'])) for k in r.STORES]

    def rows(self, index=0):
        return copy.deepcopy(self.cell(index).spec['output']['expected_records'])

    def persist(self, blob):
        return dict(plaintext_sha256=r.sha(blob), ciphertext_sha256='c'*64,
                    remote_file_readback_verified=True)

    def capture(self, transport, **kw):
        return r.run_until_capture(transport, self.cell(), self.persist,
            budget=r.StudyBudget(self.plan), clock=self.clock, wait=self.clock.wait,
            utcnow=lambda: f.STAMP + timedelta(minutes=6), **kw)

    def test_separate_closed_pins_and_minimum_before_secret_access(self):
        for key, value in (('RUNNER_READY', False), ('REVIEWED_CONCURRENCY_PLAN_SHA256', None)):
            with self.subTest(key=key), patch.object(r, key, value), self.assertRaises(r.Fault) as err:
                r.execute(self.plan, IDS[0], opt_in=True, environ=f.ForbiddenEnvironment())
            self.assertEqual(err.exception.category, 'guard_closed')
        with self.assertRaises(r.Fault) as err:
            r.execute(self.plan, IDS[0], opt_in=True, environ=f.ForbiddenEnvironment(),
                deadline=self.clock()+499, clock=self.clock)
        self.assertEqual(err.exception.category, 'deadline_exceeded')
        self.assertEqual(r.load_reviewed_plan(RAW), self.plan)
        with self.assertRaises(r.Fault): r.load_reviewed_plan(r.canonical(self.plan))

    def test_rehashed_wrong_identity_controls_and_shape_still_rejected(self):
        changes = [('actor_id','ForeignActor'), ('build','1.0.23'),
                   ('force_permission_level','FULL_PERMISSIONS')]
        for key, value in changes:
            bad=copy.deepcopy(self.plan); bad['cells'][0][key]=value
            with self.subTest(key=key), patch.object(r,'REVIEWED_CONCURRENCY_PLAN_SHA256',r.sha(r.canonical(bad))):
                with self.assertRaises(r.Fault): r.validate_plan(bad)
        for change in ('order','cap','memory','timeout','concurrency','records','reserve','policy'):
            bad=copy.deepcopy(self.plan); spec=bad['cells'][0]
            if change=='order': bad['cells'][0],bad['cells'][1]=bad['cells'][1],bad['cells'][0]
            elif change=='cap': spec['options']['maxTotalChargeUsd']='0.21'
            elif change=='memory': spec['options']['memoryMbytes']=16384
            elif change=='timeout': spec['options']['timeoutSecs']=301
            elif change=='concurrency': spec['input']['maxConcurrency']=2
            elif change=='records': spec['output']['max_records']=151
            elif change=='reserve': bad['aggregate_reserved_usd']='0.67'
            else: bad['controller_policy']['polls']=6
            with self.subTest(change=change), patch.object(r,'REVIEWED_CONCURRENCY_PLAN_SHA256',r.sha(r.canonical(bad))):
                with self.assertRaises(r.Fault): r.validate_plan(bad)

    def test_exact_three_budget_claims_and_no_repeat(self):
        budget=r.StudyBudget(self.plan)
        for index in range(3): budget.claim(self.cell(index))
        self.assertEqual(budget.reserved_usd, Decimal('0.66'))
        with self.assertRaises(r.Fault): budget.claim(self.cell())

    def test_five_polls_zero_settle_and_twenty_total_with_private_restore(self):
        replies=[r.Reply(201,self.response('READY'))]+[r.Reply(200,self.response('RUNNING'))]*4
        replies += [r.Reply(200,self.response()),r.Reply(200,self.rows())]+self.metas()
        transport=f.FakeTransport(replies,settle=True)
        state=self.capture(transport)
        self.assertEqual(state.request_counts['poll'],5)
        self.assertEqual(state.request_counts['settle'],0)
        self.assertEqual(self.clock(),100)
        self.assertTrue(state.capture_verified)
        self.assertEqual(len(state.evidence['records']),150)
        state=r.restore_private_state(r.serialize_private_state(state),self.plan)
        initial=copy.deepcopy(state.evidence)
        cleanup=f.FakeTransport([r.Reply(200,self.response())]+self.metas()+[r.Reply(204,None),r.Reply(404,None,'record-not-found')]*3)
        approval=dict(plaintext_sha256=state.plaintext_sha256,ciphertext_sha256=state.ciphertext_sha256,scope_approved=True)
        result=r.cleanup_verified_capture(cleanup,state,approval,verify_local_approval=lambda *args: True,
            clock=self.clock,utcnow=lambda:f.STAMP+timedelta(minutes=7))
        self.assertEqual(result['cleanup_state'],'complete')
        self.assertEqual(state.request_counts['total'],20)
        self.assertEqual(state.evidence,initial)
        with self.assertRaises(r.Fault): r.consume(state.request_counts,'poll','capture','CONCURRENCY_PILOT')

    def test_fifth_still_active_preserves_full_failure_and_no_sixth_or_export(self):
        transport=f.FakeTransport([r.Reply(201,self.response('READY'))]+[r.Reply(200,self.response('RUNNING'))]*5,settle=True)
        state=self.capture(transport)
        self.assertTrue(state.latest_active)
        self.assertFalse(state.capture_verified)
        self.assertEqual([x[0] for x in transport.requests],['start']+['poll']*5)
        self.assertEqual(state.request_counts['total'],6)
        self.assertEqual(state.diagnostic['category'],'terminal_unconfirmed')

    def test_nullable_counter_projection_and_configured_ceiling_not_truth_change(self):
        rows=self.rows(); rows[0].update({key:None for key in COUNTERS})
        rows[1].update({key:1 for key in COUNTERS},duration_ms=0,elapsed_ms=Decimal('2.5'))
        output=r.validate_output(rows,self.cell())
        self.assertIsNone(output[0][COUNTERS[0]])
        self.assertEqual(output[1][COUNTERS[0]],1)
        for invalid in (True,0,2,-1,Decimal('NaN'),'1',1.5):
            bad=self.rows();bad[0][COUNTERS[0]]=invalid
            with self.subTest(value=str(invalid)),self.assertRaises(r.OutputFault):r.validate_output(bad,self.cell())
        bad=self.rows();bad.append(bad[0])
        with self.assertRaises(r.OutputFault) as err:r.validate_output(bad,self.cell())
        self.assertLessEqual(len(err.exception.records),151)

    def test_http_exact_native_query_and_export_sentinel(self):
        seen=[]
        replies=[f.HttpReply(201,r.canonical(self.response())),f.HttpReply(200,r.canonical(self.rows()))]
        def opener(req,timeout):seen.append((req,timeout));return replies.pop(0)
        transport=r.HttpTransport(self.cell(),f.TOKEN,opener=opener,clock=self.clock)
        self.assertEqual(transport.deadline,self.clock()+540)
        start=transport.request('start',{},30)
        transport.bind_run(r.validate_run(start.body['data'],self.cell()))
        transport.request('export',transport.identity,10)
        query=parse_qs(urlsplit(seen[0][0].full_url).query)
        self.assertEqual(query,dict(build=['1.0.22'],memory=['8192'],timeout=['300'],
            maxTotalChargeUsd=['0.20'],restartOnError=['false'],forcePermissionLevel=['LIMITED_PERMISSIONS']))
        self.assertEqual(json.loads(seen[0][0].data)['maxConcurrency'],1)
        self.assertEqual(parse_qs(urlsplit(seen[1][0].full_url).query)['limit'],['151'])
        self.assertNotIn(f.TOKEN,seen[0][0].full_url)
        with self.assertRaises(r.Fault):transport.request('settle',transport.identity,65)
        self.assertEqual(len(seen),2)

    def test_late_same_id_active_revocation_survives_pilot_stage(self):
        state=self.capture(f.FakeTransport([r.Reply(201,self.response()),r.Reply(200,self.rows())]+self.metas()))
        fresh=self.response('RUNNING');fresh['data']['options']={}
        transport=f.FakeTransport([r.Reply(200,fresh)])
        original_request=transport.request
        def late(*args):
            reply=original_request(*args);self.clock.wait(121);return reply
        transport.request=late
        approval=dict(plaintext_sha256=state.plaintext_sha256,ciphertext_sha256=state.ciphertext_sha256,scope_approved=True)
        result=r.cleanup_verified_capture(transport,state,approval,verify_local_approval=lambda *args:True,
            clock=self.clock,utcnow=lambda:f.STAMP+timedelta(minutes=7))
        self.assertEqual(result['cleanup_state'],'blocked')
        self.assertTrue(state.latest_active)
        self.assertEqual([x[0] for x in transport.requests],['fresh_terminal'])

    def test_public_projection_omits_private_measurements(self):
        state=self.capture(f.FakeTransport([r.Reply(201,self.response()),r.Reply(200,self.rows())]+self.metas()))
        public=r.canonical(r.public_result(state)).decode()
        self.assertEqual(r.public_result(state)['stage'],'CONCURRENCY_PILOT')
        for forbidden in (*COUNTERS,'records','usage_total_usd','billing_evidence','PrivateOwner',f.TOKEN):
            self.assertNotIn(forbidden,public)

    def test_fixed_private_driver_manifest_file_and_closed_guard(self):
        class NoSecret(dict):
            def get(self,key,*args):
                if key=='APIFY_TOKEN':raise AssertionError('Secret access before closed guard')
                return super().get(key,*args)
        with patch.object(driver.os,'environ',f.ForbiddenEnvironment()),patch.object(driver,'plan',side_effect=AssertionError()):
            self.assertEqual(driver.smoke_manifest('concurrency-pilot'),list(IDS))
        self.assertEqual(driver.plan(IDS[0]),self.plan)
        for bad in ('concurrency-pilot-playwright-c2','concurrency-pilot-all'):
            with self.assertRaises(r.Fault):driver.check_cell(bad)
        with patch.object(r,'RUNNER_READY',False),patch('sys.argv',['workflow_driver.py','capture','--cell',IDS[0],'--execute']),\
             patch.object(driver.os,'environ',NoSecret()),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(driver.main(),1)
        self.assertEqual(json.loads(out.getvalue())['stage'],'CONCURRENCY_PILOT')


if __name__=='__main__':unittest.main()
