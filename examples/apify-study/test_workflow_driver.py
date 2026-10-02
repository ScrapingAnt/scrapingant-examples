"""Offline workflow wiring tests; fake public approval responses only."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workflow_driver as driver
import test_runner as fixture


class Reply:
    status = 200
    def __init__(self, body): self.body=body;self.offset=0
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return self.body[:n]
    def read1(self,n):
        blob=self.body[self.offset:self.offset+n];self.offset+=len(blob);return blob


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.approval={'plaintext_sha256':'a'*64,'ciphertext_sha256':'b'*64,'scope_approved':True}

    def test_closed_guard_precedes_environment_or_provider(self):
        class Forbidden(dict):
            def get(self,*args): raise AssertionError('Environment read before guard')
        with patch.object(driver.runner,'RUNNER_READY',False), patch.object(driver.runner,'execute') as run:
            with self.assertRaises(driver.runner.Fault):
                driver.capture('smoke-cheerio-scraper',environ=Forbidden())
            run.assert_not_called()

    def test_approval_strict_keys_exact_hash_pair(self):
        self.assertTrue(driver.matches_approval(self.approval,'a'*64,'b'*64))
        for changed in [dict(self.approval,scope_approved=1),dict(self.approval,extra='PRIVATE'),
                        dict(self.approval,plaintext_sha256='c'*64),None,{}]:
            self.assertFalse(driver.matches_approval(changed,'a'*64,'b'*64))

    def test_public_approval_route_is_fixed_and_has_no_credentials(self):
        requested=[]
        approval=self.approval
        class Opener:
            def open(self,req,timeout):
                requested.append(req)
                return Reply(json.dumps(approval).encode())
        result=driver.fetch_approval('smoke-cheerio-scraper',opener=Opener())
        self.assertEqual(result,self.approval)
        self.assertEqual(requested[0].full_url,driver.APPROVAL_BASE+'smoke-cheerio-scraper.json')
        self.assertNotIn('Authorization',requested[0].headers)
        for value in ['../secret','https://example.com','smoke-rag-web-browser']:
            with self.assertRaises(driver.runner.Fault):driver.fetch_approval(value,opener=Opener())
        self.assertEqual(len(requested),1)

    def test_approval_response_is_bounded_and_errors_are_fixed(self):
        class Opener:
            def __init__(self,body):self.body=body
            def open(self,*args,**kwargs):return Reply(self.body)
        for body in [b'x'*16385,b'PRIVATE_PROVIDER_RESPONSE',b'[]']:
            self.assertIsNone(driver.fetch_approval('smoke-cheerio-scraper',opener=Opener(body)))

    def test_approval_wait_expiry_never_calls_provider(self):
        clock=[0]
        def now():return clock[0]
        def wait(seconds):clock[0]+=seconds
        with patch.object(driver,'fetch_approval',return_value=None) as fetch:
            result=driver.await_approval('smoke-cheerio-scraper','a'*64,'b'*64,
                                         seconds=31,clock=now,wait=wait)
        self.assertIsNone(result)
        self.assertLessEqual(fetch.call_count,3)
        self.assertLessEqual(clock[0],31)

    def test_trickled_approval_uses_read1_and_route_deadline(self):
        clock=[0.0]
        class Trickle(Reply):
            def read(self,n):raise AssertionError('Blocking chunk-fill read forbidden')
            def read1(self,n):
                clock[0]+=1
                return super().read1(1)
        class Opener:
            def open(self,*args,**kwargs):return Trickle(json.dumps(self.approval).encode())
            approval=self.approval
        self.assertIsNone(driver.fetch_approval('smoke-cheerio-scraper',opener=Opener(),
                                                clock=lambda:clock[0],deadline=5.0))
        self.assertLessEqual(clock[0],5.0)

    def test_public_result_excludes_private_cleanup_meters(self):
        fake={'cleanup_state':'complete','owner_attention_required':False,
              'diagnostic':None,'refreshed_run':{'usage_total_usd':'PRIVATE'},
              'refreshed_storage':{'dataset':{'storageBytes':123}},'stores':{'dataset':'absent'}}
        public=driver.cleanup_public(fake)
        self.assertEqual(set(public),{'cleanup_state','owner_attention_required','diagnostic'})
        self.assertNotIn('PRIVATE',json.dumps(public))

    def test_two_phase_driver_preserves_budget_state_and_private_meters(self):
        """Full offline wiring, real age/fsync, synthetic provider responses only."""
        r=driver.runner
        reviewed=fixture.plan_fixture()
        reviewed['cells'][0]['cell_id']='smoke-cheerio-scraper'
        stamp=datetime.now(timezone.utc)-timedelta(seconds=3)
        run=fixture.response()
        run['data'].update(startedAt=stamp.isoformat(),finishedAt=(stamp+timedelta(seconds=1)).isoformat())
        metas=[fixture.metadata(k) for k in ('dataset','kv','queue')]
        for meta in metas:meta['data']['createdAt']=stamp.isoformat()
        capture_calls=fixture.FakeTransport([r.Reply(201,run),r.Reply(200,fixture.RECORDS),
                                              *[r.Reply(200,m) for m in metas]])
        cleanup_calls=fixture.FakeTransport([r.Reply(200,run),*[r.Reply(200,m) for m in metas],
                                             *[reply for _ in range(3) for reply in (r.Reply(204,None),r.Reply(404,None))]])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'recipient.txt').write_bytes((driver.ROOT/'recipient.txt').read_bytes())
            private=root/'private';private.mkdir(mode=0o700)
            binary=fixture.Path('/tmp/apify-age-bin/age/age')
            if 'STUDY_TEST_AGE_BIN' in driver.os.environ:binary=Path(driver.os.environ['STUDY_TEST_AGE_BIN'])
            def execute(plan,cell_id,**kwargs):
                self.assertIsInstance(kwargs['budget'],r.StudyBudget)
                return r.run_until_capture(capture_calls,r.prepare_cell(plan,cell_id),kwargs['persist_encrypted'],
                                           budget=kwargs['budget'])
            def transport(cell,token,**kwargs):
                self.assertEqual(kwargs['mode'],'cleanup')
                self.assertEqual(kwargs['request_counts']['total'],5)
                self.assertEqual(kwargs['identity']['id'],'PrivateRun')
                return cleanup_calls
            with patch.object(r,'RUNNER_READY',True),patch.object(r,'REVIEWED_PLAN_SHA256',r.sha(r.canonical(reviewed))),\
                 patch.object(driver,'ROOT',root),patch.object(driver,'plan',return_value=reviewed),\
                 patch.object(driver,'private_paths',return_value=(private,binary)),\
                 patch.object(r,'execute',side_effect=execute):
                public=driver.capture('smoke-cheerio-scraper',environ={})
                self.assertTrue(public['capture_scope_verified'])
                self.assertNotIn('PrivateRun',json.dumps(public))
                self.assertEqual((private/'state.json').stat().st_mode&0o777,0o600)
                approved={'plaintext_sha256':public['plaintext_sha256'],
                          'ciphertext_sha256':public['ciphertext_sha256'],'scope_approved':True}
                with patch.object(driver,'await_approval',return_value=approved),patch.object(r,'HttpTransport',side_effect=transport):
                    final=driver.cleanup('smoke-cheerio-scraper',environ={'APIFY_TOKEN':fixture.TOKEN})
                self.assertEqual(final['cleanup_state'],'complete')
                self.assertEqual(final['request_counts']['total'],15)
                self.assertEqual(len(cleanup_calls.requests),10)
                self.assertTrue(cleanup_calls.authorized)
                self.assertNotIn('PrivateRun',json.dumps(final))
                self.assertNotIn('usage_total_usd',json.dumps(final))
                self.assertTrue((root/'final.age').is_file())


if __name__=='__main__':unittest.main()
