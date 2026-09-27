"""Rebuild publication counts offline from captured, record-validated JSON."""
import argparse
from collections import Counter
import json
from pathlib import Path
from oracle import score
from requests_matrix import CASE_MATCHES

DIAGNOSTICS = {
    "redirect_cookie_accumulation", "second_catalog_scope", "domain_path_lookup_and_clear",
    "https_mount_still_allows_http", "unsupported_httponly_keyword", "unsupported_samesite_keyword",
}


def summarize(capture):
    rounds = capture["rounds"]
    if not rounds or [r["round"] for r in rounds] != list(range(1, len(rounds) + 1)):
        raise ValueError("Capture must have consecutively numbered nonempty rounds")
    observations, diagnostics = [], []
    for result in rounds:
        if Counter(row["case"] for row in result["observations"]) != Counter(CASE_MATCHES.keys()):
            raise ValueError("Every round must contain each extraction case exactly once")
        if Counter(row["case"] for row in result["diagnostics"]) != Counter(DIAGNOSTICS):
            raise ValueError("Every round must contain each diagnostic exactly once")
        for row in result["observations"]:
            actual = score(row["records"])
            if any(row[key] != value for key, value in actual.items()):
                raise ValueError("Stored scores disagree with the independently recomputed records")
            if row["row_count"] != len(row["records"]):
                raise ValueError("Stored row count disagrees with records")
            expected_matches = CASE_MATCHES[row["case"]]
            if (not row["check_passed"] or row["status"] != 200 or row["row_count"] != 4
                    or actual["matching_records"] != expected_matches
                    or actual["exact_match"] != (expected_matches == 4)
                    or row["expected_matching_records"] != expected_matches):
                raise ValueError("Capture contains an unexpected extraction outcome")
        if not all(row["check_passed"] for row in result["diagnostics"]):
            raise ValueError("Capture contains a failed diagnostic")
        observations.extend(result["observations"])
        diagnostics.extend(result["diagnostics"])
    cases = []
    for name in CASE_MATCHES:
        rows = [row for row in observations if row["case"] == name]
        cases.append({
            "case": name, "observations": len(rows),
            "statuses": sorted({row["status"] for row in rows}),
            "row_counts": sorted({row["row_count"] for row in rows}),
            "matching_records_per_observation": sorted({row["matching_records"] for row in rows}),
            "expected_records_per_observation": 4,
            "selected_currencies": sorted({row["wire"]["selected_currency"] for row in rows}),
            "active_member": sorted({row["wire"]["active_member"] for row in rows}),
            "stored_cookie_counts": sorted({row["stored_cookie_count"] for row in rows}),
        })
    return {
        "source": "expected_output/requests.json", "tested_at": capture["tested_at"],
        "environment": capture["environment"], "rounds": len(rounds),
        "extraction_observations": len(observations), "diagnostic_observations": len(diagnostics),
        "checks_total": len(observations) + len(diagnostics),
        "all_checks_passed": True, "expected_record_comparisons": 4 * len(observations),
        "matching_records": sum(row["matching_records"] for row in observations),
        "all_extractions_http_200_and_four_rows": all(row["status"] == 200 and row["row_count"] == 4 for row in observations),
        "exact_extractions": sum(row["exact_match"] for row in observations),
        "cases": cases,
        "interpretation": "Designed positive and negative controls; totals are not production success rates.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(__file__).parent / "expected_output/requests.json")
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.input.read_text())), indent=2))


if __name__ == "__main__":
    main()
