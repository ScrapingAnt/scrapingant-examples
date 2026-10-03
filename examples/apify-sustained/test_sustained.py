"""Synthetic offline sustained-contract tests; no provider, real invoice or paid start."""
import contextlib,copy,io,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal
import runner as r
import workflow_driver as driver
import evidence_transport as crypto
ROOT=Path(__file__).resolve().parent
PLAN=r.load_reviewed_plan((ROOT/'sustained-plan.json').read_bytes())
CELL=r.prepare_cell(PLAN,'sustained-playwright-c5-7680')
TRUTH=CELL.spec['output']['expected_records']
class ForbiddenEnvironment:
 def get(self,*args):raise AssertionError('Environment lookup before validation')
class SustainedTests(unittest.TestCase):
 def test_closed_guard_precedes_environment_and_paths(self):
  with patch.object(r,'RUNNER_READY',False),patch.object(r,'SUSTAINED_READY',False):
   with self.assertRaises(r.Fault) as err:r.execute(PLAN,CELL.cell_id,opt_in=True,environ=ForbiddenEnvironment())
   self.assertEqual(err.exception.category,'guard_closed')
   with patch.object(driver,'private_paths',side_effect=AssertionError('private path access')):
    with self.assertRaises(r.Fault):driver.capture(CELL.cell_id,environ=ForbiddenEnvironment())
 def test_exact_pins_reject_legacy_and_changed_payload(self):
  raw=(ROOT/'sustained-plan.json').read_bytes()
  with self.assertRaises(r.Fault):r.load_reviewed_plan(raw+b' ')
  for change in ('stage','currency','memory','truth','native'):
   bad=copy.deepcopy(PLAN)
   if change=='stage':bad['stage']='CONCURRENCY_PILOT'
   elif change=='currency':bad['aggregate_reserved_usd']='3.11'
   elif change=='memory':bad['cells'][0]['options']['memoryMbytes']=8192
   elif change=='truth':bad['cells'][0]['output']['expected_records'][0]['price_minor']+=1
   else:bad['cells'][0]['input']['maxRequestRetries']=1
   with self.subTest(change=change),self.assertRaises(r.Fault):r.validate_plan(bad)
  with self.assertRaises(r.Fault):r.prepare_cell(PLAN,'concurrency-pilot-playwright-c5')
 def test_short_deadline_precedes_token_even_after_source_opt_in(self):
  with patch.object(r,'RUNNER_READY',True),patch.object(r,'SUSTAINED_READY',True):
   with self.assertRaises(r.Fault) as err:
    r.execute(PLAN,CELL.cell_id,opt_in=True,environ=ForbiddenEnvironment(),budget=r.StudyBudget(PLAN),persist_encrypted=lambda _:None,clock=lambda:0,deadline=10679)
   self.assertEqual(err.exception.category,'deadline_exceeded')
 def test_truth_acceptance_order_and_nullable_telemetry(self):
  rows=[dict(row,duration_ms=None,elapsed_ms=10800000,native_active_tasks_start=None,native_active_tasks_end=5,native_desired_tasks_start=5,native_desired_tasks_end=None) for row in reversed(TRUTH)]
  start=time.monotonic();got=r.validate_output(rows,CELL)
  self.assertEqual(len(got),7680);self.assertLess(time.monotonic()-start,10)
  self.assertLess(len(r.canonical(got)),4194304)
 def test_missing_duplicate_foreign_sentinel_wrong_and_bad_telemetry_fail(self):
  for change in ('missing','duplicate','foreign','sentinel','wrong','boolean','large_timing','nonfinite','oversized'):
   rows=copy.deepcopy(TRUTH)
   if change=='missing':rows.pop()
   elif change=='duplicate':rows[-1]=copy.deepcopy(rows[0])
   elif change=='foreign':rows[0]['case_id']='cs-999999'
   elif change=='sentinel':rows.append(copy.deepcopy(rows[0]))
   elif change=='wrong':rows[0]['price_minor']+=1
   elif change=='boolean':rows[0]['native_active_tasks_start']=True
   elif change=='large_timing':rows[0]['elapsed_ms']=10800001
   elif change=='nonfinite':rows[0]['duration_ms']=float('nan')
   else:rows[0]['name']='A'*513
   with self.subTest(change=change),self.assertRaises(r.OutputFault):r.validate_output(rows,CELL)
 def test_exact_cumulative_call_ceiling_and_no_settle_or_repeat_start(self):
  counts=r.empty_counts();r.consume(counts,'start','capture','SUSTAINED')
  for _ in range(160):r.consume(counts,'poll','capture','SUSTAINED')
  with self.assertRaises(r.Fault):r.consume(counts,'poll','capture','SUSTAINED')
  with self.assertRaises(r.Fault):r.consume(counts,'settle','capture','SUSTAINED')
  r.consume(counts,'export','capture','SUSTAINED')
  for kind in r.STORES:r.consume(counts,'metadata_'+kind,'capture','SUSTAINED')
  r.consume(counts,'fresh_terminal','cleanup','SUSTAINED')
  for kind in r.STORES:
   for prefix in ('metadata','delete','absence'):r.consume(counts,prefix+'_'+kind,'cleanup','SUSTAINED')
  self.assertEqual(counts['total'],175);r.validate_counts(counts,'SUSTAINED')
  with self.assertRaises(r.Fault):r.consume(counts,'start','capture','SUSTAINED')
 def test_one_cell_budget_retains_full_reserve_and_rejects_second_claim(self):
  b=r.StudyBudget(PLAN);b.claim(CELL);self.assertEqual(b.reserved_usd,Decimal('3.10'))
  with self.assertRaises(r.Fault):b.claim(CELL)
 def test_crypto_bound_duplicate_and_nonfinite_json(self):
  exact=b'{"synthetic":"'+b'A'*(crypto.MAX_PLAINTEXT_BYTES-16)+b'"}'
  self.assertEqual(len(exact),crypto.MAX_PLAINTEXT_BYTES)
  self.assertIsInstance(crypto.json_payload(exact),dict)
  for bad in (exact+b' ',b'{"x":1,"x":2}',b'{"x":NaN}'):
   with self.assertRaises(crypto.TransportError):crypto.json_payload(bad)
 def test_encryption_preflight_large_controlled_payload(self):
  binary=os.environ.get('SUSTAINED_TEST_AGE_BIN')
  if not binary:self.skipTest('Optional pinned age binary not supplied')
  blob=r.canonical({'synthetic':True,'payload':'A'*5000000})
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'test.age';receipt=crypto.encrypt_capture(blob,dest,binary,(ROOT/'recipient.txt').read_text().strip())
   self.assertEqual(receipt['plaintext_sha256'],crypto.digest(blob));self.assertTrue(receipt['remote_file_readback_verified'])
   self.assertEqual(dest.stat().st_mode&0o777,0o600)
 def test_fixed_workflow_has_no_replay_retry_abort_or_unbounded_job(self):
  path=ROOT/'apify-study-sustained.yml'
  if not path.is_file():path=ROOT.parents[1]/'.github/workflows/apify-study-sustained.yml'
  text=path.read_text()
  for expected in ('timeout-minutes: 240','github.run_attempt == 1','cancel-in-progress: false','default: offline','retention-days: 7','persist-credentials: false'):
   self.assertIn(expected,text)
  self.assertEqual(text.count('secrets.APIFY_TOKEN'),3)
  self.assertNotIn('strategy:',text);self.assertNotIn('workflow_run:',text)
  for phase in ('capture','cleanup'):self.assertIn('workflow_driver.py '+phase+' --cell '+CELL.cell_id+' --execute',text)
if __name__=='__main__':unittest.main()
