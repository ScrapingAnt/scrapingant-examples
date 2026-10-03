"""Separate closed two-GET monthly product-billing diagnostic; no Actor starts.

Header auth to fixed HTTPS routes only. Failures consume a slot; no redirects,
retry, profile/payment routes or raw-body persistence. Private projection is
allowlisted and authenticated-encrypted before upload. Existing guard untouched.
"""
import argparse,json,os,hashlib
from pathlib import Path
from time import monotonic
from urllib.request import Request,HTTPRedirectHandler,build_opener
from urllib.error import HTTPError,URLError
import evidence_transport as crypto
import monthly_usage_projection as projection

BILLING_READY=False
URLS=('https://api.apify.com/v2/users/me/usage/monthly?date=2026-10-03','https://api.apify.com/v2/users/me/limits')
ROOT=Path(__file__).resolve().parent
REVIEWED_SOURCES={'monthly_usage_projection.py': '93a5f8381aa680bbba07fcb7ea539cf071ce2e659c52e4777e17cee878b6509b', 'evidence_transport.py': 'eada45743952f7433ade8ecec6358f1130b386964478a533584efb8957a1c6f6', 'recipient.txt': '7da784c7f41ff4e52cce510c67943403dab25843a997bd805d6c4b4c7415ddac'}
def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')
def private_paths(environ):
 temp=environ.get('RUNNER_TEMP')
 if type(temp)is not str or not Path(temp).is_absolute():raise ReadError('persistence_failed')
 folder=Path(temp)/'apify-monthly-diagnostic-private'
 folder.mkdir(mode=0o700,exist_ok=True)
 if folder.is_symlink():raise ReadError('persistence_failed')
 folder.chmod(0o700)
 return folder,Path(temp)/'age-v1.3.2'/'age'/'age'
CATEGORIES=('guard_closed','opt_in_required','token_unavailable','route_rejected','deadline_exceeded','unexpected_status','http_error','redirect_refused','connection_error','invalid_json','response_too_large','transport_error','persistence_failed')
class ReadError(Exception):
 def __init__(self,category,status=None):
  self.category=category if category in CATEGORIES else 'transport_error';self.status=status if type(status)is int and 100<=status<=599 else None
  super().__init__('private_billing_read_stopped')
 def safe(self):return {'category':self.category,'http_status':self.status}
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def guard():
 if BILLING_READY is not True:raise ReadError('guard_closed')
def verify_sources():
 for name,expected in REVIEWED_SOURCES.items():
  path=ROOT/name
  if path.is_symlink() or not path.is_file() or path.stat().st_size>131072 or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
   raise ReadError('persistence_failed')
def token_valid(token):
 if type(token)is not str or not 1<=len(token)<=512 or any(ord(c)<33 or ord(c)>126 for c in token):raise ReadError('token_unavailable')

class Transport:
 def __init__(self,token,*,opener=None,clock=monotonic):
  guard();token_valid(token);self._token=token;self.calls=0;self.failed=False;self.clock=clock;self.deadline=clock()+30
  self._open=opener if opener is not None else build_opener(NoRedirect()).open
 def __repr__(self):return '<fixed private two-GET diagnostic>'
 def get(self,url):
  guard()
  if self.failed or self.calls>=2 or url!=URLS[self.calls]:raise ReadError('route_rejected')
  remaining=self.deadline-self.clock()
  if remaining<=0:raise ReadError('deadline_exceeded')
  self.calls+=1;route=min(self.deadline,self.clock()+10)
  request=Request(url,method='GET',headers={'Authorization':'Bearer '+self._token,'Accept':'application/json','Accept-Encoding':'identity'})
  response=None;status=None
  try:
   response=self._open(request,timeout=min(10,remaining));status=response.status
   if type(status)is not int or status!=200:raise ReadError('unexpected_status',status)
   raw=bytearray()
   while True:
    if self.clock()>=route:raise ReadError('deadline_exceeded',status)
    chunk=response.read1(min(8192,projection.RESPONSE_LIMIT+1-len(raw)))
    if self.clock()>route:raise ReadError('deadline_exceeded',status)
    if not chunk:break
    raw.extend(chunk)
    if len(raw)>projection.RESPONSE_LIMIT:raise ReadError('response_too_large',status)
   try:value=projection.parse_response(bytes(raw))
   except projection.ProjectionError:raise ReadError('invalid_json',status) from None
   if self.clock()>route:raise ReadError('deadline_exceeded',status)
   return value
  except HTTPError as e:
   self.failed=True;status=e.code;e.close()
   raise ReadError('redirect_refused' if type(status)is int and 300<=status<=399 else 'http_error',status) from None
  except ReadError:self.failed=True;raise
  except (URLError,OSError):self.failed=True;raise ReadError('connection_error',status) from None
  except Exception:self.failed=True;raise ReadError('transport_error',status) from None
  finally:
   if response is not None:
    try:response.close()
    except Exception:pass

def collect(transport):
 values=[];reads=[]
 for stage,url in zip(('monthly','limits'),URLS):
  try:values.append(transport.get(url));reads.append({'stage':stage,'http_status':200,'category':'ok'})
  except ReadError as e:reads.append(dict(stage=stage,**e.safe()));break
  except Exception:reads.append({'stage':stage,'http_status':None,'category':'transport_error'});break
 value=projection.project(values[0] if values else None,values[1] if len(values)>1 else None)
 value.update(reads=reads,requests_attempted=len(reads),provider_starts=0,deletions=0)
 return value

def execute(*,opt_in=False,environ=None):
 guard()
 if opt_in is not True:raise ReadError('opt_in_required')
 verify_sources()
 env=os.environ if environ is None else environ
 folder,binary=private_paths(env);recipient=(ROOT/'recipient.txt').read_text().strip()
 preflight=folder/'monthly-preflight.age'
 crypto.encrypt_capture(b'{"synthetic_preflight":true,"provider_starts":0}',preflight,binary,recipient);preflight.unlink()
 token=env.get('APIFY_TOKEN');token_valid(token)
 value=collect(Transport(token))
 receipt=crypto.encrypt_capture(canonical(value),ROOT/'monthly-usage.age',binary,recipient)
 public=projection.public_projection(value)
 public.update(reads=value['reads'],requests_attempted=value['requests_attempted'],provider_starts=0,deletions=0,plaintext_sha256=receipt['plaintext_sha256'],ciphertext_sha256=receipt['ciphertext_sha256'])
 crypto.durable_write(ROOT/'monthly-usage-public.json',canonical(public))
 return public

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');args=p.parse_args()
 if not args.execute:print(json.dumps({'mode':'offline','provider_requests':0,'provider_starts':0}));return 0
 try:out=execute(opt_in=True);print(json.dumps(out,sort_keys=True));return 0 if out['requests_attempted']==2 and all(r['category']=='ok' for r in out['reads']) else 1
 except Exception as e:
  safe=e.safe() if isinstance(e,ReadError) else ReadError('persistence_failed').safe()
  print(json.dumps({'evidence_type':'billing_read_blocked','provider_starts':0,'diagnostic':safe}));return 1
if __name__=='__main__':raise SystemExit(main())
