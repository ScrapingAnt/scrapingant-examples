"""Closed exact original sustained-run read-only evidence recovery.

Seven ordered GETs maximum: hash-selected run list, exact run, dataset metadata,
raw export, clean export, original clean field projection and existing run log.
No starts, deletion, settings/profile routes, retries, pagination or redirects.
Raw bytes are encrypted separately; only fixed diagnostics and hashes are public.
"""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError
import copy,hashlib,json,os,re,sys,time

ROOT=Path(__file__).resolve().parent
DEPS=ROOT.parent/'apify-sustained'
sys.path.insert(0,str(DEPS))
import runner
import evidence_transport as crypto

RECOVERY_READY=False
SPEC_SHA256='735af7b63b63f2242caffd6cb0c5d100e4c2146fac87b292e77bfb31fb70a292'
STAGES=('list','run','dataset','raw','clean','projection','log')
LABELS={stage:stage+'.age' for stage in STAGES if stage!='list'}
OUTPUTS=tuple(LABELS.values())+('manifest.age','recovery-public.json')
MAX_GETS=7
SMALL_LIMIT=131072
RAW_LIMIT=8388608
ROUTE_SECONDS=15
WALL_SECONDS=120
CATEGORIES=('guard_closed','opt_in_required','source_invalid','preflight_failed',
    'token_unavailable','route_invalid','deadline_exceeded','access_denied','http_error',
    'redirect_refused','transport_error','body_limit','response_invalid','target_not_found',
    'scope_mismatch','dataset_invalid','encryption_failed')


def sha(blob):return hashlib.sha256(blob).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


class RecoveryError(Exception):
    def __init__(self,category,stage='preflight',status=None):
        self.category=category if category in CATEGORIES else'transport_error'
        self.stage=stage if stage in STAGES+('preflight','evidence')else'preflight'
        self.status=status if type(status)is int and 100<=status<=599 else None
        super().__init__('original_readonly_recovery_stopped')
    def safe(self):return {'category':self.category,'stage':self.stage,'http_status':self.status}


def guard():
    if RECOVERY_READY is not True:raise RecoveryError('guard_closed')


def strict_json(blob):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate')
            result[key]=value
        return result
    def reject(_):raise ValueError('nonfinite')
    try:return json.loads(blob,object_pairs_hook=pairs,parse_float=Decimal,parse_constant=reject)
    except Exception:raise RecoveryError('response_invalid')from None


