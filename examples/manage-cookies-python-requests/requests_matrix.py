"""Three-round Requests extraction matrix against one self-authored local origin."""
import argparse
import copy
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile
import time

from requests import Request, Session
from requests.adapters import HTTPAdapter
from requests.cookies import CookieConflictError, cookiejar_from_dict

from catalog_fixture import CatalogFixture
from cookie_state import load_jar, save_private_jar
from oracle import score

CASE_MATCHES = {
    "independent_requests": 0,
    "persistent_session": 4,
    "per_call_cookies": 4,
    "per_call_followup": 0,
    "final_response_cookies_only": 0,
    "lwp_full_restore": 4,
    "get_dict_roundtrip": 0,
    "request_prepare": 0,
    "session_prepare_request": 4,
    "expired_session": 0,
    "clear_session": 0,
    "server_revocation": 0,
}


def new_session():
    session = Session()
    # This fixture must never use ambient proxy configuration or .netrc credentials.
    session.trust_env = False
    return session


def environment():
    return {
        "os": f"macOS {platform.mac_ver()[0]}" if platform.system() == "Darwin" else f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "dependencies": {name: importlib.metadata.version(name) for name in (
            "requests", "urllib3", "certifi", "charset-normalizer", "idna")},
    }


def observe(case, response, jar):
    response.raise_for_status()
    payload = response.json()
    result = {
        "case": case, "status": response.status_code,
        "row_count": len(payload["records"]), "records": payload["records"],
        **score(payload["records"]), "wire": payload["wire"],
        "stored_cookie_count": len(jar),
    }
    expected = CASE_MATCHES[case]
    result["expected_matching_records"] = expected
    result["check_passed"] = (
        response.status_code == 200 and result["row_count"] == 4
        and result["matching_records"] == expected
        and result["exact_match"] == (expected == 4)
    )
    return result


