import copy
import json
import unittest
from pathlib import Path
from score import analyze,evaluate
from budget import model,PLANS

CAPTURES=[json.loads(s) for s in (Path(__file__).parent/'data/captures.jsonl').read_text().splitlines()]

class OfflineTests(unittest.TestCase):
    def test_documented_price_inputs(self):
        prices=json.loads((Path(__file__).parent/'data/prices.json').read_text())
        for p in prices['plans']:
            self.assertEqual(PLANS[p['name']],(p['price_usd'],p['monthly_credits'],p['credits_per_topup']))
    def test_full_replay(self):
        rows,s=analyze(CAPTURES)
        self.assertEqual((len(rows),s['credits_consumed']),(200,200))
        self.assertTrue(all(x['basic_preservation_pass']==14 for x in s['balanced_settings']))
        self.assertEqual((s['pairs'][0]['credits'],s['pairs'][0]['accepted_delayed_outputs'],s['pairs'][0]['credits_per_accepted']),(16,8,2))
        self.assertEqual(s['pairs'][1]['accepted_delayed_outputs'],0)
        self.assertIsNone(s['pairs'][1]['credits_per_accepted'])
    def test_missing_capture_rejected(self):
        with self.assertRaises(ValueError): analyze(CAPTURES[:-1])
    def test_duplicate_capture_rejected(self):
        with self.assertRaises(ValueError): analyze(CAPTURES+[CAPTURES[0]])
    def test_unknown_debit_not_zero(self):
        c=copy.deepcopy(CAPTURES); c[0]['metadata'].pop('creditsUsed')
        with self.assertRaises(ValueError): analyze(c)
    def test_price_tampering_rejected(self):
        c=copy.deepcopy(next(x for x in CAPTURES if x['fixture']=='complete-catalog'))
        c['markdown']=c['markdown'].replace('34.99','35.99')
        self.assertFalse(evaluate(c)['basic_preservation'])
    def test_missing_price_is_preserved_but_not_accepted(self):
        c=next(x for x in CAPTURES if x['fixture']=='missing-price')
        r=evaluate(c); self.assertTrue(r['basic_preservation']); self.assertFalse(r['two_numeric_prices'])
    def test_404_is_diagnostic(self):
        r=evaluate(next(x for x in CAPTURES if x['fixture']=='missing-http-404'))
        self.assertEqual(r['target_status'],404); self.assertTrue(r['basic_preservation'])
    def test_delayed_placeholder_fails(self):
        c=next(x for x in CAPTURES if x['unit_type']=='delayed-same-pair')
        self.assertEqual(c['metadata']['statusCode'],200); self.assertFalse(evaluate(c)['basic_preservation'])
    def test_tables_contracts_differ(self):
        r=evaluate(next(x for x in CAPTURES if x['fixture']=='html-tables'))
        self.assertTrue(r['html_structure']); self.assertFalse(r['visible_only_markdown'])
    def test_zero_accepted_undefined(self):
        self.assertIsNone(model('Hobby',16,0)['usd_per_accepted'])
    def test_topup_boundary(self):
        self.assertEqual(model('Hobby',5000,5000)['bill_usd'],19)
        self.assertEqual(model('Hobby',5001,5001)['bill_usd'],24)
        self.assertEqual(model('Hobby',6000,6000)['bill_usd'],24)
        self.assertEqual(model('Hobby',6001,6001)['bill_usd'],29)
    def test_free_boundary(self):
        self.assertEqual(model('Free',1000,1000)['bill_usd'],0)
        with self.assertRaises(ValueError): model('Free',1001,1001)
    def test_underutilization(self):
        r=model('Standard',30000,27000)
        self.assertEqual(r['unused_plan_credits'],70000)
        self.assertAlmostEqual(r['usd_per_accepted'],99/27000)
        self.assertEqual(model('Standard',3000,3000)['usd_per_accepted'],.033)
    def test_plan_boundary(self):
        self.assertEqual(model('Standard',100001,100000)['bill_usd'],104)
    def test_invalid_counts(self):
        with self.assertRaises(ValueError): model('Hobby',-1,1)

if __name__=='__main__': unittest.main()