def load_reviewed():
    try:
        spec_path=ROOT/'scope-spec.json'
        if spec_path.is_symlink()or not spec_path.is_file()or not 1<=spec_path.stat().st_size<=8192:raise ValueError()
        blob=spec_path.read_bytes()
        if sha(blob)!=SPEC_SHA256:raise ValueError()
        spec=json.loads(blob)
        if set(spec)!= {'schema_version','actor_id','cell_id','target_run_sha256','original_scope_sha256',
            'started_after','started_before','dependency_sha256'}or type(spec['schema_version'])is not int or spec['schema_version']!=1:raise ValueError()
        if set(spec['dependency_sha256'])!={'runner.py','billing_projection.py','evidence_transport.py','sustained-plan.json','recipient.txt'}:raise ValueError()
        for name,expected in spec['dependency_sha256'].items():
            path=DEPS/name
            if path.is_symlink()or not path.is_file()or path.stat().st_size>4194304 or sha(path.read_bytes())!=expected:raise ValueError()
        if any(getattr(runner,key)is not False for key in ('RUNNER_READY','SUSTAINED_READY','GRAPH_READY','CONCURRENCY_READY')):raise ValueError()
        for field in ('target_run_sha256','original_scope_sha256'):
            if re.fullmatch('[a-f0-9]{64}',spec[field])is None:raise ValueError()
        if runner.timestamp(spec['started_before'])-runner.timestamp(spec['started_after']) != timedelta(minutes=1):raise ValueError()
        plan=runner.load_reviewed_plan((DEPS/'sustained-plan.json').read_bytes())
        cell=runner.prepare_cell(plan,spec['cell_id'])
        if cell.spec['actor_id']!=spec['actor_id']or cell.spec['build']!='1.0.22':raise ValueError()
        recipient=(DEPS/'recipient.txt').read_text().strip()
        if re.fullmatch('age1[a-z0-9]{58}',recipient)is None:raise ValueError()
        return spec,cell,recipient
    except Exception:raise RecoveryError('source_invalid')from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Transport:
    def __init__(self,token,spec,cell,*,opener=None,clock=time.monotonic):
        guard()
        if type(token)is not str or not 16<=len(token)<=512 or re.fullmatch('[A-Za-z0-9_-]+',token)is None:raise RecoveryError('token_unavailable')
        self._token=token;self.spec=copy.deepcopy(spec);self.cell=cell
        self._open=opener if opener is not None else build_opener(NoRedirect()).open
        self.clock=clock;self.deadline=clock()+WALL_SECONDS;self.calls=0;self.failed=False;self.identity=None
    def __repr__(self):return '<bounded original-run read-only transport>'
    def bind(self,identity):
        if (self.calls!=2 or self.failed or runner.scope_commitment(identity)!=self.spec['original_scope_sha256']
            or sha(identity.get('id','').encode())!=self.spec['target_run_sha256']
            or identity.get('status')!='SUCCEEDED'):raise RecoveryError('scope_mismatch','run')
        self.identity=copy.deepcopy(identity)
    def url(self,stage,reference):
        guard()
        if self.failed or self.calls>=MAX_GETS or stage!=STAGES[self.calls]:raise RecoveryError('route_invalid',stage)
        if stage=='list':
            if reference is not None:raise RecoveryError('route_invalid',stage)
            return 'https://api.apify.com/v2/actors/'+self.spec['actor_id']+'/runs?'+urlencode({
                'limit':5,'offset':0,'desc':'false','startedAfter':self.spec['started_after'],'startedBefore':self.spec['started_before']})
        try:runner.ident(reference)
        except Exception:raise RecoveryError('scope_mismatch',stage)from None
        if stage=='run':
            if sha(reference.encode())!=self.spec['target_run_sha256']:raise RecoveryError('scope_mismatch',stage)
            return 'https://api.apify.com/v2/actor-runs/'+reference
        if not self.identity:raise RecoveryError('scope_mismatch',stage)
        if stage=='log':
            if reference!=self.identity['id']:raise RecoveryError('scope_mismatch',stage)
            return 'https://api.apify.com/v2/actor-runs/'+reference+'/log?stream=false&raw=true'
        if reference!=self.identity['defaultDatasetId']:raise RecoveryError('scope_mismatch',stage)
        base='https://api.apify.com/v2/datasets/'+reference
        if stage=='dataset':return base
        if stage=='raw':query={'format':'json','offset':0,'limit':7681,'desc':'false','clean':'false','skipHidden':'false','skipEmpty':'false'}
        elif stage=='clean':query={'format':'json','offset':0,'limit':7681,'desc':'false','clean':'true'}
        else:query={'format':'json','clean':'true','limit':7681,'fields':','.join(self.cell.spec['output']['fields'])}
        return base+'/items?'+urlencode(query)
    def get(self,stage,reference=None):
        url=self.url(stage,reference);deadline=min(self.deadline,self.clock()+ROUTE_SECONDS)
        if self.clock()>=deadline:raise RecoveryError('deadline_exceeded',stage)
        self.calls+=1;response=None;status=None;limit=SMALL_LIMIT if stage in ('list','run','dataset')else RAW_LIMIT
        try:
            request=Request(url,method='GET',headers={'Authorization':'Bearer '+self._token,
                'Accept':'text/plain'if stage=='log'else'application/json','Accept-Encoding':'identity'})
            response=self._open(request,timeout=max(.001,deadline-self.clock()));status=response.status
            if type(status)is not int or status!=200:raise RecoveryError('http_error',stage,status)
            content_type=response.getheader('Content-Type')
            if not isinstance(content_type,str)or content_type.split(';',1)[0].strip().lower()!=('text/plain'if stage=='log'else'application/json'):raise RecoveryError('response_invalid',stage,status)
            if response.getheader('Content-Encoding')not in (None,'identity'):raise RecoveryError('response_invalid',stage,status)
            raw=bytearray()
            while True:
                remaining=deadline-self.clock()
                if remaining<=0:raise RecoveryError('deadline_exceeded',stage,status)
                sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                if sock is not None:sock.settimeout(max(.001,remaining))
                chunk=response.read1(min(65536,limit+1-len(raw)))
                if self.clock()>=deadline:raise RecoveryError('deadline_exceeded',stage,status)
                if not isinstance(chunk,bytes):raise RecoveryError('response_invalid',stage,status)
                if not chunk:break
                raw.extend(chunk)
                if len(raw)>limit:raise RecoveryError('body_limit',stage,status)
            headers={name:response.getheader(name)for name in ('Date','Content-Type','Content-Length',
                'X-Apify-Pagination-Offset','X-Apify-Pagination-Limit','X-Apify-Pagination-Count','X-Apify-Pagination-Total','X-Apify-Pagination-Desc')}
            return bytes(raw),headers
        except HTTPError as exc:
            status=exc.code;exc.close();self.failed=True
            raise RecoveryError('access_denied'if status in (401,403)else'redirect_refused'if 300<=status<400 else'http_error',stage,status)from None
        except RecoveryError:self.failed=True;raise
        except Exception:
            self.failed=True
            raise RecoveryError('deadline_exceeded'if self.clock()>=deadline else'transport_error',stage,status)from None
        finally:
            if response is not None:
                try:response.close()
                except Exception:pass


