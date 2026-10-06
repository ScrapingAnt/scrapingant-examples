"""Prospective offline contracts. Old scores and raw bytes are preserved separately."""
from collections import Counter
from decimal import Decimal, localcontext
import copy, re
import frozen_acceptance as frozen

FIELDS={'case_id','sku','name','price_minor','currency'}
SOCIAL=('discords','facebooks','instagrams','linkedIns','pinterests','reddits','snapchats','telegrams',
    'threads','tiktoks','twitters','whatsapps','youtubes','facebookProfiles','instagramProfiles',
    'tiktokProfiles','twitterProfiles','youtubeProfiles','leadsEnrichment')
cost_per_1000=frozen.cost_per_1000

def normalize_ai(row,url,truth):
    if not isinstance(row,dict)or row.get('url')!=url or not frozen.success(row):return None
    data=row.get('data')
    if isinstance(data,list):
        if len(data)!=1 or not isinstance(data[0],dict):return None
        data=data[0]
    if not isinstance(data,dict)or set(data)!=FIELDS or set(truth)!=FIELDS:return None
    if type(data['price_minor'])is not int or any(type(data[k])is not str for k in FIELDS-{'price_minor'}):return None
    if data!=truth:return None
    result=copy.deepcopy(row);result['data']=copy.deepcopy(data)
    return result

def summarize(cell,rows,cases,foreign,duplicate):
    errors=sum(isinstance(x,dict)and x.get('#error')is True for x in rows)
    markers=sum(isinstance(x,dict)and '#error'in x and type(x['#error'])is not bool for x in rows)
    malformed=sum(not isinstance(x,dict)for x in rows)
    accepted=sum(x['accepted']for x in cases)
    return {'assigned':cell['assigned_case_count'],'returned_raw_rows':len(rows),'accepted':accepted,
        'missing_cases':sum(x['returned']==0 for x in cases),'foreign_rows':foreign,'duplicate_rows':duplicate,
        'native_error_rows':errors,'invalid_native_error_markers':markers,'malformed_rows':malformed,'cases':cases,
        'full_assigned_output_complete':len(cases)==cell['assigned_case_count']and accepted==len(cases)
            and not(errors or markers or malformed or foreign or duplicate),
        'accepted_valid_partial_outputs_counted':True,'synthetic_truth':True,
        'prospective_contract_version':cell['prospective_contract_version'],
        'runtime_benchmark_or_invoice_claim':False}

def content_contract(contract,text):
    """Exact historical WCC text rule: whitespace only, distinct IDs, text primary."""
    if type(text)is not str:return {'accepted':False}
    required=contract['required_sentence_ids'];expected=contract['expected_sentences']
    found=set(re.findall(r'\bS[0-9]{3,6}\b',text));boiler=set(re.findall(r'\bB[0-9]{3,6}\b',text))
    normalized=re.sub(r'\s+',' ',text)
    matched=len(found&set(required));kept=sum(re.sub(r'\s+',' ',s)in normalized for s in expected.values())
    return {'accepted':matched*100>=len(required)*95 and kept*100>=len(required)*95 and len(boiler)<=1,
        'matched':matched,'required':len(required),'sentence_matches':kept,'boilerplate_ids':len(boiler),
        'foreign_sentence_ids':len(found-set(required)),'code_marker_preserved':contract['code_marker']in text,
        'table_marker_preserved':contract['table_marker']in text}

def phone(value):
    if type(value)is not str or len(value)>40 or re.fullmatch(r'\+?[0-9() .-]+',value)is None:return None
    digits=re.sub(r'[^0-9]','',value)
    if len(digits)==10:digits='1'+digits
    return digits if len(digits)==11 and digits.startswith('1')else None

def contacts(cell,rows):
    truths=cell['output']['expected_records'];known={x['url']for x in truths}
    counts=Counter(x.get('url')if type(x.get('url'))is str else None for x in rows if frozen.success(x))
    cases=[]
    for truth in truths:
        matches=[x for x in rows if frozen.success(x)and x.get('url')==truth['url']]
        result={'case_id':truth['case_id'],'returned':len(matches),'accepted':False}
        if len(matches)==1:
            row=matches[0];emails=row.get('emails');phones=row.get('phones')
            email_ok=isinstance(emails,list)and all(type(x)is str for x in emails)
            phone_ok=isinstance(phones,list)and all(phone(x)is not None for x in phones)
            actual_email=emails if email_ok else [];actual_phone=[phone(x)for x in phones]if phone_ok else []
            result.update(expected_email_count=len(truth['emails']),expected_phone_count=len(truth['phones']),
                matched_emails=len(set(actual_email)&set(truth['emails'])),
                false_positive_emails=len(set(actual_email)-set(truth['emails'])),
                matched_phones=len(set(actual_phone)&set(truth['phones'])),
                false_positive_phones=len(set(actual_phone)-set(truth['phones'])),
                phones_uncertain_reported=copy.deepcopy(row.get('phonesUncertain')),
                provenance_matches=row.get('originalStartUrl')==truth['originalStartUrl'])
            empty_enrichment=all(k not in row or row[k]==[]for k in SOCIAL)
            uncertain=row.get('phonesUncertain',[])
            uncertain_valid=isinstance(uncertain,list)and all(type(x)is str for x in uncertain)
            no_verification='chargeableEmailVerificationsCount'not in row or (type(row['chargeableEmailVerificationsCount'])is int and row['chargeableEmailVerificationsCount']==0)
            result['unexpected_enrichment_or_social']=not(empty_enrichment and no_verification)
            result['accepted']=result['provenance_matches']and email_ok and phone_ok and sorted(actual_email)==sorted(truth['emails'])and sorted(actual_phone)==sorted(truth['phones'])and empty_enrichment and no_verification and uncertain_valid
        cases.append(result)
    return summarize(cell,rows,cases,sum(n for key,n in counts.items()if key not in known),
        sum(max(0,n-1)for key,n in counts.items()if key in known))

