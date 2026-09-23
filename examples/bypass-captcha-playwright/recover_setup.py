"""Archive a proven zero-request fixture failure for explicit manual recovery.

This tool makes no network calls. Use only after the batch controller stops.
It never releases a provider failure, paid request, ambiguous request or running
job. Re-running broad_matrix with the same plan then fills this unmeasured slot.
"""
import argparse
import json
from pathlib import Path

def eligible_setup_failure(record):
    return (record.get('outcome') == 'error' and record.get('error_stage') == 'fixture_setup'
            and type(record.get('task_create_requests')) is int and record['task_create_requests'] == 0
            and type(record.get('paid_tasks_created')) is int and record['paid_tasks_created'] == 0
            and record.get('task_creation_uncertain') is False
            and record.get('provider_reported_cost_usd') is None)


def archive_setup_failure(directory, job_id):
    from broad_matrix import make_schedule, MAX_ROUNDS
    job = next((r for r in make_schedule(MAX_ROUNDS) if r['id'] == job_id), None)
    if job is None:
        raise ValueError('Unknown planned trial')
    path = directory / (job_id + '.json')
    record = json.loads(path.read_text())
    if any(record.get(k) != job[k] for k in ('id', 'case', 'provider', 'trial')):
        raise ValueError('Trial identity mismatch')
    if not eligible_setup_failure(record):
        raise ValueError('Cannot prove this is an uncharged fixture-only failure')
    archive = directory / 'setup_diagnostics'
    archive.mkdir(exist_ok=True)
    attempts = list(archive.glob(job_id + '.attempt-*.json'))
    if len(attempts) >= 2:
        raise ValueError('Two setup recoveries already attempted; inspect the fixture')
    target = archive / (job_id + f'.attempt-{len(attempts) + 1:02}.json')
    # Preserve the complete diagnostic before removing only the active reservation.
    # A crash before unlink keeps the original reservation, preventing a new task.
    with target.open('x') as file:
        file.write(path.read_text())
    path.unlink()
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', required=True)
    args = parser.parse_args()
    path = archive_setup_failure(args.output, args.archive)
    print(json.dumps({'archived_diagnostic': str(path.relative_to(args.output)),
                      'paid_tasks_created': 0, 'next_step': 'Explicitly resume the same matrix plan.'}))


if __name__ == '__main__':
    main()
