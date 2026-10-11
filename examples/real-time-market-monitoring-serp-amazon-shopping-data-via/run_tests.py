"""Emit the actual unittest outcome as JSON; no timing benchmark."""
import io
import json
import unittest


class Results(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


suite = unittest.defaultTestLoader.discover(".", pattern="test_*.py")
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, resultclass=Results, verbosity=2).run(suite)
print(json.dumps({"tests_run": result.testsRun, "successful": result.wasSuccessful(), "passed": result.passed,
                  "failures": [{"test": str(t), "detail": detail} for t, detail in result.failures + result.errors],
                  "skipped": [{"test": str(t), "reason": reason} for t, reason in result.skipped]}, indent=2, sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)