def select_target(value,spec):
    data=value.get('data')if isinstance(value,dict)else None
    if (not isinstance(data,dict)or any(type(data.get(k))is not int or data[k]<0 for k in ('offset','limit','count','total'))
        or data['offset']!=0 or data['limit']!=5 or data.get('desc')is not False
        or not isinstance(data.get('items'),list)or len(data['items'])!=data['count']
        or data['count']>5 or data['total']<data['count']):raise RecoveryError('response_invalid','list',200)
    matches=[];seen=set()
    for row in data['items']:
        try:
            reference=runner.ident(row.get('id'))
            if reference in seen:raise ValueError()
            seen.add(reference)
            if sha(reference.encode())==spec['target_run_sha256']:
                if row.get('actId')!=spec['actor_id']or not runner.timestamp(spec['started_after'])<=runner.timestamp(row.get('startedAt'))<=runner.timestamp(spec['started_before']):raise ValueError()
                matches.append(reference)
        except Exception:raise RecoveryError('response_invalid','list',200)from None
    if len(matches)!=1:raise RecoveryError('target_not_found','list',200)
    return matches[0]


def validated_identity(body,cell):
    data=body.get('data')if isinstance(body,dict)else None
    candidate=copy.deepcopy(data)
    # The frozen runner accepts native int/float cap scalars. Preserve all raw
    # response bytes, while bridging strict Decimal parsing only for this exact
    # integral USD3 cap; strings, booleans and different caps remain rejected.
    if isinstance(candidate,dict)and isinstance(candidate.get('options'),dict):
        amount=candidate['options'].get('maxTotalChargeUsd')
        if isinstance(amount,Decimal):
            expected=Decimal(cell.spec['options']['maxTotalChargeUsd'])
            if not amount.is_finite()or amount!=expected or amount!=amount.to_integral_value():raise RecoveryError('scope_mismatch','run',200)
            candidate['options']['maxTotalChargeUsd']=int(amount)
    return runner.validate_run(candidate,cell,required_status='SUCCEEDED')


def encrypt_raw(blob,path,binary,recipient):
    try:
        if not isinstance(blob,bytes)or not 1<=len(blob)<=RAW_LIMIT:raise ValueError()
        if path.exists()or path.is_symlink():raise ValueError()
        cipher=crypto.crypto(binary,['--encrypt','--recipient',recipient],blob)
        if not cipher.startswith(b'age-encryption.org/v1\n')or len(cipher)>RAW_LIMIT+65536:raise ValueError()
        crypto.durable_write(path,cipher)
        return {'plaintext_sha256':sha(blob),'plaintext_bytes':len(blob),'ciphertext_sha256':sha(cipher),
            'ciphertext_bytes':len(cipher),'durable_encrypted_readback_verified':True}
    except Exception:raise RecoveryError('encryption_failed','evidence')from None


