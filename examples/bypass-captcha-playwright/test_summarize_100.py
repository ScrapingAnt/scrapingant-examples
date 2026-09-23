"""Keep expanded-sample statistics and their concurrency phases distinct."""
import unittest

from summarize_100 import summarize_extended_cell, phase_cells


class ExpandedSummary(unittest.TestCase):
    def test_success_tail_latency_excludes_failed_task_duration(self):
        rows = [dict(id=str(i), trial=i, outcome='accepted', solution_delivered=True,
                     server_accepted=True, provider_elapsed_seconds=i) for i in range(1, 21)]
        rows.append(dict(id='21', trial=21, outcome='error', provider_elapsed_seconds=300,
                         solution_delivered=False, provider_error_code='ERROR_TOKEN_EXPIRED'))
        result = summarize_extended_cell([{'id': str(i)} for i in range(1, 22)], rows)
        self.assertEqual(result['planned'], 21)
        self.assertEqual(result['outcomes']['error'], 1)
        self.assertEqual(result['returned_solution_percentiles_seconds'], {'n': 20, 'p90': 18, 'p95': 19})
        self.assertEqual(result['failed_provider_call_seconds'], {'n': 1, 'median': 300, 'min': 300, 'max': 300})

    def test_no_successes_produces_no_invented_percentiles(self):
        result = summarize_extended_cell([{'id': 'one'}], [dict(id='one',trial=11,outcome='error')])
        self.assertEqual(result['returned_solution_percentiles_seconds'], {'n': 0})
        self.assertEqual(result['configured_concurrency'], [])

    def test_first_ten_and_added_trials_keep_separate_denominators(self):
        jobs=[dict(id=str(i),case='recaptcha-v2',provider='2captcha',trial=i)
              for i in (1,10,11,100)]
        rows=[dict(**r,outcome='accepted',server_accepted=True) for r in jobs[:3]]
        plan={'cases':{'recaptcha-v2':{}},'jobs':jobs}
        initial=phase_cells(plan,rows,1,10)[0]
        added=phase_cells(plan,rows,11,100)[0]
        self.assertEqual((initial['planned'],initial['server_accepted']), (2,2))
        self.assertEqual((added['planned'],added['server_accepted'],added['missing_records']), (2,1,1))


if __name__ == '__main__':
    unittest.main()
