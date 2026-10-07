"""Named synthetic streams only. No network opener is used by these tests."""
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch
import contextlib,copy,io,json,tempfile,unittest
import list_probe as p

TOKEN='named_synthetic_token_123'

class Response:
    def __init__(self,raw,status=200,mime='application/json',encoding=None,tick=None):
        self.stream=io.BytesIO(raw);self.status=status;self.mime=mime;self.encoding=encoding;self.tick=tick;self.closed=False
    def getheader(self,k):return self.mime if k=='Content-Type' else self.encoding if k=='Content-Encoding' else None
    def read1(self,n):
        if self.tick:self.tick()
        return self.stream.read1(n)
    def close(self):self.closed=True;self.stream.close()

def error_body():
    return json.dumps({'error':{'type':'invalid-parameter','message':'Named synthetic diagnostic message; not a captured provider error.'}}).encode()

def listing(rows=None,total=None):
    rows=[] if rows is None else rows
    return json.dumps({'data':{'offset':0,'limit':5,'count':len(rows),
        'total':len(rows)if total is None else total,'desc':False,'items':rows}}).encode()

def row():return {'id':'R'*17,'actId':p.SCOPE['actor_id'],'startedAt':'2026-10-06T13:30:08.600Z'}

def capture(raw,status=400,mime='application/json',encoding=None,*,persist=None):
    calls=[];saved={};response=Response(raw,status,mime,encoding)
    def default_persist(stage,body):
        saved[stage]=body
        return {'plaintext_sha256':p.original.sha(body),'plaintext_bytes':len(body),
            'ciphertext_sha256':'a'*64,'ciphertext_bytes':len(body)+512,
            'durable_encrypted_readback_verified':True}
    def opener(req,timeout):
        calls.append((req,timeout))
        if status==200:return response
        raise HTTPError(req.full_url,status,'named synthetic reason',
            {'Content-Type':mime,'Content-Encoding':encoding},response)
    with patch.object(p,'RECOVERY_READY',True):
        probe=p.ListProbe(TOKEN,opener=opener,persist=persist or default_persist)
        result=probe.run()
    return result,calls,saved,response,probe

