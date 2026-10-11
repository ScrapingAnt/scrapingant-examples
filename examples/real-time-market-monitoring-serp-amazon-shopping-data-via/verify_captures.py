"""Check captured files against independently authored literal expectations."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ORACLE = json.loads((ROOT / "fixtures/oracle.json").read_text())


def validate_record_capture(snapshot, name):
    expected = ORACLE[name]
    assert snapshot["context"] == {**ORACLE["provenance"], "observed_utc": expected["observed_utc"]}, "snapshot provenance mismatch"
    assert snapshot["page"] == 1 and snapshot["expected_count"] == 6, "window mismatch"
    assert snapshot["complete"] == expected["complete"], "completeness mismatch"
    assert snapshot["issues"] == expected["issues"], "issues mismatch"
    assert [[r[c] for c in expected["record_columns"]] for r in snapshot["records"]] == expected["records"], "record oracle mismatch"
    for record in snapshot["records"]:
        assert {k: record[k] for k in snapshot["context"]} == snapshot["context"], "record provenance mismatch"


def main():
    for name in ("baseline", "changed", "truncated"):
        validate_record_capture(json.loads((ROOT / "expected_output" / (name + ".json")).read_text()), name)
    for name in ("changed", "truncated"):
        result = json.loads((ROOT / "expected_output" / (name + "-diff.json")).read_text())
        assert result == ORACLE[name + "_diff"], "diff oracle mismatch"
    naive = json.loads((ROOT / "expected_output/naive.json").read_text())
    assert naive == {"demonstration": "Wrong: ignores snapshot completeness", "missing_asins": ["B000000003", "B000000004", "B000000005"], "missing_count": 3, "current_complete": False}, "naive negative example mismatch"
    # Negative controls prove the validator rejects capture tampering.
    checks = 0
    for field, value in (("sponsored_status", "organic"), ("observed_position", 99), ("asin", "B000000099"), ("price", "0.00"), ("query", "different query")):
        capture = json.loads((ROOT / "expected_output/baseline.json").read_text())
        capture["records"][0][field] = value
        try:
            validate_record_capture(capture, "baseline")
        except AssertionError:
            checks += 1
        else:
            raise AssertionError("tampered capture passed")
    print(json.dumps({"record_captures_checked": 3, "diff_captures_checked": 2,
                      "naive_negative_example_checked": 1, "tamper_negative_controls_rejected": checks, "status": "passed"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
