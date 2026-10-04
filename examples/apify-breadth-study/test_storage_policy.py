"""Synthetic storage-scope evidence; absence is never invented."""
import copy, unittest
from unittest.mock import patch
import controller as c
import storage_policy as p
from test_controller import Response, identity
from test_specialists import cell as synthetic_cell

def native():
    run=identity();run['status']='RUNNING'
    run['storageIds']={'datasets':{'default':run['defaultDatasetId']},'keyValueStores':{'default':run['defaultKeyValueStoreId']},'requestQueues':{'default':run['defaultRequestQueueId']}}
    return run

class StorageTests(unittest.TestCase):
    def test_default_registered_aliases(self):
        self.assertEqual(p.aliases(native()),{'state':'default_only','registered_default_only':True})
    def test_absent_aliases_remain_unknown(self):
        run=native();del run['storageIds']
        self.assertIsNone(p.aliases(run)['registered_default_only'])
    def test_extra_and_malformed_aliases_are_breaches(self):
        for mutation in ('named','wrong-default','malformed','unknown-group'):
            run=native()
            if mutation=='named':run['storageIds']['datasets']['articles-state']='SYNTHNAM000000001'
            elif mutation=='wrong-default':run['storageIds']['datasets']['default']='SYNTHNAM000000001'
            elif mutation=='malformed':run['storageIds']['datasets']=[]
            else:run['storageIds']['synthetic-extra']={}
            with self.assertRaises(p.PolicyBreach):p.aliases(run)
    def test_quiet_log_and_default_aliases_do_not_prove_absence(self):
        cell=synthetic_cell('article-text')
        run=native();run['status']='SUCCEEDED';f=p.findings(cell,run,'Named synthetic quiet log')
        self.assertTrue(f['Article_runtime_compatibility_observed'])
        self.assertFalse(f['all_named_storage_access_absence_proven'])
        self.assertFalse(p.continuation(cell,{'full_assigned_output_complete':True},run,f))
    def test_positive_named_log_stops_without_log_leak(self):
        cell=synthetic_cell('article-text')
        for log in ('Opening articles-state','Opening ARTICLES-SCRAPED-synthetic.invalid'):
            with self.assertRaises(p.PolicyBreach)as exc:p.require_log_scope(cell,log)
            self.assertEqual(str(exc.exception),'storage_policy_breach')
    def test_first_specialist_partial_blocks_continuation(self):
        cell=next(x for x in c.load_plan()['cells']if x['actor']=='apify/ai-web-scraper')
        self.assertFalse(p.continuation(cell,{'full_assigned_output_complete':False},{'status':'SUCCEEDED'},{}))
        self.assertTrue(p.continuation(cell,{'full_assigned_output_complete':True},{'status':'SUCCEEDED'},{}))
    def test_abort_requires_bound_identity_and_storage_breach(self):
        cell=next(x for x in c.load_plan()['cells']if x['actor']=='apify/playwright-scraper')
        with patch.object(c,'ACTIVE_CELL',cell['cell_id']):
            t=c.Transport(cell,'synthetic-token',opener=lambda*a,**kw:Response(status=200),clock=lambda:0)
            with self.assertRaises(c.Stopped):t.permit_storage_abort('extra_storage_alias')
            t.bind(native())
            with self.assertRaises(c.Stopped):t.request('abort')
            with self.assertRaises(c.Stopped):t.permit_storage_abort('synthetic-other-reason')
            t.permit_storage_abort('extra_storage_alias');route=t.route('abort')
            self.assertIn('/actor-runs/'+identity()['id']+'/abort?gracefully=false',route[1])
            t.request('abort')
            with self.assertRaises(c.Stopped):t.request('abort')
            self.assertEqual(t.counts,{'abort':1})

if __name__=='__main__':unittest.main()
