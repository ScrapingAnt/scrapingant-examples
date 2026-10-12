"""Verify stored outputs against literal records and conservative refresh invariants."""
import argparse
import json
from pathlib import Path
from greenhouse_single_post import HTTP_CANONICAL, SOURCE_URL, record_oracle_matches

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
    owned = read("greenhouse-single-post-owned.json")
    assert owned["complete"] and record_oracle_matches(owned["records"])
    assert owned["completeness_scope"] == "one_selected_posting_page"
    assert not owned["board_inventory_complete"] and owned["max_pages"] == 1
    assert owned["execution"]["provider_dispatches"] == 0
    return (directory / "summary.txt").read_text(), (directory / "failure-matrix.txt").read_text()


def verify_recorded_single_post():
    """Check safe captured facts; do not pretend the withheld HTML is replayed."""
    folder = ROOT / "expected_output/live-single-post-2026-10-12"
    receipt = json.loads((folder / "receipt.json").read_text())
    result = json.loads((folder / "collection.json").read_text())
    assert receipt["requests"] == 1 and receipt["actual_receipt_credits"] == 1 and receipt["accepted"]
    assert receipt["http_status"] == 200 and receipt["target_status"] == "200"
    assert receipt["response_bytes"] == 104223
    assert receipt["response_sha256"] == "b8385bbc2da7e5d34e469dad34117c059449bb68786df0e5063dc21ed09bb886"
    assert receipt["parameters"] == {"url": SOURCE_URL, "browser": "false", "proxy_type": "datacenter",
                                      "proxy_country": "us", "timeout": "30", "return_page_source": "false"}
    assert not receipt["body_distributed"] and not receipt["hash_reproducible_from_projection"]
    assert not (folder / "response.html").exists()
    assert result["complete"] and result["semantic_oracle_matches"] and record_oracle_matches(result["records"])
    assert result["records"][0]["observedUTC"] == "2026-10-12T09:42:20Z"
    assert result["completeness_scope"] == "one_selected_posting_page" and not result["board_inventory_complete"]
    assert result["counters"] == {"requested_pages": 1, "fetched_pages": 1, "accepted_pages": 1,
                                  "unique_records": 1, "failures": 0}
    assert result["source_metadata"]["canonical_url"] == HTTP_CANONICAL
    assert result["source_metadata"]["canonical_scheme_differs"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-dir", type=Path)
    args = parser.parse_args()
    saved = verify(ROOT / "expected_output")
    if args.fresh_dir:
        assert verify(args.fresh_dir) == saved, "fresh summary or failure matrix differs from saved capture"
    verify_recorded_single_post()
    print("capture_verification=passed literal_records=3 failure_cases=10")
    print("single_post_verification=passed owned_fixture=1 recorded_posts=1 withheld_full_HTML=true")