def collect(transport,cell,spec,persist):
    value={'schema_version':1,'evidence_type':'private_exact_original_sustained_evidence_recovery',
        'scope_spec_sha256':SPEC_SHA256,'target_run_sha256':spec['target_run_sha256'],
        'original_scope_sha256':spec['original_scope_sha256'],'identity':None,
        'reads':[],'files':{},'requests_attempted':0,'complete':False,'diagnostic':None,
        'provider_start_attempts':0,'deletions':0,'settings_changes':0,'retained_holds_usd':'8.69'}
    stage='list';status=None
    def read(current,reference=None):
        nonlocal stage,status
        stage=current;status=None
        blob,headers=transport.get(stage,reference);status=200
        value['reads'].append({'stage':stage,'http_status':200,'category':'ok','observed_at_utc':datetime.now(timezone.utc).isoformat()})
        return blob,headers
    def save(blob,headers,rows=None):
        proof=persist(stage,blob)
        value['files'][LABELS[stage]]={**proof,'stage':stage,'headers':headers,'row_count':rows}
    try:
        blob,_=read('list');target=select_target(strict_json(blob),spec)
        # Unselected list records are never retained in ciphertext or public output.
        blob,headers=read('run',target);body=strict_json(blob)
        identity=validated_identity(body,cell)
        transport.bind(identity);value['identity']=identity;save(blob,headers)
        blob,headers=read('dataset',identity['defaultDatasetId']);body=strict_json(blob)
        metadata=body.get('data')if isinstance(body,dict)else None
        runner.validate_metadata(metadata,'dataset',identity)
        if type(metadata.get('itemCount'))is not int or not 0<=metadata['itemCount']<=7681:raise RecoveryError('dataset_invalid','dataset',200)
        save(blob,headers);value['dataset_item_count_at_read']=metadata['itemCount']
        for stage_name in ('raw','clean','projection'):
            blob,headers=read(stage_name,identity['defaultDatasetId']);rows=strict_json(blob)
            if not isinstance(rows,list)or len(rows)>7681:raise RecoveryError('response_invalid',stage,200)
            save(blob,headers,len(rows))
            if stage=='raw'and len(rows)!=metadata['itemCount']:raise RecoveryError('dataset_invalid',stage,200)
        blob,headers=read('log',identity['id']);blob.decode('utf-8');save(blob,headers)
        value['complete']=True
    except Exception as exc:
        error=exc if isinstance(exc,RecoveryError)else RecoveryError('scope_mismatch'if stage in ('run','dataset')else'response_invalid',stage,status)
        value['diagnostic']=error.safe()
        if not value['reads']or value['reads'][-1]['stage']!=stage:value['reads'].append(error.safe())
    value['requests_attempted']=transport.calls
    return value


def public_projection(value,manifest_proof):
    return {'schema_version':1,'evidence_type':'encrypted_exact_original_sustained_recovery',
        'requests_attempted':value['requests_attempted'],'max_requests':MAX_GETS,
        'reads':[{key:read.get(key)for key in ('stage','http_status','category')}for read in value['reads']],
        'complete':value['complete'],'scope_verified':value['identity']is not None,
        'diagnostic':value['diagnostic'],'provider_start_attempts':0,'deletions':0,'settings_changes':0,
        'plaintext_sha256':manifest_proof['plaintext_sha256'],'ciphertext_sha256':manifest_proof['ciphertext_sha256'],
        'encrypted_file_readback_verified':manifest_proof['durable_encrypted_readback_verified']}


def execute(*,opt_in=False,environ=None):
    guard()
    if opt_in is not True:raise RecoveryError('opt_in_required')
    spec,cell,recipient=load_reviewed()
    env=os.environ if environ is None else environ
    temp=env.get('RUNNER_TEMP')
    if type(temp)is not str or not Path(temp).is_absolute():raise RecoveryError('preflight_failed')
    folder=Path(temp)/'apify-original-recovery-private'
    if folder.is_symlink():raise RecoveryError('preflight_failed')
    folder.mkdir(mode=0o700,exist_ok=True);folder.chmod(0o700)
    binary=Path(temp)/'age-v1.3.2'/'age'/'age'
    if any((ROOT/name).exists()or(ROOT/name).is_symlink()for name in OUTPUTS):raise RecoveryError('preflight_failed')
    preflight=folder/'preflight.age';encrypt_raw(b'{"synthetic_preflight":true}',preflight,binary,recipient);preflight.unlink()
    token=env.get('APIFY_TOKEN')
    transport=Transport(token,spec,cell)
    value=collect(transport,cell,spec,lambda stage,blob:encrypt_raw(blob,ROOT/LABELS[stage],binary,recipient))
    proof=encrypt_raw(canonical(value),ROOT/'manifest.age',binary,recipient)
    public=public_projection(value,proof)
    crypto.durable_write(ROOT/'recovery-public.json',canonical(public))
    return public


if __name__=='__main__':
    if sys.argv[1:]!=['--execute']:
        print('{"mode":"offline","provider_requests":0,"provider_start_attempts":0}')
    else:
        try:
            result=execute(opt_in=True);print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result['complete']else 1)
        except RecoveryError as exc:
            print(json.dumps({'diagnostic':exc.safe(),'provider_start_attempts':0,'deletions':0}));raise SystemExit(1)
        except Exception:
            print('{"diagnostic":{"category":"preflight_failed","stage":"preflight","http_status":null},"provider_start_attempts":0,"deletions":0}');raise SystemExit(1)
