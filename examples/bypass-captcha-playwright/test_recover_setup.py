"""Only demonstrably uncharged fixture failures can be prepared for manual recovery."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from recover_setup import archive_setup_failure


class SetupRecovery(unittest.TestCase):
    def test_preserves_uncharged_diagnostic_before_releasing_trial_id(self):
        record={'id':'geetest-v4-anticaptcha-11','case':'geetest-v4','provider':'anticaptcha','trial':11,
                'outcome':'error','error_stage':'fixture_setup','task_create_requests':0,
                'paid_tasks_created':0,'task_creation_uncertain':False,'provider_reported_cost_usd':None}
        with TemporaryDirectory() as directory:
            root=Path(directory)
            path=root/(record['id']+'.json')
            path.write_text(json.dumps(record))
            target=archive_setup_failure(root,record['id'])
            self.assertFalse(path.exists())
            self.assertEqual(json.loads(target.read_text()),record)

    def test_never_releases_started_paid_ambiguous_or_solver_failed_trials(self):
        base={'id':'geetest-v4-anticaptcha-11','case':'geetest-v4','provider':'anticaptcha','trial':11,
              'outcome':'error','error_stage':'fixture_setup','task_create_requests':0,
              'paid_tasks_created':0,'task_creation_uncertain':False,'provider_reported_cost_usd':None}
        changes=[{'task_create_requests':1},{'paid_tasks_created':1},{'task_creation_uncertain':True},
                 {'error_stage':'provider_solve'},{'outcome':'started'}, {'provider_reported_cost_usd':'0.001'},
                 {'task_create_requests':False},{'paid_tasks_created':0.0}]
        with TemporaryDirectory() as directory:
            root=Path(directory)
            for change in changes:
                record={**base,**change}
                path=root/(record['id']+'.json')
                path.write_text(json.dumps(record))
                with self.assertRaises(ValueError):
                    archive_setup_failure(root,record['id'])
                self.assertEqual(json.loads(path.read_text()),record)


if __name__=='__main__':
    unittest.main()
