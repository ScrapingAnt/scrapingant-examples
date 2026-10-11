#!/usr/bin/env python3
"""Independent literal output oracle; never parses HTML or derives expected fields."""
import copy
import json
from pathlib import Path
import sys
import unittest

EXPECTED_RECORDS = [
    {"mode": "raw", "sku": "CSHARP-001", "title": "C# & HTTP", "price": 99.95,
     "currency": "USD", "credits": 1, "attempts": 1},
    {"mode": "rendered", "sku": "CSHARP-001", "title": "C# & HTTP", "price": 99.95,
     "currency": "USD", "credits": 10, "attempts": 1},
]


def verify(value):
    if value.get("scope") != "offline-synthetic" or value.get("cases") != 48:
        raise ValueError("Unexpected scope or case count")
    if value.get("records") != EXPECTED_RECORDS:
        raise ValueError("Independent literal record oracle mismatch")


class Controls(unittest.TestCase):
    def check_mutation(self, mutate):
        value = {"scope": "offline-synthetic", "cases": 48, "records": copy.deepcopy(EXPECTED_RECORDS)}
        mutate(value)
        with self.assertRaises(ValueError):
            verify(value)

    def test_wrong_title(self):
        self.check_mutation(lambda v: v["records"][0].update(title="Wrong"))

    def test_wrong_price(self):
        self.check_mutation(lambda v: v["records"][0].update(price=0))

    def test_missing_record(self):
        self.check_mutation(lambda v: v["records"].pop())

    def test_false_live_scope(self):
        self.check_mutation(lambda v: v.update(scope="live"))

    def test_invented_credit(self):
        self.check_mutation(lambda v: v["records"][1].update(credits=1))


if __name__ == "__main__":
    if sys.argv[1:] == ["--controls"]:
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        if not result.wasSuccessful():
            raise SystemExit(1)
        print("PASS 5/5 independent oracle mutation controls")
    else:
        verify(json.loads(Path("actual_output/results.json").read_text()))
        oracle = json.loads(Path("fixtures/oracle.json").read_text())
        if oracle != {"sku": "CSHARP-001", "title": "C# & HTTP", "price": 99.95, "currency": "USD"}:
            raise ValueError("Fixture oracle changed")
        print("PASS independent literal oracle: 2 simulated records, 4 fields each")