class ProbeTests(unittest.TestCase):
    def test_closed_before_transport_or_credentials(self):
        with patch.object(p,'RECOVERY_READY',False),self.assertRaises(p.ProbeStop)as error:
            p.ListProbe(None,opener=lambda *a:self.fail(),persist=lambda *a:self.fail())
        self.assertEqual(error.exception.category,'guard_closed')

    def test_unchanged_documented_query_header_only_GET(self):
        _,calls,_,_,_=capture(error_body());request,timeout=calls[0]
        self.assertEqual(request.get_method(),'GET');self.assertIsNone(request.data)
        self.assertEqual(urlsplit(request.full_url).path,'/v2/actors/'+p.SCOPE['actor_id']+'/runs')
        self.assertEqual(parse_qs(urlsplit(request.full_url).query),{
            'limit':['5'],'offset':['0'],'desc':['false'],'startedAfter':['2026-10-06T13:30:00Z'],
            'startedBefore':['2026-10-06T13:30:59.999999Z']})
        self.assertNotIn(TOKEN,request.full_url);self.assertEqual(request.get_header('Authorization'),'Bearer '+TOKEN)
        self.assertGreater(timeout,0);self.assertLessEqual(timeout,15)

    def test_400_body_retained_exact_privately_and_stream_closed(self):
        raw=error_body();result,calls,saved,response,_=capture(raw)
        self.assertEqual(len(calls),1);self.assertEqual(saved,{'list-error':raw});self.assertTrue(response.closed)
        self.assertTrue(result['error_type_and_message_available_privately'])
        self.assertEqual(result['diagnostic'],{'category':'http_error','stage':'list','http_status':400})
        public=json.dumps(result)
        self.assertNotIn('Named synthetic diagnostic message',public);self.assertNotIn('invalid-parameter',public)

    def test_same_instance_consumed_no_retry(self):
        _,calls,_,_,probe=capture(error_body())
        with patch.object(p,'RECOVERY_READY',True),self.assertRaises(p.ProbeStop)as error:probe.run()
        self.assertEqual(error.exception.category,'intent_consumed');self.assertEqual(len(calls),1)

    def test_all_outcomes_preserve_unknowns_holds_and_stop(self):
        for raw,status in ((error_body(),400),(listing(),200),(listing([row()]),200)):
            result,*_=capture(raw,status)
            for key in ('original_five_GET_recovery_contract_complete','terminal_identity_and_input_verified',
                        'rejected_before_run_proven','ready_for_next_Actor_start'):
                self.assertFalse(result[key])
            for key in ('latest_terminal_run_usd','accepted_output_denominator'):self.assertIsNone(result[key])
            self.assertEqual(result['Contact_full_hold_usd'],'0.53');self.assertEqual(result['hold_release_usd'],'0')
            self.assertEqual([result[k]for k in ('Actor_starts','aborts','DELETEs','item_exports')],[0]*4)

    def test_200_empty_or_unique_list_is_only_observation(self):
        for rows in ([],[row()]):
            result,calls,saved,_,_=capture(listing(rows),200)
            self.assertTrue(result['list_page_validated']);self.assertEqual(len(calls),1)
            self.assertEqual(result['complete_empty_window_observed'],not rows)
            self.assertEqual(result['one_candidate_observed'],bool(rows));self.assertEqual(set(saved),{'list'})

    def test_multiple_truncated_foreign_or_boundary_rows_stop(self):
        rows=[row(),{**row(),'id':'S'*17}]
        for raw in (listing(rows),listing([],total=1),listing([{**row(),'actId':'X'*17}]),
                    listing([{**row(),'startedAt':'2026-10-06T13:31:00.000Z'}])):
            result,_,saved,_,_=capture(raw,200)
            self.assertFalse(result['list_page_validated']);self.assertEqual(saved,{})

    def test_error_body_limit_plus_one_no_persistence(self):
        result,calls,saved,response,_=capture(b'x'*(p.ERROR_LIMIT+1))
        self.assertEqual(result['diagnostic']['category'],'body_limit');self.assertEqual(saved,{})
        self.assertEqual(len(calls),1);self.assertTrue(response.closed)

    def test_exact_error_limit_supported_without_truncation(self):
        raw=error_body();raw+=b' '*(p.ERROR_LIMIT-len(raw))
        result,_,saved,_,_=capture(raw)
        self.assertTrue(result['error_type_and_message_available_privately']);self.assertEqual(saved['list-error'],raw)

    def test_wrong_mime_encoding_JSON_and_envelope_stop(self):
        cases=[(error_body(),'text/html',None),(error_body(),'application/json','gzip'),
            (b'{"error":{},"error":{}}','application/json',None),
            (b'{"error":{"type":"invalid-parameter"}}','application/json',None)]
        for raw,mime,encoding in cases:
            result,_,saved,response,_=capture(raw,mime=mime,encoding=encoding)
            self.assertFalse(result['error_type_and_message_available_privately']);self.assertEqual(saved,{})
            self.assertTrue(response.closed)

    def test_other_HTTP_status_or_redirect_not_read_or_retried(self):
        for status in (302,403,429,500):
            result,calls,saved,response,_=capture(b'not JSON; must be unread',status)
            self.assertEqual(result['HTTP_status'],status);self.assertEqual(len(calls),1)
            self.assertEqual(saved,{});self.assertTrue(response.closed)

    def test_credentials_plain_or_JSON_escaped_never_saved(self):
        for message in (TOKEN,'apify_api_named_synthetic_token_not_real',TOKEN.replace('_','\\u005f')):
            raw=('{"error":{"type":"invalid-parameter","message":"'+message+'"}}').encode()
            result,_,saved,_,_=capture(raw)
            self.assertEqual(result['diagnostic']['category'],'credential_in_response');self.assertEqual(saved,{})

    def test_missing_or_forged_encrypted_receipt_stops(self):
        for callback in (lambda *a:None,lambda *a:{'durable_encrypted_readback_verified':True}):
            result,*_=capture(error_body(),persist=callback)
            self.assertEqual(result['diagnostic']['category'],'encrypted_persistence_failed')
            self.assertFalse(result['error_type_and_message_available_privately'])

    def test_error_read_deadline_stops_with_one_request(self):
        clock=[0];response=Response(error_body(),400,tick=lambda:clock.__setitem__(0,16))
        def opener(req,timeout):raise HTTPError(req.full_url,400,'synthetic',{'Content-Type':'application/json'},response)
        with patch.object(p,'RECOVERY_READY',True):
            result=p.ListProbe(TOKEN,opener=opener,persist=lambda *a:self.fail(),clock=lambda:clock[0]).run()
        self.assertEqual(result['requests_attempted'],1);self.assertEqual(result['diagnostic']['category'],'deadline_exceeded')
        self.assertTrue(response.closed)

    def test_expired_deadline_before_opener_consumes_zero_GETs(self):
        clock=iter((0,16))
        with patch.object(p,'RECOVERY_READY',True):
            probe=p.ListProbe(TOKEN,opener=lambda *a,**k:self.fail(),persist=lambda *a:self.fail(),clock=lambda:next(clock))
            result=probe.run()
        self.assertEqual(result['requests_attempted'],0)
        self.assertEqual(result['diagnostic']['category'],'deadline_exceeded')

    def test_success_body_limit_exact_and_plus_one(self):
        raw=listing();raw+=b' '*(p.SUCCESS_LIMIT-len(raw))
        result,_,saved,_,_=capture(raw,200)
        self.assertTrue(result['list_page_validated']);self.assertEqual(saved['list'],raw)
        result,_,saved,_,_=capture(raw+b' ',200)
        self.assertEqual(result['diagnostic']['category'],'body_limit');self.assertEqual(saved,{})

