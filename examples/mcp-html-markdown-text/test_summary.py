"""Offline analysis checks: missing inference is not a zero-charge format failure."""
import unittest
from summarize_runs import aggregate_model, wilson_interval

def observation(arm,repeat,accepted,cost=0.001,completion='[]'):
    return {'phase':'offline','case':'links','arm':arm,'repeat':repeat,'completion':completion,
            'actual_cost_usd':cost,'reserved_usd':0.0036,'outcome':'accepted' if accepted else 'incorrect_records',
            'score':{'accepted_page':accepted,'correct_slots':12 if accepted else 10,'expected_slots':12}}

class AnalysisTests(unittest.TestCase):
    def test_missing_completion_retains_attempt_cost_and_balances_repeats(self):
        rows=[observation('markdown',0,False,None,None)]
        rows += [observation(arm,repeat,arm!='text') for repeat in (1,2) for arm in ('html','markdown','text')]
        rows += [observation('html',0,True),observation('text',0,False)]
        result=aggregate_model(rows)
        md=next(r for r in result['cells'] if r['arm']=='markdown')
        self.assertEqual((md['attempts'],md['completions'],md['accepted_pages']),(3,2,2))
        self.assertIsNone(md['all_attempts_token_rate_cost_usd'])
        self.assertAlmostEqual(md['known_token_rate_cost_usd'],0.002)
        self.assertAlmostEqual(md['conservative_accounted_usd'],0.0056)
        self.assertIsNone(md['all_attempts_cost_per_accepted_page_usd'])
        self.assertEqual(result['balanced'][0]['matched_repeats'],[1,2])
        self.assertEqual(result['balanced'][0]['arms']['html']['accepted_pages'],2)
        self.assertEqual(result['balanced'][0]['arms']['text']['accepted_pages'],0)

    def test_zero_correct_denominator_is_undefined_even_with_known_cost(self):
        result=aggregate_model([observation('text',0,False)])
        cell=result['cells'][0]
        self.assertEqual(cell['all_attempts_token_rate_cost_usd'],0.001)
        self.assertIsNone(cell['all_attempts_cost_per_accepted_page_usd'])

    def test_charged_refusal_counts_as_inference_without_completion_text(self):
        row=observation('html',0,False,0.001,None)
        row.update(usage={'prompt_tokens':100,'completion_tokens':20},outcome='refusal')
        cell=aggregate_model([row])['cells'][0]
        self.assertEqual(cell['inference_responses'],1)
        self.assertEqual(cell['completion_strings'],0)
        self.assertEqual(cell['exact_page_accuracy'],0)
        self.assertEqual(cell['unique_completion_strings'],0)
        self.assertIsNone(cell['known_token_rate_cost_per_accepted_page_usd'])

    def test_nominal_wilson_bounds_do_not_report_certain_one_or_zero(self):
        self.assertAlmostEqual(wilson_interval(5,5)[0],0.5655175352)
        self.assertAlmostEqual(wilson_interval(0,5)[1],0.4344824648)
        self.assertEqual(wilson_interval(0,0),None)

if __name__=='__main__':unittest.main()
