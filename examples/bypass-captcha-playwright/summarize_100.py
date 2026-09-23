"""Summarize the 100-trial extension with separate initial/added concurrency phases."""
import argparse
import json
from math import ceil
from pathlib import Path

from summarize_broad import latency, summarize, summarize_cell
from recover_setup import eligible_setup_failure


def summarize_extended_cell(jobs, rows):
    result = summarize_cell(jobs, rows)
    values = sorted(r['provider_elapsed_seconds'] for r in rows
                    if r.get('solution_delivered') is True and 'provider_elapsed_seconds' in r)
    result['returned_solution_percentiles_seconds'] = (
        {'n': len(values), 'p90': values[ceil(.90 * len(values)) - 1],
         'p95': values[ceil(.95 * len(values)) - 1]} if values else {'n': 0})
    result['failed_provider_call_seconds'] = latency([
        r['provider_elapsed_seconds'] for r in rows
        if r.get('solution_delivered') is not True and 'provider_elapsed_seconds' in r])
    result['configured_concurrency'] = [dict(batch_workers=batch, per_provider=provider)
        for batch, provider in sorted({(r['configured_batch_workers'], r['configured_provider_workers'])
                                      for r in rows if 'configured_batch_workers' in r})]
    return result


def phase_cells(plan, rows, first, last):
    cells = []
    for case in plan['cases']:
        for provider in ('2captcha', 'anticaptcha'):
            jobs = [r for r in plan['jobs'] if r['case'] == case and r['provider'] == provider
                    and first <= r['trial'] <= last]
            selected = sorted([r for r in rows if r['case'] == case and r['provider'] == provider
                               and first <= r['trial'] <= last], key=lambda r: r['trial'])
            cells.append({'case': case, 'provider': provider, **summarize_extended_cell(jobs, selected)})
    return cells


def summarize_100(directory):
    result = summarize(directory)
    plan = json.loads((directory / 'plan.json').read_text())
    if plan['rounds'] != 100:
        raise ValueError('Expected an explicitly planned 100-trial-per-cell experiment')
    rows = [json.loads((directory / (job['id'] + '.json')).read_text())
            for job in plan['jobs'] if (directory / (job['id'] + '.json')).exists()]
    result['cells'] = phase_cells(plan, rows, 1, 100)
    result['phases'] = {
        'initial_10': {'trial_range': [1, 10], 'planned': 120,
                       'cells': phase_cells(plan, rows, 1, 10)},
        'added_90': {'trial_range': [11, 100], 'planned': 1080,
                     'cells': phase_cells(plan, rows, 11, 100)},
    }
    result['blocks_of_ten'] = [{'trial_range': [first, first + 9],
                              'cells': phase_cells(plan, rows, first, first + 9)}
                             for first in range(1, 101, 10)]
    diagnostics = []
    for path in sorted((directory / 'setup_diagnostics').glob('*.json')):
        row = json.loads(path.read_text())
        if not eligible_setup_failure(row):
            raise ValueError('Recovery archive contains an ambiguous or provider-paid attempt')
        diagnostics.append({**{k: row.get(k) for k in ('id', 'case', 'provider', 'trial',
                            'tested_at', 'error_class', 'elapsed_seconds', 'task_create_requests',
                            'paid_tasks_created')}, 'source': str(path.relative_to(directory))})
    result['uncharged_setup_diagnostics'] = diagnostics
    result['browser_workflow_attempts'] = len(rows) + len(diagnostics)
    result['percentile_method'] = 'Nearest rank: sorted returned-solution latencies at ceil(p*n); failures excluded and summarized separately.'
    result['comparison_scope'] = 'Initial10 and added90 are separate phases. Pooled timings mix invocation times and settings; consult per-cell concurrency metadata and the dated report. Legacy records omit concurrency fields.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('expected_output/broad-100-2026-09-23'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(summarize_100(args.input), indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
