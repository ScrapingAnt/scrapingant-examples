"""Fixed one-GET Contact list diagnostic, closed by default.

The native adapter uses the existing credential and encrypted persistence.
It retains bounded structured HTTP400 error details privately.
The documented original query is deliberately unchanged; all outcomes stop.
"""
from pathlib import Path
from datetime import datetime,timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request,build_opener
import copy,hashlib,importlib.util,json,os,re,sys,time

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent/'apify-contact-readonly-recovery'
RECOVERY_READY = False
SPEC_SHA256 = '5841a5df40d867e660cbb4be66d880b9491b9106f864769003f6b98b3221c99e'
WORKFLOW = '.github/workflows/apify-contact-list-probe.yml'
REPOSITORY = 'ScrapingAnt/scrapingant-examples'
ERROR_LIMIT = 16384
SUCCESS_LIMIT = 131072
SECONDS = 15

class ProbeStop(Exception):
    def __init__(self,category):
        self.category = category
        super().__init__('contact_list_probe_stopped')

def load_reviewed():
    try:
        path=ROOT/'probe-scope.json'
        if path.is_symlink()or not path.is_file()or not 1<=path.stat().st_size<=8192:raise ValueError()
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=SPEC_SHA256:raise ValueError()
        spec=json.loads(raw)
        if not(spec['schema_version']==1 and spec['diagnostic_id']=='contact-list-error-capture-v1'
            and spec['maximum_new_GETs']==1 and spec['historical_diagnostic_GETs']==1
            and spec['maximum_aggregate_GETs']==5 and spec['maximum_aggregate_after_this_dispatch']==2
            and spec['HTTP400_error_body_limit_bytes']==ERROR_LIMIT and spec['success_body_limit_bytes']==SUCCESS_LIMIT
            and spec['request_seconds']==SECONDS and spec['capture_wall_seconds']==90
            and spec['no_resumption']is True and spec['original_query_unchanged']is True):raise ValueError()
        repo=ROOT.parent.parent
        for name,digest in spec['dependency_sha256'].items():
            dependency=repo/name
            if dependency.is_symlink()or not dependency.is_file()or hashlib.sha256(dependency.read_bytes()).hexdigest()!=digest:
                raise ValueError()
        reference=SOURCE/'recover_contact.py'
        module_spec=importlib.util.spec_from_file_location('contact_probe_original',reference)
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        if module.RECOVERY_READY is not False:raise ValueError()
        scope,validators,crypto,recipient=module.load_reviewed()
        if module.SPEC_SHA256!=spec['original_scope_sha256']:raise ValueError()
        return spec,module,scope,validators,crypto,recipient
    except Exception:raise ProbeStop('source_invalid')from None

PROBE_SPEC,original,SCOPE,VALIDATORS,CRYPTO,RECIPIENT=load_reviewed()

def fixed_url():
    return 'https://api.apify.com/v2/actors/'+SCOPE['actor_id']+'/runs?'+urlencode({
        'limit':5,'offset':0,'desc':'false','startedAfter':SCOPE['started_after'],
        'startedBefore':SCOPE['started_before']})

