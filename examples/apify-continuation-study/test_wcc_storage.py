"""Named synthetic WCC R3 metadata/route bounds; no provider or actual run."""
import copy,io,unittest
from unittest.mock import patch
import controller as c
import storage_policy as s

PLAN=c.load_plan()
R3=next(x for x in PLAN['cells']if x['cell_id']==s.WCC_R3)
R2=next(x for x in PLAN['cells']if x['cell_id']=='cap-r2-website-content-crawler')
EXTRA='SYNTHERR000000001'

def run():
    value={'id':'SYNTHRUN000000001','userId':'SYNTHUSR000000001','actId':R3['actor_id'],
        'buildNumber':R3['build'],'defaultDatasetId':'SYNTHDAT000000001',
        'defaultKeyValueStoreId':'SYNTHKVS000000001','defaultRequestQueueId':'SYNTHQUE000000001',
        'startedAt':'2026-10-06T00:00:00Z','finishedAt':'2026-10-06T00:01:00Z','status':'SUCCEEDED'}
    value['storageIds']={'datasets':{'default':value['defaultDatasetId'],'errors':EXTRA},
        'keyValueStores':{'default':value['defaultKeyValueStoreId']},
        'requestQueues':{'default':value['defaultRequestQueueId']}}
    return value

def metadata():
    value=run()
    return {'id':EXTRA,'userId':value['userId'],'actId':value['actId'],'actRunId':value['id'],
        'name':None,'createdAt':value['startedAt'],'itemCount':2,'stats':{'storageBytes':256}}

def validate(meta=None,value=None,observed='2026-10-06T00:02:00Z'):
    return s.validate_extra(R3,run()if value is None else value,metadata()if meta is None else meta,observed,EXTRA)

