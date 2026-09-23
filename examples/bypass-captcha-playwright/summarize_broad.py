"""Rebuild descriptive counts from retained trials; no network calls or paid jobs."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from statistics import median


def latency(values):
    return ({'n': len(values), 'median': round(median(values), 3),
             'min': min(values), 'max': max(values)} if values else {'n': 0})


def summarize_cell(jobs, rows):
    costs = [Decimal(r['provider_reported_cost_usd']) for r in rows
             if r.get('provider_reported_cost_usd') is not None]
    returned = [r for r in rows if r.get('solution_delivered') is True]
    return {
        'planned': len(jobs), 'records': len(rows), 'missing_records': len(jobs) - len(rows),
        'outcomes': dict(sorted(Counter(r['outcome'] for r in rows).items())),
        'execution_outcomes': dict(sorted(Counter(r['execution_outcome'] for r in rows
                                                  if r.get('execution_outcome')).items())),
        'task_create_requests': sum(r.get('task_create_requests', 0) for r in rows),
        'tasks_created': sum(r.get('paid_tasks_created', 0) for r in rows),
        'uncertain_task_creations': sum(r.get('task_creation_uncertain') is True for r in rows),
        'solutions_delivered': len(returned),
        'server_verifications': sum(r.get('server_acceptance_tested') is True for r in rows),
        'server_accepted': sum(r.get('server_accepted') is True for r in rows),
        'server_rejected': sum(r.get('server_accepted') is False for r in rows),
        'ocr_correct': sum(r.get('ground_truth_match') is True for r in rows),
        'ocr_wrong': sum(r.get('ground_truth_match') is False for r in rows),
        'token_only_observations': sum(r['outcome'] == 'token_delivered_unverified' for r in rows),
        'solution_latency_seconds': latency([r['provider_elapsed_seconds'] for r in returned
                                             if 'provider_elapsed_seconds' in r]),
        'completed_workflow_seconds': latency([r['workflow_elapsed_seconds'] for r in rows
                                               if 'workflow_elapsed_seconds' in r]),
        'reported_cost': {'coverage': len(costs),
                          'total_usd': str(sum(costs, Decimal(0))) if costs else None},
        'v3_scores': [r['verification']['score'] for r in rows if 'score' in r.get('verification', {})],
        'provider_errors': dict(sorted(Counter(r['provider_error_code'] for r in rows
                                                if r.get('provider_error_code')).items())),
        'replay_results': [{'trial': r['trial'], **r['immediate_replay']} for r in rows
                            if 'immediate_replay' in r],
    }


def summarize(directory):
    plan = json.loads((directory / 'plan.json').read_text())
    rows = []
    for job in plan['jobs']:
        path = directory / (job['id'] + '.json')
        if path.exists():
            row = json.loads(path.read_text())
            if any(row.get(key) != job[key] for key in ('id', 'case', 'provider', 'trial')):
                raise ValueError('Record does not match planned job')
            rows.append(row)
    cells = []
    for case in plan['cases']:
        for provider in ('2captcha', 'anticaptcha'):
            jobs = [r for r in plan['jobs'] if r['case'] == case and r['provider'] == provider]
            selected = sorted([r for r in rows if r['case'] == case and r['provider'] == provider],
                              key=lambda r: r['trial'])
            cells.append({'case': case, 'provider': provider, **summarize_cell(jobs, selected)})
    return {
        'scope': 'Six-case cohort only; earlier four paid tasks excluded.',
        'planned': plan['planned_tasks'], 'records': len(rows),
        'tasks_created': sum(r.get('paid_tasks_created', 0) for r in rows),
        'uncertain_task_creations': sum(r.get('task_creation_uncertain') is True for r in rows),
        'unfinished': [r['id'] for r in rows if r['outcome'] == 'started'],
        'started_at': min((r['tested_at'] for r in rows if 'tested_at' in r), default=None),
        'cells': cells,
        'spending_observations': [json.loads(p.read_text()) for p in sorted(directory.glob('spending-*.json'))],
        'latency_scope': 'SDK call wall time for returned solutions, including creation and polling; failures excluded and counted separately.',
        'workflow_scope': 'Completed browser workflows; first v3/GeeTest trial also includes optional immediate replay.',
        'cost_scope': 'Provider-reported task costs with explicit receipt coverage; balances/deltas are separate observations.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('expected_output/broad-2026-09-23'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(summarize(args.input), indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
