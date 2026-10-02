"""One reviewed smoke cell per sequential manual job; private state is never uploaded.

Phase1 writes encrypted evidence plus safe hashes/status. After the owner-side
process decrypts, validates, fsyncs and reads back that exact evidence, it writes
an exact hash-only approval to this existing repository's main branch. Phase2
reads that fixed public approval route, then revalidates terminal/run/store scope
before any approved new unnamed default-store deletion. Missing proof means no
deletion. No private identity key is present in Actions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import evidence_transport as crypto
import runner

ROOT=Path(__file__).resolve().parent
ALLOWED_CELLS=('smoke-cheerio-scraper','smoke-web-scraper','smoke-playwright-scraper',
               'smoke-puppeteer-scraper','smoke-website-content-crawler','smoke-rag-web-browser')
CAPABILITY_CELLS=tuple(value[0] for value in runner.CAPABILITY_CELL_IDENTITIES)
MANIFEST_SCOPES=('cheerio','remaining-five','capability-first-repetition','capability-remaining-repetitions')
APPROVAL_BASE='https://raw.githubusercontent.com/ScrapingAnt/scrapingant-examples/main/examples/apify-study/approvals/'
MAX_APPROVAL_BYTES=16384
MAX_APPROVAL_READS=75
APPROVAL_INTERVAL_SECONDS=15


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def check_cell(cell):
    if cell not in ALLOWED_CELLS+CAPABILITY_CELLS:raise runner.Fault('invalid_cell')
    return 'CAPABILITY' if cell in CAPABILITY_CELLS else 'SMOKE'


def smoke_manifest(scope):
    """Fixed finite cells only; no plan, environment, token or provider access."""
    if scope=='cheerio':return [ALLOWED_CELLS[0]]
    if scope=='remaining-five':return list(ALLOWED_CELLS[1:])
    if scope=='capability-first-repetition':return list(CAPABILITY_CELLS[:12])
    if scope=='capability-remaining-repetitions':return list(CAPABILITY_CELLS[12:])
    raise runner.Fault('invalid_cell')


def matches_approval(value,plain_sha,cipher_sha):
    return (isinstance(value,dict) and set(value)=={'plaintext_sha256','ciphertext_sha256','scope_approved'}
            and value.get('plaintext_sha256')==plain_sha and value.get('ciphertext_sha256')==cipher_sha
            and runner.digest(plain_sha) and runner.digest(cipher_sha) and value.get('scope_approved') is True)


def fetch_approval(cell,*,opener=None,clock=monotonic,deadline=None):
    check_cell(cell)
    opener=opener or build_opener(NoRedirect())
    req=Request(APPROVAL_BASE+cell+'.json',method='GET',headers={'User-Agent':'ScrapingAnt-owned-study-approval/1'})
    try:
        route=min(clock()+10,deadline) if deadline is not None else clock()+10
        if route<=clock():return None
        with opener.open(req,timeout=min(10,route-clock())) as response:
            if response.status!=200:return None
            chunks=[];size=0
            while size<=MAX_APPROVAL_BYTES:
                if clock()>=route:return None
                chunk=response.read1(min(4096,MAX_APPROVAL_BYTES+1-size))
                if clock()>route:return None
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
            blob=b''.join(chunks)
        if len(blob)>MAX_APPROVAL_BYTES:return None
        value=crypto.json_payload(blob)
        return value if isinstance(value,dict) else None
    except (HTTPError,OSError,ValueError,UnicodeError,RecursionError,crypto.TransportError,AttributeError):
        return None


def await_approval(cell,plain_sha,cipher_sha,*,seconds,clock=monotonic,wait=sleep):
    check_cell(cell)
    deadline=clock()+max(0,min(seconds,runner.APPROVAL_AGE_SECONDS))
    for _ in range(MAX_APPROVAL_READS):
        if deadline-clock()<10:break
        value=fetch_approval(cell,clock=clock,deadline=deadline)
        if matches_approval(value,plain_sha,cipher_sha):return value
        remaining=deadline-clock()
        if remaining<=0:break
        wait(min(APPROVAL_INTERVAL_SECONDS,remaining))
    return None


def private_paths(environ):
    temp=environ.get('RUNNER_TEMP')
    if not isinstance(temp,str) or not Path(temp).is_absolute():raise runner.Fault('persistence_failed','evidence')
    folder=Path(temp)/'apify-study-private'
    folder.mkdir(mode=0o700,exist_ok=True)
    if folder.is_symlink():raise runner.Fault('persistence_failed','evidence')
    folder.chmod(0o700)
    binary=Path(temp)/'age-v1.3.2'/'age'/'age'
    return folder,binary


def plan(cell=None):
    stage=check_cell(cell) if cell is not None else 'SMOKE'
    reviewed=runner.load_reviewed_plan((ROOT/('capability-plan.json' if stage=='CAPABILITY' else 'plan.json')).read_bytes())
    if reviewed['stage']!=stage:raise runner.Fault('unreviewed_plan')
    return reviewed


def safe_write(path,value):
    crypto.durable_write(path,runner.canonical(value))


def capture(cell,*,environ=None):
    stage=check_cell(cell)
    runner.require_guard(stage)
    reviewed=plan(cell) if stage=='CAPABILITY' else plan()
    if runner.prepare_cell(reviewed,cell).spec.get('force_permission_level')!='LIMITED_PERMISSIONS':
        raise runner.Fault('invalid_cell')
    environ=os.environ if environ is None else environ
    folder,binary=private_paths(environ)
    recipient=(ROOT/'recipient.txt').read_text().strip()
    # Prove that the pinned binary, public recipient and durable output work
    # before any provider call. The local identity roundtrip was reviewed first.
    preflight=folder/'preflight.age'
    crypto.encrypt_capture(b'{"synthetic_transport_preflight":true,"provider_calls":0}',preflight,binary,recipient)
    preflight.unlink()
    state=runner.execute(reviewed,cell,opt_in=True,environ=environ,
        budget=runner.StudyBudget(reviewed),
        persist_encrypted=lambda payload:crypto.encrypt_capture(payload,ROOT/'capture.age',binary,recipient))
    crypto.durable_write(folder/'state.json',runner.serialize_private_state(state))
    public=runner.public_result(state)
    public['plaintext_sha256']=state.plaintext_sha256 if runner.digest(state.plaintext_sha256) else None
    public['encrypted_capture_verified']=state.encrypted_verified is True
    public['capture_scope_verified']=state.capture_verified is True
    safe_write(ROOT/'capture-public.json',public)
    return public


def cleanup_public(result):
    diagnostic=result.get('diagnostic')
    diagnostic=runner.Fault(diagnostic.get('category'),diagnostic.get('stage'),diagnostic.get('http_status')).safe() if isinstance(diagnostic,dict) else None
    state=result.get('cleanup_state')
    return {'cleanup_state':state if state in ('complete','blocked','residual') else 'blocked',
            'owner_attention_required':result.get('owner_attention_required') is not False,'diagnostic':diagnostic}


def cleanup(cell,*,environ=None):
    stage=check_cell(cell)
    runner.require_guard(stage)
    reviewed=plan(cell) if stage=='CAPABILITY' else plan()
    environ=os.environ if environ is None else environ
    folder,binary=private_paths(environ)
    file=folder/'state.json'
    if file.is_symlink() or file.stat().st_mode&0o777!=0o600:raise runner.Fault('state_mismatch','approval')
    with file.open('rb') as stream:blob=stream.read(2*crypto.MAX_PLAINTEXT_BYTES+1)
    state=runner.restore_private_state(blob,reviewed)
    if state.cell.cell_id!=cell:raise runner.Fault('state_mismatch','approval')
    blocked={'cleanup_state':'blocked','owner_attention_required':True,'diagnostic':None}
    if not state.capture_verified or not state.encrypted_verified or state.latest_active:
        result=blocked
    else:
        finish=runner.timestamp(state.identity['finishedAt'])
        seconds=runner.APPROVAL_AGE_SECONDS-(datetime.now(timezone.utc)-finish).total_seconds()
        approval=await_approval(cell,state.plaintext_sha256,state.ciphertext_sha256,seconds=seconds)
        if approval is None:
            result=dict(blocked,diagnostic=runner.Fault('approval_missing','approval').safe())
        else:
            try:
                token=environ.get('APIFY_TOKEN')
                if not isinstance(token,str) or not token:raise runner.Fault('token_unavailable')
                transport=runner.HttpTransport(state.cell,token,mode='cleanup',identity=state.identity,
                                                request_counts=state.request_counts)
                result=runner.cleanup_verified_capture(transport,state,approval,
                    verify_local_approval=lambda plain,cipher,record:matches_approval(record,plain,cipher) and record==approval)
            except runner.Fault as exc:
                result=dict(blocked,diagnostic=exc.safe())
            except Exception:
                result=dict(blocked,diagnostic=runner.Fault('transport_error','cleanup').safe())
    final={'schema_version':1,'stage':state.cell.stage,'cell_id':cell,'initial_capture':state.evidence,
           'cleanup':result,'request_counts':state.request_counts,'finalized_at':datetime.now(timezone.utc).isoformat()}
    recipient=(ROOT/'recipient.txt').read_text().strip()
    receipt=crypto.encrypt_capture(runner.canonical(final),ROOT/'final.age',binary,recipient)
    public=cleanup_public(result)
    public.update(cell_id=cell,stage=state.cell.stage,request_counts=state.request_counts,
                  plaintext_sha256=receipt['plaintext_sha256'],ciphertext_sha256=receipt['ciphertext_sha256'])
    safe_write(ROOT/'final-public.json',public)
    return public


def main():
    parser=argparse.ArgumentParser(description='Bounded reviewed smoke transport; default offline')
    parser.add_argument('phase',choices=('manifest','capture','cleanup'))
    parser.add_argument('--smoke-scope',choices=MANIFEST_SCOPES)
    parser.add_argument('--cell',choices=ALLOWED_CELLS+CAPABILITY_CELLS,default=ALLOWED_CELLS[0])
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if args.phase=='manifest':
        if args.execute:parser.error('manifest is offline only')
        print(json.dumps(smoke_manifest(args.smoke_scope or 'cheerio')))
        return 0
    if args.smoke_scope is not None:parser.error('smoke scope applies only to the offline manifest')
    if not args.execute:
        print(json.dumps({'mode':'offline','provider_calls':0,'guard_closed':runner.RUNNER_READY is not True}))
        return 0
    try:
        value=capture(args.cell) if args.phase=='capture' else cleanup(args.cell)
        print(json.dumps(value,sort_keys=True))
        if args.phase=='capture':
            valid=(value.get('capture_scope_verified') is True and value.get('encrypted_capture_verified') is True
                   and value.get('owner_attention_required') is False and value.get('status') in runner.TERMINAL)
        else:
            valid=value.get('cleanup_state')=='complete' and value.get('owner_attention_required') is False
        return 0 if valid else 1
    except Exception as exc:
        fault=exc if isinstance(exc,runner.Fault) else runner.Fault('persistence_failed','evidence')
        print(json.dumps({'cell_id':args.cell,'stage':check_cell(args.cell),'diagnostic':fault.safe(),'owner_attention_required':True}))
        return 1


if __name__=='__main__':raise SystemExit(main())
