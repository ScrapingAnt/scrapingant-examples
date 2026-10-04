"""Offline useful-output contract. Synthetic truth; never an invoice or LLM score."""
from collections import Counter
from decimal import Decimal, localcontext
import html, re
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs

FIELDS = ('case_id', 'sku', 'name', 'price_minor', 'currency')

def normalized(text): return re.sub(r'\s+', ' ', html.unescape(text)).strip()

def text_contract(contract, text):
    if type(text) is not str or not text.strip():
        return {'accepted': False, 'sentence_matches': 0, 'id_matches': 0, 'boilerplate_ids': None}
    clean = normalized(text)
    required = contract['required_sentence_ids']
    ids = sum(bool(re.search(r'\b' + re.escape(x) + r'\b', clean)) for x in required)
    sentences = sum(normalized(x) in clean for x in contract['expected_sentences'].values())
    boiler = sum(bool(re.search(r'\b' + re.escape(x) + r'\b', clean)) for x in contract['boilerplate_ids'])
    return {'accepted': ids * 100 >= len(required) * 95
            and sentences * 100 >= len(contract['expected_sentences']) * 95 and boiler <= 1,
            'sentence_matches': sentences, 'id_matches': ids, 'boilerplate_ids': boiler}

class ParsedHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.tags = [], set()
    def handle_starttag(self, tag, attrs): self.tags.add(tag.lower())
    def handle_data(self, data): self.parts.append(data)

def evaluate_generic(cell, rows):
    if not isinstance(rows, list): raise ValueError('rows_array_required')
    out = cell['output']
    expected = out['expected_records']
    cases = []
    native_errors = sum(isinstance(x, dict) and x.get('#error') is True for x in rows)
    invalid_markers = sum(isinstance(x, dict) and '#error' in x
                          and type(x['#error']) is not bool for x in rows)
    malformed_rows = sum(not isinstance(x, dict) for x in rows)
    def success(row):
        # Raw browser exports include both '#error': false success records and
        # '#error': true native failures. Absent markers are normal for other Actors.
        return isinstance(row, dict) and ('#error' not in row or row['#error'] is False)
    def identifier(row):
        value = row.get('case_id')
        return value if type(value) is str else None
    if expected is not None:
        keys = {x['case_id'] for x in expected}
        occurrences = Counter(identifier(x) for x in rows if success(x))
        for truth in expected:
            matched = [x for x in rows if success(x)
                       and x.get('case_id') == truth['case_id']]
            valid = (len(matched) == 1 and type(matched[0].get('price_minor')) is int
                     and {k: matched[0].get(k) for k in FIELDS} == truth)
            cases.append({'case_id': truth['case_id'], 'returned': len(matched), 'accepted': valid})
        foreign = sum(n for key, n in occurrences.items() if key not in keys)
        duplicate = sum(max(0, n - 1) for key, n in occurrences.items() if key in keys)
    else:
        def url(row):
            if not isinstance(row, dict): return None
            if out.get('url_source') == 'metadata.url':
                meta = row.get('metadata')
                value = meta.get('url') if isinstance(meta, dict) else None
            else: value = row.get('url')
            return value if type(value) is str else None
        known = set(out['allowed_urls'])
        occurrences = Counter(url(x) for x in rows if success(x))
        foreign = sum(n for key, n in occurrences.items() if key not in known)
        duplicate = sum(max(0, n - 1) for key, n in occurrences.items() if key in known)
        for contract in out['content_contracts']:
            matched = [x for x in rows if success(x) and url(x) == contract['url']]
            result = {'case_id': contract['case_id'], 'returned': len(matched), 'accepted': False}
            if len(matched) == 1:
                row = matched[0]
                for field in ('text', 'markdown'):
                    result[field] = text_contract(contract, row.get(field))
                formatting = contract['mode'] == 'formatting-heavy'
                marker_ok = (not formatting or all(type(row.get(field)) is str
                    and all(contract[k] in row[field] for k in ('code_marker', 'table_marker'))
                    for field in ('text', 'markdown')))
                result['format_markers_preserved'] = marker_ok
                h = row.get('html')
                result['html_requested'] = 'html' in cell['input'].get('outputFormats', [])
                result['html_structure_preserved'] = False
                if isinstance(h, str):
                    parsed = ParsedHTML()
                    parsed.feed(h)
                    body = ' '.join(parsed.parts)
                    shape = not formatting or ('table' in parsed.tags and bool({'pre', 'code'} & parsed.tags)
                        and all(contract[k] in body for k in ('code_marker', 'table_marker')))
                    result['html_structure_preserved'] = shape and text_contract(contract, body)['accepted']
                result['accepted'] = result['text']['accepted'] and result['markdown']['accepted'] and marker_ok
                if result['html_requested']:
                    result['accepted'] = result['accepted'] and result['html_structure_preserved']
            cases.append(result)
    return {'assigned': cell['assigned_case_count'], 'returned_raw_rows': len(rows),
        'accepted': sum(x['accepted'] for x in cases), 'native_error_rows': native_errors,
        'invalid_native_error_markers': invalid_markers, 'malformed_rows': malformed_rows,
        'missing_cases': sum(x['returned'] == 0 for x in cases), 'duplicate_rows': duplicate,
        'foreign_rows': foreign, 'cases': cases,
        'accepted_valid_partial_outputs_counted': True, 'full_assigned_output_complete':
        all(x['accepted'] for x in cases) and len(cases) == cell['assigned_case_count']
        and not (native_errors or invalid_markers or malformed_rows or duplicate or foreign)}