def native_env():
    return {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':p.REPOSITORY,'GITHUB_REF':'refs/heads/main',
        'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'12345',
        'GITHUB_SHA':'a'*40,'GITHUB_WORKFLOW_REF':p.REPOSITORY+'/'+p.WORKFLOW+'@refs/heads/main',
        'APIFY_CONTACT_LIST_EXPECTED_SOURCE_SHA':'a'*40,'APIFY_CONTACT_LIST_PROBE_OPT_IN':'yes',
        'APIFY_TOKEN':TOKEN,'RUNNER_TEMP':'/named-synthetic-runner-temp'}

def execute_fake(root,raw,status=400,env=None):
    calls=[];env=native_env()if env is None else env
    def opener(request,timeout):
        calls.append(request);response=Response(raw,status)
        if status==200:return response
        raise HTTPError(request.full_url,status,'named synthetic',{'Content-Type':'application/json'},response)
    def encrypt(body,path,binary,recipient,crypto):
        # Named synthetic envelope, never used by the production adapter.
        cipher=b'age-encryption.org/v1\n'+body.hex().encode()+b'\n'
        crypto.durable_write(path,cipher)
        return {'plaintext_sha256':p.original.sha(body),'plaintext_bytes':len(body),
            'ciphertext_sha256':p.original.sha(cipher),'ciphertext_bytes':len(cipher),
            'durable_encrypted_readback_verified':True}
    with patch.object(p,'RECOVERY_READY',True),patch.object(p,'load_reviewed',return_value=(
        p.PROBE_SPEC,p.original,p.SCOPE,p.VALIDATORS,p.CRYPTO,p.RECIPIENT)),patch.object(p.original,'encrypt_raw',side_effect=encrypt):
        public=p.execute(env,output_root=root,opener=opener,utc=lambda:'2026-10-06T20:00:10Z')
    return public,calls

