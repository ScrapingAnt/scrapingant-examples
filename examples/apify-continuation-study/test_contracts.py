"""Named synthetic prospective cases; no network, accounts or real bills."""
import copy, hashlib, json, unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import acceptance as a
import controller as c
import input_contracts as inputs
import storage_policy as s

PLAN=c.load_plan()
def cell(actor):return next(x for x in PLAN['cells']if x['actor']==actor)
AI=cell('apify/ai-web-scraper');GOOGLE=cell(s.GOOGLE);CONTACT=cell('vdrmota/contact-info-scraper');WCC=cell('apify/website-content-crawler')

def ai_rows():return [{'url':url,'data':[copy.deepcopy(truth)]}for url,truth in zip(AI['output']['allowed_urls'],AI['output']['expected_records'])]
def contact_rows():return [{'url':x['url'],'originalStartUrl':x['originalStartUrl'],'emails':x['emails'][:],
    'phones':x['phones'][:],'phonesUncertain':[],'leadsEnrichment':[]}for x in CONTACT['output']['expected_records']]
def google_run():
    run={'id':'SYNTHRUN000000001','userId':'SYNTHUSR000000001','actId':GOOGLE['actor_id'],
        'defaultDatasetId':'SYNTHDAT000000001','defaultKeyValueStoreId':'SYNTHKVS000000001',
        'defaultRequestQueueId':'SYNTHQUE000000001','startedAt':'2026-10-06T00:00:00Z',
        'finishedAt':'2026-10-06T00:01:00Z','status':'SUCCEEDED'}
    run['storageIds']={'datasets':{'default':run['defaultDatasetId'],'linkProspecting':'SYNTHEXT000000001'},
        'keyValueStores':{'default':run['defaultKeyValueStoreId']},'requestQueues':{'default':run['defaultRequestQueueId']}}
    return run
def extra_meta():
    run=google_run();return {'id':'SYNTHEXT000000001','userId':run['userId'],'actId':run['actId'],
        'actRunId':run['id'],'createdAt':'2026-10-06T00:00:00Z','name':None,'itemCount':0,'stats':{'storageBytes':0}}

