"""Offline tests for all-build/all-status coverage, never starts or deletes."""
from copy import deepcopy
import json
import io
import unittest
from unittest.mock import patch
from calibration import PUBLIC_ACTOR_ID, build_plan
import coverage as c

END='2026-10-02T15:00:00Z'

def row(number=0, build='other-build', status='FAILED'):
    return {'id':'fakeRun'+str(number),'actId':PUBLIC_ACTOR_ID,'userId':'fakeUser',
            'startedAt':'2026-10-02T14:10:50Z','buildNumber':build,'status':status,
            'defaultKeyValueStoreId':'fakeKv'+str(number)}

class Fake:
    def __init__(self, rows=None):
        self.rows=[] if rows is None else rows; self.calls=[]; self.total=len(self.rows)
        self.inputs={r['defaultKeyValueStoreId']:build_plan(c.BUILD)['input'] for r in self.rows}
    def get(self, stage, **kwargs):
        self.calls.append((stage,kwargs))
        if stage=='identity': return {'data':{'id':'fakeUser','username':'PRIVATE_ACCOUNT'}}
        if stage=='page':
            offset=kwargs['offset']; items=self.rows[offset:offset+c.LIMIT]
            return {'data':{'offset':offset,'limit':c.LIMIT,'count':len(items),'total':self.total,'items':items}}
        if stage=='run': return {'data':next(r for r in self.rows if r['id']==kwargs['run_id'])}
        if stage=='input': return self.inputs[kwargs['kv_id']]
        raise AssertionError

class CoverageTests(unittest.TestCase):
    def test_complete_empty_is_only_retry_eligible_case(self):
        fake=Fake(); result=c.check_coverage(fake,END)
        self.assertTrue(result['coverage_complete']); self.assertTrue(result['retry_eligible'])
        self.assertEqual(result['listed_run_count'],0); self.assertEqual(len(fake.calls),2)

    def test_any_build_any_status_candidate_prevents_retry(self):
        for build in (None,'3.0.26','3.0.25'):
            for status in ('READY','RUNNING','FAILED','SUCCEEDED','TIMED-OUT','ABORTED'):
                fake=Fake([row(build=build,status=status)]); result=c.check_coverage(fake,END)
                self.assertTrue(result['coverage_complete']); self.assertFalse(result['retry_eligible'])
                self.assertEqual(result['matching_test_inputs'],1)
                self.assertEqual(len(fake.calls),4)

    def test_complete_second_page_uses_frozen_window(self):
        fake=Fake([row(i) for i in range(6)]); result=c.check_coverage(fake,END)
        self.assertTrue(result['coverage_complete']); self.assertFalse(result['retry_eligible'])
        self.assertEqual([kw['offset'] for stage,kw in fake.calls if stage=='page'],[0,5])
        self.assertTrue(all(kw['end']==END for stage,kw in fake.calls if stage=='page'))
        self.assertEqual(len(fake.calls),15)

    def test_over_bound_remains_incomplete_no_candidate_followup(self):
        fake=Fake([row(i) for i in range(11)]); result=c.check_coverage(fake,END)
        self.assertFalse(result['coverage_complete']); self.assertFalse(result['retry_eligible'])
        self.assertEqual(len(fake.calls),2)

    def test_changed_total_between_pages_remains_incomplete(self):
        class Changing(Fake):
            def get(self,stage,**kw):
                result=super().get(stage,**kw)
                if stage=='page' and kw['offset']==5: result['data']['total']=7
                return result
        result=c.check_coverage(Changing([row(i) for i in range(6)]),END)
        self.assertFalse(result['coverage_complete']); self.assertFalse(result['retry_eligible'])

    def test_duplicate_or_out_of_window_or_wrong_actor_rejected(self):
        for rows in ([row(),row()], [dict(row(),startedAt='2026-10-02T13:59:59Z')],
                     [dict(row(),actId='otherActor')]):
            result=c.check_coverage(Fake(rows),END)
            self.assertFalse(result['coverage_complete']); self.assertFalse(result['retry_eligible'])

    def test_foreign_owner_is_not_followed(self):
        fake=Fake([dict(row(),userId='otherUser')]); result=c.check_coverage(fake,END)
        self.assertFalse(result['retry_eligible']); self.assertEqual(len(fake.calls),2)

    def test_changed_run_id_or_kv_or_owner_prevents_input_read(self):
        for field,value in [('id','otherRun'),('userId','otherUser'),('defaultKeyValueStoreId','otherKv')]:
            class Changing(Fake):
                def get(self,stage,**kw):
                    result=deepcopy(super().get(stage,**kw))
                    if stage=='run': result['data'][field]=value
                    return result
            fake=Changing([row()]); result=c.check_coverage(fake,END)
            self.assertFalse(result['retry_eligible']); self.assertEqual(len(fake.calls),3)

    def test_different_input_never_means_retry_is_safe(self):
        fake=Fake([row()]); fake.inputs['fakeKv0']={'maxConcurrency':True,'PRIVATE_VALUE':'sensitive'}
        result=c.check_coverage(fake,END)
        self.assertFalse(result['retry_eligible']); self.assertEqual(result['matching_test_inputs'],0)
        for value in ('fakeRun0','fakeKv0','fakeUser','PRIVATE_ACCOUNT','PRIVATE_VALUE','sensitive'):
            self.assertNotIn(value,json.dumps(result))

    def test_http_or_network_failure_is_incomplete_and_sanitized(self):
        class Broken(Fake):
            def get(self,stage,**kw): raise c.ReadFailure(401,'authentication_rejected')
        result=c.check_coverage(Broken(),END)
        self.assertFalse(result['retry_eligible']); self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['reads'][0]['http_status'],401)

    def test_query_includes_broad_time_and_no_status_or_build_filter(self):
        query=c.page_path(5,END)
        self.assertIn('offset=5',query); self.assertIn('limit=5',query)
        self.assertNotIn('status=',query); self.assertNotIn('build',query)
        self.assertNotIn('desc=',query)
        self.assertIn('14%3A00%3A00Z',query)

    def test_invalid_page_types_or_counts_do_not_claim_complete(self):
        for change in ({'count':1},{'total':True},{'offset':1},{'limit':1000}):
            class Broken(Fake):
                def get(self,stage,**kw):
                    result=super().get(stage,**kw)
                    if stage=='page': result['data'].update(change)
                    return result
            self.assertFalse(c.check_coverage(Broken(),END)['retry_eligible'])

