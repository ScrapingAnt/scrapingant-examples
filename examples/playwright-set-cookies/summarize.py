"""Recompute comparison from captures without browser/network calls."""
import argparse
import json
from pathlib import Path
from collections import Counter

from browser_matrix import EXPECTED_MATCHES
from state import score_records


DIAGNOSTICS = {
    "cookie_inserted_before_first_navigation",
    "httponly_visible_to_context_not_document",
    "context_mutation_remains_isolated",
    "route_normal", "route_fetch_then_continue", "route_fetch_then_fulfill",
}


def validate_captures(captures):
    names = [data["browser"] for data in captures]
    if not names or len(names) != len(set(names)):
        raise ValueError("Expected nonempty, distinct browser captures")
    expected_cases = set(EXPECTED_MATCHES) | DIAGNOSTICS
    for data in captures:
        runs = data["runs"]
        if not runs or [run["round"] for run in runs] != list(range(1, len(runs) + 1)):
            raise ValueError("Expected consecutive rounds starting at one")
        for run in runs:
            if Counter(case["case"] for case in run["cases"]) != Counter(expected_cases):
                raise ValueError("Every expected case must appear exactly once per round")
            for case in run["cases"]:
                name = case["case"]
                if name in EXPECTED_MATCHES:
                    if case["kind"] != "extraction":
                        raise ValueError("Incorrect case kind")
                    score = score_records(case["records"])
                    if any(case.get(key) != value for key, value in score.items()):
                        raise ValueError("Stored score disagrees with independently rescored records")
                    expected = EXPECTED_MATCHES[name]
                    if case["expected_matching_records"] != expected:
                        raise ValueError("Incorrect expected-record hypothesis")
                    passed = (case["target_status"] == 200 and score["row_count"] == 4
                              and score["matching_records"] == expected
                              and score["exact_match"] == (expected == 4))
                else:
                    if case["kind"] != "diagnostic":
                        raise ValueError("Incorrect case kind")
                    if name.startswith("route_"):
                        hits = 2 if name == "route_fetch_then_continue" else 1
                        if case["expected_server_hits"] != hits or case["navigations"] != 1:
                            raise ValueError("Incorrect route diagnostic hypothesis")
                        passed = case["target_status"] == 200 and case["server_hits"] == hits
                    elif name == "cookie_inserted_before_first_navigation":
                        passed = (case["page_url"] == "about:blank"
                                  and case["fixture_navigation_delta"] == 0
                                  and "demo_session" in case["cookie_names"])
                    elif name == "httponly_visible_to_context_not_document":
                        passed = ("demo_session" in case["context_cookie_names"]
                                  and case["context_cookie_http_only"].get("demo_session") is True
                                  and "demo_session=" not in case["document_cookie"])
                    else:
                        passed = (case["other_session"] == "guest-v1"
                                  and case["seeded_session"] == "member-v1")
                if type(case.get("check_passed")) is not bool or case["check_passed"] != passed:
                    raise ValueError("Stored check flag disagrees with captured observation")


def summarize_captures(captures):
    validate_captures(captures)
    all_cases = [dict(browser=data['browser'], round=run['round'], **case)
                 for data in captures for run in data['runs'] for case in run['cases']]
    rows = [case for case in all_cases if case['kind'] == 'extraction']
    diagnostics = [case for case in all_cases if case['kind'] == 'diagnostic']
    result = {
        'primary_browsers': {data['browser']: data['environment'] for data in captures},
        'primary_checks': len(all_cases),
        'passed_checks': sum(c['check_passed'] for c in all_cases),
        'primary_extraction_observations': len(rows),
        'primary_diagnostic_observations': len(diagnostics),
        'records_per_extraction': 4,
        'record_opportunities': len(rows) * 4,
        'matching_record_observations': sum(c['matching_records'] for c in rows),
        'exact_extraction_observations': sum(c['exact_match'] for c in rows),
        'http_200_extraction_observations': sum(c['target_status'] == 200 for c in rows),
        'four_row_extraction_observations': sum(c['row_count'] == 4 for c in rows),
        'case_outcomes': {}, 'diagnostic_outcomes': {},
        'limitations': [
            'Deterministic self-authored fixture, not a production reliability estimate.',
            'Three repeats per browser share one host and fixture design.',
            'Region in localStorage is an explicit fixture design, not a universal website rule.',
            'API state handoff still needs this application-specific region query parameter.',
            'HTTP loopback does not test Secure delivery or cross-site SameSite behavior.',
            'No real login, MFA, SSO, IP-bound sessions, sessionStorage or IndexedDB test.',
            'Quickstart and exploratory captures are excluded from primary denominators.',
        ],
    }
    for name in dict.fromkeys(case['case'] for case in rows):
        entries = [case for case in rows if case['case'] == name]
        result['case_outcomes'][name] = {
            'observations': len(entries),
            'statuses': sorted(set(c['target_status'] for c in entries)),
            'row_counts': sorted(set(c['row_count'] for c in entries)),
            'matching_record_counts': sorted(set(c['matching_records'] for c in entries)),
            'audiences': sorted(set(c['audience'] for c in entries)),
            'regions': sorted(set(c['region'] for c in entries)),
            'all_checks_passed': all(c['check_passed'] for c in entries),
        }
    for name in dict.fromkeys(case['case'] for case in diagnostics):
        entries = [case for case in diagnostics if case['case'] == name]
        result['diagnostic_outcomes'][name] = {
            'observations': len(entries),
            'all_checks_passed': all(c['check_passed'] for c in entries),
        }
        if name.startswith('route_'):
            result['diagnostic_outcomes'][name]['server_hit_counts'] = sorted(set(c['server_hits'] for c in entries))
            result['diagnostic_outcomes'][name]['total_server_hits'] = sum(c['server_hits'] for c in entries)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=Path, default=Path(__file__).resolve().parent / 'expected_output')
    parser.add_argument('--browsers', nargs='+', choices=['chromium', 'firefox'], default=['chromium', 'firefox'])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    captures = [json.loads((args.input_dir / f'{name}.json').read_text()) for name in args.browsers]
    result = summarize_captures(captures)
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end='')
