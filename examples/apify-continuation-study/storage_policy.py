"""Prospective registered-store contract; never proves absence of every SDK access."""
from datetime import datetime, timedelta
import re

GOOGLE='apify/google-search-scraper'
DEFAULTS={'datasets':'defaultDatasetId','keyValueStores':'defaultKeyValueStoreId','requestQueues':'defaultRequestQueueId'}

class PolicyBreach(ValueError):
    def __init__(self,reason='extra_storage_alias'):
        self.reason=reason
        super().__init__('storage_policy_breach')

def stamp(value):
    try:
        if type(value)is not str or len(value)>64:raise ValueError()
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
        if date.tzinfo is None or date.utcoffset()!=timedelta(0):raise ValueError()
        return date
    except (ValueError,TypeError,OverflowError):raise PolicyBreach('malformed_storage_aliases')from None

def aliases(cell,run,pinned=None):
    mapping=run.get('storageIds')
    if not isinstance(mapping,dict)or set(mapping)!=set(DEFAULTS):raise PolicyBreach('malformed_storage_aliases')
    ids=[]
    for group,field in DEFAULTS.items():
        values=mapping[group]
        expected={'default'}|({'linkProspecting'}if group=='datasets'and cell['actor']==GOOGLE else set())
        if not isinstance(values,dict)or set(values)!=expected:raise PolicyBreach()
        if values['default']!=run.get(field):raise PolicyBreach('malformed_storage_aliases')
        for identity in values.values():
            if type(identity)is not str or re.fullmatch(r'[A-Za-z0-9]{17}',identity)is None:raise PolicyBreach('malformed_storage_aliases')
            ids.append(identity)
    if len(ids)!=len(set(ids)):raise PolicyBreach('malformed_storage_aliases')
    extra=mapping['datasets'].get('linkProspecting')
    if pinned is not None and extra!=pinned:raise PolicyBreach()
    return {'state':'google_exact_aliases'if extra else 'default_only',
        'registered_default_only':extra is None,'extra_dataset_id':extra,
        'all_named_storage_access_absence_proven':False}

def validate_extra(cell,run,meta,observed_at,pinned):
    proof=aliases(cell,run,pinned)
    if cell['actor']!=GOOGLE or proof['extra_dataset_id']!=pinned:raise PolicyBreach()
    if not isinstance(meta,dict)or meta.get('id')!=pinned:raise PolicyBreach()
    if not(meta.get('userId')==run['userId']and meta.get('actId')==run['actId']
           and meta.get('actRunId')==run['id']and 'name'in meta and meta['name']is None):raise PolicyBreach()
    end=stamp(observed_at);start=stamp(run['startedAt']);created=stamp(meta.get('createdAt'))
    if run.get('finishedAt')is not None:end=min(end,stamp(run['finishedAt']))
    if not start<=created<=end:raise PolicyBreach()
    stats=meta.get('stats')
    if (type(meta.get('itemCount'))is not int or meta['itemCount']!=0 or not isinstance(stats,dict)
            or type(stats.get('storageBytes'))is not int or stats['storageBytes']!=0):raise PolicyBreach()
    return {'extra_dataset_fresh_unnamed_owned':True,'extra_item_count':0,'extra_storage_bytes':0,
        'metadata_only_no_extra_content_read':True,'all_named_storage_access_absence_proven':False}

def findings(cell,run,log,extra_proof=None):
    return {**aliases(cell,run),**(extra_proof or {}),
        'restricted_permission_requested':cell['force_permission_level']=='LIMITED_PERMISSIONS',
        'effective_permission_observed':None,'all_named_storage_access_absence_proven':False,
        'limited_token_allows_extra_and_prior_Actor_storage':True,
        'input_only_wire_access_proven':False,'Article_repeat_gate_passed':False}

def require_log_scope(cell,log):
    if re.search(r'articles-state|ARTICLES-SCRAPED-',log,re.IGNORECASE):raise PolicyBreach('named_state_log')

def continuation(cell,accepted,run,policy):
    if run.get('status')!='SUCCEEDED':return False
    if cell.get('prospective_first_output_gate')and not accepted['full_assigned_output_complete']:return False
    if cell['actor']==GOOGLE and policy.get('extra_dataset_fresh_unnamed_owned')is not True:return False
    return True
