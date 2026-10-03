"""Synthetic fixed-scope/transport/privacy cases; no provider or real token."""
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch
from decimal import Decimal
import copy,io,json,tempfile,unittest
import recover_original as r

TOKEN='SYNTHETIC_TOKEN_1234'


class Response:
    def __init__(self,blob,ctype='application/json',status=200,headers=None):
        self.stream=io.BytesIO(blob);self.status=status;self.closed=False
        self.headers={'Content-Type':ctype,**(headers or {})}
    def read1(self,count):return self.stream.read(count)
    def getheader(self,key):return self.headers.get(key)
    def close(self):self.closed=True


class NoEnv:
    def get(self,*args):raise AssertionError('No environment access expected')


def fixtures():
    spec,cell,_=r.load_reviewed()
    identity={'id':'A'*17,'userId':'U'*17,'actId':spec['actor_id'],
        'defaultDatasetId':'D'*17,'defaultKeyValueStoreId':'K'*17,'defaultRequestQueueId':'Q'*17,
        'startedAt':spec['started_after'],'finishedAt':spec['started_before'],
        'status':'SUCCEEDED','build':'1.0.22','options':copy.deepcopy(cell.spec['options'])}
    spec=copy.deepcopy(spec);spec['target_run_sha256']=r.sha(identity['id'].encode())
    spec['original_scope_sha256']=r.runner.scope_commitment(identity)
    listed={'data':{'offset':0,'limit':5,'count':1,'total':1,'desc':False,
        'items':[{'id':identity['id'],'actId':identity['actId'],'startedAt':identity['startedAt'],
                  'unselected_private':'SYNTHETIC_PRIVATE_TEXT'}]}}
    native={**copy.deepcopy(identity),'buildNumber':identity['build'],'usageTotalUsd':1.2}
    native['options']['maxTotalChargeUsd']=3
    metadata={'id':identity['defaultDatasetId'],'userId':identity['userId'],
        'actRunId':identity['id'],'actId':identity['actId'],'name':None,
        'createdAt':identity['startedAt'],'itemCount':2,'storageBytes':100,
        'readCount':0,'writeCount':2,'deleteCount':0,'listCount':None}
    metadata['stats']={key:metadata[key]for key in ('storageBytes','readCount','writeCount','deleteCount','listCount')}
    rows=[{'case_id':'SYNTHETIC_1','#debug':{'note':'SYNTHETIC_PRIVATE_TEXT'}},{}]
    bodies=[r.canonical(listed),r.canonical({'data':native}),r.canonical({'data':metadata}),
        r.canonical(rows),r.canonical([{'case_id':'SYNTHETIC_1'}]),
        r.canonical([{'case_id':'SYNTHETIC_1'}]),b'SYNTHETIC preserved run log\n']
    return spec,cell,identity,bodies


