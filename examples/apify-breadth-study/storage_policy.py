"""Registered storage evidence is narrower than proof of all storage accesses."""
import re

class PolicyBreach(ValueError):
    def __init__(self, reason):
        self.reason=reason
        super().__init__('storage_policy_breach')

def aliases(run):
    mapping=run.get('storageIds')
    if mapping is None: return {'state':'absent','registered_default_only':None}
    if not isinstance(mapping,dict):raise PolicyBreach('malformed_storage_aliases')
    expected={'datasets':'defaultDatasetId','keyValueStores':'defaultKeyValueStoreId','requestQueues':'defaultRequestQueueId'}
    if set(mapping)-set(expected):raise PolicyBreach('extra_storage_alias')
    for group,field in expected.items():
        values=mapping.get(group)
        if values is None:continue
        if not isinstance(values,dict):raise PolicyBreach('malformed_storage_aliases')
        if set(values)-{'default'}:raise PolicyBreach('extra_storage_alias')
        if values.get('default')!=run.get(field):raise PolicyBreach('malformed_storage_aliases')
    complete=set(mapping)==set(expected) and all(mapping[k]=={'default':run.get(v)}for k,v in expected.items())
    return {'state':'default_only'if complete else 'incomplete','registered_default_only':True if complete else None}

def findings(cell,run,log):
    registered=aliases(run)
    article=cell['actor']=='lukaskrivka/article-extractor-smart'
    named_seen=article and bool(re.search(r'articles-state|ARTICLES-SCRAPED-',log,re.IGNORECASE))
    # No negative-log or alias result proves the absence of SDK/storage accesses.
    return {**registered,'named_state_marker_observed':named_seen,
        'all_named_storage_access_absence_proven':False,
        'restricted_permission_requested':cell['force_permission_level']=='LIMITED_PERMISSIONS',
        'effective_permission_observed':None,
        'Article_runtime_compatibility_observed':article and run.get('status')=='SUCCEEDED',
        'Article_repeat_gate_passed':False if article else None,
        'requires_independent_absence_evidence':article,
        'limited_token_allows_extra_and_prior_Actor_storage':True}

def require_log_scope(cell,log):
    if cell['actor']=='lukaskrivka/article-extractor-smart' and re.search(r'articles-state|ARTICLES-SCRAPED-',log,re.IGNORECASE):
        raise PolicyBreach('named_state_log')

def continuation(cell,acceptance,run,policy):
    # Exploratory or non-product comparisons must first establish full useful output.
    if cell.get('first_exploratory') and (run.get('status')!='SUCCEEDED' or not acceptance['full_assigned_output_complete']):
        return False
    if cell['actor']=='lukaskrivka/article-extractor-smart':
        return policy.get('Article_repeat_gate_passed')is True
    return True