def evaluate(cell,rows,terminal_status='SUCCEEDED'):
    if not isinstance(rows,list):raise ValueError('rows_array_required')
    kind=cell['output']['kind']
    if kind=='contact-details':return contacts(cell,rows)
    if kind=='ai-products':
        old=frozen.evaluate(cell,rows);normalized=[];trace=[]
        for index,row in enumerate(rows):
            truth=next((x for i,x in enumerate(cell['output']['expected_records'])
                if isinstance(row,dict)and row.get('url')==cell['output']['allowed_urls'][i]),None)
            value=normalize_ai(row,row.get('url'),truth)if truth is not None else None
            normalized.append(value if value is not None else copy.deepcopy(row))
            trace.append({'raw_row_index':index,'strict_normalization_accepted':value is not None,
                'shape':'single_object_array'if isinstance(row,dict)and isinstance(row.get('data'),list)else 'object_or_invalid'})
        result=frozen.evaluate(cell,normalized)
        result.update(prospective_contract_version=cell['prospective_contract_version'],
            frozen_object_only_score=old,normalization_trace=trace,
            original_R1_score_reclassified=False,raw_rows_mutated=False)
        return result
    if kind=='wcc-original-text':
        contracts=cell['output']['content_contracts'];known={x['url']for x in contracts}
        counts=Counter(x.get('url')if type(x.get('url'))is str else None for x in rows if frozen.success(x))
        cases=[]
        for contract in contracts:
            matches=[x for x in rows if frozen.success(x)and x.get('url')==contract['url']]
            row={'case_id':contract['case_id'],'returned':len(matches),'accepted':False}
            if len(matches)==1:
                row['text']=content_contract(contract,matches[0].get('text'))
                row['markdown']=content_contract(contract,matches[0].get('markdown'))
                row['accepted']=terminal_status=='SUCCEEDED'and row['text']['accepted']
            cases.append(row)
        result=summarize(cell,rows,cases,sum(n for key,n in counts.items()if key not in known),sum(max(0,n-1)for key,n in counts.items()if key in known))
        result['primary']='original text contract; Markdown and formatting markers diagnostic'
        result['original_819_assignment_preserved']=True
        return result
    if kind=='serp-pages':
        result=frozen.evaluate(cell,rows);result['prospective_contract_version']=cell['prospective_contract_version']
        result['original_R1_policy_failure_reclassified']=False
        return result
    raise ValueError('unknown_prospective_contract')

def commerce_metrics(truth,row):
    """Offline prerequisite only: one native Offer; no SKU guess or multiple-offer selection."""
    if not isinstance(row,dict):return {'accepted':False,'reason':'row_object_required'}
    offer=row.get('offers')
    if isinstance(offer,list):
        if len(offer)!=1:return {'accepted':False,'reason':'one_offer_required'}
        offer=offer[0]
    if not isinstance(offer,dict)or type(offer.get('price'))not in (str,int,Decimal):return {'accepted':False,'reason':'price_missing_or_float'}
    try:
        if len(str(offer['price']))>96:raise ValueError('price_precision_bound')
        with localcontext()as ctx:
            ctx.prec=128
            price=Decimal(offer['price']);minor=price*100
            exact=price.is_finite()and 0<=price<=Decimal('1e18')and minor==minor.to_integral_value()
    except (ValueError,ArithmeticError):exact=False;minor=None
    return {'accepted':row.get('url')==truth['url']and row.get('inputUrl')==truth['url']
        and row.get('name')==truth['name']and exact and minor==truth['price_minor']
        and offer.get('priceCurrency')==truth['currency'],
        'SKU_present_diagnostic_only':'sku'in row,'SKU_truth_match_if_present':row.get('sku')==truth['sku'],
        'currency':'USD','cadence':'one assigned product page','runnable_actor_contract':False}
