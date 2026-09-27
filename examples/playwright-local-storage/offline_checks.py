"""Capture actual unit-test results without exporting filesystem paths."""
import argparse
import io
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('run_output/offline-checks.json'))
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent), pattern='test_*.py')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    data = {'captured_at': datetime.now(timezone.utc).isoformat(), 'tests_run': result.testsRun,
            'failures': len(result.failures), 'errors': len(result.errors),
            'skipped': len(result.skipped), 'successful': result.wasSuccessful()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data))
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise SystemExit(1)
