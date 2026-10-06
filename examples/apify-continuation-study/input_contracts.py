"""Admission before secret access; fixed candidates, native inputs and options only."""
from decimal import Decimal
import hashlib, json

ACTORS={'apify/ai-web-scraper':'paOtbjvyUiNsr1Qms',
    'apify/google-search-scraper':'nFJndFXA5zjCTuudP',
    'apify/website-content-crawler':'aYG0l9s7dbB7j3gbS',
    'vdrmota/contact-info-scraper':'9Sk4JJhEma9vBKqrg'}
SPECS={
    'breadth-r2-ai-web':('apify/ai-web-scraper','0.2.26',8192,180,'0.20','0.01',6),
    'breadth-r3-ai-web':('apify/ai-web-scraper','0.2.26',8192,180,'0.20','0.01',6),
    'breadth-r2-google-search':('apify/google-search-scraper','0.0.455',1024,120,'0.50','0.01',3),
    'breadth-r3-google-search':('apify/google-search-scraper','0.0.455',1024,120,'0.50','0.01',3),
    'cap-r2-website-content-crawler':('apify/website-content-crawler','0.3.97',8192,120,'0.08','0.02',30),
    'cap-r3-website-content-crawler':('apify/website-content-crawler','0.3.97',8192,120,'0.08','0.02',30),
    'continuation-contact-pilot':('vdrmota/contact-info-scraper','0.2.238',512,120,'0.50','0.03',6)}

def validate(cell):
    if not isinstance(cell,dict)or cell.get('cell_id')not in SPECS:raise ValueError('unreviewed_cell')
    actor,build,memory,timeout,cap,other,assigned=SPECS[cell['cell_id']]
    if cell.get('actor')!=actor or cell.get('actor_id')!=ACTORS[actor]:raise ValueError('actor_scope')
    expected={'build':build,'memoryMbytes':memory,'timeoutSecs':timeout,'maxTotalChargeUsd':cap,'restartOnError':False}
    options=cell.get('options')
    if (not isinstance(options,dict)or options!=expected or type(options['memoryMbytes'])is not int
            or type(options['timeoutSecs'])is not int or options['restartOnError']is not False):raise ValueError('native_options')
    if cell.get('build')!=build or cell.get('force_permission_level')!='LIMITED_PERMISSIONS':raise ValueError('build_permission')
    if cell.get('ancillary_reserve_usd')!=other or type(cell.get('assigned_case_count'))is not int or cell['assigned_case_count']!=assigned:raise ValueError('units_cap_denominator')
    blob=json.dumps(cell['input'],sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
    if hashlib.sha256(blob).hexdigest()!=cell.get('native_input_sha256'):raise ValueError('input_sha')
    if cell['cell_id'].startswith('continuation-contact'):
        i=cell['input'];truth=cell['output']['expected_records']
        required={'startUrls':[{'url':x['url']}for x in truth],'maxRequestsPerStartUrl':1,
            'mergeContacts':False,'maxDepth':0,'maxRequests':6,'sameDomain':True,'considerChildFrames':False,
            'maximumLeadsEnrichmentRecords':0,'leadsEnrichmentDepartments':[],
            'verifyLeadsEnrichmentEmails':False,'scrapeSocialMediaProfiles':
            {k:False for k in ('facebooks','instagrams','tiktoks','twitters','youtubes')},
            'useBrowser':False,'waitUntil':'domcontentloaded','proxyConfig':{'useApifyProxy':False}}
        if i!=required or Decimal(cap)<Decimal('0.50'):raise ValueError('contact_bound')
        prefix='https://scrapingant.github.io/scrapingant-examples/fixtures/apify-continuation-v1/contacts/'
        if len(truth)!=6 or len({x['url']for x in truth})!=6 or any(x['url']!=prefix+f'contact-{n:03d}.html'for n,x in enumerate(truth)):raise ValueError('owned_contact_URLs')
    return True
