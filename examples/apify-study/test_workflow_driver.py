"""Offline workflow wiring tests; fake public approval responses only."""
import contextlib
import io
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

    def test_remaining_without_wcc_is_exact_twenty_two_with_unchanged_native_cells(self):
        expected=[v['cell_id']for v in fixture.capability_plan_fixture()['cells'][12:]
                  if not v['cell_id'].endswith('-website-content-crawler')]
        with patch.object(driver.os,'environ',fixture.ForbiddenEnvironment()),patch.object(driver,'plan',side_effect=AssertionError('Manifest reads plan')):
            selected=driver.smoke_manifest('capability-remaining-without-wcc')
        self.assertEqual(selected,expected);self.assertEqual(len(selected),22)
        self.assertTrue(all(not c.endswith('-website-content-crawler')for c in selected))
        self.assertIn('capability-remaining-without-wcc',driver.MANIFEST_SCOPES)

    def test_capability_scopes_are_exact_first_twelve_and_remaining_twenty_four_offline(self):
        expected=[v['cell_id'] for v in fixture.capability_plan_fixture()['cells']]
        with patch.object(driver.os, 'environ', fixture.ForbiddenEnvironment()), patch.object(driver, 'plan', side_effect=AssertionError('Manifest reads plan')):
            first=driver.smoke_manifest('capability-first-repetition')
            later=driver.smoke_manifest('capability-remaining-repetitions')
        self.assertEqual(first, expected[:12]); self.assertEqual(later, expected[12:])
        self.assertEqual(len(set(first+later)),36)
        for bad in ('capability-core','capability-r4','cap-r1-cheerio-static'):
            with self.assertRaises(driver.runner.Fault): driver.smoke_manifest(bad)

    def test_capability_file_and_scope_are_selected_before_environment_and_limited_is_required(self):
        r=driver.runner; reviewed=fixture.capability_plan_fixture(); raw=json.dumps(reviewed,indent=2).encode()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'capability-plan.json').write_bytes(raw)
            with patch.object(driver,'ROOT',root), patch.object(r,'REVIEWED_CAPABILITY_PLAN_SHA256',r.sha(r.canonical(reviewed)),create=True),\
                 patch.object(r,'REVIEWED_CAPABILITY_PLAN_FILE_SHA256',r.sha(raw),create=True):
                self.assertEqual(driver.plan('cap-r1-cheerio-static'),reviewed)
                with self.assertRaises(r.Fault):driver.plan('cap-r4-cheerio-static')
        with patch.object(r,'RUNNER_READY',False), patch.object(driver,'plan',side_effect=AssertionError('Closed guard reads plan')):
            with self.assertRaises(r.Fault) as error:driver.capture('cap-r1-cheerio-static',environ=fixture.ForbiddenEnvironment())
        self.assertEqual(error.exception.category,'guard_closed')
        reviewed['cells'][0].pop('force_permission_level')
        with patch.object(r,'RUNNER_READY',True), patch.object(r,'REVIEWED_CAPABILITY_PLAN_SHA256',r.sha(r.canonical(reviewed)),create=True),\
             patch.object(driver,'plan',return_value=reviewed):
            with self.assertRaises(r.Fault):driver.capture('cap-r1-cheerio-static',environ=fixture.ForbiddenEnvironment())

    def test_capability_approval_route_keeps_one_fixed_cell_and_no_credentials(self):
        requested=[]; approval=self.approval
        class Opener:
            def open(self,req,timeout): requested.append(req.full_url); return Reply(json.dumps(approval).encode())
        self.assertEqual(driver.fetch_approval('cap-r3-rag-web-browser-formatting',opener=Opener()),approval)
        self.assertEqual(requested,[driver.APPROVAL_BASE+'cap-r3-rag-web-browser-formatting.json'])
        for cell in ('cap-r4-rag-web-browser-formatting','../cap-r1-cheerio-static'):
            with self.assertRaises(driver.runner.Fault):driver.fetch_approval(cell,opener=Opener())
        self.assertEqual(len(requested),1)

    def test_capability_manifest_cli_and_workflow_are_finite_and_fail_fast(self):
        with patch('sys.argv',['workflow_driver.py','manifest','--smoke-scope','capability-first-repetition']),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(driver.main(),0)
        self.assertEqual(len(json.loads(out.getvalue())),12)
        workflow=(driver.ROOT.parents[1]/'.github/workflows/apify-study-smoke.yml').read_text()
        self.assertIn('capability-first-repetition',workflow)
        self.assertIn('capability-remaining-without-wcc',workflow)
        self.assertNotIn('          - capability-remaining-repetitions',workflow)
        self.assertIn('max-parallel: 1',workflow);self.assertIn('fail-fast: true',workflow)
        self.assertIn("github.run_attempt == 1",workflow)

    def test_closed_capability_cli_failure_reports_stage_without_reading_secret(self):
        class NoSecret(dict):
            def get(self,key,*args):
                if key=='APIFY_TOKEN':raise AssertionError('secret read before guard')
                return super().get(key,*args)
        with patch.object(driver.runner,'RUNNER_READY',False),patch.object(driver.os,'environ',NoSecret()),\
             patch('sys.argv',['workflow_driver.py','capture','--cell','cap-r1-cheerio-static','--execute']),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(driver.main(),1)
        public=json.loads(out.getvalue())
        self.assertEqual(public.get('stage'),'CAPABILITY')
        self.assertEqual(public['diagnostic']['category'],'guard_closed')

    def test_manifest_has_only_one_or_the_exact_five_cells_without_environment(self):
        self.assertTrue(callable(getattr(driver, 'smoke_manifest', None)), 'fixed offline manifest is missing')
        class Forbidden(dict):
            def get(self, *args): raise AssertionError('Manifest must not read environment')
        with patch.object(driver.os, 'environ', Forbidden()), patch.object(driver, 'plan', side_effect=AssertionError('Manifest must not read plan')):
            self.assertEqual(driver.smoke_manifest('cheerio'), ['smoke-cheerio-scraper'])
            self.assertEqual(driver.smoke_manifest('remaining-five'), ['smoke-web-scraper', 'smoke-playwright-scraper',
                             'smoke-puppeteer-scraper', 'smoke-website-content-crawler', 'smoke-rag-web-browser'])
            for value in ('all', '../other', None, 'remaining-five '):
                with self.assertRaises(driver.runner.Fault): driver.smoke_manifest(value)

    def test_manifest_cli_stays_offline_with_closed_guard(self):
        self.assertTrue(callable(getattr(driver, 'smoke_manifest', None)), 'fixed offline manifest is missing')
        with patch.object(driver.runner, 'RUNNER_READY', False), patch('sys.argv', ['workflow_driver.py', 'manifest', '--smoke-scope', 'remaining-five']), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(driver.main(), 0)
        self.assertEqual(json.loads(out.getvalue()), ['smoke-web-scraper', 'smoke-playwright-scraper',
                         'smoke-puppeteer-scraper', 'smoke-website-content-crawler', 'smoke-rag-web-browser'])

    def test_capture_requires_explicit_limited_before_environment_access(self):
        class Forbidden(dict):
            def get(self, *args): raise AssertionError('Environment read before permission validation')
        reviewed = fixture.plan_fixture(); reviewed['cells'][0]['cell_id'] = 'smoke-cheerio-scraper'
        with patch.object(driver.runner, 'RUNNER_READY', True), patch.object(driver.runner, 'REVIEWED_PLAN_SHA256', driver.runner.sha(driver.runner.canonical(reviewed))), patch.object(driver, 'plan', return_value=reviewed):
            try: driver.capture('smoke-cheerio-scraper', environ=Forbidden())
            except Exception as exc: problem = exc
            else: problem = None
        self.assertIsInstance(problem, driver.runner.Fault)
        self.assertEqual(problem.category, 'invalid_cell')

    def test_capture_scope_failure_and_incomplete_cleanup_exit_nonzero(self):
        cases = [('capture', {'status':'RUNNING','capture_scope_verified':False,'encrypted_capture_verified':True,'owner_attention_required':True}),
                 ('capture', {'status':'SUCCEEDED','capture_scope_verified':True,'encrypted_capture_verified':False,'owner_attention_required':True}),
                 ('cleanup', {'cleanup_state':'blocked','owner_attention_required':True}),
                 ('cleanup', {'cleanup_state':'residual','owner_attention_required':True}),
                 ('cleanup', {'cleanup_state':'complete','owner_attention_required':True})]
        for phase, value in cases:
            with self.subTest(phase=phase, value=value), patch.object(driver, phase, return_value=value), patch('sys.argv', ['workflow_driver.py', phase, '--execute']), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(driver.main(), 1)
                self.assertEqual(json.loads(out.getvalue()), value)

    def test_valid_terminal_failure_and_complete_cleanup_allow_next_job(self):
        for status in ('SUCCEEDED','FAILED','TIMED-OUT','ABORTED'):
            value = {'status':status,'capture_scope_verified':True,'encrypted_capture_verified':True,'owner_attention_required':False}
            with self.subTest(status=status), patch.object(driver, 'capture', return_value=value), patch('sys.argv', ['workflow_driver.py', 'capture', '--execute']), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(driver.main(), 0)
        with patch.object(driver, 'cleanup', return_value={'cleanup_state':'complete','owner_attention_required':False}), patch('sys.argv', ['workflow_driver.py','cleanup','--execute']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(driver.main(), 0)

    def test_each_pinned_cell_has_its_own_fixed_approval_route(self):
        for cell in ('smoke-cheerio-scraper','smoke-web-scraper','smoke-playwright-scraper',
                     'smoke-puppeteer-scraper','smoke-website-content-crawler','smoke-rag-web-browser'):
            requested = []
            approval = self.approval
            class Opener:
                def open(self, req, timeout):
                    requested.append(req.full_url); return Reply(json.dumps(approval).encode())
            try: result = driver.fetch_approval(cell, opener=Opener())
            except driver.runner.Fault: result = None
            self.assertEqual(result, self.approval)
            self.assertEqual(requested, [driver.APPROVAL_BASE+cell+'.json'])

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
        for value in ['../secret','https://example.com','smoke-rag-web-browser-extra']:
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

    def _exercise_two_phase_driver(self, *, status='SUCCEEDED', foreign_metadata=False, token_available=True):
        """Full offline wiring, real age/fsync, synthetic provider responses only."""
        r=driver.runner
        reviewed=fixture.plan_fixture()
        reviewed['cells'][0].update(cell_id='smoke-cheerio-scraper',actor='apify/cheerio-scraper',
                                    actor_id='YrQuEkowkNCLdk4j2',force_permission_level='LIMITED_PERMISSIONS')
        stamp=datetime.now(timezone.utc)-timedelta(seconds=3)
        run=fixture.response(status=status,actId='YrQuEkowkNCLdk4j2')
        run['data'].update(startedAt=stamp.isoformat(),finishedAt=(stamp+timedelta(seconds=1)).isoformat())
        metas=[fixture.metadata(k,actId='YrQuEkowkNCLdk4j2') for k in ('dataset','kv','queue')]
        for meta in metas:meta['data']['createdAt']=stamp.isoformat()
        if foreign_metadata:metas[0]['data']['userId']='ForeignOwner'
        exported=[r.Reply(200,fixture.RECORDS)] if status=='SUCCEEDED' else []
        capture_calls=fixture.FakeTransport([r.Reply(201,run),*exported,
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
                self.assertEqual(kwargs['request_counts']['total'],5 if status=='SUCCEEDED' else 4)
                self.assertEqual(kwargs['identity']['id'],'PrivateRun')
                return cleanup_calls
            with patch.object(r,'RUNNER_READY',True),patch.object(r,'REVIEWED_PLAN_SHA256',r.sha(r.canonical(reviewed))),\
                 patch.object(driver,'ROOT',root),patch.object(driver,'plan',return_value=reviewed),\
                 patch.object(driver,'private_paths',return_value=(private,binary)),\
                 patch.object(r,'execute',side_effect=execute):
                public=driver.capture('smoke-cheerio-scraper',environ={})
                self.assertEqual(public['capture_scope_verified'],not foreign_metadata)
                self.assertNotIn('PrivateRun',json.dumps(public))
                self.assertEqual((private/'state.json').stat().st_mode&0o777,0o600)
                self.assertTrue((root/'capture.age').is_file())
                private_state=json.loads((private/'state.json').read_bytes())
                approved={'plaintext_sha256':public['plaintext_sha256'],
                          'ciphertext_sha256':public['ciphertext_sha256'],'scope_approved':True}
                with patch.object(driver,'await_approval',return_value=approved),patch.object(r,'HttpTransport',side_effect=transport):
                    final=driver.cleanup('smoke-cheerio-scraper',environ={'APIFY_TOKEN':fixture.TOKEN} if token_available else {})
                if foreign_metadata or not token_available:
                    self.assertEqual(final['cleanup_state'],'blocked')
                    self.assertEqual(cleanup_calls.requests,[])
                else:
                    self.assertEqual(final['cleanup_state'],'complete')
                    self.assertEqual(final['request_counts']['total'],15 if status=='SUCCEEDED' else 14)
                    self.assertEqual(len(cleanup_calls.requests),10)
                    self.assertTrue(cleanup_calls.authorized)
                self.assertNotIn('PrivateRun',json.dumps(final))
                self.assertNotIn('usage_total_usd',json.dumps(final))
                self.assertTrue((root/'final.age').is_file())
                return public,final,private_state

    def test_two_phase_driver_preserves_budget_state_and_private_meters(self):
        self._exercise_two_phase_driver()

    def test_terminal_failed_actor_preserves_capture_and_completes_cleanup(self):
        public,final,state=self._exercise_two_phase_driver(status='FAILED')
        self.assertEqual(public['status'],'FAILED')
        self.assertEqual(state['evidence']['extraction_state'],'terminal_failure')
        self.assertEqual(final['cleanup_state'],'complete')

    def test_invalid_capture_scope_preserves_encrypted_initial_and_blocked_final(self):
        public,final,state=self._exercise_two_phase_driver(foreign_metadata=True)
        self.assertFalse(public['capture_scope_verified'])
        self.assertEqual(final['cleanup_state'],'blocked')
        self.assertTrue(final['owner_attention_required'])

    def test_missing_cleanup_token_preserves_encrypted_blocked_final(self):
        public,final,state=self._exercise_two_phase_driver(token_available=False)
        self.assertEqual(final['cleanup_state'],'blocked')
        self.assertEqual(final['diagnostic']['category'],'token_unavailable')


if __name__=='__main__':unittest.main()
