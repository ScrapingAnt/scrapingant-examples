"""Verify stored outputs against literal records and conservative refresh invariants."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent


def verify(directory):
    def read(name):
        return json.loads((directory / name).read_text())
    baseline = read("baseline.json")
    origin = baseline["source"].split("/careers/")[0]
    oracle = json.loads((ROOT / "fixtures/expected-records.json").read_text().replace(
        "__ORIGIN__", origin).replace("2026-10-11T21:00:00Z", baseline["observedUTC"]))
    assert baseline["records"] == oracle
    assert baseline["complete"] and baseline["counters"]["cards_seen"] == 4
    assert baseline["counters"]["duplicate_cards"] == 1
    complete = read("complete-refresh.json")
    assert complete["added_ids"] == ["NS-004"]
    assert complete["removed_ids"] == ["NS-002"] and not complete["removals_suppressed"]
    assert complete["changed"] == [{"jobID": "NS-001", "fields": {
        "title": {"before": "Platform Engineer", "after": "Senior Platform Engineer"},
        "location": {"before": "Leeds, UK", "after": "Remote - UK"}}}]
    partial = read("partial-refresh.json")
    assert partial["removed_ids"] == [] and partial["removals_suppressed"]
    assert partial["retained_previous_ids"] == ["NS-002", "NS-003"]
    assert len(partial["next_snapshot"]["records"]) == 3
    matrix = read("failure-matrix.json")
    expected = [
        ("baseline", 2, 3, True, []),
        ("hostile_next", 1, 2, False, ["next_url_rejected"]),
        ("loop", 1, 2, False, ["pagination_loop"]),
        ("page_budget", 1, 2, False, ["page_budget"]),
        ("conflict", 2, 2, False, ["conflicting_id"]),
        ("missing_location", 2, 2, False, ["record_invalid"]),
        ("denied", 2, 2, False, ["listing_envelope"]),
        ("http_fail", 2, 1, False, ["http_503"]),
        ("empty", 1, 0, True, []),
        ("empty_unconfirmed", 1, 0, False, ["unconfirmed_empty"]),
    ]
    actual = [(row["case"], row["counters"]["requested_pages"], row["counters"]["unique_records"],
               row["complete"], [failure["code"] for failure in row["failures"]]) for row in matrix]
    assert actual == expected
    replay = read("greenhouse-replay.json")
    assert [row["jobID"] for row in replay["candidate_records"]] == json.loads(
        (ROOT / "fixtures/greenhouse-expected-ids.json").read_text())
    assert replay["candidate_count"] == 19 and not replay["validated_for_refresh"]
    assert replay["missing_required_fields"] == ["applicationURL"]
    return (directory / "summary.txt").read_text(), (directory / "failure-matrix.txt").read_text()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-dir", type=Path)
    args = parser.parse_args()
    saved = verify(ROOT / "expected_output")
    if args.fresh_dir:
        assert verify(args.fresh_dir) == saved, "fresh summary or failure matrix differs from saved capture"
    print("capture_verification=passed literal_records=3 failure_cases=10")