class ListProbe:
    def __init__(self,token,*,opener,persist,clock=time.monotonic):
        if RECOVERY_READY is not True: raise ProbeStop('guard_closed')
        if type(token) is not str or re.fullmatch('[A-Za-z0-9_-]{16,512}',token) is None:
            raise ProbeStop('token_unavailable')
        self._token=token; self._open=opener; self._persist=persist
        self._clock=clock; self._used=False

    def __repr__(self):return '<closed-scope Contact list probe>'

    def _read(self,stream,headers,limit,end):
        mime=headers.get('Content-Type') if headers is not None else None
        if type(mime) is not str or mime.split(';',1)[0].strip().lower()!='application/json':
            raise ProbeStop('unexpected_content_type')
        if headers.get('Content-Encoding') not in (None,'identity'):
            raise ProbeStop('unexpected_content_encoding')
        raw=bytearray()
        while True:
            remaining=end-self._clock()
            if remaining<=0:raise ProbeStop('deadline_exceeded')
            sock=getattr(getattr(getattr(stream,'fp',None),'raw',None),'_sock',None)
            if sock is not None:sock.settimeout(max(.001,remaining))
            chunk=stream.read1(min(8192,limit+1-len(raw)))
            if self._clock()>=end:raise ProbeStop('deadline_exceeded')
            if not isinstance(chunk,bytes):raise ProbeStop('invalid_body')
            if not chunk:break
            raw.extend(chunk)
            if len(raw)>limit:raise ProbeStop('body_limit')
        if not raw:raise ProbeStop('invalid_body')
        try:body=original.strict(bytes(raw))
        except original.Stop:raise ProbeStop('invalid_JSON') from None
        # Never retain credentials, even in encrypted error evidence. Scan raw
        # and decoded strings so JSON escapes do not defeat the token check.
        def secret(value):
            if isinstance(value,str):
                return self._token in value or re.search(r'apify_api_[A-Za-z0-9_-]+',value) is not None
            if isinstance(value,dict):return any(secret(k) or secret(v) for k,v in value.items())
            if isinstance(value,list):return any(secret(v) for v in value)
            return False
        if self._token.encode() in raw or secret(body):raise ProbeStop('credential_in_response')
        return bytes(raw),body

    def _save(self,stage,raw):
        try:proof=self._persist(stage,raw)
        except Exception:raise ProbeStop('encrypted_persistence_failed') from None
        if (not isinstance(proof,dict) or proof.get('durable_encrypted_readback_verified') is not True
            or proof.get('plaintext_sha256')!=original.sha(raw)
            or proof.get('plaintext_bytes')!=len(raw)
            or type(proof.get('ciphertext_bytes')) is not int or proof['ciphertext_bytes']<=len(raw)
            or re.fullmatch('[a-f0-9]{64}',str(proof.get('ciphertext_sha256'))) is None):
            raise ProbeStop('encrypted_persistence_failed')
        return copy.deepcopy(proof)

    def run(self):
        if self._used:raise ProbeStop('intent_consumed')
        if RECOVERY_READY is not True:raise ProbeStop('guard_closed')
        self._used=True; end=self._clock()+SECONDS
        result={'schema_version':1,'scope_sha256':SPEC_SHA256,
            'request_url_sha256':original.sha(fixed_url().encode()),'requests_attempted':0,
            'HTTP_status':None,'diagnostic':None,'files':{},'list_page_validated':False,
            'complete_empty_window_observed':False,'one_candidate_observed':False,
            'error_type_and_message_available_privately':False,
            'original_five_GET_recovery_contract_complete':False,
            'terminal_identity_and_input_verified':False,'latest_terminal_run_usd':None,
            'accepted_output_denominator':None,'rejected_before_run_proven':False,
            'ready_for_next_Actor_start':False,'Actor_starts':0,'aborts':0,'DELETEs':0,
            'item_exports':0,'hold_release_usd':'0','Contact_full_hold_usd':'0.53'}
        response=None; error_response=None
        try:
            request=Request(fixed_url(),method='GET',headers={
                'Authorization':'Bearer '+self._token,'Accept':'application/json','Accept-Encoding':'identity'})
            remaining=end-self._clock()
            if remaining<=0:raise ProbeStop('deadline_exceeded')
            result['requests_attempted']=1
            try:response=self._open(request,timeout=max(.001,remaining))
            except HTTPError as error:
                error_response=error;result['HTTP_status']=error.code
                if error.code!=400:
                    raise ProbeStop('redirect_refused'if 300<=error.code<=399 else'http_error_body_not_in_scope')
                raw,body=self._read(error.fp,error.headers,ERROR_LIMIT,end)
                envelope=body.get('error') if isinstance(body,dict) else None
                if (not isinstance(envelope,dict) or type(envelope.get('type')) is not str
                    or not 1<=len(envelope['type'])<=128 or type(envelope.get('message')) is not str
                    or not 1<=len(envelope['message'])<=4096):
                    raise ProbeStop('unexpected_error_envelope')
                result['files']['list-error.age']=self._save('list-error',raw)
                result['error_type_and_message_available_privately']=True
                result['diagnostic']={'category':'http_error','stage':'list','http_status':400}
                return result
            result['HTTP_status']=response.status
            if response.status!=200:raise ProbeStop('unexpected_HTTP_status')
            headers={k:response.getheader(k) for k in ('Content-Type','Content-Encoding')}
            raw,body=self._read(response,headers,SUCCESS_LIMIT,end)
            try:candidate=original.select_candidate(body,SCOPE)
            except original.Stop as error:raise ProbeStop(error.category) from None
            result['files']['list.age']=self._save('list',raw)
            result['list_page_validated']=True
            result['complete_empty_window_observed']=candidate is None
            result['one_candidate_observed']=candidate is not None
        except ProbeStop as error:
            result['diagnostic']={'category':error.category,'stage':'list','http_status':result['HTTP_status']}
        except (URLError,OSError):
            result['diagnostic']={'category':'transport_error','stage':'list','http_status':result['HTTP_status']}
        except Exception:
            result['diagnostic']={'category':'unexpected_response','stage':'list','http_status':result['HTTP_status']}
        finally:
            if response is not None:response.close()
            if error_response is not None:error_response.close()
        return result

