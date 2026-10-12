"""Independent literal oracle for fake native-contract records; no HTML/network/key access."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

EXPECTED_CASES = 62
EXPECTED_PRODUCT = {"sku": "SYNTH-000", "title": "Synthetic product 000", "price": Decimal("12.34"), "currency": "USD"}
EXPECTED_RECORDS = [dict(mode=mode, **EXPECTED_PRODUCT, credits=cost, attempts=1)
                    for mode, cost in (("raw", 1), ("rendered", 10))]


def verify(value):
    if value.get("scope") != "offline-owned-jsonld" or value.get("cases") != EXPECTED_CASES:
        raise ValueError("Unexpected native scope or case denominator")
    if value.get("records") != EXPECTED_RECORDS:
        raise ValueError("Independent native record literals differ")


class Controls(unittest.TestCase):
    def reject(self, mutate):
        value = {"scope": "offline-owned-jsonld", "cases": EXPECTED_CASES, "records": copy.deepcopy(EXPECTED_RECORDS)}
        mutate(value)
        with self.assertRaises(ValueError):
            verify(value)

    def test_wrong_sku(self): self.reject(lambda v: v["records"][0].update(sku="OTHER"))
    def test_wrong_title(self): self.reject(lambda v: v["records"][0].update(title="Wrong"))
    def test_wrong_price(self): self.reject(lambda v: v["records"][0].update(price=0))
    def test_missing_record(self): self.reject(lambda v: v["records"].pop())
    def test_false_live_scope(self): self.reject(lambda v: v.update(scope="live"))
    def test_invented_receipt(self): self.reject(lambda v: v["records"][1].update(credits=1))
    def test_wrong_denominator(self): self.reject(lambda v: v.update(cases=-1))


if __name__ == "__main__":
    if sys.argv[1:] == ["--controls"]:
        result = unittest.TextTestRunner(stream=sys.stdout).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        if not result.wasSuccessful(): raise SystemExit(1)
        print("PASS 7/7 native literal-oracle mutation controls")
    else:
        verify(json.loads(Path("actual_output/jsonld-results.json").read_text(), parse_float=Decimal))
        oracle = json.loads(Path("live-captures/product-jsonld/oracle.json").read_text(), parse_float=Decimal)
        if oracle != EXPECTED_PRODUCT: raise ValueError("Native committed oracle differs from literals")
        print("PASS native independent literal oracle: 2 simulated records, 4 fields each")