class CoverageTransportTests(unittest.TestCase):
    def test_complete_maximum_uses23_fixed_gets_no_more(self):
        fake=Fake([row(i) for i in range(10)])
        class Opener:
            calls=[]
            def open(self,request,timeout):
                self.calls.append(request)
                path=request.full_url
                if '/users/me' in path: value=fake.get('identity')
                elif '/actors/' in path: value=fake.get('page',offset=5 if 'offset=5' in path else 0,end=END)
                elif '/actor-runs/' in path: value=fake.get('run',run_id=path.rsplit('/',1)[-1])
                else: value=fake.get('input',kv_id=path.split('/key-value-stores/')[1].split('/')[0])
                response=io.BytesIO(json.dumps(value).encode()); response.status=200; return response
        opener=Opener(); transport=c.CoverageTransport('FAKE_TOKEN',END,opener=opener)
        with patch.object(c,'MAX_READS',23): result=c.check_coverage(transport,END)
        self.assertTrue(result['correlation_complete']); self.assertEqual(len(opener.calls),23)
        self.assertTrue(all(r.get_method()=='GET' and 'FAKE_TOKEN' not in r.full_url for r in opener.calls))
        for stage in ('identity','page','run','input','POST','DELETE'):
            with self.assertRaises(c.ReadFailure): transport.get(stage)
        self.assertEqual(len(opener.calls),23)

    def test_remaining21_limit_is_honored_after_failed_first_check(self):
        fake=Fake([row(i) for i in range(10)])
        result=c.check_coverage(fake,END)
        self.assertEqual(len(fake.calls),21); self.assertEqual(result['requests_attempted'],21)
        self.assertFalse(result['correlation_complete']); self.assertFalse(result['retry_eligible'])

    def test_error_body_only_emits_known_type_and_query_hint(self):
        body={'error':{'type':'invalid-input','message':'startedBefore wrong PRIVATE_TOKEN_VALUE'},
              'proxy':{'password':'PRIVATE_PROXY'},'id':'PRIVATE_ACCOUNT'}
        error=c.SafeQueryFailure(400,'request_rejected',body)
        self.assertEqual(error.provider_error_type,'invalid-input'); self.assertEqual(error.parameter_hint,'startedBefore')
        self.assertNotIn('PRIVATE',str(error))
        unknown=c.SafeQueryFailure(400,'request_rejected',{'error':{'type':'PRIVATE_TOKEN','message':'PRIVATE_OTHER'}})
        self.assertIsNone(unknown.provider_error_type); self.assertIsNone(unknown.parameter_hint)

    def test_freeze_end_has_three_fractional_digits_and_utc(self):
        self.assertRegex(c.freeze_end(),r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')

    def test_failed_page_cannot_be_retried(self):
        class Opener:
            calls=0
            def open(self,request,timeout):
                self.calls+=1
                value={'data':{'id':'fakeUser'}} if self.calls==1 else {}
                response=io.BytesIO(json.dumps(value).encode()); response.status=200; return response
        opener=Opener(); transport=c.CoverageTransport('FAKE_TOKEN',END,opener=opener)
        transport.get('identity'); transport.get('page',offset=0,end=END)
        with self.assertRaises(c.ReadFailure): transport.get('page',offset=0,end=END)
        self.assertEqual(opener.calls,2)

    def test_arbitrary_routes_rejected_before_network(self):
        class Opener:
            def open(self,*args,**kwargs): raise AssertionError
        for stage,kw in [('page',{'offset':0,'end':END}),('run',{'run_id':'whatever'}),
                         ('input',{'kv_id':'whatever'}),('DELETE',{}),('POST',{})]:
            with self.assertRaises(c.ReadFailure): c.CoverageTransport('FAKE_TOKEN',END,opener=Opener()).get(stage,**kw)

    def test_oversize_invalid_json_and_deadline_stop(self):
        for raw,category in [(b'x'*(c.RESPONSE_LIMIT+1),'response_too_large'),(b'bad','invalid_json')]:
            class Opener:
                def open(self,*args,**kw):
                    response=io.BytesIO(raw); response.status=200; return response
            with self.assertRaises(c.ReadFailure) as cm:
                c.CoverageTransport('FAKE_TOKEN',END,opener=Opener()).get('identity')
            self.assertEqual(cm.exception.category,category)
        transport=c.CoverageTransport('FAKE_TOKEN',END)
        transport._deadline=0
        with self.assertRaises(c.ReadFailure): transport.get('identity')

    def test_closed_gate_before_token_access(self):
        def no_token(key,*args):
            if key=='APIFY_TOKEN': raise AssertionError
            return None
        with patch.object(c,'WIDE_OPEN',False),patch.object(c.os.environ,'get',side_effect=no_token):
            self.assertEqual(c.main(['--execute-read-only']),1)

if __name__=='__main__': unittest.main()
