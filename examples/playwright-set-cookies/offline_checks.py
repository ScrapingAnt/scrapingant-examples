"""Run boundary tests and demonstrate the duplicate-row regression detector."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import unittest

import test_state
from state import EXPECTED


def run():
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent), pattern='test_*.py')
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)

    # Deliberate in-memory mutation: the test must reject naive membership counting.
    # This is a sensitivity check, not a claim that this bug shipped previously.
    original = test_state.score_records
    def vulnerable_score(rows):
        count = sum((r.get('sku'), r.get('currency'), r.get('price')) in EXPECTED for r in rows)
        return {'matching_records': count, 'exact_match': count == 4}
    try:
        test_state.score_records = vulnerable_score
        mutant_suite = unittest.TestSuite([
            test_state.OracleTests('test_duplicate_rows_cannot_replace_missing_skus'),
        ])
        mutant = unittest.TextTestRunner(stream=io.StringIO()).run(mutant_suite)
    finally:
        test_state.score_records = original
    report = {
        'tested_at': datetime.now(timezone.utc).isoformat(),
        'command': 'python -m unittest -v',
        'tests_run': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'all_passed': result.wasSuccessful(),
        'duplicate_oracle_mutation': {
            'mutation': 'Naive tuple-membership sum allows four copies of one SKU to count as four matches.',
            'tests_run': mutant.testsRun,
            'expected_failures_observed': len(mutant.failures), 'errors': len(mutant.errors),
            'detected': len(mutant.failures) == 1 and not mutant.errors,
        },
    }
    if not result.wasSuccessful():
        print(output.getvalue())
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run()
    data = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
    print(data, end='')
    raise SystemExit(0 if result['all_passed'] and result['duplicate_oracle_mutation']['detected'] else 1)