class Contracts(unittest.TestCase):
    def test_all_48_owned_fixture_bytes_and_42_required_paths(self):
        manifest=json.loads((c.ROOT/'fixture-manifest.json').read_text())
        self.assertEqual((manifest['all_assets'],manifest['required_assets']),(48,42))
        for path,item in manifest['assets'].items():
            blob=(c.ROOT.parents[1]/path).read_bytes()
            self.assertEqual(c.sha(blob),item['sha256']);self.assertEqual(len(blob),item['bytes']);self.assertTrue(item['synthetic'])
    def test_AI_dual_score_and_raw_byte_preservation(self):
        rows=ai_rows();before=c.canonical(rows);r=a.evaluate(AI,rows)
        self.assertEqual((r['assigned'],r['accepted'],r['frozen_object_only_score']['accepted']),(6,6,0))
        self.assertTrue(r['full_assigned_output_complete']);self.assertFalse(r['original_R1_score_reclassified'])
        self.assertEqual(c.canonical(rows),before)
    def test_AI_one_object_also_passes(self):
        rows=ai_rows()
        for row in rows:row['data']=row['data'][0]
        self.assertEqual(a.evaluate(AI,rows)['accepted'],6)
    def test_AI_zero_multi_wrong_types_unknown_fields_and_native_error(self):
        for change in ('empty','multi','string-price','bool-price','extra-field','foreign','error','bad-marker','missing'):
            rows=ai_rows()
            if change=='empty':rows[0]['data']=[]
            elif change=='multi':rows[0]['data']*=2
            elif change=='string-price':rows[0]['data'][0]['price_minor']=str(rows[0]['data'][0]['price_minor'])
            elif change=='bool-price':rows[0]['data'][0]['price_minor']=True
            elif change=='extra-field':rows[0]['data'][0]['extra']='unreviewed'
            elif change=='foreign':rows[0]['url']='https://example.com/'
            elif change=='error':rows[0]['#error']=True
            elif change=='bad-marker':rows[0]['#error']='false'
            else:rows.pop()
            with self.subTest(change=change):
                r=a.evaluate(AI,rows);self.assertEqual(r['assigned'],6);self.assertLess(r['accepted'],6);self.assertFalse(r['full_assigned_output_complete'])
    def test_AI_duplicate_is_not_first_item_selection(self):
        rows=ai_rows();rows.append(copy.deepcopy(rows[0]));r=a.evaluate(AI,rows)
        self.assertEqual(r['duplicate_rows'],1);self.assertEqual(r['accepted'],5);self.assertFalse(r['full_assigned_output_complete'])
    def test_zero_accepted_denominator_and_exact_currency(self):
        self.assertIsNone(a.cost_per_1000('0.20',0));self.assertIsNone(a.cost_per_1000(None,6))
        self.assertEqual(a.cost_per_1000('0.12',6),'20.00')
        for value in ('NaN','-1',0.2):
            with self.assertRaises((ValueError,ArithmeticError)):a.cost_per_1000(value,6)
    def test_Contact_exact_pages_emails_phones_provenance(self):
        rows=contact_rows();rows[0]['phones']=['+1 (202) 555-0100'];r=a.evaluate(CONTACT,rows)
        self.assertEqual((r['assigned'],r['accepted']),(6,6));self.assertTrue(r['full_assigned_output_complete'])
    def test_Contact_uncertain_phone_not_promoted_to_verified(self):
        rows=contact_rows();rows[0]['phonesUncertain']=rows[0]['phones'];rows[0]['phones']=[]
        r=a.evaluate(CONTACT,rows);self.assertEqual(r['accepted'],5);self.assertFalse(r['full_assigned_output_complete'])
    def test_Contact_foreign_duplicate_enrichment_bad_arrays_missing(self):
        for change in ('foreign','duplicate','enrichment','social','paid-email','string-email','phone-extension','provenance','missing'):
            rows=contact_rows()
            if change=='foreign':rows[0]['url']='https://example.com/'
            elif change=='duplicate':rows.append(copy.deepcopy(rows[0]))
            elif change=='enrichment':rows[0]['leadsEnrichment']=[{'synthetic':True}]
            elif change=='social':rows[0]['linkedIns']=['https://example.com/']
            elif change=='paid-email':rows[0]['chargeableEmailVerificationsCount']=1
            elif change=='string-email':rows[0]['emails']='contact000@example.com'
            elif change=='phone-extension':rows[0]['phones']=['12025550100 ext 1']
            elif change=='provenance':rows[0]['originalStartUrl']=rows[1]['url']
            else:rows.pop()
            with self.subTest(change=change):self.assertFalse(a.evaluate(CONTACT,rows)['full_assigned_output_complete'])
    def test_Contact_false_positives_are_reported(self):
        rows=contact_rows();rows[0]['emails'].append('false-positive@example.com');rows[0]['phones'].append('12025550199')
        r=a.evaluate(CONTACT,rows);self.assertEqual(r['cases'][0]['false_positive_emails'],1)
        self.assertEqual(r['cases'][0]['false_positive_phones'],1);self.assertEqual(r['accepted'],5)
    def test_WCC_original_text_primary_markdown_diagnostic(self):
        rows=[{'url':x['url'],'text':' '.join(x['expected_sentences'].values())}for x in WCC['output']['content_contracts']]
        r=a.evaluate(WCC,rows);self.assertEqual((r['assigned'],r['accepted']),(30,30))
        self.assertFalse(r['cases'][0]['markdown']['accepted']);self.assertTrue(r['original_819_assignment_preserved'])
        self.assertEqual(a.evaluate(WCC,rows,'TIMED-OUT')['accepted'],0)
    def test_WCC_95_percent_sentence_boundary_distinct_boilerplate(self):
        truth=WCC['output']['content_contracts'][0];sentences=list(truth['expected_sentences'].values())
        self.assertTrue(a.content_contract(truth,' '.join(sentences[:19])+' B000 B000')['accepted'])
        self.assertFalse(a.content_contract(truth,' '.join(sentences[:18]))['accepted'])
        self.assertFalse(a.content_contract(truth,' '.join(sentences)+' B000 B999')['accepted'])
        self.assertFalse(a.content_contract(truth,' '.join(truth['required_sentence_ids']))['accepted'])
    def test_Ecommerce_offline_offer_currency_precision_no_SKU_guess(self):
        truth=json.loads((c.ROOT/'synthetic-truth.json').read_text())['commerce'][0]
        row={'url':truth['url'],'inputUrl':truth['url'],'name':truth['name'],'offers':{'price':'12.34','priceCurrency':'USD'}}
        r=a.commerce_metrics(truth,row);self.assertTrue(r['accepted']);self.assertFalse(r['SKU_present_diagnostic_only']);self.assertFalse(r['runnable_actor_contract'])
        self.assertTrue(a.commerce_metrics(truth,{**row,'offers':{'price':Decimal('12.34'),'priceCurrency':'USD'}})['accepted'])
        for offer in ({'price':'12.341','priceCurrency':'USD'},{'price':'12.34','priceCurrency':'EUR'},
            {'price':12.34,'priceCurrency':'USD'},[row['offers'],row['offers']],{'price':'NaN','priceCurrency':'USD'},
            {'price':'12.34000000000000000000000000000000000000001','priceCurrency':'USD'}):
            self.assertFalse(a.commerce_metrics(truth,{**row,'offers':offer})['accepted'])

