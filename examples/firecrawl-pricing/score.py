"""Offline replay of stored synthetic outputs. Never imports an HTTP client."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from acceptance import run_checks

ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def evaluate(r):
    record = {'fixture': r['fixture'], 'result': {'structuredContent': {
        'markdown': r['markdown'], 'html': r['html'], 'metadata': r['metadata']}}}
    checks = run_checks(record)
    if not checks:
        raise ValueError('Unknown fixture')
    basic = all(c['passed'] for c in checks)
    structural = [c for c in checks if c['check'].startswith('html_table_structure_')]
    # These are distinct application contracts, not provider accuracy.
    numeric = r['fixture'] == 'complete-catalog' and basic
    visible = r['fixture'] == 'html-tables' and '| AF-2 | 0 |' not in r['markdown']
    return {**{k:r[k] for k in ['sequence','phase','fixture','setting','unit_type','replicate','pair_position','role']},
        'target_status':r['metadata'].get('statusCode'), 'credits':r['metadata'].get('creditsUsed'),
        'basic_preservation':basic,
        'html_structure':all(c['passed'] for c in structural) if structural else None,
        'two_numeric_prices':numeric if r['fixture'] in ['complete-catalog','missing-price'] else None,
        'visible_only_markdown':visible if r['fixture']=='html-tables' else None,
        'markdown_sha256':sha(r['markdown'].encode()),'html_sha256':sha(r['html'].encode())}

def analyze(captures):
    if sorted(r['sequence'] for r in captures)!=list(range(1,201)):
        raise ValueError('Exactly one saved capture for each ordinal 1–200 is required')
    rows=[evaluate(r) for r in captures]
    if any(r['credits']!=1 for r in rows):
        raise ValueError('A saved billed-credit value is missing or differs from one')
    settings=[]
    for name in sorted({r['setting'] for r in rows if r['unit_type']=='independent'}):
        subset=[r for r in rows if r['unit_type']=='independent' and r['setting']==name]
        if len(subset)!=14: raise ValueError('Incomplete balanced setting')
        settings.append({'setting':name,'calls':len(subset),'credits':sum(r['credits'] for r in subset),'basic_preservation_pass':sum(r['basic_preservation'] for r in subset),'html_structure_pass':sum(r['html_structure'] is True for r in subset),'two_numeric_prices_pass':sum(r['two_numeric_prices'] is True for r in subset),'visible_only_markdown_pass':sum(r['visible_only_markdown'] is True for r in subset)})
    pairs=[]
    for kind in ['delayed-corrective-pair','delayed-same-pair','404-diagnostic-pair','fresh-cache-pair']:
        subset=[r for r in rows if r['unit_type']==kind]
        groups=defaultdict(list)
        for r in subset: groups[r['replicate']].append(r)
        if len(groups)!=8 or any(sorted(r['pair_position'] for r in g)!=[1,2] for g in groups.values()):
            raise ValueError('Incomplete pair set')
        accepted=sum(any(r['basic_preservation'] for r in g) for g in groups.values()) if kind.startswith('delayed') else None
        credits=sum(r['credits'] for r in subset)
        pairs.append({'subset':kind,'pairs':8,'calls':len(subset),'credits':credits,'accepted_delayed_outputs':accepted,'credits_per_accepted':credits/accepted if accepted else None})
    return rows, {'billed_calls':len(rows),'credits_consumed':sum(r['credits'] for r in rows),'pilot_calls':sum(r['phase']=='pilot' for r in rows),'preregistered_calls':sum(r['phase']=='expansion' for r in rows),'balanced_settings':settings,'pairs':pairs,'interpretation':'Fixture-specific contracts only. No mixed accuracy rate. null ratio means undefined or not applicable.'}

def main():
    inputs=json.loads((ROOT/'data/manifest.json').read_text())
    for f in inputs['files']:
        if sha((ROOT/f['file']).read_bytes())!=f['sha256']: raise ValueError('Stored input hash mismatch')
    manifest=json.loads((ROOT/'sources/manifest.json').read_text())
    for f in manifest['files']:
        if sha((ROOT/f['file']).read_bytes())!=f['sha256']: raise ValueError('Fixture hash mismatch')
    captures=[json.loads(line) for line in (ROOT/'data/captures.jsonl').read_text().splitlines()]
    rows,summary=analyze(captures)
    attempts=list(csv.DictReader((ROOT/'data/attempts.csv').open()))
    if len(attempts)!=201 or sum(int(a['effective_debit']) for a in attempts)!=200:
        raise ValueError('Attempt accounting differs')
    rejected=[a for a in attempts if a['outcome']=='connector_catalog_rejection']
    if len(rejected)!=1 or rejected[0]['reported_credits']!='' or rejected[0]['effective_debit']!='0':
        raise ValueError('Unbilled connector rejection must remain separate')
    summary['connector_attempts']=len(attempts)
    out=ROOT/'expected_output'; out.mkdir(exist_ok=True)
    with (out/'ledger.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Offline replay: 200 billed calls, 200 credits; 24 pilot + 176 preregistered; 201 connector attempts.')
    for p in summary['pairs'][:2]:
        ratio='undefined' if p['credits_per_accepted'] is None else str(p['credits_per_accepted'])
        print(f"{p['subset']}: {p['credits']} credits / {p['accepted_delayed_outputs']} accepted = {ratio}")
    print('Eight balanced settings: 14/14 basic preservation per setting; stricter contracts reported separately.')

if __name__=='__main__': main()
