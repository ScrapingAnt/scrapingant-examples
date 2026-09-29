"""Regression checks use copies of saved evidence; never invoke providers."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from live import RESERVATION
from replay import DEFAULT, replay

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.capture=Path(self.temp.name)/'capture'
        shutil.copytree(DEFAULT,self.capture)
    def tearDown(self):self.temp.cleanup()
    def test_retrieval_checked_when_model_failed(self):
        (self.capture/'complete.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):replay(self.capture)
    def test_raw_envelope_checked_when_model_failed(self):
        p=self.capture/'complete.tool.json';data=json.loads(p.read_text());data['isError']=True;p.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'tool_error'):replay(self.capture)
    def test_unknown_usage_not_silently_zero(self):
        p=self.capture/'model-runs.json';data=json.loads(p.read_text());row=dict(data['runs'][0]);row['repeat']=2;row['usage']={'prompt_tokens':100,'completion_tokens':10};row['list_price_upper_estimate_usd']=0.000056;data['runs'].append(row);p.write_text(json.dumps(data))
        summary=replay(self.capture)[0]['summary']
        self.assertEqual(summary['attempts_without_usage'],1)
        self.assertIsNone(summary['prompt_tokens'])
        self.assertIsNone(summary['list_price_upper_estimate_usd'])
    def test_reservation_fits_approved_budget(self):
        self.assertAlmostEqual(RESERVATION,0.4222304)
        self.assertLessEqual(15*RESERVATION,10)

if __name__=='__main__':unittest.main()
