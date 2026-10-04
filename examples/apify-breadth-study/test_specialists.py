"""Named synthetic fixtures; do not enter measured study evidence."""
import copy, unittest
from urllib.parse import urlencode
import controller as c
import acceptance as a

PLAN=c.load_plan()
def cell(kind):
    if kind == 'article-text':
        # Pure historical-contract fixture; never an executable plan entry.
        contracts = [{'url': 'https://synthetic.invalid/article-' + str(i),
            'required_sentence_ids': ['SYNTH-TEXT-' + str(i)],
            'expected_sentences': {'SYNTH-TEXT-' + str(i): 'SYNTH-TEXT-' + str(i) + ' is named synthetic prose.'},
            'boilerplate_ids': ['SYNTH-NAV-' + str(i), 'SYNTH-FOOTER-' + str(i)]} for i in range(6)]
        return {'evidence_type': 'named_synthetic_analysis_only', 'cell_id': 'deferred-synthetic-article',
            'actor': 'lukaskrivka/article-extractor-smart', 'actor_id': 'hy5TYiCBwQ9o8uRKG',
            'force_permission_level': 'LIMITED_PERMISSIONS', 'first_exploratory': True,
            'assigned_case_count': 6, 'output': {'kind': kind, 'content_contracts': contracts,
                'allowed_urls': [x['url'] for x in contracts]}}
    return next(copy.deepcopy(x) for x in PLAN['cells'] if x['output']['kind'] == kind)
def ai_rows(spec):
    return [{'url':u,'data':copy.deepcopy(t),'markdown':'Synthetic visible product'}for u,t in zip(spec['output']['allowed_urls'],spec['output']['expected_records'])]
def article_rows(spec):
    return [{'url':x['url'],'loadedUrl':x['url'],'title':'Synthetic article',
        'text':' '.join(x['expected_sentences'].values())}for x in spec['output']['content_contracts']]
def serp_rows(spec):
    return [{'searchQuery':{'term':q,'page':1,'url':'https://www.google.com/search?'+urlencode({'q':q})},
        'organicResults':[{'title':'Synthetic documentation result','url':'https://'+domain+'/synthetic-doc'}]}
        for q,domain in zip(spec['output']['queries'],spec['output']['expected_domains'])]
def trend_rows(spec):
    return [{'inputUrlOrTerm':'robots.txt','searchTerm':'robots.txt',
        'interestOverTime_timelineData':[{'time':str(spec['output']['start_epoch']+i*86400),'value':[50+i],'hasData':[True]}for i in range(2)]}]

