"""Closed six-GET recovery of one hash-committed WCC run and four stores.

No start, abort, listing, item export, retry, redirect or storage mutation.
Existing Actions token only; a separately approved data-only target is required.
Original default-only failure remains. Recovery never authorizes another start.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
from urllib.request import build_opener
import ast,copy,json,os,re,sys,time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'apify-breadth-study'))
import recover_existing as base

RECOVERY_READY = True
SPEC_SHA256='dbb70daad8322778699f64ccbba1f3143b00a4578677a26b6e1b63d62a642c2e'
STAGES=('run','dataset','kv','queue','extra','meter')
TARGET_FIELDS=base.TARGET_FIELDS+('options','extraDatasetAlias','extraDatasetId')
DEPS={'apify-breadth-study/recover_existing.py','apify-breadth-study/controller.py',
 'apify-breadth-study/storage_policy.py','apify-breadth-study/breadth-plan.json',
 'apify-continuation-study/controller.py','apify-continuation-study/continuation-plan.json',
 'apify-study/runner.py','apify-study/billing_projection.py',
 'apify-sustained/evidence_transport.py','apify-sustained/recipient.txt'}

def fail(category,stage='preflight',status=None):
    error=base.RecoveryError(category,stage,status)
    error.stage=stage if stage in STAGES+('preflight','evidence')else'preflight'
    return error
def guard():
    if RECOVERY_READY is not True:raise fail('guard_closed')
def stamp(value):
    try:
        if type(value)is not str or len(value)>64:raise ValueError()
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
        if date.tzinfo is None or date.utcoffset().total_seconds()!=0:raise ValueError()
        return date
    except Exception:raise fail('scope_mismatch')from None
def load_reviewed():
    try:
        p=ROOT/'scope.json'
        if p.is_symlink()or not p.is_file()or not 1<=p.stat().st_size<=8192:raise ValueError()
        blob=p.read_bytes();spec=base.strict(blob)
        if base.sha(blob)!=SPEC_SHA256 or set(spec['dependencies_sha256'])!=DEPS:raise ValueError()
        if not(spec['schema_version']==1 and spec['cell_id']=='cap-r2-website-content-crawler'
            and spec['actor_id']=='aYG0l9s7dbB7j3gbS'and spec['build']=='0.3.97'
            and spec['maximum_GETs']==6 and spec['provider_mutations']==0
            and spec['target_secret_name']=='APIFY_WCC_RECOVERY_TARGET'
            and spec['body_limit_bytes']==131072 and spec['transport_wall_seconds']==150
            and spec['route_timeout_seconds']==20 and spec['strict_run_cap_usd']=='0.08'
            and spec['retained_ancillary_reserve_usd']=='0.02'
            and spec['original_default_only_failure_preserved']is True
            and spec['future_Actor_start_authorized']is False):raise ValueError()
        for name,digest in spec['dependencies_sha256'].items():
            path=ROOT.parent/name
            if path.is_symlink()or not path.is_file()or base.sha(path.read_bytes())!=digest:raise ValueError()
        for name in ('apify-breadth-study/controller.py','apify-continuation-study/controller.py'):
            nodes=ast.parse((ROOT.parent/name).read_text()).body
            values=[ast.literal_eval(n.value)for n in nodes if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name)and t.id=='ACTIVE_CELL'for t in n.targets)]
            if values!=[None]:raise ValueError()
        if base.RECOVERY_READY is not False or base.controller.ACTIVE_CELL is not None:raise ValueError()
        plan=base.strict((ROOT.parent/'apify-continuation-study/continuation-plan.json').read_bytes())
        cell=next(c for c in plan['cells']if c['cell_id']==spec['cell_id'])
        if cell['actor']!='apify/website-content-crawler'or cell['actor_id']!=spec['actor_id']or cell['build']!=spec['build']:raise ValueError()
        validators,crypto=base.controller.load_sources()
        if any(getattr(validators,k)is not False for k in ('RUNNER_READY','GRAPH_READY','CONCURRENCY_READY')):raise ValueError()
        recipient=(ROOT.parent/'apify-sustained/recipient.txt').read_text().strip()
        if re.fullmatch(r'age1[a-z0-9]{58}',recipient)is None:raise ValueError()
        return spec,cell,validators,crypto,recipient
    except Exception:raise fail('source_invalid')from None

def target_from_data(value,spec,validators,cell):
    try:
        if type(value)is not str or not 1<=len(value.encode())<=8192 or base.sha(value.encode())!=spec['target_payload_sha256']:raise ValueError()
        target=base.strict(value.encode())
        if set(target)!=set(TARGET_FIELDS):raise ValueError()
        for key in base.TARGET_FIELDS[:6]+('extraDatasetId',):
            if type(target[key])is not str or re.fullmatch(r'[A-Za-z0-9]{17}',target[key])is None:raise ValueError()
        if not(target['actId']==cell['actor_id']and target['build']==cell['build']
            and target['status']=='ABORTING'and target['finishedAt']is None
            and target['extraDatasetAlias']=='errors'and target['options']==cell['options']
            and len({target[k]for k in base.TARGET_FIELDS[3:6]+('extraDatasetId',)})==4):raise ValueError()
        validators.timestamp(target['startedAt'])
        return target
    except Exception:raise fail('target_invalid')from None

def validate_run(data,validators,cell,target,initial=None):
    try:
        identity=validators.validate_run(data,SimpleNamespace(spec=cell),initial or target)
        expected={'datasets':{'default':target['defaultDatasetId'],'errors':target['extraDatasetId']},
            'keyValueStores':{'default':target['defaultKeyValueStoreId']},'requestQueues':{'default':target['defaultRequestQueueId']}}
        if data.get('storageIds')!=expected:raise ValueError()
        if initial and (identity['status']!=initial['status']or identity['finishedAt']!=initial['finishedAt']):raise ValueError()
        return identity
    except Exception:raise fail('scope_mismatch')from None

def project_meter(data,validators,cell):
    value=validators.run_receipt(data,SimpleNamespace(spec=cell))
    if type(value.get('usage_total_usd'))is int:value['usage_total_usd']=str(value['usage_total_usd'])
    amount=value.get('usage_total_usd')
    if amount is not None:
        try:
            number=Decimal(amount)
            if not number.is_finite()or number<0:raise ValueError()
        except Exception:raise fail('response_invalid')from None
    return value

def metadata(data,stage,target,identity):
    field={'dataset':'defaultDatasetId','kv':'defaultKeyValueStoreId','queue':'defaultRequestQueueId','extra':'extraDatasetId'}[stage]
    if not isinstance(data,dict)or data.get('id')!=target[field]or data.get('userId')!=identity['userId']:raise fail('scope_mismatch',stage)
    for name,expected in (('actId',identity['actId']),('actRunId',identity['id'])):
        if name in data and data[name]is not None and data[name]!=expected:raise fail('scope_mismatch',stage)
    name_valid='name'in data and (data['name']is None or type(data['name'])is str)
    created=None
    if type(data.get('createdAt'))is str:
        try:created=stamp(data['createdAt'])
        except base.RecoveryError:pass
    fresh=created is not None and stamp(identity['startedAt'])<=created<=stamp(identity['finishedAt'])
    stats=data.get('stats')if isinstance(data.get('stats'),dict)else{}
    size=stats.get('storageBytes');size=size if type(size)is int and 0<=size<=10**15 else None
    count=data.get('itemCount');count=count if type(count)is int and 0<=count<=10**9 else None
    owned=(data.get('actId')==identity['actId']and data.get('actRunId')==identity['id'])
    unnamed=name_valid and data['name']is None
    return {'role':'registered_errors_dataset'if stage=='extra'else'default_'+stage,
        'ID_and_owner_match':True,'Actor_and_run_association_verified':owned,
        'name_present_and_valid':name_valid,'named':None if not name_valid else not unnamed,
        'created_at':data.get('createdAt'),'created_within_strict_run_window':fresh,
        'storage_bytes':size,'item_count':count if stage in ('dataset','extra')else None,
        'fresh_unnamed_owned_verified':owned and unnamed and fresh,
        'byte_measurement_known':size is not None,'extra_items_not_read':True,
        'absence_of_other_SDK_storage_access_proven':False}

class Transport(base.Transport):
    def __init__(self,token,target,*,opener=None,clock=time.monotonic):
        guard()
        if type(token)is not str or re.fullmatch(r'[A-Za-z0-9_-]{16,512}',token)is None:raise fail('token_unavailable')
        self._token,self.target,self.clock=token,copy.deepcopy(target),clock
        self._open=opener or build_opener(base.NoRedirect()).open
        self.deadline,self.calls,self.failed=clock()+150,0,False
    def __repr__(self):return'<bounded six-GET WCC recovery transport>'
    def route(self,stage):
        guard()
        if self.failed or self.calls>=6 or stage!=STAGES[self.calls]:raise fail('route_invalid',stage)
        if stage in ('run','meter'):path='actor-runs/'+self.target['id']
        else:
            route,field={'dataset':('datasets','defaultDatasetId'),'kv':('key-value-stores','defaultKeyValueStoreId'),
                'queue':('request-queues','defaultRequestQueueId'),'extra':('datasets','extraDatasetId')}[stage]
            path=route+'/'+self.target[field]
        return'https://api.apify.com/v2/'+path,131072
    def get(self,stage):
        try:return super().get(stage)
        except base.RecoveryError as e:raise fail(e.category,stage,e.status)from None

def collect(transport,spec,cell,validators,persist):
    value={'schema_version':1,'scope_spec_sha256':SPEC_SHA256,'target_payload_sha256':spec['target_payload_sha256'],
      'identity':None,'files':{},'stores':{},'requests_attempted':0,'capture_complete':False,'capture_diagnostic':None,
      'terminal_verified':False,'latest_native_nonterminal_observed':False,'latest_terminal_run_meter':None,
      'latest_meter_is_current_terminal_observation':False,
      'meter_snapshot_used_once':True,'four_stores_fresh_unnamed_owned_verified':False,
      'original_default_only_failure_preserved':True,'ready_for_next_Actor_start':False,
      'Actor_starts':0,'aborts':0,'DELETEs':0,'item_exports':0,'hold_release_usd':'0','invoice_finality':False}
    stage='run'
    try:
        for stage in STAGES:
            blob,headers=transport.get(stage)
            proof=persist(stage,blob)
            value['files'][stage+'.age']={**proof,'headers':headers,'observed_at_utc':datetime.now(timezone.utc).isoformat()}
            body=base.strict(blob);data=body.get('data')if isinstance(body,dict)else None
            if stage in ('run','meter'):
                if isinstance(data,dict)and data.get('id')==transport.target['id']and data.get('status')in validators.ACTIVE:
                    value['latest_native_nonterminal_observed']=True;value['terminal_verified']=False
                    value['latest_meter_is_current_terminal_observation']=False
                identity=validate_run(data,validators,cell,transport.target,value['identity'])
                value['identity']=identity
                if identity['status']not in validators.TERMINAL:raise fail('preflight_failed',stage)
                if stamp(identity['finishedAt'])>datetime.now(timezone.utc)+timedelta(seconds=5):raise fail('scope_mismatch',stage)
                value['terminal_verified']=True
                value['latest_terminal_run_meter']=project_meter(data,validators,cell)
                value['latest_meter_is_current_terminal_observation']=True
            else:value['stores'][stage]=metadata(data,stage,transport.target,value['identity'])
        value['capture_complete']=True
        value['four_stores_fresh_unnamed_owned_verified']=all(x['fresh_unnamed_owned_verified']for x in value['stores'].values())
    except Exception as e:
        error=e if isinstance(e,base.RecoveryError)else fail('scope_mismatch',stage)
        value['capture_diagnostic']=error.safe()
    value['requests_attempted']=transport.calls
    return value

def public_projection(value,proof):
    return {'schema_version':1,'scope_spec_sha256':SPEC_SHA256,'maximum_GETs':6,'capture_complete':value['capture_complete'],
      'terminal_verified':value['terminal_verified'],'latest_native_nonterminal_observed':value['latest_native_nonterminal_observed'],
      'capture_diagnostic':value['capture_diagnostic'],'requests_attempted':value['requests_attempted'],
      'encrypted_files':len(value['files']),'original_default_only_failure_preserved':True,
      'ready_for_next_Actor_start':False,'Actor_starts':0,'aborts':0,'DELETEs':0,'item_exports':0,
      'plaintext_sha256':proof['plaintext_sha256'],'ciphertext_sha256':proof['ciphertext_sha256'],
      'durable_encrypted_readback_verified':proof['durable_encrypted_readback_verified']}

def execute(*,opt_in=False,environ=None):
    guard()
    if opt_in is not True:raise fail('opt_in_required')
    spec,cell,validators,crypto,recipient=load_reviewed()
    env=os.environ if environ is None else environ
    target=target_from_data(env.get(spec['target_secret_name']),spec,validators,cell)
    temp=env.get('RUNNER_TEMP');output=ROOT/'capture'
    if type(temp)is not str or not Path(temp).is_absolute()or output.exists()or output.is_symlink():raise fail('preflight_failed')
    output.mkdir(mode=0o700);binary=Path(temp)/'age-v1.3.2/age/age'
    preflight=output/'preflight.age';base.encrypt_raw(b'{"named_synthetic_preflight":true}',preflight,binary,recipient,crypto);preflight.unlink()
    transport=Transport(env.get('APIFY_TOKEN'),target)
    value=collect(transport,spec,cell,validators,
        lambda stage,blob:base.encrypt_raw(blob,output/(stage+'.age'),binary,recipient,crypto))
    proof=base.encrypt_raw(base.canonical(value),output/'manifest.age',binary,recipient,crypto)
    public=public_projection(value,proof);crypto.durable_write(output/'recovery-public.json',base.canonical(public))
    return public

if __name__=='__main__':
    if sys.argv[1:]!=['--execute']:print('{"mode":"offline","provider_requests":0,"Actor_starts":0,"DELETEs":0}')
    else:
        try:
            result=execute(opt_in=True);print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result['capture_complete']else 1)
        except base.RecoveryError as e:print(json.dumps({'diagnostic':e.safe(),'Actor_starts':0,'DELETEs':0}));raise SystemExit(1)
        except Exception:print('{"diagnostic":{"category":"preflight_failed"},"Actor_starts":0,"DELETEs":0}');raise SystemExit(1)
