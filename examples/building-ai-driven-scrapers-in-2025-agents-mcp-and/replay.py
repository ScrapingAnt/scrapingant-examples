"""Re-score saved live captures offline; never performs retrieval/model requests."""
import argparse
import hashlib
import json
from pathlib import Path
from validate import validate_json
from live import unpack

ROOT=Path(__file__).resolve().parent
DEFAULT=ROOT/'expected_output/live-2026-09-30'

def replay(capture):
    retrievals=json.loads((capture/'retrievals.json').read_text())
    runs=json.loads((capture/'model-runs.json').read_text())
    by_case={r['case']:r for r in retrievals['retrievals']}
    for row in retrievals['retrievals']:
        if row['status']=='ok':
            markdown=(capture/f"{row['case']}.md").read_text()
            if hashlib.sha256(markdown.encode()).hexdigest()!=row['content_sha256']:
                raise ValueError('retrieval content hash mismatch')
            envelope=json.loads((capture/f"{row['case']}.tool.json").read_text())
            if unpack(envelope)!=markdown:
                raise ValueError('saved Markdown differs from raw tool response')
    results=[];accepted=[];quarantine=[]
    for run in runs['runs']:
        case=run['case'];name=f"{case}-{run['repeat']}"
        if run['status']!='ok':
            results.append({'run':name,'status':run['status'],'complete_run_success':False})
            continue
        markdown=(capture/f'{case}.md').read_text()
        assert hashlib.sha256(markdown.encode()).hexdigest()==by_case[case]['content_sha256'], 'content hash mismatch'
        response=json.loads((capture/f'{name}.model.json').read_text())
        text=response['choices'][0]['message']['content']
        result=validate_json(text,markdown,by_case[case]['url'],case)
        if response['choices'][0]['finish_reason']!='stop':
            result['errors'].append('incomplete_model_output')
            result['quarantine'].extend({'record':r,'reasons':['incomplete_model_output']} for r in result['accepted'])
            result['accepted']=[];result['accepted_count']=0;result['complete_run_success']=False
        result.update(run=name,status='scored')
        accepted.extend({'run':name,'record':r} for r in result['accepted'])
        quarantine.extend({'run':name,**r} for r in result['quarantine'])
        results.append(result)
    scored=[r for r in results if r['status']=='scored']
    def total(key):return sum(r[key] for r in scored)
    emitted=total('emitted_count');expected=total('expected_count');matches=total('oracle_value_match_count')
    summary={'retrieval_attempts':len(retrievals['retrievals']), 'retrieval_successes':sum(r['status']=='ok' for r in retrievals['retrievals']), 'model_attempts':len(runs['runs']), 'completed_model_runs':len(scored), 'schema_valid_records':total('schema_valid_count'),'emitted_records':emitted,'expected_records_across_completed_runs':expected,'oracle_value_matches':matches,'accepted_records':len(accepted),'quarantined_records':len(quarantine),'schema_pass_rate':total('schema_valid_count')/emitted if emitted else None,'precision':matches/emitted if emitted else None,'recall':matches/expected if expected else None,'complete_run_successes':sum(r['complete_run_success'] for r in results),'complete_run_success_rate':sum(r['complete_run_success'] for r in results)/len(results) if results else None,'omitted_ids':sum(len(r['omissions']) for r in scored),'duplicate_ids':sum(len(r['duplicate_ids']) for r in scored),'hallucinated_ids':sum(len(r['hallucinated_ids']) for r in scored),'prompt_tokens':sum(r.get('usage',{}).get('prompt_tokens',0) for r in runs['runs']),'completion_tokens':sum(r.get('usage',{}).get('completion_tokens',0) for r in runs['runs']),'list_price_upper_estimate_usd':sum(r.get('list_price_upper_estimate_usd',0) for r in runs['runs']),'reserved_upper_bound_usd':len(runs['runs'])*runs['reservation_usd_per_attempt'],'scrapingant_credit_cost':None}
    unknown_usage=sum(not all(k in r.get('usage',{}) for k in ('prompt_tokens','completion_tokens')) or 'list_price_upper_estimate_usd' not in r for r in runs['runs'])
    summary['attempts_without_usage']=unknown_usage
    if unknown_usage or not runs['runs']:
        for key in ('prompt_tokens','completion_tokens','list_price_upper_estimate_usd'):
            summary[key]=None
    return {'summary':summary,'runs':results},accepted,quarantine

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture',type=Path,default=DEFAULT);parser.add_argument('--write',type=Path)
    args=parser.parse_args();report,accepted,quarantine=replay(args.capture)
    if args.write:
        args.write.mkdir(parents=True,exist_ok=True)
        (args.write/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
        for filename,rows in [('accepted.jsonl',accepted),('quarantine.jsonl',quarantine)]:
            (args.write/filename).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    print(json.dumps(report['summary'],indent=2))