class SpecialistTests(unittest.TestCase):
    def test_exact_nested_AI_products(self):
        spec=cell('ai-products');r=a.evaluate(spec,ai_rows(spec))
        self.assertEqual((r['assigned'],r['accepted']),(6,6));self.assertTrue(r['full_assigned_output_complete'])
    def test_AI_hallucination_string_price_missing_and_extra_fields(self):
        spec=cell('ai-products')
        for mutation in ('price-string','invented-name','extra','missing','case-id'):
            rows=ai_rows(spec)
            if mutation=='price-string':rows[0]['data']['price_minor']=str(rows[0]['data']['price_minor'])
            elif mutation=='invented-name':rows[0]['data']['name']='Named synthetic hallucination'
            elif mutation=='extra':rows[0]['data']['invented']='synthetic'
            elif mutation=='missing':del rows[0]['data']['sku']
            else:rows[0]['data']['case_id']='foreign-synthetic'
            self.assertEqual(a.evaluate(spec,rows)['accepted'],5)
    def test_AI_duplicate_foreign_and_missing_denominators(self):
        spec=cell('ai-products');rows=ai_rows(spec);rows.append(copy.deepcopy(rows[0]))
        result=a.evaluate(spec,rows);self.assertEqual(result['duplicate_rows'],1);self.assertEqual(result['accepted'],5)
        rows=ai_rows(spec)[:-1];rows[0]['url']='https://synthetic.invalid/foreign'
        result=a.evaluate(spec,rows);self.assertEqual(result['assigned'],6);self.assertEqual(result['foreign_rows'],1);self.assertEqual(result['missing_cases'],2)
    def test_article_accepts_text_without_markdown_HTML(self):
        spec=cell('article-text');r=a.evaluate(spec,article_rows(spec))
        self.assertEqual(r['accepted'],6);self.assertTrue(r['full_assigned_output_complete'])
        self.assertTrue(all(x['markdown_or_html_required']is False for x in r['cases']))
    def test_article_missing_text_wrong_loaded_URL_boilerplate(self):
        spec=cell('article-text')
        for mutation in ('missing','redirect','boilerplate'):
            rows=article_rows(spec)
            if mutation=='missing':del rows[0]['text']
            elif mutation=='redirect':rows[0]['loadedUrl']='https://synthetic.invalid/redirect'
            else:rows[0]['text']+=' '+' '.join(spec['output']['content_contracts'][0]['boilerplate_ids'])
            self.assertLess(a.evaluate(spec,rows)['accepted'],6)
    def test_SERP_page_denominator_separate_from_organic_count(self):
        spec=cell('serp-pages');rows=serp_rows(spec);rows[0]['organicResults']*=5
        r=a.evaluate(spec,rows);self.assertEqual((r['assigned'],r['accepted']),(3,3))
        self.assertEqual(r['cases'][0]['organic_result_count'],5)
    def test_SERP_query_page_URL_and_result_scheme_contract(self):
        spec=cell('serp-pages')
        for mutation in ('query','page','query-url','unsafe-result','off-site','empty'):
            rows=serp_rows(spec)
            if mutation=='query':rows[0]['searchQuery']['term']='foreign synthetic'
            elif mutation=='page':rows[0]['searchQuery']['page']=True
            elif mutation=='query-url':rows[0]['searchQuery']['url']='https://synthetic.invalid/?q=x'
            elif mutation=='unsafe-result':rows[0]['organicResults'][0]['url']='javascript:synthetic()'
            elif mutation=='off-site':rows[0]['organicResults'][0]['url']='https://synthetic.invalid/'
            else:rows[0]['organicResults']=[]
            r=a.evaluate(spec,rows);self.assertLess(r['accepted'],3);self.assertFalse(r['full_assigned_output_complete'])
    def test_Trends_temporal_interest_contract_not_search_volume(self):
        spec=cell('trends');r=a.evaluate(spec,trend_rows(spec))
        self.assertEqual(r['accepted'],1);self.assertFalse(r['cases'][0]['absolute_search_volume_validated'])
    def test_Trends_wrong_query_values_flags_interval_and_duplicate_time(self):
        spec=cell('trends')
        for mutation in ('term','101','boolean','string','nodata','duplicate-time','outside','malformed'):
            rows=trend_rows(spec);point=rows[0]['interestOverTime_timelineData'][0]
            if mutation=='term':rows[0]['searchTerm']='foreign synthetic'
            elif mutation=='101':point['value']=[101]
            elif mutation=='boolean':point['value']=[True]
            elif mutation=='string':point['value']=['50']
            elif mutation=='nodata':
                for p in rows[0]['interestOverTime_timelineData']:p['hasData']=[False]
            elif mutation=='duplicate-time':rows[0]['interestOverTime_timelineData'][1]['time']=point['time']
            elif mutation=='outside':point['time']=str(spec['output']['end_epoch_exclusive'])
            else:point['time']='NaN'
            self.assertEqual(a.evaluate(spec,rows)['accepted'],0)
    def test_native_errors_false_markers_and_bad_shapes_visible(self):
        spec=cell('ai-products');rows=ai_rows(spec);rows[0]['#error']=False
        rows[1]={'#error':True};rows[2]['#error']='false';rows[3]=None
        result=a.evaluate(spec,rows)
        self.assertEqual((result['native_error_rows'],result['invalid_native_error_markers'],result['malformed_rows']),(1,1,1))
        self.assertEqual((result['assigned'],result['accepted']),(6,3))
    def test_products_partial_and_known_zero_cost(self):
        spec=cell('products');r=a.evaluate(spec,spec['output']['expected_records'][:2])
        self.assertEqual((r['assigned'],r['accepted']),(3840,2));self.assertFalse(r['full_assigned_output_complete'])
        self.assertEqual(a.cost_per_1000('0',2),'0');self.assertIsNone(a.cost_per_1000('1',0))
    def test_unknown_contract_and_invalid_rows_fail(self):
        spec=cell('trends');spec['output']['kind']='synthetic-unrecognized'
        with self.assertRaises(ValueError):a.evaluate(spec,[])
        with self.assertRaises(ValueError):a.evaluate(cell('trends'),{})

if __name__=='__main__':unittest.main()
