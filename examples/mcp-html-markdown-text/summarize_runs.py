#!/usr/bin/env python3
"""Recompute live evidence summary from retained public captures; no network or keys."""
import collections
import hashlib
import json
from pathlib import Path
import tiktoken

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'expected_output'
def sha(data):return hashlib.sha256(data).hexdigest()

def summarize():
    mcp_dir=OUT/'live-mcp-2026-10-11';mcp=json.loads((mcp_dir/'ledger.json').read_text())
    model_dir=OUT/'live-model-2026-10-11';model=json.loads((model_dir/'ledger.json').read_text())
    result={'measurement':'hosted_static_mcp_acquisition_and_incomplete_fixed_model_phase',
            'source_url':mcp['source_url'],'server_info':mcp['server_info'],'protocol':mcp['negotiated_protocol'],
            'mcp_attempts':len(mcp['calls']),'mcp_complete':mcp.get('complete',False),
            'mcp_credits_documented_bound':mcp['reserved_credit_upper_bound'],
            'observed_account_delta_total':mcp['observed_account_delta_total'],
            'credit_receipts':None,'credit_attribution':'Scoped read-only contemporaneous account delta, no exclusive per-request receipts; concurrent traffic cannot be ruled out.',
            'model_attempts':len(model['calls']),'model_complete':model.get('complete',False),
            'model_completions':sum(row.get('completion') is not None for row in model['calls']),
            'model_stop_reason':model.get('stop_reason'),'model_actual_known_cost_usd':model['actual_reported_usage_cost_usd'],
            'model_total_actual_cost_usd':None if any(row['actual_cost_usd'] is None for row in model['calls']) else model['actual_reported_usage_cost_usd'],
            'model_accounted_upper_bound_usd':model['accounted_usd'],
            'model_accuracy':None,'model_cost_per_correct_output':None,'mcp_cost_per_model_correct_output':None,
            'source_ledger_sha256':{'mcp':sha((mcp_dir/'ledger.json').read_bytes()),'model':sha((model_dir/'ledger.json').read_bytes())},
            'mcp_rows':[],'model_rows':[],'all_failures_retained':True}
    for arm in ('html','markdown','text'):
        rows=[row for row in mcp['calls'] if row['arm']==arm]
        values=[]
        for row in rows:
            for field in ('response','content'):
                data=(mcp_dir/row[field+'_file']).read_bytes()
                if sha(data)!=row[field+'_sha256']:raise ValueError('Retained MCP capture hash mismatch')
            values.append((mcp_dir/row['content_file']).read_bytes())
        content=values[0].decode('utf8')
        result['mcp_rows'].append({'arm':arm,'attempts':len(rows),'required_values_present':sum(row.get('required_values_survive',False) for row in rows),
            'required_non_null_slots_per_output':12,'unique_output_hashes':len({sha(v) for v in values}),
            'utf8_bytes':len(values[0]),'o200k_base':len(tiktoken.get_encoding('o200k_base').encode(content,disallowed_special=())),
            'cl100k_base':len(tiktoken.get_encoding('cl100k_base').encode(content,disallowed_special=())),
            'matches_offline_reference':all(v==(OUT/f'catalog.{arm}').read_bytes() for v in values),
            'observed_account_delta':sum(row['observed_account_delta'] for row in rows),
            'outcomes':dict(collections.Counter(row['outcome'] for row in rows)),
            'source_identity_note':'Five HTML outputs match frozen source; source bytes for separately acquired Markdown/text calls are not exposed.'})
    for row in model['calls']:
        if sha((model_dir/row['response_file']).read_bytes())!=row['response_sha256']:raise ValueError('Retained model capture hash mismatch')
        data=json.loads((model_dir/row['response_file']).read_text())
        result['model_rows'].append({**{key:row.get(key) for key in ('attempt','phase','case','arm','repeat','http_status','outcome','actual_cost_usd','reserved_usd','score')},
                                    'provider_error_code':data.get('error',{}).get('code')})
    return result

if __name__=='__main__':
    result=summarize();(OUT/'execution-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'mcp_attempts':result['mcp_attempts'],'account_delta':result['observed_account_delta_total'],'model_attempts':result['model_attempts'],'model_completions':result['model_completions'],'model_stop':result['model_stop_reason']}))
