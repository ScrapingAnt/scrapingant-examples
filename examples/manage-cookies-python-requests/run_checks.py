"""Run all local tests and emit only portable result metadata to JSON."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {
        "tested_at": datetime.now(timezone.utc).isoformat(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "passed": result.wasSuccessful(),
        "scope": "offline jar/oracle boundaries plus loopback fixture/matrix/summary checks; no external requests",
    }
    rendered = json.dumps(summary, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