def run_round(round_number):
    observations, diagnostics = [], []
    with CatalogFixture() as fixture:
        catalog = fixture.base_url + "/catalog/eu/products"
        login = fixture.base_url + "/login"
        # A new short-lived Session for each independent request prevents state reuse.
        with new_session() as first:
            first.get(login, timeout=5).raise_for_status()
        with new_session() as second:
            observations.append(observe("independent_requests", second.get(catalog, timeout=5), second.cookies))
        with new_session() as seeded:
            final = seeded.get(login, timeout=5)
            final.raise_for_status()
            diagnostics.append({
                "case": "redirect_cookie_accumulation", "history_responses": len(final.history),
                "redirect_cookie_count": len(final.history[0].cookies),
                "final_response_cookie_count": len(final.cookies),
                "session_cookie_count": len(seeded.cookies),
                "check_passed": len(final.history) == 1 and len(final.history[0].cookies) == 1
                and len(final.cookies) == 2 and len(seeded.cookies) == 3,
            })
            observations.append(observe("persistent_session", seeded.get(catalog, timeout=5), seeded.cookies))
            source_jar = copy.deepcopy(seeded.cookies)
            final_jar = copy.deepcopy(final.cookies)
            scoped_us = seeded.get(fixture.base_url + "/catalog/us/products", timeout=5).json()
            diagnostics.append({
                "case": "second_catalog_scope", "records": scoped_us["records"], "wire": scoped_us["wire"],
                "check_passed": scoped_us["records"] == [
                    {"sku": "BK-101", "currency": "USD", "price_minor": 1699},
                    {"sku": "PN-202", "currency": "USD", "price_minor": 899},
                    {"sku": "NB-303", "currency": "USD", "price_minor": 2399},
                    {"sku": "BG-404", "currency": "USD", "price_minor": 4699},
                ] and scoped_us["wire"]["region_cookie_count"] == 1,
            })
            conflict = None
            try:
                seeded.cookies.get("region")
            except CookieConflictError as error:
                conflict = type(error).__name__
            explicit_lookup = seeded.cookies.get("region", domain="127.0.0.1", path="/catalog/eu") == "EUR"
            seeded.cookies.clear(domain="127.0.0.1", path="/catalog/eu", name="region")
            diagnostics.append({
                "case": "domain_path_lookup_and_clear", "ambiguous_lookup_exception": conflict,
                "explicit_eu_lookup_correct": explicit_lookup,
                "eu_cookie_removed": seeded.cookies.get("region", domain="127.0.0.1", path="/catalog/eu") is None,
                "us_cookie_retained": seeded.cookies.get("region", domain="127.0.0.1", path="/catalog/us") == "USD",
                "check_passed": conflict == "CookieConflictError" and explicit_lookup and len(seeded.cookies) == 2
                and seeded.cookies.get("region", domain="127.0.0.1", path="/catalog/us") == "USD",
            })
        with new_session() as session:
            observations.append(observe("per_call_cookies", session.get(catalog, cookies=source_jar, timeout=5), session.cookies))
            observations.append(observe("per_call_followup", session.get(catalog, timeout=5), session.cookies))
        with new_session() as session:
            session.cookies.update(final_jar)
            observations.append(observe("final_response_cookies_only", session.get(catalog, timeout=5), session.cookies))
        with tempfile.TemporaryDirectory(prefix="requests-cookie-demo-") as tmp, new_session() as session:
            snapshot = Path(tmp) / "private.lwp"
            save_private_jar(source_jar, snapshot, include_session=True)
            session.cookies = load_jar(snapshot, include_session=True)
            observations.append(observe("lwp_full_restore", session.get(catalog, timeout=5), session.cookies))
        with new_session() as session:
            # Deliberately lossy control: two region cookies collapse to one entry.
            session.cookies = cookiejar_from_dict(source_jar.get_dict())
            observations.append(observe("get_dict_roundtrip", session.get(catalog, timeout=5), session.cookies))
        with new_session() as session:
            session.cookies.update(source_jar)
            prepared = Request("GET", catalog).prepare()
            observations.append(observe("request_prepare", session.send(prepared, timeout=5), session.cookies))
            prepared = session.prepare_request(Request("GET", catalog))
            observations.append(observe("session_prepare_request", session.send(prepared, timeout=5), session.cookies))
        with new_session() as session:
            session.cookies.update(copy.deepcopy(source_jar))
            for cookie in session.cookies:
                if cookie.name == "sid":
                    cookie.expires = int(time.time()) - 60
            observations.append(observe("expired_session", session.get(catalog, timeout=5), session.cookies))
        with new_session() as session:
            session.cookies.update(source_jar)
            session.cookies.clear(domain="127.0.0.1", path="/", name="sid")
            observations.append(observe("clear_session", session.get(catalog, timeout=5), session.cookies))
        with new_session() as session:
            session.cookies.update(source_jar)
            fixture.revoke()
            observations.append(observe("server_revocation", session.get(catalog, timeout=5), session.cookies))
        with new_session() as session:
            session.mount("https://", HTTPAdapter())
            response = session.get(catalog, timeout=5)
            diagnostics.append({
                "case": "https_mount_still_allows_http", "http_adapter_present": "http://" in session.adapters,
                "http_status": response.status_code,
                "check_passed": "http://" in session.adapters and response.status_code == 200,
            })
        for keyword, value in (("httponly", True), ("samesite", "Strict")):
            with new_session() as session:
                exception = None
                try:
                    session.cookies.set("demo", "synthetic", **{keyword: value})
                except TypeError as error:
                    exception = type(error).__name__
                diagnostics.append({"case": f"unsupported_{keyword}_keyword", "exception": exception,
                                    "check_passed": exception == "TypeError"})
    return {"round": round_number, "observations": observations, "diagnostics": diagnostics}


def run_matrix(rounds=3):
    results = [run_round(n) for n in range(1, rounds + 1)]
    all_checks = [item["check_passed"] for result in results
                  for group in ("observations", "diagnostics") for item in result[group]]
    return {
        "tested_at": datetime.now(timezone.utc).isoformat(), "environment": environment(),
        "fixture": "self-authored loopback HTTP catalog", "rounds": results,
        "extraction_observations": sum(len(r["observations"]) for r in results),
        "diagnostic_observations": sum(len(r["diagnostics"]) for r in results),
        "checks_passed": sum(all_checks), "checks_total": len(all_checks),
        "all_checks_passed": all(all_checks), "external_requests": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_matrix(args.rounds)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(json.dumps({key: result[key] for key in (
        "tested_at", "extraction_observations", "diagnostic_observations",
        "checks_passed", "checks_total", "all_checks_passed", "external_requests")}, indent=2))
    if not result["all_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