class AdapterTests(unittest.TestCase):
    def test_closed_adapter_and_CLI_before_env_access(self):
        class NoEnv(dict):
            def get(self,*a):raise AssertionError('closed guard must not inspect environment')
        with patch.object(p,'RECOVERY_READY',False),self.assertRaises(p.ProbeStop)as error:p.execute(NoEnv())
        self.assertEqual(error.exception.category,'guard_closed')
        output=io.StringIO()
        with patch.object(p,'RECOVERY_READY',False),contextlib.redirect_stdout(output):code=p.main(['--execute'],NoEnv())
        self.assertEqual(code,2);self.assertNotIn(TOKEN,output.getvalue())

    def test_opt_in_before_source_and_native_environment(self):
        with patch.object(p,'RECOVERY_READY',True),patch.object(p,'load_reviewed',side_effect=AssertionError()),self.assertRaises(p.ProbeStop)as error:
            p.execute({})
        self.assertEqual(error.exception.category,'opt_in_required')

    def test_wrong_native_event_branch_attempt_SHA_or_workflow_stops(self):
        replacements={'GITHUB_ACTIONS':'false','GITHUB_REPOSITORY':'foreign/repo','GITHUB_REF':'refs/heads/other',
            'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'2','GITHUB_RUN_ID':'not-a-run',
            'GITHUB_SHA':'invalid','APIFY_CONTACT_LIST_EXPECTED_SOURCE_SHA':'b'*40,'GITHUB_WORKFLOW_REF':'wrong'}
        for key,value in replacements.items():
            env=native_env();env[key]=value
            with self.subTest(key=key),patch.object(p,'RECOVERY_READY',True),self.assertRaises(p.ProbeStop)as error:
                p.execute(env,opener=lambda *a,**k:self.fail())
            self.assertEqual(error.exception.category,'native_binding_invalid')

    def test_source_scope_tamper_stops_before_opener(self):
        with tempfile.TemporaryDirectory()as tmp,patch.object(p,'ROOT',Path(tmp)),patch.object(p,'RECOVERY_READY',True),self.assertRaises(p.ProbeStop)as error:
            p.execute(native_env(),opener=lambda *a,**k:self.fail())
        self.assertEqual(error.exception.category,'source_invalid')

    def test_native_400_adapter_writes_only_encrypted_body_and_safe_projection(self):
        with tempfile.TemporaryDirectory()as tmp:
            public,calls=execute_fake(Path(tmp),error_body())
            output=Path(tmp)/'capture';names={f.name for f in output.iterdir()}
            self.assertEqual(names,{'intent-local.json','list-error.age','manifest.age','probe-public.json'})
            self.assertEqual(len(calls),1);self.assertTrue(public['error_type_and_message_available_privately'])
            self.assertEqual(public['native_binding'],{'workflow_id':12345,'source_commit':'a'*40,'workflow_path':p.WORKFLOW,'run_attempt':1})
            self.assertNotIn('Named synthetic diagnostic message',(output/'probe-public.json').read_text())
            self.assertNotIn(TOKEN,json.dumps(public));self.assertFalse(public['ready_for_next_Actor_start'])

    def test_native_200_empty_and_unique_stop_after_list(self):
        for rows in ([],[row()]):
            with tempfile.TemporaryDirectory()as tmp:
                public,calls=execute_fake(Path(tmp),listing(rows),200)
                self.assertEqual(len(calls),1);self.assertTrue(public['list_page_validated'])
                self.assertFalse(public['original_five_GET_recovery_contract_complete'])
                self.assertFalse(public['ready_for_next_Actor_start'])
                self.assertEqual({f.name for f in (Path(tmp)/'capture').iterdir()},
                    {'intent-local.json','list.age','manifest.age','probe-public.json'})

    def test_output_exists_or_symlink_stops_before_any_GET(self):
        for symlink in (False,True):
            with tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);target=root/'capture'
                target.symlink_to(root/'missing')if symlink else target.mkdir()
                with patch.object(p,'RECOVERY_READY',True),self.assertRaises(p.ProbeStop)as error:
                    p.execute(native_env(),output_root=root,opener=lambda *a,**k:self.fail())
                self.assertEqual(error.exception.category,'preflight_failed')

    def test_preflight_encryption_failure_before_provider(self):
        with tempfile.TemporaryDirectory()as tmp,patch.object(p,'RECOVERY_READY',True),patch.object(p,'load_reviewed',return_value=(
            p.PROBE_SPEC,p.original,p.SCOPE,p.VALIDATORS,p.CRYPTO,p.RECIPIENT)),patch.object(p.original,'encrypt_raw',side_effect=RuntimeError()),self.assertRaises(p.ProbeStop)as error:
            p.execute(native_env(),output_root=Path(tmp),opener=lambda *a,**k:self.fail())
        self.assertEqual(error.exception.category,'encrypted_persistence_failed')

    def test_existing_capture_consumes_native_intent_no_replay(self):
        with tempfile.TemporaryDirectory()as tmp:
            execute_fake(Path(tmp),error_body())
            with patch.object(p,'RECOVERY_READY',True),self.assertRaises(p.ProbeStop)as error:
                p.execute(native_env(),output_root=Path(tmp),opener=lambda *a,**k:self.fail())
            self.assertEqual(error.exception.category,'preflight_failed')

    def test_capture_wall_expires_before_provider(self):
        clock=iter((0,91))
        with tempfile.TemporaryDirectory()as tmp,patch.object(p,'RECOVERY_READY',True),self.assertRaises(p.ProbeStop)as error:
            p.execute(native_env(),output_root=Path(tmp),opener=lambda *a,**k:self.fail(),clock=lambda:next(clock))
        self.assertEqual(error.exception.category,'deadline_exceeded')

    def test_default_or_wrong_CLI_arguments_are_offline(self):
        for args,code in (([],0),(['--wrong'],2)):
            output=io.StringIO()
            with patch.object(p,'execute',side_effect=AssertionError()),contextlib.redirect_stdout(output):actual=p.main(args,{})
            self.assertEqual(actual,code);self.assertIn('provider_requests',output.getvalue())

