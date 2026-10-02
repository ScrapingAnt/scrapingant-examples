"""One approved wider read-only check. All statuses/builds, no start or DELETE."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from calibration import API, PUBLIC_ACTOR_ID, REVIEWED_GUARD, build_plan
from diagnosis import BUILD, NoRedirect, ReadFailure, RESPONSE_LIMIT, identifier, identity_id, moment

START='2026-10-02T14:00:00Z'
LIMIT=5
MAX_PAGES=2
MAX_READS=21  # Remaining from23 after the first wider check used2GETs.
WIDE_OPEN=False  # Closed after the single corrected read-only dispatch.
ERROR_TYPES=('invalid-input','invalid-parameter','invalid-value','invalid-request','invalid-id',
             'parameter-required','param-not-one-of','schema-validation-error','invalid-token',
             'missing-api-token','insufficient-permissions')
QUERY_KEYS=('startedAfter','startedBefore','desc','limit','offset')

def freeze_end():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

class SafeQueryFailure(ReadFailure):
    def __init__(self,status,category,body):
        super().__init__(status,category)
        error=body.get('error') if isinstance(body,dict) else None
        error=error if isinstance(error,dict) else {}
        self.provider_error_type=error.get('type') if error.get('type') in ERROR_TYPES else None
        message=error.get('message')
        hints=[key for key in QUERY_KEYS if isinstance(message,str) and re.search(r'\b'+key+r'\b',message)]
        self.parameter_hint=hints[0] if len(hints)==1 else None  # Hint only, never a causal claim.

def page_path(offset,end):
    return '/actors/apify~web-scraper/runs?'+urlencode({'limit':LIMIT,'offset':offset,
                                                     'startedAfter':START,'startedBefore':end})

def page_data(response,offset,end,total=None):
    if not isinstance(response,dict) or not isinstance(response.get('data'),dict): raise ValueError
    data=response['data']
    if any(type(data.get(k)) is not int or data[k]<0 for k in ('total','offset','count','limit')): raise ValueError
    items=data.get('items')
    if (data['offset']!=offset or data['limit']!=LIMIT or not isinstance(items,list)
            or data['count']!=len(items) or len(items)!=min(LIMIT,max(data['total']-offset,0))
            or (total is not None and data['total']!=total)): raise ValueError
    for run in items:
        if (not isinstance(run,dict) or not identifier(run.get('id')) or run.get('actId')!=PUBLIC_ACTOR_ID
                or not moment(START)<=moment(run.get('startedAt'))<=moment(end)): raise ValueError
    return data['total'],items

def exact_run(response,candidate,user_id,end):
    if not isinstance(response,dict) or not isinstance(response.get('data'),dict): raise ValueError
    run=response['data']
    if (run.get('id')!=candidate['id'] or run.get('actId')!=PUBLIC_ACTOR_ID or run.get('userId')!=user_id
            or run.get('startedAt')!=candidate['startedAt'] or not identifier(run.get('defaultKeyValueStoreId'))
            or not moment(START)<=moment(run['startedAt'])<=moment(end)
            or (candidate.get('defaultKeyValueStoreId') is not None
                and candidate['defaultKeyValueStoreId']!=run['defaultKeyValueStoreId'])): raise ValueError
    # No build, status or options filter: pending/wrong-build candidates must remain visible.
    return run

def check_coverage(transport,end):
    result={'evidence_type':'wider_read_only_coverage_not_a_bill','window_start':START,'window_end':end,
            'all_statuses':True,'all_builds':True,'page_limit':LIMIT,'maximum_pages':MAX_PAGES,
            'maximum_reads':MAX_READS,'requests_attempted':0,'reads':[],'pages_read':0,
            'coverage_complete':False,'listed_run_count':None,'matching_test_inputs':None,
            'correlation_complete':False,'retry_eligible':False,'console_token_identity_match':None,
            'outcome':'unknown'}
    def read(stage,**kw):
        if result['requests_attempted']>=MAX_READS: raise ReadFailure(None,'route_rejected')
        result['requests_attempted']+=1
        try: value=transport.get(stage,**kw)
        except ReadFailure as error:
            result['reads'].append({'stage':stage,'http_status':error.status,'category':error.category,
                                   'provider_error_type':getattr(error,'provider_error_type',None),
                                   'parameter_hint':getattr(error,'parameter_hint',None)})
            raise
        result['reads'].append({'stage':stage,'http_status':200,'category':'ok'}); return value
    try:
        user=identity_id(read('identity')); rows=[]; total=None
        for page in range(MAX_PAGES):
            total,items=page_data(read('page',offset=page*LIMIT,end=end),page*LIMIT,end,total)
            result['pages_read']+=1
            if total>LIMIT*MAX_PAGES:
                result['outcome']='coverage_exceeds_bound'; return result
            rows.extend(items)
            if len(rows)==total: break
        if len(rows)!=total or len({r['id'] for r in rows})!=len(rows): raise ValueError
        result.update(coverage_complete=True,listed_run_count=len(rows))
        if not rows:
            result.update(correlation_complete=True,matching_test_inputs=0,retry_eligible=True,
                          outcome='complete_empty_actor_window'); return result
        if any(r.get('userId') is not None and r['userId']!=user for r in rows):
            result['outcome']='foreign_owner_unresolved'; return result
        matched=0
        for candidate in rows:
            run=exact_run(read('run',run_id=candidate['id']),candidate,user,end)
            supplied=read('input',kv_id=run['defaultKeyValueStoreId'])
            if json.dumps(supplied,sort_keys=True,allow_nan=False)==json.dumps(build_plan(BUILD)['input'],sort_keys=True):
                matched+=1
        result.update(matching_test_inputs=matched,correlation_complete=True,outcome='runs_present_no_retry')
    except ReadFailure: result['outcome']='read_failed_unresolved'
    except Exception: result['outcome']='validation_failed_unresolved'
    return result

class CoverageTransport:
    def __init__(self,token,end,*,opener=None):
        if not isinstance(token,str) or not token or len(token)>4096 or any(ord(c)<33 or ord(c)>126 for c in token):
            raise ReadFailure(None,'authentication_rejected')
        self._token=token; self._end=end; self._opener=build_opener(NoRedirect()) if opener is None else opener
        self._calls=0; self._deadline=monotonic()+250; self._user=None; self._pages=[]; self._total=None
        self._rows={}; self._kv={}; self._seen_runs=set(); self._seen_kv=set(); self._seen_page_offsets=set()

    def get(self,stage,**kw):
        if self._calls>=MAX_READS: raise ReadFailure(None,'route_rejected')
        if stage=='identity' and self._calls==0 and not kw: path='/users/me'
        elif (stage=='page' and self._user is not None and len(self._pages)<MAX_PAGES
              and kw=={'offset':len(self._pages)*LIMIT,'end':self._end} and not self._rows
              and kw['offset'] not in self._seen_page_offsets
              and (self._total is None or len(self._pages)*LIMIT<self._total)):
            self._seen_page_offsets.add(kw['offset'])
            path=page_path(kw['offset'],self._end)
        elif stage=='run' and set(kw)=={'run_id'} and kw['run_id'] in self._rows and kw['run_id'] not in self._seen_runs:
            self._seen_runs.add(kw['run_id']); path='/actor-runs/'+kw['run_id']
        elif stage=='input' and set(kw)=={'kv_id'} and kw['kv_id'] in self._kv and kw['kv_id'] not in self._seen_kv:
            self._seen_kv.add(kw['kv_id']); path='/key-value-stores/'+kw['kv_id']+'/records/INPUT'
        else: raise ReadFailure(None,'route_rejected')
        remaining=self._deadline-monotonic()
        if remaining<=0: raise ReadFailure(None,'wall_deadline')
        self._calls+=1
        request=Request(API+path,method='GET',headers={'Authorization':'Bearer '+self._token,
                                                     'Accept':'application/json','Accept-Encoding':'identity'})
        try:
            with self._opener.open(request,timeout=min(10,remaining)) as response:
                status=response.status
                if status!=200: raise ReadFailure(status,'unexpected_status')
                raw=bytearray(); reader=getattr(response,'read1',response.read)
                while True:
                    if monotonic()>=self._deadline: raise ReadFailure(status,'wall_deadline')
                    chunk=reader(min(8192,RESPONSE_LIMIT+1-len(raw)))
                    if not chunk: break
                    raw.extend(chunk)
                    if len(raw)>RESPONSE_LIMIT: raise ReadFailure(status,'response_too_large')
                try: parsed=json.loads(raw.decode('utf-8'),parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
                except (ValueError,UnicodeError): raise ReadFailure(status,'invalid_json') from None
        except HTTPError as error:
            status=error.code; body=None
            try:
                raw=bytearray(); reader=getattr(error,'read1',error.read); stop=min(self._deadline,monotonic()+10)
                while monotonic()<stop:
                    chunk=reader(min(8192,RESPONSE_LIMIT+1-len(raw)))
                    if not chunk: break
                    raw.extend(chunk)
                    if len(raw)>RESPONSE_LIMIT: raise ValueError
                if monotonic()>=stop: raise ValueError
                body=json.loads(raw.decode('utf-8'))
            except Exception: pass
            finally: error.close()
            category={401:'authentication_rejected',403:'forbidden',404:'not_found'}.get(status)
            raise SafeQueryFailure(status,category or ('provider_error' if status>=500 else 'request_rejected'),body) from None
        except ReadFailure: raise
        except (OSError,URLError): raise ReadFailure(None,'transport_error') from None
        try:
            if stage=='identity': self._user=identity_id(parsed)
            elif stage=='page':
                total,items=page_data(parsed,kw['offset'],self._end,self._total)
                self._total=total; self._pages.append(items)
                rows=[r for page in self._pages for r in page]
                if total<=LIMIT*MAX_PAGES and len(rows)==total and len({r['id'] for r in rows})==len(rows):
                    if all(r.get('userId') in (None,self._user) for r in rows): self._rows={r['id']:r for r in rows}
            elif stage=='run':
                run=exact_run(parsed,self._rows[kw['run_id']],self._user,self._end)
                self._kv[run['defaultKeyValueStoreId']]=run['id']
        except Exception: pass
        return parsed

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute-read-only',action='store_true')
    args=parser.parse_args(argv)
    if not args.execute_read_only:
        print(json.dumps({'evidence_type':'offline_wider_plan','provider_requests':0,'maximum_reads':MAX_READS,
                          'methods':['GET'],'all_statuses':True,'all_builds':True})); return 0
    if WIDE_OPEN is not True or REVIEWED_GUARD.get('ready') is not False:
        print(json.dumps({'outcome':'guard_closed','provider_requests':0})); return 1
    end=freeze_end()  # Freeze documented millisecond UTC format before token access.
    try: transport=CoverageTransport(os.environ.get('APIFY_TOKEN'),end)
    except ReadFailure:
        print(json.dumps({'outcome':'token_invalid','provider_requests':0})); return 1
    result=check_coverage(transport,end); encoded=json.dumps(result,indent=2,sort_keys=True)+'\n'
    Path('coverage-receipt.json').write_text(encoded,encoding='utf-8'); print(encoded,end=''); return 0

if __name__=='__main__': raise SystemExit(main())