class WCCStorage(unittest.TestCase):
    def test_nonempty_measured_errors_allowed_metadata_only(self):
        proof=validate()
        self.assertEqual((proof['extra_item_count'],proof['extra_storage_bytes']),(2,256))
        self.assertTrue(proof['metadata_only_no_extra_content_read'])
        self.assertFalse(proof['all_named_storage_access_absence_proven'])

    def test_exact_limits_and_zero_are_both_accepted(self):
        for count,size in ((0,0),(30,1048576),(0,1048576),(30,0)):
            meta=metadata();meta.update(itemCount=count,stats={'storageBytes':size})
            self.assertEqual(validate(meta)['extra_item_count'],count)

    def test_item_units_missing_bool_negative_fraction_string_and_excess(self):
        for value in (None,False,-1,1.5,'2',31):
            meta=metadata();meta['itemCount']=value
            with self.subTest(value=value),self.assertRaises(s.PolicyBreach):validate(meta)
        meta=metadata();del meta['itemCount']
        with self.assertRaises(s.PolicyBreach):validate(meta)

    def test_byte_units_missing_bool_negative_fraction_string_and_excess(self):
        for value in (None,False,-1,1.5,'256',1048577):
            meta=metadata();meta['stats']['storageBytes']=value
            with self.subTest(value=value),self.assertRaises(s.PolicyBreach):validate(meta)
        for stats in ({},None,[],{'storageBytesMiB':1}):
            meta=metadata();meta['stats']=stats
            with self.subTest(stats=stats),self.assertRaises(s.PolicyBreach):validate(meta)

    def test_owned_exact_run_association_and_explicit_null_name(self):
        for key in ('id','userId','actId','actRunId','name'):
            meta=metadata();meta[key]='SYNTHBAD000000001'
            with self.subTest(key=key),self.assertRaises(s.PolicyBreach):validate(meta)
            meta=metadata();del meta[key]
            with self.subTest(missing=key),self.assertRaises(s.PolicyBreach):validate(meta)

    def test_strict_start_finish_and_initial_observation_creation_bounds(self):
        for created in ('2026-10-05T23:59:59Z','2026-10-06T00:01:01Z','2026-10-06T00:00:00',None):
            meta=metadata();meta['createdAt']=created
            with self.subTest(created=created),self.assertRaises(s.PolicyBreach):validate(meta)
        active=run();active['finishedAt']=None;meta=metadata();meta['createdAt']='2026-10-06T00:00:02Z'
        with self.assertRaises(s.PolicyBreach):validate(meta,active,'2026-10-06T00:00:01Z')

    def test_exact_four_distinct_aliases_and_stable_errors_ID(self):
        self.assertEqual(s.aliases(R3,run(),EXTRA)['state'],'wcc_r3_exact_errors_aliases')
        for mutation in ('unknown','missing','duplicate','default','group','swap'):
            value=run()
            if mutation=='unknown':value['storageIds']['datasets']['other']='SYNTHOTH000000001'
            elif mutation=='missing':del value['storageIds']['datasets']['errors']
            elif mutation=='duplicate':value['storageIds']['datasets']['errors']=value['defaultDatasetId']
            elif mutation=='default':value['storageIds']['datasets']['default']='SYNTHBAD000000001'
            elif mutation=='group':value['storageIds']['other']={}
            else:value['storageIds']['datasets']['errors']='SYNTHNEW000000001'
            with self.subTest(mutation=mutation),self.assertRaises(s.PolicyBreach):s.aliases(R3,value,EXTRA)

    def test_consumed_R2_stays_default_only_and_scope_failure_is_not_reclassified(self):
        with self.assertRaises(s.PolicyBreach):s.aliases(R2,run())
        value=run();del value['storageIds']['datasets']['errors']
        self.assertEqual(s.aliases(R2,value)['state'],'default_only')
        self.assertNotIn('storage_contract',R2)

    def test_other_Actors_cannot_inherit_errors_exception(self):
        for cell in PLAN['cells']:
            if cell['cell_id']==s.WCC_R3:continue
            bad=copy.deepcopy(cell);bad['storage_contract']=copy.deepcopy(s.WCC_ERRORS_CONTRACT)
            with self.subTest(cell=cell['cell_id']),self.assertRaises(s.PolicyBreach):s.extra_contract(bad)

    def test_missing_mutated_profile_wrong_actor_build_and_boolean_units_fail_before_token(self):
        mutations=[('actor','apify/ai-web-scraper'),('actor_id','SYNTHBAD000000001'),('build','0.3.98'),
            ('storage_contract',None)]
        for key,value in mutations:
            bad=copy.deepcopy(R3);bad[key]=value
            with patch.object(c,'ACTIVE_CELL',s.WCC_R3),self.assertRaises(c.Stopped):c.Transport(bad,None)
        for field,value in [('maximum_items',31),('maximum_items',True),('maximum_storage_bytes',1048577),
            ('metadata_only',1),('initial_and_final_required',False),('alias','linkProspecting')]:
            bad=copy.deepcopy(R3);bad['storage_contract'][field]=value
            with self.subTest(field=field),patch.object(c,'ACTIVE_CELL',s.WCC_R3),self.assertRaises(c.Stopped):c.Transport(bad,None)

    def test_native_actor_and_build_binding(self):
        for field,value in [('actId','SYNTHBAD000000001'),('buildNumber','0.3.98')]:
            native=run();native[field]=value
            with self.subTest(field=field),self.assertRaises(s.PolicyBreach):s.aliases(R3,native)

    def test_two_metadata_GETs_once_each_never_extra_items_or_delete(self):
        class Response:
            status=200
            def __init__(self):self.stream=io.BytesIO(b'{"data":{}}')
            def read1(self,n):return self.stream.read(n)
            def close(self):pass
        with patch.object(c,'ACTIVE_CELL',s.WCC_R3):
            transport=c.Transport(R3,'named-synthetic-token',clock=lambda:0,opener=lambda *a,**k:Response())
            transport.bind(run());transport.bind_extra(run())
            self.assertEqual(transport.route('extra_initial'),('GET',c.API+'/datasets/'+EXTRA,200,15,131072,1))
            with self.assertRaises(c.Stopped):transport.request('extra_final')
            transport.request('extra_initial')
            with self.assertRaises(c.Stopped):transport.request('extra_initial')
            transport.counts['export']=1;transport.request('extra_final')
            with self.assertRaises(c.Stopped):transport.request('extra_final')
            for operation in ('extra_items','delete','list','https://other.example'):
                with self.assertRaises(c.Stopped):transport.route(operation)

    def test_metadata_does_not_change_native_input_options_text_or_denominators(self):
        self.assertEqual(R3['input'],R2['input']);self.assertEqual(R3['options'],R2['options'])
        self.assertEqual(R3['output'],R2['output']);self.assertEqual(R3['assigned_case_count'],30)
        self.assertEqual(R3['native_input_sha256'],'9d8386bd36091cb114355eab935b5bca6cd4d38815b7679acd059eea282b49c3')
        self.assertEqual(R3['prospective_contract_version'],'original-wcc-text-contract-v1')

    def test_no_continuation_without_errors_proof_or_terminal_success(self):
        accepted={'full_assigned_output_complete':True}
        self.assertFalse(s.continuation(R3,accepted,run(),{}))
        self.assertTrue(s.continuation(R3,accepted,run(),validate()))
        value=run();value['status']='ABORTED'
        self.assertFalse(s.continuation(R3,accepted,value,validate()))

if __name__=='__main__':unittest.main()