PUBLIC_FIELDS = ('schema_version','scope_sha256','request_url_sha256','requests_attempted',
    'HTTP_status','diagnostic','list_page_validated','complete_empty_window_observed',
    'one_candidate_observed','error_type_and_message_available_privately',
    'original_five_GET_recovery_contract_complete','terminal_identity_and_input_verified',
    'rejected_before_run_proven','ready_for_next_Actor_start','Actor_starts','aborts','DELETEs',
    'item_exports','hold_release_usd','native_binding')

def native_binding(env):
    sha=env.get('GITHUB_SHA');run=env.get('GITHUB_RUN_ID')
    if not(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==REPOSITORY
        and env.get('GITHUB_REF')=='refs/heads/main' and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
        and env.get('GITHUB_RUN_ATTEMPT')=='1' and type(run)is str and run.isdecimal()and int(run)>0
        and type(sha)is str and re.fullmatch('[a-f0-9]{40}',sha)
        and env.get('APIFY_CONTACT_LIST_EXPECTED_SOURCE_SHA')==sha
        and env.get('GITHUB_WORKFLOW_REF')==REPOSITORY+'/'+WORKFLOW+'@refs/heads/main'):
        raise ProbeStop('native_binding_invalid')
    return {'workflow_id':int(run),'source_commit':sha,'workflow_path':WORKFLOW,'run_attempt':1}

def public_projection(result,proof):
    return {**{key:result[key]for key in PUBLIC_FIELDS},**proof}

def execute(env,*,output_root=ROOT,opener=None,clock=time.monotonic,
            utc=lambda:datetime.now(timezone.utc).isoformat()):
    if RECOVERY_READY is not True:raise ProbeStop('guard_closed')
    if env.get('APIFY_CONTACT_LIST_PROBE_OPT_IN')!='yes':raise ProbeStop('opt_in_required')
    spec,module,scope,_,crypto,recipient=load_reviewed()
    if scope!=SCOPE:raise ProbeStop('source_invalid')
    binding=native_binding(env)
    temporary=env.get('RUNNER_TEMP')
    if type(temporary)is not str:raise ProbeStop('preflight_failed')
    binary=Path(temporary)/'age-v1.3.2/age/age'
    output=Path(output_root)/'capture'
    if output.exists()or output.is_symlink():raise ProbeStop('preflight_failed')
    started=clock();end=started+spec['capture_wall_seconds']
    output.mkdir(mode=0o700)
    intent=output/'intent-local.json'
    crypto.durable_write(intent,module.canonical({'native_binding':binding,'one_dispatch_consumed':True}))
    def encrypted(stage,raw):
        if clock()>=end:raise ProbeStop('deadline_exceeded')
        try:proof=module.encrypt_raw(raw,output/(stage+'.age'),binary,recipient,crypto)
        except Exception:raise ProbeStop('encrypted_persistence_failed')from None
        if clock()>=end:raise ProbeStop('deadline_exceeded')
        return proof
    encrypted('preflight',b'{"named_synthetic_preflight":true}')
    (output/'preflight.age').unlink()
    if clock()>=end:raise ProbeStop('deadline_exceeded')
    observations={}
    def persist(stage,raw):
        proof=encrypted(stage,raw);observations[stage]=utc();return proof
    transport=ListProbe(env.get('APIFY_TOKEN'),opener=opener if opener is not None
        else build_opener(module.NoRedirect()).open,persist=persist,clock=clock)
    result=transport.run();result['native_binding']=binding;result['observations']=observations
    result['original_scope_sha256']=module.SPEC_SHA256
    result['capture_wall_seconds']=90;result['one_native_intent_consumed']=True
    if clock()>=end:raise ProbeStop('deadline_exceeded')
    proof=encrypted('manifest',module.canonical(result))
    public=public_projection(result,proof)
    crypto.durable_write(output/'probe-public.json',module.canonical(public))
    return public

def main(args,env):
    if not args:
        print('{"mode":"offline","provider_requests":0,"Actor_starts":0,"DELETEs":0}')
        return 0
    if args!=['--execute']:
        print('{"diagnostic":{"category":"arguments_invalid"},"provider_requests":0}')
        return 2
    try:print(original.canonical(execute(env)).decode());return 0
    except ProbeStop as error:
        print(original.canonical({'diagnostic':{'category':error.category},'Actor_starts':0,'DELETEs':0}).decode())
        return 2

if __name__=='__main__':sys.exit(main(sys.argv[1:],os.environ))
