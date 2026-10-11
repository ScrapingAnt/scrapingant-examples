#!/usr/bin/env python3
"""Recompute live evidence summary from retained public captures; no network or keys."""
import collections
import hashlib
import json
import math
from pathlib import Path
import tiktoken
from contract import score
from model_run import calculate_cost

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'expected_output'
def sha(data):return hashlib.sha256(data).hexdigest()

def wilson_interval(successes,n):
    """Nominal 95% repeat interval; independence is an explicit approximation."""
    if not n:return None
    z=1.959963984540054;p=successes/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-radius),min(1,center+radius)]

def inference(row):return bool(row.get('usage')) or row.get('completion') is not None

def aggregate_model(rows):
    cells=[];balanced=[]
    for phase,case,arm in sorted({(r['phase'],r['case'],r['arm']) for r in rows}):
        group=[r for r in rows if (r['phase'],r['case'],r['arm'])==(phase,case,arm)]
        completed=[r for r in group if inference(r)]
        accepted=sum(r['score']['accepted_page'] for r in completed)
        known=sum(r['actual_cost_usd'] for r in group if r['actual_cost_usd'] is not None)
        unknown=sum(r['actual_cost_usd'] is None for r in group)
        total=None if unknown else known
        cells.append({'phase':phase,'case':case,'arm':arm,'attempts':len(group),'completions':len(completed),
            'inference_responses':len(completed),'completion_strings':sum(r.get('completion') is not None for r in completed),
            'accepted_pages':accepted,'exact_page_accuracy':accepted/len(completed) if completed else None,
            'nominal_wilson_95_repeat_interval':wilson_interval(accepted,len(completed)),
            'correct_slots':sum(r['score']['correct_slots'] for r in completed),
            'expected_slots':sum(r['score']['expected_slots'] for r in completed),
            'outcomes':dict(collections.Counter(r['outcome'] for r in group)),
            'unknown_charge_attempts':unknown,'known_token_rate_cost_usd':known,'all_attempts_token_rate_cost_usd':total,
            'conservative_accounted_usd':known+sum(r['reserved_usd'] for r in group if r['actual_cost_usd'] is None),
            'all_attempts_cost_per_accepted_page_usd':total/accepted if total is not None and accepted else None,
            'known_token_rate_cost_per_accepted_page_usd':known/accepted if accepted else None,
            'unique_completion_strings':len({r['completion'] for r in completed if r.get('completion') is not None}),
            'system_fingerprints':sorted({r['system_fingerprint'] for r in completed if r.get('system_fingerprint')})})
    for phase,case in sorted({(r['phase'],r['case']) for r in rows}):
        groups={arm:[r for r in rows if (r['phase'],r['case'],r['arm'])==(phase,case,arm) and inference(r)] for arm in ('html','markdown','text')}
        matched=sorted(set.intersection(*(set(r['repeat'] for r in group) for group in groups.values())))
        balanced.append({'phase':phase,'case':case,'matched_repeats':matched,'n_per_arm':len(matched),
            'arms':{arm:{'accepted_pages':sum(r['score']['accepted_page'] for r in group if r['repeat'] in matched),
                         'correct_slots':sum(r['score']['correct_slots'] for r in group if r['repeat'] in matched),
                         'expected_slots':sum(r['score']['expected_slots'] for r in group if r['repeat'] in matched)} for arm,group in groups.items()}})
    return {'cells':cells,'balanced':balanced,
        'accuracy_denominator':'Inference responses, including refusals/truncation/incorrect JSON; pre-inference failures retained separately as attempts and unknown costs.',
        'uncertainty':'Nominal Wilson 95% intervals assume independent Bernoulli repeats on this same input/model/settings. Repeated identical inputs may be correlated; these intervals are descriptive and do not establish website-population coverage. Seven selected records are not a representative test corpus.',
        'cost_basis':'API-reported token usage at published standard rates, not invoice receipts. Unknown-charge attempts retain their allowance reservation; their all-attempts actual total and cost per correct output are null.'}

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
            'model_inference_responses':sum(inference(row) for row in model['calls']),
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
        if row.get('usage'):
            if row['actual_cost_usd']!=calculate_cost(data['usage']):raise ValueError('Model cost recomputation differs')
            candidate=None
            choice=data['choices'][0]
            if choice['finish_reason']=='stop' and not choice['message'].get('refusal'):
                try:candidate=json.loads(choice['message'].get('content'))
                except (ValueError,TypeError):pass
            if row['score']!=score(row['case'],candidate):raise ValueError('Model score recomputation differs')
        result['model_rows'].append({**{key:row.get(key) for key in ('attempt','phase','case','arm','repeat','http_status','outcome','actual_cost_usd','reserved_usd','score')},
                                    'public_failure_classification':data.get('error',{}).get('public_classification')})
    result['model_analysis']=aggregate_model(model['calls'])
    result['measurement']='hosted_static_mcp_acquisition_and_fixed_model_extraction' if result['model_completions'] else 'hosted_static_mcp_acquisition_and_incomplete_fixed_model_phase'
    if result['model_completions']:result['model_accuracy']='Per-case/arm exact-page rates in model_analysis; unlike tasks are not pooled.'
    result['model_settings']={key:model.get(key) for key in ('model','schema','system_prompt','task_sha256')}
    result['model_settings'].update(temperature=0,top_p=1,n=1,max_completion_tokens=1000,service_tier='default',store=False)
    return result

if __name__=='__main__':
    result=summarize();(OUT/'execution-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'mcp_attempts':result['mcp_attempts'],'account_delta':result['observed_account_delta_total'],'model_attempts':result['model_attempts'],'model_completions':result['model_completions'],'model_stop':result['model_stop_reason']}))
