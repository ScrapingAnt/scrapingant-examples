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


class AnthropicReplayTests(unittest.TestCase):
    def test_framing_is_bounded(self):
        from replay import decode_framing
        self.assertEqual(decode_framing('{"records":[]}')[1],'raw')
        self.assertEqual(decode_framing('```json\n{"records":[]}\n```'),('{"records":[]}', 'single_json_fence'))
        for text in ('Here you go:\n```json\n{}\n```','```json\n{}\n```\n```json\n{}\n```','```json\n{}'):
            self.assertEqual(decode_framing(text)[1],'raw')
    def test_actual_anthropic_capture(self):
        capture=DEFAULT.parent/'anthropic-2026-09-30'
        report,_,_=replay(capture)
        self.assertEqual(report['summary']['model_attempts'],15)
        self.assertEqual(report['summary']['raw_json_parse_successes'],0)
        self.assertEqual(report['summary']['single_json_fences_decoded'],15)
        self.assertEqual(report['summary']['emitted_records'],30)
    def test_truncated_output_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture=Path(tmp)/'capture';shutil.copytree(DEFAULT.parent/'anthropic-2026-09-30',capture)
            p=capture/'complete-1.model.json';data=json.loads(p.read_text());data['stop_reason']='max_tokens';p.write_text(json.dumps(data))
            report,_,_=replay(capture)
            result=next(r for r in report['runs'] if r['run']=='complete-1')
            self.assertEqual(result['accepted_count'],0)
            self.assertFalse(result['complete_run_success'])
            self.assertIn('incomplete_model_output',result['errors'])

class AnthropicRequestTests(unittest.TestCase):
    def test_request_contract_without_network(self):
        from unittest.mock import patch, MagicMock
        from live import extract
        with tempfile.TemporaryDirectory() as tmp:
            capture=Path(tmp)/'capture';shutil.copytree(DEFAULT,capture)
            (capture/'model-runs.json').unlink()
            response=MagicMock(status_code=200)
            response.json.return_value=json.loads((DEFAULT.parent/'anthropic-2026-09-30/complete-1.model.json').read_text())
            with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'synthetic-test-key','MODEL_BUDGET_USD':'10'}),patch('live.httpx.Client') as client:
                post=client.return_value.__enter__.return_value.post;post.return_value=response
                extract(capture,'anthropic')
                self.assertEqual(post.call_count,15)
                args,kwargs=post.call_args_list[0]
                self.assertEqual(args[0],'https://api.anthropic.com/v1/messages')
                self.assertEqual(kwargs['headers']['anthropic-version'],'2023-06-01')
                self.assertEqual(kwargs['json']['model'],'claude-haiku-4-5-20251001')
                self.assertEqual(kwargs['json']['max_tokens'],2000)
                self.assertNotIn('response_format',kwargs['json'])
                self.assertNotIn('oracle',kwargs['json']['system'].lower())
    def test_budget_prevents_request(self):
        from unittest.mock import patch
        from live import extract
        with tempfile.TemporaryDirectory() as tmp:
            capture=Path(tmp)/'capture';shutil.copytree(DEFAULT,capture);(capture/'model-runs.json').unlink()
            with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'synthetic-test-key','MODEL_BUDGET_USD':'0.20'}),patch('live.httpx.Client') as client:
                with self.assertRaisesRegex(ValueError,'budget exhausted'):extract(capture,'anthropic')
                client.return_value.__enter__.return_value.post.assert_not_called()

if __name__=='__main__':unittest.main()
