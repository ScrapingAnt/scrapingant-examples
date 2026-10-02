"""Read-only correlation of ONE consumed attempt. Offline preview is the default.

No start, retry, deletion, account mutation, run export or raw-response persistence.
Identity and IDs remain in memory. Only a fixed sanitized schema is emitted.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from calibration import API, PUBLIC_ACTOR_ID, REVIEWED_GUARD, build_plan

BUILD = "3.0.25"
START = "2026-10-02T14:10:40Z"
END = "2026-10-02T14:11:00Z"
LIMIT = 5
RESPONSE_LIMIT = 131072
STAGES = ("identity", "runs", "run", "input")
OUTPUT = "diagnosis-receipt.json"
# Read-only authorization consumed by workflow37021960829; no further dispatch.
DIAGNOSTIC_OPEN = False


class ReadFailure(Exception):
    def __init__(self, status, category):
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        allowed = {"authentication_rejected", "forbidden", "not_found", "request_rejected",
                   "provider_error", "transport_error", "invalid_json", "response_too_large",
                   "unexpected_status", "route_rejected", "wall_deadline"}
        self.category = category if category in allowed else "transport_error"
        super().__init__(self.category)


class InvalidMetadata(Exception):
    pass


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9]{1,64}", value) is not None


def moment(value):
    if not isinstance(value, str): raise InvalidMetadata
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset().total_seconds() != 0: raise ValueError
        return result
    except (ValueError, OverflowError): raise InvalidMetadata from None


def identity_id(response):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict): raise InvalidMetadata
    value = response["data"].get("id")
    if not identifier(value): raise InvalidMetadata
    return value


def actor_build_time_match(run):
    if not isinstance(run, dict) or not identifier(run.get("id")): raise InvalidMetadata
    started = moment(run.get("startedAt"))
    return (run.get("actId") == PUBLIC_ACTOR_ID and run.get("buildNumber") == BUILD
            and moment(START) <= started <= moment(END))


def candidates(response):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict): raise InvalidMetadata
    data = response["data"]
    for field in ("offset", "limit", "count", "total"):
        if type(data.get(field)) is not int or data[field] < 0: raise InvalidMetadata
    items = data.get("items")
    if (data["offset"] != 0 or data["limit"] != LIMIT or not isinstance(items, list)
            or len(items) > LIMIT or data["count"] != len(items) or data["total"] < len(items)):
        raise InvalidMetadata
    if data["total"] != len(items): return None
    return [run for run in items if actor_build_time_match(run)]


def validate_candidate(response, candidate, user_id):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict): raise InvalidMetadata
    run = response["data"]
    if (not actor_build_time_match(run) or run["id"] != candidate["id"]
            or run.get("startedAt") != candidate.get("startedAt")
            or run.get("userId") != user_id or not identifier(run.get("defaultKeyValueStoreId"))):
        raise InvalidMetadata
    if (candidate.get("defaultKeyValueStoreId") is not None
            and run["defaultKeyValueStoreId"] != candidate["defaultKeyValueStoreId"]): raise InvalidMetadata
    options = run.get("options")
    if not isinstance(options, dict): raise InvalidMetadata
    if (options.get("build") != BUILD or type(options.get("memoryMbytes")) is not int
            or options["memoryMbytes"] != 1024 or type(options.get("timeoutSecs")) is not int
            or options["timeoutSecs"] != 120
            or ("restartOnError" in options and options["restartOnError"] is not False)):
        raise InvalidMetadata
    cap = options.get("maxTotalChargeUsd")
    try:
        if isinstance(cap, bool) or cap is None or Decimal(str(cap)) != Decimal("0.10"): raise InvalidMetadata
    except (InvalidOperation, ValueError): raise InvalidMetadata from None
    return run


def diagnose(transport):
    result = {"evidence_type": "read_only_diagnostic_not_a_bill_or_runtime_benchmark",
              "prior_workflow": "37018036109", "maximum_requests": 4, "requests_attempted": 0,
              "reads": [], "authenticated_identity_established": False,
              "console_token_identity_match": None, "run_token_identity_match": None,
              "actor_build_time_candidate": None, "input_match": None,
              "exact_attempt_match": None, "outcome": "unknown"}

    def read(stage, **kwargs):
        result["requests_attempted"] += 1
        try: response = transport.get(stage, **kwargs)
        except ReadFailure as failure:
            result["reads"].append({"stage": stage, "http_status": failure.status, "category": failure.category})
            result["outcome"] = stage + "_read_failed"
            raise
        result["reads"].append({"stage": stage, "http_status": 200, "category": "ok"})
        return response

    try:
        try: user_id = identity_id(read("identity"))
        except InvalidMetadata:
            result["outcome"] = "identity_invalid"; return result
        result["authenticated_identity_established"] = True
        try: matches = candidates(read("runs"))
        except InvalidMetadata:
            result["outcome"] = "listing_invalid"; return result
        if matches is None:
            result["outcome"] = "listing_incomplete"; return result
        if not matches:
            result.update(actor_build_time_candidate=False, exact_attempt_match=False,
                          outcome="no_matching_run_in_token_scope"); return result
        if len(matches) != 1:
            result["outcome"] = "multiple_candidates"; return result
        result["actor_build_time_candidate"] = True
        candidate = matches[0]
        if candidate.get("userId") is not None and candidate["userId"] != user_id:
            result.update(run_token_identity_match=False, outcome="candidate_owner_mismatch"); return result
        response = read("run", run_id=candidate["id"])
        if isinstance(response, dict) and isinstance(response.get("data"), dict):
            result["run_token_identity_match"] = response["data"].get("userId") == user_id
        try: run = validate_candidate(response, candidate, user_id)
        except InvalidMetadata:
            result["outcome"] = "candidate_invalid"; return result
        actual_input = read("input", kv_id=run["defaultKeyValueStoreId"])
        # JSON equality preserves types: Python would otherwise equate True with 1.
        result["input_match"] = (json.dumps(actual_input, sort_keys=True, allow_nan=False)
                                 == json.dumps(build_plan(BUILD)["input"], sort_keys=True, allow_nan=False))
        result["exact_attempt_match"] = result["input_match"]
        result["outcome"] = "exact_attempt_match" if result["input_match"] else "input_mismatch"
    except ReadFailure:
        pass
    except Exception:
        # Never expose exception strings, traceback locals or arbitrary provider structures.
        result["outcome"] = "local_validation_failure"
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


class ReadOnlyTransport:
    """At most four fixed GETs, once each, with ephemeral reference binding."""
    def __init__(self, token, *, opener=None):
        if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c)<33 or ord(c)>126 for c in token):
            raise ReadFailure(None, "authentication_rejected")
        self._token = token
        self._opener = build_opener(NoRedirect()) if opener is None else opener
        self._calls = 0
        self._deadline = monotonic() + 50
        self._user = self._candidate = self._kv = None

    def get(self, stage, *, run_id=None, kv_id=None):
        if self._calls >= 4 or stage != STAGES[self._calls]: raise ReadFailure(None, "route_rejected")
        if stage == "identity":
            if run_id is not None or kv_id is not None: raise ReadFailure(None, "route_rejected")
            path = "/users/me"
        elif stage == "runs":
            if self._user is None or run_id is not None or kv_id is not None: raise ReadFailure(None, "route_rejected")
            query = urlencode({"limit": LIMIT, "offset": 0, "desc": "true", "startedAfter": START, "startedBefore": END})
            path = "/actors/apify~web-scraper/runs?" + query
        elif stage == "run":
            if self._candidate is None or run_id != self._candidate["id"] or kv_id is not None: raise ReadFailure(None, "route_rejected")
            path = "/actor-runs/" + run_id
        else:
            if self._kv is None or kv_id != self._kv or run_id is not None: raise ReadFailure(None, "route_rejected")
            path = "/key-value-stores/" + kv_id + "/records/INPUT"
        remaining = self._deadline - monotonic()
        if remaining <= 0: raise ReadFailure(None, "wall_deadline")
        self._calls += 1
        request = Request(API + path, method="GET", headers={"Authorization": "Bearer " + self._token,
                          "Accept": "application/json", "Accept-Encoding": "identity"})
        try:
            with self._opener.open(request, timeout=min(10, remaining)) as response:
                status = response.status
                if status != 200: raise ReadFailure(status, "unexpected_status")
                raw = bytearray()
                read_chunk = getattr(response, "read1", response.read)
                while True:
                    if monotonic() >= self._deadline: raise ReadFailure(status, "wall_deadline")
                    chunk = read_chunk(min(8192, RESPONSE_LIMIT + 1 - len(raw)))
                    if not chunk: break
                    raw.extend(chunk)
                    if len(raw) > RESPONSE_LIMIT: raise ReadFailure(status, "response_too_large")
                try:
                    parsed = json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                except (ValueError, UnicodeError): raise ReadFailure(status, "invalid_json") from None
        except HTTPError as failure:
            # Do not read an error body: it may contain identity, input, signed URLs or secrets.
            status = failure.code
            failure.close()
            category = {401: "authentication_rejected", 403: "forbidden", 404: "not_found"}.get(status)
            if category is None: category = "provider_error" if status >= 500 else "request_rejected"
            raise ReadFailure(status, category) from None
        except ReadFailure: raise
        except (URLError, OSError, TimeoutError): raise ReadFailure(None, "transport_error") from None
        try:
            if stage == "identity": self._user = identity_id(parsed)
            elif stage == "runs":
                matches = candidates(parsed)
                if (matches is not None and len(matches) == 1
                        and matches[0].get("userId") in (None, self._user)): self._candidate = matches[0]
            elif stage == "run": self._kv = validate_candidate(parsed, self._candidate, self._user)["defaultKeyValueStoreId"]
        except InvalidMetadata: pass
        return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-read-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_read_only:
        print(json.dumps({"evidence_type":"offline_diagnostic_plan", "provider_requests":0,
                          "maximum_requests":4, "methods":["GET"], "start_capability":False,
                          "delete_capability":False, "scope":"consumed workflow37018036109 only"}, sort_keys=True))
        return 0
    if REVIEWED_GUARD.get("ready") is not False:
        print(json.dumps({"outcome":"execution_guard_must_be_closed", "requests_attempted":0}, sort_keys=True))
        return 1
    if DIAGNOSTIC_OPEN is not True:
        print(json.dumps({"outcome":"diagnostic_authorization_consumed", "requests_attempted":0}, sort_keys=True))
        return 1
    # Only this dedicated, separately approved workflow supplies the existing secret.
    try: transport = ReadOnlyTransport(os.environ.get("APIFY_TOKEN"))
    except ReadFailure:
        print(json.dumps({"outcome":"token_missing_or_invalid", "requests_attempted":0}, sort_keys=True))
        return 1
    result = diagnose(transport)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    Path(OUTPUT).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__": raise SystemExit(main())