class RecoveryTests(unittest.TestCase):
    def setUp(self):self.spec,self.cell,self.identity,self.bodies=fixtures()
    def transport(self,opener,clock=lambda:0):
        with patch.object(r,'RECOVERY_READY',True):return r.Transport(TOKEN,self.spec,self.cell,opener=opener,clock=clock)
    def collect(self,bodies=None,*,failure_at=None):
        requests=[];saved={};responses=[];bodylist=bodies or self.bodies
        def open_(request,timeout):
            index=len(requests);requests.append((request,timeout))
            if index==failure_at:raise HTTPError(request.full_url,403,'SYNTHETIC_SECRET_MESSAGE',{},io.BytesIO(b'SYNTHETIC_TOKEN'))
            response=Response(bodylist[index],'text/plain'if index==6 else'application/json');responses.append(response);return response
        def persist(stage,blob):
            saved[stage]=blob;return {'plaintext_sha256':r.sha(blob),'ciphertext_sha256':'e'*64,
                'plaintext_bytes':len(blob),'ciphertext_bytes':len(blob)+200,'durable_encrypted_readback_verified':True}
        with patch.object(r,'RECOVERY_READY',True):
            t=r.Transport(TOKEN,self.spec,self.cell,opener=open_,clock=lambda:0)
            value=r.collect(t,self.cell,self.spec,persist)
        return value,requests,saved,responses
    def test_closed_before_environment_paths_or_token(self):
        with patch.object(r,'RECOVERY_READY',False),patch.object(r,'load_reviewed',side_effect=AssertionError('source')):
            with self.assertRaises(r.RecoveryError)as context:r.execute(opt_in=True,environ=NoEnv())
            self.assertEqual(context.exception.category,'guard_closed')
            with self.assertRaises(r.RecoveryError):r.Transport(TOKEN,self.spec,self.cell)
    def test_explicit_opt_in_precedes_environment(self):
        with patch.object(r,'RECOVERY_READY',True):
            with self.assertRaises(r.RecoveryError)as context:r.execute(environ=NoEnv())
            self.assertEqual(context.exception.category,'opt_in_required')
    def test_existing_all_dependencies_and_paid_guards_verified(self):
        spec,cell,recipient=r.load_reviewed();self.assertEqual(cell.spec['build'],'1.0.22');self.assertTrue(recipient.startswith('age1'))
        with patch.object(r,'SPEC_SHA256','e'*64):
            with self.assertRaises(r.RecoveryError):r.load_reviewed()
        with patch.object(r.runner,'SUSTAINED_READY',True):
            with self.assertRaises(r.RecoveryError):r.load_reviewed()
    def test_seven_gets_header_auth_exact_routes_no_retry_or_starts(self):
        value,calls,saved,responses=self.collect();self.assertTrue(value['complete']);self.assertEqual(len(calls),7)
        self.assertEqual(set(saved),{'run','dataset','raw','clean','projection','log'})
        for request,timeout in calls:
            self.assertEqual(request.get_method(),'GET');self.assertEqual(request.get_header('Authorization'),'Bearer '+TOKEN)
            self.assertNotIn(TOKEN,request.full_url);self.assertEqual(urlsplit(request.full_url).hostname,'api.apify.com');self.assertLessEqual(timeout,15)
        self.assertTrue(all(response.closed for response in responses))
    def test_raw_clean_and_original_projection_preserved_separately(self):
        value,calls,saved,_=self.collect()
        self.assertEqual(saved['raw'],self.bodies[3]);self.assertEqual(saved['clean'],self.bodies[4]);self.assertEqual(saved['projection'],self.bodies[5]);self.assertEqual(saved['log'],self.bodies[6])
        self.assertEqual(value['files']['raw.age']['row_count'],2);self.assertEqual(value['files']['clean.age']['row_count'],1)
        raw=parse_qs(urlsplit(calls[3][0].full_url).query);clean=parse_qs(urlsplit(calls[4][0].full_url).query)
        self.assertEqual(raw['clean'],['false']);self.assertEqual(raw['skipHidden'],['false']);self.assertEqual(raw['skipEmpty'],['false'])
        self.assertEqual(clean['clean'],['true']);self.assertNotIn('fields',clean)
        projection=parse_qs(urlsplit(calls[5][0].full_url).query)
        self.assertEqual(projection['fields'],[','.join(self.cell.spec['output']['fields'])])
        self.assertEqual(parse_qs(urlsplit(calls[6][0].full_url).query),{'stream':['false'],'raw':['true']})
    def test_unselected_list_raw_not_retained(self):
        value,_,saved,_=self.collect();self.assertNotIn('list',saved)
        self.assertNotIn('SYNTHETIC_PRIVATE_TEXT',json.dumps(value))
    def test_public_output_no_identity_headers_paths_rows_or_provider_strings(self):
        value,_,_,_=self.collect();public=r.public_projection(value,{'plaintext_sha256':'a'*64,'ciphertext_sha256':'b'*64,'durable_encrypted_readback_verified':True})
        self.assertEqual(set(public),{'schema_version','evidence_type','requests_attempted','max_requests','reads','complete','scope_verified','diagnostic','provider_start_attempts','deletions','settings_changes','plaintext_sha256','ciphertext_sha256','encrypted_file_readback_verified'})
        text=json.dumps(public)
        for private in (TOKEN,self.identity['id'],self.identity['userId'],self.identity['defaultDatasetId'],'SYNTHETIC_PRIVATE_TEXT','row_count','headers'):
            self.assertNotIn(private,text)
    def test_authenticated_access_denial_stops_on_first_failed_read(self):
        for index in range(7):
            value,calls,_,_=self.collect(failure_at=index)
            self.assertFalse(value['complete']);self.assertEqual(len(calls),index+1)
            self.assertEqual(value['diagnostic']['category'],'access_denied');self.assertEqual(value['diagnostic']['http_status'],403)
            self.assertNotIn('SYNTHETIC_TOKEN',json.dumps(value))
    def test_scope_mismatch_prevents_dataset_access_and_raw_run_retention(self):
        bodies=copy.deepcopy(self.bodies);native=json.loads(bodies[1]);native['data']['userId']='F'*17;bodies[1]=r.canonical(native)
        value,calls,saved,_=self.collect(bodies);self.assertFalse(value['complete']);self.assertEqual(len(calls),2);self.assertEqual(saved,{})
    def test_active_or_other_status_stops_after_run(self):
        for status in ('RUNNING','FAILED','ABORTED'):
            bodies=copy.deepcopy(self.bodies);native=json.loads(bodies[1]);native['data']['status']=status;bodies[1]=r.canonical(native)
            value,calls,saved,_=self.collect(bodies);self.assertFalse(value['complete']);self.assertEqual(len(calls),2);self.assertEqual(saved,{})
    def test_foreign_or_named_dataset_stops_before_exports(self):
        for key,new in (('userId','F'*17),('actRunId','F'*17),('id','F'*17),('name','SYNTHETIC_NAMED')):
            bodies=copy.deepcopy(self.bodies);metadata=json.loads(bodies[2]);metadata['data'][key]=new;bodies[2]=r.canonical(metadata)
            value,calls,saved,_=self.collect(bodies);self.assertFalse(value['complete']);self.assertEqual(len(calls),3);self.assertEqual(set(saved),{'run'})
    def test_raw_count_disagreement_saved_but_blocks_next_get(self):
        bodies=copy.deepcopy(self.bodies);bodies[3]=b'[]'
        value,calls,saved,_=self.collect(bodies);self.assertFalse(value['complete']);self.assertEqual(len(calls),4);self.assertEqual(saved['raw'],b'[]')
    def test_zero_rows_is_known_zero_and_empty_array_preserved(self):
        bodies=copy.deepcopy(self.bodies);metadata=json.loads(bodies[2]);metadata['data']['itemCount']=0;bodies[2]=r.canonical(metadata)
        bodies[3:6]=[b'[]']*3;value,_,saved,_=self.collect(bodies)
        self.assertTrue(value['complete']);self.assertEqual(value['files']['raw.age']['row_count'],0);self.assertEqual(saved['raw'],b'[]')
    def test_duplicate_hostile_json_or_nonfinite_fails(self):
        for blob in (b'{"x":1,"x":2}',b'{"x":NaN}',b'not json'):
            with self.assertRaises(r.RecoveryError):r.strict_json(blob)
        self.assertEqual(r.strict_json(b'{"x":1.46318685507055910001}')['x'],Decimal('1.46318685507055910001'))
    def test_list_target_missing_duplicate_or_wrong_actor_rejected(self):
        base=json.loads(self.bodies[0])
        for change in ('missing','duplicate','wrong_actor'):
            value=copy.deepcopy(base)
            if change=='missing':value['data']['items'][0]['id']='F'*17
            elif change=='duplicate':value['data']['items']*=2;value['data'].update(count=2,total=2)
            else:value['data']['items'][0]['actId']='F'*17
            with self.assertRaises(r.RecoveryError):r.select_target(value,self.spec)
    def test_body_limit_is_enforced_and_response_closed(self):
        response=Response(b'X'*(r.SMALL_LIMIT+1));t=self.transport(lambda *args,**kwargs:response)
        with patch.object(r,'RECOVERY_READY',True),self.assertRaises(r.RecoveryError)as context:t.get('list')
        self.assertEqual(context.exception.category,'body_limit');self.assertEqual(t.calls,1);self.assertTrue(response.closed)
    def test_bad_content_type_or_gzip_block(self):
        for response in (Response(b'{}','text/html'),Response(b'{}',headers={'Content-Encoding':'gzip'})):
            t=self.transport(lambda *args,**kwargs:response)
            with patch.object(r,'RECOVERY_READY',True),self.assertRaises(r.RecoveryError):t.get('list')
            self.assertTrue(response.closed)
    def test_trickle_cannot_extend_route_deadline(self):
        clock=[0]
        class Slow(Response):
            def read1(self,count):clock[0]+=8;return b'x'
        t=self.transport(lambda *args,**kwargs:Slow(b'{}'),clock=lambda:clock[0])
        with patch.object(r,'RECOVERY_READY',True),self.assertRaises(r.RecoveryError)as context:t.get('list')
        self.assertEqual(context.exception.category,'deadline_exceeded');self.assertEqual(t.calls,1)
    def test_invalid_order_and_foreign_id_never_open(self):
        def forbidden(*args,**kwargs):raise AssertionError('No HTTP')
        t=self.transport(forbidden)
        with patch.object(r,'RECOVERY_READY',True):
            for stage,reference in (('run',self.identity['id']),('raw',self.identity['defaultDatasetId']),('log',self.identity['id'])):
                with self.assertRaises(r.RecoveryError):t.get(stage,reference)
        self.assertEqual(t.calls,0)
    def test_extra_or_post_failure_request_never_open(self):
        t=self.transport(lambda *args,**kwargs:Response(b'{}'));t.calls=7
        with patch.object(r,'RECOVERY_READY',True),self.assertRaises(r.RecoveryError):t.get('list')
        t.calls=0;t.failed=True
        with patch.object(r,'RECOVERY_READY',True),self.assertRaises(r.RecoveryError):t.get('list')
    def test_redirects_refused_without_body_or_second_call(self):
        def redirect(req,timeout):raise HTTPError(req.full_url,302,'SYNTHETIC_PRIVATE',{},io.BytesIO(b'SYNTHETIC_PRIVATE'))
        t=self.transport(redirect)
        with patch.object(r,'RECOVERY_READY',True),self.assertRaises(r.RecoveryError)as context:t.get('list')
        self.assertEqual(context.exception.category,'redirect_refused');self.assertEqual(t.calls,1)
        self.assertIsNone(r.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_bad_token_refused_before_opener(self):
        with patch.object(r,'RECOVERY_READY',True):
            for token in (None,'short','SYNTHETIC\nTOKEN123456','x'*513):
                with self.assertRaises(r.RecoveryError):r.Transport(token,self.spec,self.cell,opener=lambda *args,**kwargs:None)
    def test_native_integral_decimal_cap_is_bridged_without_accepting_strings_or_booleans(self):
        body=r.strict_json(self.bodies[1]);body['data']['options']['maxTotalChargeUsd']=Decimal('3.0')
        self.assertEqual(r.validated_identity(body,self.cell),self.identity)
        for amount in (Decimal('3.01'),Decimal('NaN'),'3.0',True):
            changed=copy.deepcopy(body);changed['data']['options']['maxTotalChargeUsd']=amount
            with self.assertRaises((r.RecoveryError,r.runner.Fault)):r.validated_identity(changed,self.cell)
    def test_cumulative_deadline_reduces_later_request_timeout(self):
        clock=[0];timeouts=[]
        def open_(request,timeout):timeouts.append(timeout);return Response(self.bodies[len(timeouts)-1])
        t=self.transport(open_,clock=lambda:clock[0])
        with patch.object(r,'RECOVERY_READY',True):
            t.get('list');clock[0]=115;t.get('run',self.identity['id'])
        self.assertEqual(timeouts,[15,5])
    def test_existing_output_or_symlink_stops_before_token_or_crypto(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'raw.age').symlink_to(root/'missing')
            with patch.object(r,'ROOT',root),patch.object(r,'RECOVERY_READY',True),patch.object(r,'load_reviewed',return_value=(self.spec,self.cell,'age1'+'a'*58)),patch.object(r,'encrypt_raw',side_effect=AssertionError('No crypto')):
                with self.assertRaises(r.RecoveryError):r.execute(opt_in=True,environ={'RUNNER_TEMP':tmp})
    def test_raw_array_and_log_encryption_preserves_exact_input_and_durable_hash(self):
        with tempfile.TemporaryDirectory()as tmp:
            for index,blob in enumerate((b'[{}, {"synthetic":1}]',b'SYNTHETIC raw log\n')):
                cipher=b'age-encryption.org/v1\nSYNTHETIC_CIPHER'+bytes([index])
                def fake_crypto(binary,args,payload):
                    self.assertEqual(payload,blob);self.assertEqual(args,['--encrypt','--recipient','SYNTHETIC_RECIPIENT']);return cipher
                with patch.object(r.crypto,'crypto',side_effect=fake_crypto):
                    proof=r.encrypt_raw(blob,Path(tmp)/(str(index)+'.age'),Path('/synthetic/age'),'SYNTHETIC_RECIPIENT')
                self.assertEqual(proof['plaintext_sha256'],r.sha(blob));self.assertEqual(proof['ciphertext_sha256'],r.sha(cipher));self.assertTrue(proof['durable_encrypted_readback_verified'])
    def test_encryption_failure_stops_collection_before_next_get(self):
        calls=[]
        def open_(request,timeout):calls.append(request);return Response(self.bodies[len(calls)-1])
        with patch.object(r,'RECOVERY_READY',True):
            t=r.Transport(TOKEN,self.spec,self.cell,opener=open_,clock=lambda:0)
            value=r.collect(t,self.cell,self.spec,lambda *args:(_ for _ in ()).throw(r.RecoveryError('encryption_failed','evidence')))
        self.assertEqual(len(calls),2);self.assertFalse(value['complete']);self.assertEqual(value['diagnostic']['category'],'encryption_failed')


if __name__=='__main__':unittest.main()
