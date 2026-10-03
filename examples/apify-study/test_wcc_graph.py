"""Synthetic single-cell counterfactual and typed absence; no provider calls."""
import copy
from datetime import timedelta
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import runner as r
import workflow_driver as driver
import test_runner as f

RAW=(Path(__file__).parent/'capability-graph-plan.json').read_bytes()
PLAN=json.loads(RAW)

class GraphTests(unittest.TestCase):
    def setUp(self):
        self.clock=f.Clock()
        for key,value in (('RUNNER_READY',True),('GRAPH_READY',True)):
            p=patch.object(r,key,value);p.start();self.addCleanup(p.stop)
        self.cell=r.prepare_cell(PLAN,r.GRAPH_CELL_ID)

    def response(self):
        spec=self.cell.spec
        value=f.response(actId=spec['actor_id'],buildNumber=spec['build'])
        value['data']['options']=dict(spec['options'],maxTotalChargeUsd=0.08)
        return value

    def metas(self):return [r.Reply(200,f.metadata(k,actId=self.cell.spec['actor_id']))for k in r.STORES]

    def capture(self):
        rows=[{'url':self.cell.spec['output']['allowed_urls'][0],'text':'synthetic incomplete output','markdown':'synthetic incomplete output'}]
        transport=f.FakeTransport([r.Reply(201,self.response()),r.Reply(200,rows)]+self.metas())
        state=r.run_until_capture(transport,self.cell,
            lambda raw:dict(plaintext_sha256=r.sha(raw),ciphertext_sha256='c'*64,remote_file_readback_verified=True),
            budget=r.StudyBudget(PLAN),clock=self.clock,wait=self.clock.wait,
            utcnow=lambda:f.STAMP+timedelta(minutes=6))
        self.assertTrue(state.capture_verified)
        return state

    def test_exact_one_flag_and_new_identity_preserve_the_original_thirty_assignments(self):
        core=json.loads((driver.ROOT/'capability-plan.json').read_bytes())
        expected=copy.deepcopy(next(c for c in core['cells']if c['cell_id']=='cap-r1-website-content-crawler'))
        expected['cell_id']=r.GRAPH_CELL_ID;expected['input']['ignoreCanonicalUrl']=True
        self.assertEqual(self.cell.spec,expected)
        self.assertEqual(r.load_reviewed_plan(RAW),PLAN)
        self.assertEqual(driver.smoke_manifest('wcc-ignore-canonical'),[r.GRAPH_CELL_ID])
        self.assertEqual(driver.plan(r.GRAPH_CELL_ID),PLAN)
        self.assertEqual(len(self.cell.spec['output']['allowed_urls']),30)

    def test_new_stage_guards_are_independent_and_reject_before_secret_access(self):
        with patch.object(r,'GRAPH_READY',False),self.assertRaises(r.Fault)as e:
            r.execute(PLAN,r.GRAPH_CELL_ID,opt_in=True,environ=f.ForbiddenEnvironment())
        self.assertEqual(e.exception.category,'guard_closed')
        with patch.object(r,'CONCURRENCY_READY',False),self.assertRaises(r.Fault):
            driver.capture(driver.PILOT_CELLS[0],environ=f.ForbiddenEnvironment())
        for old in driver.ALLOWED_CELLS+driver.CAPABILITY_CELLS:
            with patch.object(driver,'plan',side_effect=AssertionError('completed source read')):
                with self.subTest(old=old),self.assertRaises(r.Fault):driver.capture(old,environ=f.ForbiddenEnvironment())

    def test_private_identity_restore_and_cleanup_require_three_record_not_found_types(self):
        state=self.capture();initial=copy.deepcopy(state.evidence)
        state=r.restore_private_state(r.serialize_private_state(state),PLAN)
        transport=f.FakeTransport([r.Reply(200,self.response())]+self.metas()+[r.Reply(204,None),r.Reply(404,None,'record-not-found')]*3)
        approval=dict(plaintext_sha256=state.plaintext_sha256,ciphertext_sha256=state.ciphertext_sha256,scope_approved=True)
        result=r.cleanup_verified_capture(transport,state,approval,verify_local_approval=lambda *a:True,
            clock=self.clock,utcnow=lambda:f.STAMP+timedelta(minutes=7))
        self.assertEqual(result['cleanup_state'],'complete')
        self.assertEqual(result['absence_types'],{k:'record-not-found'for k in r.STORES})
        self.assertEqual(state.request_counts['total'],15);self.assertEqual(state.evidence,initial)
        self.assertEqual(set(state.identity),set(r.IDENTITY_FIELDS)|{'startedAt','finishedAt','build','options','status'})

    def test_bare_404_is_retained_as_partial_cleanup_with_no_repeated_delete(self):
        state=self.capture();transport=f.FakeTransport([r.Reply(200,self.response())]+self.metas()+[r.Reply(204,None),r.Reply(404,None)]*3)
        proof=dict(plaintext_sha256=state.plaintext_sha256,ciphertext_sha256=state.ciphertext_sha256,scope_approved=True)
        result=r.cleanup_verified_capture(transport,state,proof,verify_local_approval=lambda *a:True,
            clock=self.clock,utcnow=lambda:f.STAMP+timedelta(minutes=7))
        self.assertEqual(result['cleanup_state'],'residual');self.assertTrue(result['owner_attention_required'])
        self.assertEqual(result['absence_types'],{})
        self.assertEqual(sum(op.startswith('delete_')for op,_,_ in transport.requests),3)
        self.assertEqual(state.request_counts['start'],1)

    def test_native_success_and_http_error_404_paths_parse_fixed_type(self):
        for error in (False,True):
            opened=[]
            class Response(f.HttpReply):headers={'Content-Type':'application/json; charset=utf-8'}
            def opener(req,timeout):
                opened.append(req.full_url)
                body=b'{"error":{"type":"record-not-found","message":"synthetic missing resource"}}'
                if error:raise HTTPError(req.full_url,404,'synthetic',Response.headers,io.BytesIO(body))
                return Response(404,body)
            counter=r.empty_counts();counter.update(start=1,total=1)
            identity=r.validate_run(self.response()['data'],self.cell)
            t=r.HttpTransport(self.cell,f.TOKEN,mode='cleanup',identity=identity,request_counts=counter,opener=opener,clock=self.clock)
            t.authorize_cleanup(identity)
            reply=t.request('absence_dataset',identity,10)
            self.assertEqual(reply.absence_type,'record-not-found');self.assertIsNone(reply.body)
            self.assertEqual(opened,['https://api.apify.com/v2/datasets/PrivateDataset'])

    def test_malformed_duplicate_oversized_or_wrong_type_404_cannot_prove_absence(self):
        t=r.HttpTransport(self.cell,f.TOKEN,clock=self.clock)
        cases=[(b'{"error":{"type":"other"}}','application/json'),
            (b'{"error":{"type":"record-not-found","type":"record-not-found"}}','application/json'),
            (b'{"error":{"type":"record-not-found"},"extra":NaN}','application/json'),
            (b'x'*16385,'application/json'),(b'{"error":{"type":"record-not-found"}}','text/html')]
        for raw,mime in cases:
            response=f.HttpReply(404,raw);response.headers={'Content-Type':mime}
            with self.subTest(size=len(raw),mime=mime),self.assertRaises(r.Fault):t.typed_absence(response,self.clock()+10)

if __name__=='__main__':unittest.main()
