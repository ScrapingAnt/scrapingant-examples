"""Check that descriptive summaries retain failure denominators and unknowns."""
import unittest
from summarize_broad import summarize_cell


class SummarySemantics(unittest.TestCase):
    def test_errors_stay_in_denominator_but_not_success_latency(self):
        jobs = [{'id': 'one'}, {'id': 'two'}, {'id': 'three'}]
        rows = [dict(id='one', paid_tasks_created=1, task_create_requests=1,
                     solution_delivered=True, server_acceptance_tested=True,
                     server_accepted=False, provider_elapsed_seconds=5,
                     outcome='rejected', provider_reported_cost_usd='0.002'),
                dict(id='two', paid_tasks_created=1, task_create_requests=1,
                     solution_delivered=False, outcome='error',
                     provider_elapsed_seconds=300, provider_error_code='ERROR_CAPTCHA_UNSOLVABLE')]
        cell = summarize_cell(jobs, rows)
        self.assertEqual((cell['planned'], cell['missing_records'], cell['tasks_created']), (3, 1, 2))
        self.assertEqual(cell['server_accepted'], 0)
        self.assertEqual(cell['solution_latency_seconds'], {'n': 1, 'median': 5, 'min': 5, 'max': 5})
        self.assertEqual(cell['reported_cost']['coverage'], 1)
        self.assertEqual(cell['outcomes']['error'], 1)

    def test_token_delivery_does_not_become_server_acceptance(self):
        cell = summarize_cell([{'id': 'one'}], [dict(id='one', outcome='token_delivered_unverified',
            solution_delivered=True, server_acceptance_tested=False, server_accepted=None)])
        self.assertEqual(cell['solutions_delivered'], 1)
        self.assertEqual(cell['server_verifications'], 0)
        self.assertEqual(cell['server_accepted'], 0)
        self.assertEqual(cell['token_only_observations'], 1)
        self.assertIsNone(cell['reported_cost']['total_usd'])

    def test_timeout_after_acceptance_is_preserved_as_a_separate_outcome(self):
        cell = summarize_cell([{'id': 'one'}], [dict(id='one', outcome='accepted',
            server_accepted=True, execution_outcome='process_timeout')])
        self.assertEqual(cell['server_accepted'], 1)
        self.assertEqual(cell['execution_outcomes'], {'process_timeout': 1})


if __name__ == '__main__':
    unittest.main()