class WorkflowTests(unittest.TestCase):
    def test_offline_matrix_is_secret_free_and_exact_test_command(self):
        workflow=json.loads((p.ROOT.parent.parent/p.WORKFLOW).read_bytes())
        job=workflow['jobs']['offline']
        self.assertEqual(job['strategy']['matrix']['python'],['3.10','3.12'])
        self.assertNotIn('secrets.',json.dumps(job))
        self.assertEqual(job['steps'][-1]['run'],'python -B -m unittest test_list_probe.py')
        self.assertFalse(workflow['on']['workflow_dispatch']['inputs']['execute_probe']['default'])

    def test_native_job_gate_pinned_checkout_and_single_command(self):
        workflow=json.loads((p.ROOT.parent.parent/p.WORKFLOW).read_bytes());job=workflow['jobs']['probe']
        self.assertEqual(job['needs'],'offline');self.assertEqual(job['timeout-minutes'],5)
        self.assertEqual(job['if'],"github.event_name == 'workflow_dispatch' && inputs.execute_probe && github.ref == 'refs/heads/main' && github.run_attempt == 1 && inputs.expected_source_sha == github.sha")
        self.assertEqual(job['steps'][0]['with'],{'ref':'${{ github.sha }}','persist-credentials':False})
        step=job['steps'][3]
        self.assertEqual(step['run'],'python -B list_probe.py --execute')
        self.assertEqual(step['env']['APIFY_TOKEN'],'${{ secrets.APIFY_TOKEN }}')
        self.assertEqual(step['env']['APIFY_CONTACT_LIST_EXPECTED_SOURCE_SHA'],'${{ inputs.expected_source_sha }}')
        self.assertEqual(workflow['concurrency']['group'],'apify-contact-readonly-recovery')

    def test_artifact_allowlist_no_plaintext_keys_or_intent(self):
        workflow=json.loads((p.ROOT.parent.parent/p.WORKFLOW).read_bytes());step=workflow['jobs']['probe']['steps'][-1]
        self.assertEqual(step['if'],'always()');self.assertEqual(step['with']['retention-days'],7)
        self.assertEqual({Path(x).name for x in step['with']['path'].splitlines()},
            {'list.age','list-error.age','manifest.age','probe-public.json'})
        self.assertNotIn('intent-local.json',step['with']['path']);self.assertNotIn('agekey',json.dumps(workflow))
        self.assertIn('cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10',job_install:=workflow['jobs']['probe']['steps'][2]['run'])
        self.assertIn('age-v1.3.2-linux-amd64.tar.gz',job_install)

if __name__=='__main__':unittest.main()
