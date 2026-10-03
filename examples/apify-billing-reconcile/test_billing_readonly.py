"""Bounded synthetic HTTP diagnostic tests. No real token, account or request."""
import io,json,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from decimal import Decimal
import billing_readonly as b
class Response:
 def __init__(self,blob,status=200):self.stream=io.BytesIO(blob);self.status=status;self.closed=False
 def read1(self,n):return self.stream.read(n)
 def close(self):self.closed=True
class Env:
 def get(self,*args):raise AssertionError('No environment before source guard')
class BillingReadTests(unittest.TestCase):
 def test_closed_before_environment_paths_opener_or_secret(self):
  with patch.object(b,'BILLING_READY',False),patch.object(b,'private_paths',side_effect=AssertionError('paths')):
   with self.assertRaises(b.ReadError)as e:b.execute(opt_in=True,environ=Env())
   self.assertEqual(e.exception.category,'guard_closed')
   with self.assertRaises(b.ReadError):b.Transport('SYNTHETIC_TOKEN',opener=lambda *a,**k:None)
 def test_exact_two_header_gets_no_profile_query_token_or_third_call(self):
  calls=[]
  def open_(req,timeout):
   calls.append((req.full_url,req.get_method(),req.get_header('Authorization'),timeout))
   return Response(b'{"data":{"amount":0.13660374560593733001,"profile":"SYNTHETIC_PII"}}')
  with patch.object(b,'BILLING_READY',True):
   t=b.Transport('SYNTHETIC_TOKEN',opener=open_,clock=lambda:0)
   got=t.get(b.URLS[0]);self.assertEqual(got['data']['amount'],Decimal('0.13660374560593733001'))
   t.get(b.URLS[1])
   with self.assertRaises(b.ReadError):t.get(b.URLS[1])
  self.assertEqual([row[0]for row in calls],list(b.URLS));self.assertEqual(len(calls),2)
  for url,method,auth,timeout in calls:
   self.assertEqual(method,'GET');self.assertEqual(auth,'Bearer SYNTHETIC_TOKEN');self.assertNotIn('TOKEN',url);self.assertLessEqual(timeout,10)
 def test_failure_consumes_slot_and_stops_without_reading_error_body_or_retry(self):
  calls=[]
  def open_(req,timeout):
   calls.append(req.full_url)
   error=HTTPError(req.full_url,403,'SYNTHETIC_PII',{},io.BytesIO(b'SYNTHETIC_TOKEN'))
   raise error
  with patch.object(b,'BILLING_READY',True):
   t=b.Transport('SYNTHETIC_TOKEN',opener=open_,clock=lambda:0);value=b.collect(t)
   self.assertEqual(t.calls,1);self.assertEqual(value['requests_attempted'],1)
   with self.assertRaises(b.ReadError):t.get(b.URLS[0])
   with self.assertRaises(b.ReadError):t.get(b.URLS[1])
  self.assertEqual(len(calls),1);self.assertNotIn('SYNTHETIC',json.dumps(value))
  self.assertEqual(value['reads'][0]['category'],'http_error');self.assertFalse(value['individual_run_ancillary_reconciled'])
 def test_body_limit_invalid_json_and_route_deadline_stop(self):
  for blob,category in ((b'A'*(b.projection.RESPONSE_LIMIT+1),'response_too_large'),(b'{"x":1,"x":2}','invalid_json'),(b'{"x":NaN}','invalid_json')):
   response=Response(blob)
   with patch.object(b,'BILLING_READY',True):
    t=b.Transport('SYNTHETIC_TOKEN',opener=lambda *a,**k:response,clock=lambda:0)
    with self.subTest(category=category),self.assertRaises(b.ReadError)as e:t.get(b.URLS[0])
    self.assertEqual(e.exception.category,category);self.assertEqual(t.calls,1);self.assertTrue(response.closed)
  clock=[0]
  def slow(*a,**k):clock[0]=11;return Response(b'{}')
  with patch.object(b,'BILLING_READY',True):
   t=b.Transport('SYNTHETIC_TOKEN',opener=slow,clock=lambda:clock[0])
   with self.assertRaises(b.ReadError)as e:t.get(b.URLS[0])
   self.assertEqual(e.exception.category,'deadline_exceeded')
 def test_helper_and_recipient_integrity_precede_environment_access(self):
  b.verify_sources()
  with patch.object(b,'BILLING_READY',True),patch.object(b,'REVIEWED_SOURCES',{'recipient.txt':'a'*64}):
   with self.assertRaises(b.ReadError)as e:b.execute(opt_in=True,environ=Env())
   self.assertEqual(e.exception.category,'persistence_failed')
 def test_unsafe_route_and_token_block_before_open(self):
  def forbidden(*a,**k):raise AssertionError('No HTTP for unsafe inputs')
  with patch.object(b,'BILLING_READY',True):
   with self.assertRaises(b.ReadError):b.Transport('TOKEN\n',opener=forbidden)
   for url in (b.URLS[0]+'&token=SYNTHETIC',b.URLS[1],'http://api.apify.com/v2/users/me/usage/monthly?date=2026-10-03'):
    t=b.Transport('SYNTHETIC_TOKEN',opener=forbidden)
    with self.assertRaises(b.ReadError):t.get(url)
    self.assertEqual(t.calls,0)
if __name__=='__main__':unittest.main()
