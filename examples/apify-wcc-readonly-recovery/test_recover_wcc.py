"""Named synthetic responses only. No network, account or Actor operations."""
import copy,json,io,unittest
from urllib.error import HTTPError
from unittest.mock import patch
import recover_wcc as r

class Reply:
    status=200
    def __init__(self,blob,ctype='application/json',encoding=None):self.body=io.BytesIO(blob);self.ctype=ctype;self.encoding=encoding;self.closed=False
    def getheader(self,name):return self.ctype if name=='Content-Type'else self.encoding if name=='Content-Encoding'else None
    def read1(self,n):return self.body.read(n)
    def close(self):self.closed=True

class NamedSyntheticRecovery(unittest.TestCase):
    def setUp(self):
        self.guard=patch.object(r,'RECOVERY_READY',True);self.guard.start();self.addCleanup(self.guard.stop)
        self.spec,self.cell,self.validators,_,_=r.load_reviewed()
        self.target={'id':'SYNTHETICRUN00001','userId':'SYNTHETICUSER0001','actId':self.cell['actor_id'],
          'defaultDatasetId':'SYNTHETICDATA0001','defaultKeyValueStoreId':'SYNTHETICKV000001',
          'defaultRequestQueueId':'SYNTHETICQUEUE000','extraDatasetId':'SYNTHETICERROR000',
          'startedAt':'2026-10-06T00:00:00.000Z','finishedAt':None,'status':'ABORTING','build':self.cell['build'],
          'options':copy.deepcopy(self.cell['options']),'extraDatasetAlias':'errors'}
        self.run={k:v for k,v in self.target.items()if k not in ('extraDatasetId','extraDatasetAlias','build')}
        self.run['options']=copy.deepcopy(self.target['options'])
        self.run['options']['maxTotalChargeUsd']=0.08
        self.run.update(status='ABORTED',finishedAt='2026-10-06T00:00:10.000Z',buildNumber=self.cell['build'],usageTotalUsd=0,
          storageIds={'datasets':{'default':self.target['defaultDatasetId'],'errors':self.target['extraDatasetId']},
            'keyValueStores':{'default':self.target['defaultKeyValueStoreId']},'requestQueues':{'default':self.target['defaultRequestQueueId']}})
        self.payloads={'run':{'data':self.run},'meter':{'data':copy.deepcopy(self.run)}}
        for stage,field in (('dataset','defaultDatasetId'),('kv','defaultKeyValueStoreId'),('queue','defaultRequestQueueId'),('extra','extraDatasetId')):
            self.payloads[stage]={'data':{'id':self.target[field],'userId':self.target['userId'],'actId':self.target['actId'],
                'actRunId':self.target['id'],'name':None,'createdAt':'2026-10-06T00:00:01.000Z','stats':{'storageBytes':0},'itemCount':0}}
        self.requests=[];self.persisted={}
    def transport(self):
        def opener(request,timeout):
            stage=r.STAGES[len(self.requests)];self.requests.append((request,timeout))
            return Reply(json.dumps(self.payloads[stage]).encode())
        return r.Transport('NAMED_SYNTHETIC_TOKEN_0001',self.target,opener=opener,clock=lambda:0)
    def collect(self):
        t=self.transport()
        def persist(stage,blob):self.persisted[stage]=blob;return{'named_synthetic_proof':True}
        self.value=r.collect(t,self.spec,self.cell,self.validators,persist)
        return self.value
    def test_closed_source_guard_is_default(self):
        with patch.object(r,'RECOVERY_READY',False):
            with self.assertRaises(r.base.RecoveryError):r.Transport('NAMED_SYNTHETIC_TOKEN_0001',self.target,opener=lambda *a:None)
    def test_source_and_exact_WCC_build_options_are_bound(self):
        self.assertEqual(self.cell['cell_id'],'cap-r2-website-content-crawler');self.assertEqual(self.cell['options']['maxTotalChargeUsd'],'0.08')
        self.assertFalse(r.base.RECOVERY_READY);self.assertIsNone(r.base.controller.ACTIVE_CELL)
    def test_target_hash_and_fields(self):
        blob=r.base.canonical(self.target).decode();spec={**self.spec,'target_payload_sha256':r.base.sha(blob.encode())}
        self.assertEqual(r.target_from_data(blob,spec,self.validators,self.cell),self.target)
        with self.assertRaises(r.base.RecoveryError):r.target_from_data(blob+' ',spec,self.validators,self.cell)
    def test_target_rejects_unknown_fields_Actor_alias_and_option_changes(self):
        for field,new in (('extraDatasetAlias','default'),('actId','SYNTHETICACTOR0001'),('options',{}),('finishedAt','2026-10-06T00:00:01Z'),('injected','value')):
            target=copy.deepcopy(self.target);target[field]=new;blob=r.base.canonical(target).decode();spec={**self.spec,'target_payload_sha256':r.base.sha(blob.encode())}
            with self.subTest(field=field),self.assertRaises(r.base.RecoveryError):r.target_from_data(blob,spec,self.validators,self.cell)
    def test_success_six_ordered_GETs_zero_known_terminal_meter(self):
        v=self.collect();self.assertTrue(v['capture_complete']);self.assertTrue(v['terminal_verified']);self.assertEqual(v['requests_attempted'],6)
        self.assertEqual(v['latest_terminal_run_meter']['usage_total_usd'],'0');self.assertTrue(v['four_stores_fresh_unnamed_owned_verified'])
        self.assertFalse(v['ready_for_next_Actor_start']);self.assertTrue(v['original_default_only_failure_preserved'])
        self.assertEqual(v['Actor_starts']+v['aborts']+v['DELETEs']+v['item_exports'],0)
    def test_exact_routes_methods_no_query_or_mutations(self):
        self.collect()
        paths=['actor-runs/'+self.target['id'],'datasets/'+self.target['defaultDatasetId'],'key-value-stores/'+self.target['defaultKeyValueStoreId'],
            'request-queues/'+self.target['defaultRequestQueueId'],'datasets/'+self.target['extraDatasetId'],'actor-runs/'+self.target['id']]
        for(request,timeout),path in zip(self.requests,paths):
            self.assertEqual(request.full_url,'https://api.apify.com/v2/'+path);self.assertEqual(request.get_method(),'GET')
            self.assertEqual(request.get_header('Authorization'),'Bearer NAMED_SYNTHETIC_TOKEN_0001');self.assertLessEqual(timeout,20)
    def test_urgent_nonterminal_first_stops_after_one_GET(self):
        for status in ('READY','RUNNING','ABORTING','TIMING-OUT'):
            self.requests=[];self.persisted={};self.run.update(status=status,finishedAt=None)
            v=self.collect();self.assertFalse(v['capture_complete']);self.assertTrue(v['latest_native_nonterminal_observed'])
            self.assertFalse(v['terminal_verified']);self.assertEqual(v['requests_attempted'],1);self.assertEqual(set(self.persisted),{'run'})
            self.assertIsNone(v['latest_terminal_run_meter'])
    def test_run_identity_owner_options_and_alias_mismatch_stops_first(self):
        originals=copy.deepcopy(self.run)
        changes=[('id','SYNTHETICWRONG0001'),('userId','SYNTHETICOTHER0001'),('options',{}),('buildNumber','0.3.98'),('storageIds',{})]
        for key,value in changes:
            self.requests=[];self.payloads['run']['data']=copy.deepcopy(originals);self.payloads['run']['data'][key]=value
            v=self.collect();self.assertFalse(v['capture_complete']);self.assertEqual(v['requests_attempted'],1)
    def test_extra_ID_or_owner_mismatch_stops_without_final_meter(self):
        for key,value in (('id','SYNTHETICOTHER0001'),('userId','SYNTHETICOTHER0001'),('actRunId','SYNTHETICOTHER0001'),('actId','SYNTHETICOTHER0001')):
            old=copy.deepcopy(self.payloads['extra']);self.requests=[];self.payloads['extra']['data'][key]=value
            v=self.collect();self.assertEqual(v['requests_attempted'],5);self.assertFalse(v['capture_complete'])
            self.assertEqual(set(self.persisted),{'run','dataset','kv','queue','extra'});self.payloads['extra']=old
    def test_name_absence_is_unknown_named_value_not_unnamed(self):
        del self.payloads['extra']['data']['name'];v=self.collect()
        self.assertTrue(v['capture_complete']);self.assertIsNone(v['stores']['extra']['named']);self.assertFalse(v['four_stores_fresh_unnamed_owned_verified'])
        self.requests=[];self.payloads['extra']['data']['name']='NAMED_SYNTHETIC_PERSISTENT_STORE';v=self.collect()
        self.assertTrue(v['stores']['extra']['named']);self.assertFalse(v['stores']['extra']['fresh_unnamed_owned_verified'])
    def test_missing_association_bytes_and_counts_do_not_become_zero(self):
        self.payloads['extra']['data'].pop('actRunId');self.payloads['extra']['data'].pop('itemCount');self.payloads['extra']['data']['stats']={}
        v=self.collect();s=v['stores']['extra'];self.assertFalse(s['Actor_and_run_association_verified'])
        self.assertIsNone(s['storage_bytes']);self.assertIsNone(s['item_count']);self.assertFalse(s['fresh_unnamed_owned_verified'])
    def test_prior_created_store_and_non_integer_bytes_not_accepted(self):
        self.payloads['extra']['data']['createdAt']='2026-10-05T23:59:59Z';self.payloads['extra']['data']['stats']['storageBytes']=True
        v=self.collect();self.assertFalse(v['stores']['extra']['created_within_strict_run_window']);self.assertIsNone(v['stores']['extra']['storage_bytes'])
    def test_nonempty_errors_metadata_does_not_export_or_establish_acceptance(self):
        self.payloads['extra']['data'].update(itemCount=3,stats={'storageBytes':1234});v=self.collect()
        self.assertEqual(v['stores']['extra']['item_count'],3);self.assertTrue(v['capture_complete']);self.assertNotIn('accepted',v)
        self.assertFalse(v['ready_for_next_Actor_start']);self.assertEqual(v['item_exports'],0)
    def test_missing_meter_unknown_and_latest_snapshot_used_once(self):
        self.payloads['meter']['data'].pop('usageTotalUsd');v=self.collect();self.assertIsNone(v['latest_terminal_run_meter']['usage_total_usd'])
        self.requests=[];self.payloads['run']['data']['usageTotalUsd']=0.01;self.payloads['meter']['data']['usageTotalUsd']=0.02
        v=self.collect();self.assertEqual(v['latest_terminal_run_meter']['usage_total_usd'],'0.02');self.assertTrue(v['meter_snapshot_used_once'])
    def test_final_active_observation_revokes_terminal_proof(self):
        self.payloads['meter']['data'].update(status='RUNNING',finishedAt=None);v=self.collect()
        self.assertFalse(v['terminal_verified']);self.assertTrue(v['latest_native_nonterminal_observed']);self.assertFalse(v['capture_complete'])
        self.assertFalse(v['latest_meter_is_current_terminal_observation'])
    def test_terminal_future_finish_stops_before_store_reads(self):
        self.run['finishedAt']='2099-10-06T00:00:10.000Z';v=self.collect()
        self.assertFalse(v['capture_complete']);self.assertEqual(v['requests_attempted'],1)
    def test_terminal_status_or_finish_change_rejected(self):
        self.payloads['meter']['data']['finishedAt']='2026-10-06T00:00:11Z';v=self.collect();self.assertFalse(v['capture_complete'])
    def test_route_order_and_seventh_GET_refused(self):
        t=self.transport()
        with self.assertRaises(r.base.RecoveryError):t.get('extra')
        self.assertEqual(t.calls,0)
        for stage in r.STAGES:t.get(stage)
        with self.assertRaises(r.base.RecoveryError):t.get('run')
        self.assertEqual(t.calls,6)
    def test_HTTP_denial_no_retry_or_redirect(self):
        for status in (401,403,302,429,500):
            def opener(request,timeout):raise HTTPError(request.full_url,status,'NAMED_SYNTHETIC_ERROR',{},None)
            t=r.Transport('NAMED_SYNTHETIC_TOKEN_0001',self.target,opener=opener,clock=lambda:0)
            v=r.collect(t,self.spec,self.cell,self.validators,lambda *a:{})
            self.assertEqual(v['requests_attempted'],1);self.assertFalse(v['capture_complete'])
            with self.assertRaises(r.base.RecoveryError):t.get('run')
        self.assertIsNone(r.base.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))
    def test_body_content_encoding_and_total_wall_bound(self):
        for reply in (Reply(b'x'*131073),Reply(b'{}','text/html'),Reply(b'{}',encoding='gzip')):
            t=r.Transport('NAMED_SYNTHETIC_TOKEN_0001',self.target,opener=lambda *a,**k:reply,clock=lambda:0)
            with self.assertRaises(r.base.RecoveryError):t.get('run')
            self.assertEqual(t.calls,1);self.assertTrue(t.failed)
        clock=[0];t=r.Transport('NAMED_SYNTHETIC_TOKEN_0001',self.target,opener=lambda *a:None,clock=lambda:clock[0]);clock[0]=151
        with self.assertRaises(r.base.RecoveryError):t.get('run')
        self.assertEqual(t.calls,0)
    def test_persistence_failure_prevents_next_request(self):
        t=self.transport()
        def persist(*a):raise OSError('NAMED_SYNTHETIC_PERSISTENCE_ERROR')
        v=r.collect(t,self.spec,self.cell,self.validators,persist);self.assertEqual(v['requests_attempted'],1);self.assertFalse(v['capture_complete'])
    def test_public_allowlist_contains_no_native_identifiers_amounts_token_or_signing_keys(self):
        self.payloads['extra']['data']['signingKey']='NAMED_SYNTHETIC_SIGNING_KEY';v=self.collect()
        public=r.public_projection(v,{'plaintext_sha256':'a'*64,'ciphertext_sha256':'b'*64,'durable_encrypted_readback_verified':True})
        text=json.dumps(public)
        for marker in (self.target['id'],self.target['userId'],self.target['extraDatasetId'],'NAMED_SYNTHETIC_TOKEN_0001','NAMED_SYNTHETIC_SIGNING_KEY','usage_total_usd','stores','identity'):
            self.assertNotIn(marker,text)
        self.assertFalse(public['ready_for_next_Actor_start'])
    def test_duplicate_JSON_and_nan_rejected(self):
        for blob in (b'{"data":{},"data":{}}',b'{"data":NaN}'):
            with self.assertRaises(r.base.RecoveryError):r.base.strict(blob)

if __name__=='__main__':unittest.main()
