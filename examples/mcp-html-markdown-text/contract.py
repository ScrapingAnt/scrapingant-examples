"""Literal output contract, separate from the representation generator."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ("name", "displayed_price", "units_sold", "share", "sku", "buy_url")
TRUTH = json.loads((ROOT / "ground_truth.json").read_text())


def score(case, candidate):
    expected = TRUTH[case]
    shape = (isinstance(candidate, list) and len(candidate) == len(expected)
             and all(isinstance(r, dict) and set(r) == set(FIELDS) for r in candidate))
    slots = len(expected) * len(FIELDS)
    correct = sum(type(candidate[i][k]) is type(r[k]) and candidate[i][k] == r[k]
                  for i, r in enumerate(expected) for k in FIELDS) if shape else 0
    return {"accepted_page": bool(shape and correct == slots),
            "correct_slots": correct, "expected_slots": slots, "shape_valid": shape}


def cost_per_correct(total_cost, accepted_pages):
    if total_cost < 0 or accepted_pages < 0:
        raise ValueError("negative cost/count")
    return total_cost / accepted_pages if accepted_pages else None
