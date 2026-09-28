"""Machine-readable unittest results without host paths or fabricated pass flags."""
import argparse
import json
import unittest
from pathlib import Path


class Capture(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.cases = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"test": test.id(), "status": "passed"})
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({"test": test.id(), "status": "failed", "error": str(err[1])})
    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({"test": test.id(), "status": "error", "error": str(err[1])})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = Capture()
    unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py").run(result)
    payload = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "cases": result.cases}
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({key: payload[key] for key in ("tests", "failures", "errors")}))
    raise SystemExit(not result.wasSuccessful())