class StorageAndAdmission(unittest.TestCase):
    def test_exact_fresh_empty_Google_extra_metadata(self):
        run=google_run();p=s.aliases(GOOGLE,run)
        self.assertEqual(p['extra_dataset_id'],'SYNTHEXT000000001');self.assertFalse(p['all_named_storage_access_absence_proven'])
        p=s.validate_extra(GOOGLE,run,extra_meta(),run['finishedAt'],'SYNTHEXT000000001')
        self.assertTrue(p['extra_dataset_fresh_unnamed_owned']);self.assertTrue(p['metadata_only_no_extra_content_read'])
    def test_Google_nonempty_named_foreign_prior_missing_bytes_and_units_rejected(self):
        for field,value in [('itemCount',1),('itemCount',False),('name','named-store'),('userId','FOREIGN0000000001'),
            ('actId',CONTACT['actor_id']),('actRunId','FOREIGN0000000001'),('createdAt','2026-10-05T23:59:59Z'),
            ('createdAt','2026-10-06T00:01:01Z'),('createdAt','2026-10-06T00:00:00'),('stats',{}),
            ('stats',{'storageBytes':1}),('stats',{'storageBytes':False}),('stats',{'storageBytes':'0'})]:
            meta=extra_meta();meta[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(s.PolicyBreach):s.validate_extra(GOOGLE,google_run(),meta,'2026-10-06T00:02:00Z','SYNTHEXT000000001')
    def test_Google_running_creation_bound_at_first_observation(self):
        run=google_run();run['finishedAt']=None;meta=extra_meta();meta['createdAt']='2026-10-06T00:00:02Z'
        with self.assertRaises(s.PolicyBreach):s.validate_extra(GOOGLE,run,meta,'2026-10-06T00:00:01Z','SYNTHEXT000000001')
    def test_unknown_alias_wrong_group_default_duplicate_or_changed_pin_rejected(self):
        for change in ('extra','group','default','duplicate','missing','changed'):
            run=google_run()
            if change=='extra':run['storageIds']['datasets']['errors']='SYNTHERR000000001'
            elif change=='group':run['storageIds']['other']={}
            elif change=='default':run['storageIds']['datasets']['default']='SYNTHBAD000000001'
            elif change=='duplicate':run['storageIds']['datasets']['linkProspecting']=run['defaultDatasetId']
            elif change=='missing':del run['storageIds']['datasets']['linkProspecting']
            else:run['storageIds']['datasets']['linkProspecting']='SYNTHNEW000000001'
            with self.subTest(change=change),self.assertRaises(s.PolicyBreach):s.aliases(GOOGLE,run,'SYNTHEXT000000001')
    def test_other_Actors_cannot_inherit_Google_extra_exception(self):
        with self.assertRaises(s.PolicyBreach):s.aliases(CONTACT,google_run())
    def test_Google_transport_extra_ID_pin_metadata_only_counted_once(self):
        with patch.object(c,'ACTIVE_CELL',GOOGLE['cell_id']):
            t=c.Transport(GOOGLE,'synthetic-token',opener=lambda *a,**k:None,clock=lambda:0);t.bind(google_run());t.bind_extra(google_run())
            method,url,*rest=t.route('extra_initial');self.assertEqual(method,'GET');self.assertTrue(url.endswith('/datasets/SYNTHEXT000000001'))
            self.assertNotIn('/items',url);self.assertEqual(rest[-1],1)
            with self.assertRaises(c.Stopped):t.route('extra_final')
            t.counts['export']=1;self.assertEqual(t.route('extra_final')[1],url)
            bad=google_run();bad['storageIds']['datasets']['linkProspecting']='SYNTHNEW000000001'
            with self.assertRaises(s.PolicyBreach):t.bind_extra(bad)
    def test_Article_and_Ecommerce_disguised_ids_rejected_before_token(self):
        for identity,actor in [('hy5TYiCBwQ9o8uRKG','lukaskrivka/article-extractor-smart'),('2APbAvDfNDOWXbkWf','apify/e-commerce-scraping-tool')]:
            bad=copy.deepcopy(CONTACT);bad['actor_id']=identity;bad['actor']=actor
            with patch.object(c,'ACTIVE_CELL',bad['cell_id']),self.assertRaises(c.Stopped)as err:c.Transport(bad,None)
            self.assertEqual(err.exception.category,'invalid_cell')
    def test_contact_bounds_cannot_be_mutated_even_with_rehashed_input(self):
        for field,value in [('maxDepth',1),('mergeContacts',True),('maximumLeadsEnrichmentRecords',1),('considerChildFrames',True),('useBrowser',True),('maxRequests',7)]:
            bad=copy.deepcopy(CONTACT);bad['input'][field]=value;bad['native_input_sha256']=c.sha(c.canonical(bad['input']))
            with self.subTest(field=field),self.assertRaises(ValueError):inputs.validate(bad)
    def test_minimum_cap_native_options_and_assigned_denominator_fixed(self):
        for field,value in [('maxTotalChargeUsd','0.15'),('memoryMbytes',True),('restartOnError',True)]:
            bad=copy.deepcopy(CONTACT);bad['options'][field]=value
            with self.assertRaises(ValueError):inputs.validate(bad)
        bad=copy.deepcopy(CONTACT);bad['assigned_case_count']=5
        with self.assertRaises(ValueError):inputs.validate(bad)
    def test_R3_depends_on_new_R2_full_output_not_old_offline_score(self):
        for x in PLAN['cells']:
            if x['cell_id'].startswith('breadth-r3-'):self.assertEqual(x['dependency'],x['cell_id'].replace('-r3-','-r2-'))
        good=a.evaluate(AI,ai_rows());self.assertTrue(s.continuation(AI,good,{'status':'SUCCEEDED'},{}))
        self.assertFalse(s.continuation(AI,a.evaluate(AI,[]),{'status':'SUCCEEDED'},{}))
        self.assertFalse(s.continuation(GOOGLE,{'full_assigned_output_complete':True},{'status':'SUCCEEDED'},{}))

if __name__=='__main__':unittest.main()