def cost_per_1000(latest_run_meter_usd, accepted):
    if type(accepted) is not int or accepted < 0: raise ValueError('accepted_count')
    if latest_run_meter_usd is None or accepted == 0: return None
    if type(latest_run_meter_usd) is not str: raise ValueError('decimal_usd_string')
    n = Decimal(latest_run_meter_usd)
    if not n.is_finite() or n < 0: raise ValueError('cost')
    with localcontext() as c:
        c.prec = 80
        return format(n * 1000 / accepted, 'f')

def web_url(value):
    if type(value) is not str or len(value) > 8192: return False
    try:
        p = urlsplit(value)
        return p.scheme in ('http', 'https') and bool(p.hostname) and p.username is None and p.password is None
    except ValueError: return False

def success(row):
    return isinstance(row, dict) and ('#error' not in row or row['#error'] is False)

def evaluate(cell, rows):
    """Keep assigned pages/queries as denominators; never substitute row/event counts."""
    if not isinstance(rows, list): raise ValueError('rows_array_required')
    out = cell['output']; kind = out.get('kind')
    if kind in ('products', 'content-formats'):
        return evaluate_generic(cell, rows)
    if kind not in ('ai-products','article-text','serp-pages','trends'):
        raise ValueError('unknown_output_contract')
    def identity(row):
        if not isinstance(row, dict): return None
        if kind in ('ai-products','article-text'): value = row.get('url')
        elif kind == 'serp-pages':
            query = row.get('searchQuery'); value = query.get('term') if isinstance(query, dict) else None
        else: value = row.get('inputUrlOrTerm')
        return value if type(value) is str else None
    expected = out.get('allowed_urls') if kind in ('ai-products','article-text') else out.get('queries') if kind == 'serp-pages' else [out['query']]
    counts = Counter(identity(row) for row in rows if success(row))
    cases=[]
    for index, key in enumerate(expected):
        matches=[row for row in rows if success(row) and identity(row)==key]
        result={'case_id':key,'returned':len(matches),'accepted':False}
        if len(matches)==1:
            row=matches[0]
            if kind=='ai-products':
                data=row.get('data');truth=out['expected_records'][index]
                result['accepted']=isinstance(data,dict) and set(data)==set(FIELDS) and type(data.get('price_minor'))is int and data==truth
                result['markdown_available']=type(row.get('markdown'))is str and bool(row['markdown'].strip())
            elif kind=='article-text':
                result['text']=text_contract(out['content_contracts'][index],row.get('text'))
                result['title_available']=type(row.get('title'))is str and bool(row['title'].strip())
                result['loaded_url_matches']=row.get('loadedUrl')==key
                result['accepted']=result['text']['accepted'] and result['title_available'] and result['loaded_url_matches']
                result['markdown_or_html_required']=False
            elif kind=='serp-pages':
                query=row['searchQuery'];organic=row.get('organicResults')
                try:
                    p=urlsplit(query.get('url','')); q=parse_qs(p.query)
                    query_url_ok=p.scheme in ('http','https') and p.hostname in ('google.com','www.google.com') and q.get('q')==[key]
                except (TypeError,ValueError): query_url_ok=False
                page_ok=type(query.get('page'))is int and query['page']==out['required_page']
                valid=isinstance(organic,list)and 1<=len(organic)<=100
                if valid:
                    valid=all(isinstance(x,dict)and type(x.get('title'))is str and bool(x['title'].strip())and web_url(x.get('url')) for x in organic)
                target=out['expected_domains'][index]
                on_site=sum((urlsplit(x['url']).hostname==target or urlsplit(x['url']).hostname.endswith('.'+target)) for x in organic)if valid else 0
                result.update(organic_result_count=len(organic)if isinstance(organic,list)else None,
                    expected_site_results=on_site, query_page_bound=query_url_ok and page_ok,
                    accepted=query_url_ok and page_ok and valid and on_site>0,
                    event_denominator='SERP page; organic count is diagnostic')
            else:
                points=row.get('interestOverTime_timelineData'); valid=isinstance(points,list)and 1<=len(points)<=1000
                times=[];with_data=0
                if valid:
                    for point in points:
                        if not isinstance(point,dict):valid=False;break
                        t=point.get('time');values=point.get('value');flags=point.get('hasData')
                        if type(t)is not str or re.fullmatch(r'[0-9]{1,12}',t)is None:
                            valid=False;break
                        epoch=int(t);times.append(epoch)
                        if not out['start_epoch']<=epoch<out['end_epoch_exclusive']:
                            valid=False;break
                        if not isinstance(values,list)or len(values)!=1 or type(values[0])is not int or not 0<=values[0]<=100:
                            valid=False;break
                        if not isinstance(flags,list)or len(flags)!=1 or type(flags[0])is not bool:
                            valid=False;break
                        with_data+=flags[0]
                    valid=valid and times==sorted(set(times)) and with_data>0
                result.update(accepted=valid and row.get('searchTerm')==out['query'],
                    timeline_point_count=len(points)if isinstance(points,list)else None,
                    points_with_data=with_data,absolute_search_volume_validated=False,
                    region_and_interval_bound_by_frozen_input=True)
        cases.append(result)
    errors=sum(isinstance(x,dict)and x.get('#error')is True for x in rows)
    markers=sum(isinstance(x,dict)and '#error'in x and type(x['#error'])is not bool for x in rows)
    malformed=sum(not isinstance(x,dict)for x in rows)
    foreign=sum(n for key,n in counts.items()if key not in set(expected))
    duplicate=sum(max(0,n-1)for key,n in counts.items()if key in set(expected))
    complete=len(cases)==cell['assigned_case_count']and all(x['accepted']for x in cases)and not(errors or markers or malformed or foreign or duplicate)
    return {'assigned':cell['assigned_case_count'],'returned_raw_rows':len(rows),'accepted':sum(x['accepted']for x in cases),
        'native_error_rows':errors,'invalid_native_error_markers':markers,'malformed_rows':malformed,
        'missing_cases':sum(x['returned']==0 for x in cases),'duplicate_rows':duplicate,'foreign_rows':foreign,
        'cases':cases,'accepted_valid_partial_outputs_counted':True,'full_assigned_output_complete':complete,
        'output_kind':kind,'reliability_or_source_accuracy_established':False}
