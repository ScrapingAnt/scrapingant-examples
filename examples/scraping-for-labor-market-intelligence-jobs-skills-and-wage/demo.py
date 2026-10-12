"""Capture actual loopback runs; never invokes managed retrieval."""
import argparse
import json
from pathlib import Path
import platform

from collector import ListingParser, SourcePolicy, collect, direct_html, refresh
from fixture_server import FixtureServer, FIXTURES
from greenhouse_replay import CAPTURE_PATH, project_capture
from greenhouse_single_post import collect_one, record_oracle_matches


def write_json(directory, name, value):
    (directory / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with FixtureServer() as server:
        policy = SourcePolicy(server.url)
        first_page = ListingParser()
        first_page.feed(direct_html(server.url))
        naive_ids = sorted({card["jobID"] for card in first_page.cards})
        baseline = collect(policy)
        expected = json.loads((FIXTURES / "expected-records.json").read_text().replace(
            "__ORIGIN__", server.origin).replace("2026-10-11T21:00:00Z", baseline["observedUTC"]))
        assert baseline["records"] == expected, "independent literal record oracle mismatch"
        write_json(directory, "baseline.json", baseline)
        write_json(directory, "record-example.json", baseline["records"][1])
        server.mode = "refresh"
        complete_refresh = refresh(baseline, collect(policy))
        write_json(directory, "complete-refresh.json", complete_refresh)
        server.mode = "http_fail"
        partial = collect(policy)
        write_json(directory, "partial-collection.json", partial)
        partial_refresh = refresh(baseline, partial)
        write_json(directory, "partial-refresh.json", partial_refresh)
        matrix = []
        for mode, budget in (("baseline", 3), ("hostile_next", 3), ("loop", 3),
                             ("baseline", 1), ("conflict", 3), ("missing_location", 3),
                             ("denied", 3), ("http_fail", 3), ("empty", 3),
                             ("empty_unconfirmed", 3)):
            server.mode = mode
            result = collect(policy, max_pages=budget)
            case = "page_budget" if budget == 1 else mode
            matrix.append({"case": case, "complete": result["complete"],
                           "counters": result["counters"], "failures": result["failures"]})
        write_json(directory, "failure-matrix.json", matrix)
        lines = ["case | requested_pages | unique_records | complete | failure",
                 "--- | --- | --- | --- | ---"]
        for row in matrix:
            lines.append(f'{row["case"]} | {row["counters"]["requested_pages"]} | '
                         f'{row["counters"]["unique_records"]} | '
                         f'{str(row["complete"]).lower()} | '
                         f'{",".join(failure["code"] for failure in row["failures"]) or "none"}')
        (directory / "failure-matrix.txt").write_text("\n".join(lines) + "\n")
        summary = [
            f"python={platform.python_version()}",
            f"first_page_only: pages=1 unique_jobs={len(naive_ids)} "
            f'oracle_matches={str(naive_ids == [row["jobID"] for row in expected]).lower()}',
            f'bounded_collection: pages={baseline["counters"]["requested_pages"]} '
            f'cards={baseline["counters"]["cards_seen"]} '
            f'duplicates={baseline["counters"]["duplicate_cards"]} '
            f'unique_jobs={len(baseline["records"])} oracle_matches=true',
            f'complete_refresh: added={",".join(complete_refresh["added_ids"])} changed='
            + ";".join(f'{row["jobID"]}:{",".join(row["fields"])}' for row in complete_refresh["changed"])
            + f' absent={",".join(complete_refresh["removed_ids"])}',
            f'partial_refresh: failures={",".join(row["code"] for row in partial["failures"])} '
            f'removed={len(partial_refresh["removed_ids"])} '
            f'retained_previous={",".join(partial_refresh["retained_previous_ids"])}',
            "managed_api_calls=0 paid_calls=0",
        ]
        replay = project_capture(json.loads(CAPTURE_PATH.read_text()), employer="Greenhouse")
        write_json(directory, "greenhouse-replay.json", replay)
        assert [row["jobID"] for row in replay["candidate_records"]] == json.loads(
            (FIXTURES / "greenhouse-expected-ids.json").read_text())
        summary.append(f'greenhouse_replay: candidate_posts={replay["candidate_count"]} '
                       'validated_for_refresh=false missing_required=applicationURL')
        (directory / "summary.txt").write_text("\n".join(summary) + "\n")
        print("\n".join(summary))
    owned_body = (FIXTURES / "greenhouse-single-post.html").read_text()
    single_post = collect_one(fetch=lambda url: owned_body, observed_utc="2026-10-12T08:26:43Z")
    single_post["execution"] = {"mode": "owned_source_shaped_fixture", "provider_dispatches": 0}
    assert single_post["complete"] and record_oracle_matches(single_post["records"])
    write_json(directory, "greenhouse-single-post-owned.json", single_post)
    print("single_post_offline: owned_fixture=1 literal_record_matches=true provider_calls=0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "expected_output")
    run(parser.parse_args().output_dir)
