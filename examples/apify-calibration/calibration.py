"""Offline plan by default. One explicitly authorized calibration uses a reviewed guard."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import json
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
from time import monotonic, sleep
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ACTOR = "apify/web-scraper"
API = "https://api.apify.com/v2"
FIXTURES = {
    "complete": "https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/complete.html",
    "changed-layout": "https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/changed-layout.html",
}
FIELDS = ("fixture", "sku", "name", "price_minor", "currency")
POLL_LIMIT = 3
RESPONSE_LIMIT = 131072
STORE_FIELDS = {"dataset": ("defaultDatasetId", "datasets"),
                "kv": ("defaultKeyValueStoreId", "key-value-stores"),
                "queue": ("defaultRequestQueueId", "request-queues")}
TERMINAL = ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED")
RUN_STATUSES = ("READY", "RUNNING", "TIMING-OUT", "ABORTING") + TERMINAL
DIAGNOSTIC_CATEGORIES = ("http_error", "connection_error", "unexpected_http_status", "response_too_large",
                         "invalid_json", "invalid_response", "invalid_run_status", "build_mismatch",
                         "options_mismatch", "invalid_identifier", "scope_mismatch", "deadline_exceeded",
                         "latest_run_active", "policy_error", "transport_error")
DIAGNOSTIC_STAGES = ("request", "response_status", "response_read", "json_decode", "run_validation",
                     "build_validation", "options_validation", "identifier_validation", "scope_validation", "local_policy")
MAX_CLEANUP_HOURS = Decimal("0.25")
CREATION_TOLERANCE_SECONDS = 5
MAX_WALL_SECONDS = 480
MINIMUM_START_SECONDS = 360
CLEANUP_RESERVE_SECONDS = 100
TERMINAL_METER_WAIT_SECONDS = 10
TIMEOUTS = {"start": 30, "poll": 65, "export": 10, "metadata": 10, "delete": 10, "absence": 10}
# Public build, pinned source/dependencies and ordinary-operation reserve reviewed 2026-10-02.
PUBLIC_BUILD_CANDIDATE = {"number": "3.0.25", "git_commit_id": "21de8bf52ca7a587e680635a4198abfada472a8e"}
PUBLIC_ACTOR_ID = "moJRLRc85AitArpNN"  # Public Actor identity verified from its public build metadata.
USAGE_FIELDS = ("ACTOR_COMPUTE_UNITS", "DATASET_READS", "DATASET_WRITES", "KEY_VALUE_STORE_READS",
                "KEY_VALUE_STORE_WRITES", "KEY_VALUE_STORE_LISTS", "REQUEST_QUEUE_READS",
                "REQUEST_QUEUE_WRITES", "DATA_TRANSFER_INTERNAL_GBYTES", "DATA_TRANSFER_EXTERNAL_GBYTES",
                "PROXY_RESIDENTIAL_TRANSFER_GBYTES", "PROXY_SERPS")
STAT_FIELDS = ("inputBodyLen", "migrationCount", "rebootCount", "restartCount", "resurrectCount",
               "memAvgBytes", "memMaxBytes", "memCurrentBytes", "cpuAvgUsage", "cpuMaxUsage",
               "cpuCurrentUsage", "netRxBytes", "netTxBytes", "durationMillis", "runTimeSecs",
               "metamorph", "computeUnits")
STORAGE_STAT_FIELDS = ("storageBytes", "readCount", "writeCount", "deleteCount", "listCount")

# This is source-controlled policy, not a CLI flag, secret, or environment override.
# Enabling it requires a reviewed all-meter bound, pinned build and retention/cleanup policy.
REVIEWED_GUARD = {
    "ready": False,
    "public_build": "3.0.25",
    "review_reference": "2026-10-02 reviewed dispatch37018036109 consumed; source21de8bf; runner5c79675",
    # Conservative ordinary-operation planning reserve, not a strict metadata-byte guarantee.
    "all_in_upper_bound_usd": "0.11",
    "bound_basis": "ordinary_operation_planning_reserve; no arbitrary-provider-failure guarantee",
    "retention_policy": {
        "mode": "cleanup",
        "upper_bound_hours": "0.25",
        "cleanup_approved": True,
        "review_reference": "2026-10-02 explicit owner yes; exact new run-owned default stores only",
    },
}
BLOCKERS = (
    "The single-run authorization was consumed by manual workflow37018036109; do not dispatch or rerun.",
    "A new execution requires separately authorized scope and a fresh reviewed guard change.",
    "The ordinary-operation reserve is not a strict metadata-byte or arbitrary-failure guarantee.",
)

# One small result per fixture. No page-function network requests, enqueueing or storage writes.
PAGE_FUNCTION = """async function pageFunction(context) {
    const allowed = {
        'https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/complete.html': 'complete',
        'https://scrapingant.github.io/scrapingant-examples/fixtures/mcp-catalog/changed-layout.html': 'changed-layout'
    };
    const fixture = allowed[context.request.url];
    if (!fixture) throw new Error('Fixture scope mismatch');
    const first = document.querySelector('p');
    const value = first ? first.textContent : '';
    if (value.length > 128) throw new Error('Fixture text exceeds contract');
    const match = /^AA101 \\| Desk Lamp \\| Price: 34\\.99 USD \\(3499 minor units\\)\\.$/.exec(value.trim());
    if (!match) throw new Error('Fixture extraction did not validate');
    return { fixture, sku: 'AA101', name: 'Desk Lamp', price_minor: 3499, currency: 'USD' };
}"""


class PolicyError(Exception):
    """A safe, local policy diagnostic, never a provider response."""


class CalibrationFailure(PolicyError):
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


class MissingStorage:
    """Typed transport evidence of HTTP 404, never inferred from JSON error text."""


class WallDeadline(PolicyError):
    """A local wall budget was exhausted; no request was made."""


def sanitized_diagnostic(data):
    """Only fixed enums and a numeric HTTP status; never exception text or arbitrary fields."""
    data = data if isinstance(data, dict) else {}
    status = data.get("http_status")
    category, stage, run_status = (data.get(key) for key in ("category", "stage", "run_status"))
    return {"http_status": status if type(status) is int and 100 <= status <= 599 else None,
            "category": category if type(category) is str and category in DIAGNOSTIC_CATEGORIES else "transport_error",
            "stage": stage if type(stage) is str and stage in DIAGNOSTIC_STAGES else "request",
            "run_status": run_status if type(run_status) is str and run_status in RUN_STATUSES else None}


class DiagnosticError(PolicyError):
    def __init__(self, category, stage, http_status=None, run_status=None):
        super().__init__("Calibration boundary failed; only sanitized diagnostics are retained.")
        self.diagnostic = sanitized_diagnostic({"category": category, "stage": stage,
                                               "http_status": http_status, "run_status": run_status})


def failure_diagnostic(error, operation, response_context=None):
    if isinstance(error, DiagnosticError):
        data = sanitized_diagnostic(error.diagnostic)
        if data["stage"].endswith("_validation") and data["http_status"] is None:
            context = sanitized_diagnostic(response_context)
            data["http_status"] = context["http_status"]
            if data["run_status"] is None: data["run_status"] = context["run_status"]
    else:
        category = "deadline_exceeded" if isinstance(error, WallDeadline) else (
            "policy_error" if isinstance(error, PolicyError) else "transport_error")
        data = sanitized_diagnostic({"category": category,
                                     "stage": "local_policy" if isinstance(error, PolicyError) else "request"})
    return {"operation": operation if type(operation) is str and operation in TIMEOUTS else None, **data}


def build_plan(build=None):
    if build is not None:
        validate_build(build)
    with localcontext() as context:
        context.prec = 28
        nominal_compute = Decimal("120") * Decimal("0.20") / Decimal("3600")
    eligible = (REVIEWED_GUARD["ready"] is True and build == REVIEWED_GUARD["public_build"])
    policy = REVIEWED_GUARD.get("retention_policy") or {}
    return {
        "schema_version": 1,
        "evidence_type": "unexecuted_plan",
        "provider_calls_performed": 0,
        "actor": ACTOR,
        "source_checked_on": "2026-10-02",
        "public_build_candidate": dict(PUBLIC_BUILD_CANDIDATE),
        "maximum_provider_calls": 14,
        "maximum_runner_wall_seconds": MAX_WALL_SECONDS,
        "minimum_remaining_start_seconds": MINIMUM_START_SECONDS,
        "request_timeouts_seconds": dict(TIMEOUTS),
        "cleanup_reserved_seconds": CLEANUP_RESERVE_SECONDS,
        "metrics_collection_enabled": eligible,
        "cleanup_preparation": {"approval": policy.get("cleanup_approved") is True, "maximum_lifetime_hours": "0.25",
                                "scope": "Only the initial run's three verified new unnamed default stores"},
        "fixture_body_bytes": {"complete": 290, "changed-layout": 422},
        "options": {"build": build, "memory": "1024", "timeout": "120",
                    "maxTotalChargeUsd": "0.10", "restartOnError": "false"},
        "input": {
            "startUrls": [{"url": url} for url in FIXTURES.values()],
            "runMode": "PRODUCTION", "linkSelector": "", "globs": [], "pseudoUrls": [],
            "maxPagesPerCrawl": 2, "maxResultsPerCrawl": 2, "maxConcurrency": 1,
            "maxRequestRetries": 0, "proxyConfiguration": {"useApifyProxy": False},
            "downloadMedia": False, "downloadCss": False, "injectJQuery": False,
            "maxScrollHeightPixels": 0, "closeCookieModals": False,
            "debugLog": False, "browserLog": False, "headless": True,
            "useChrome": False, "initialCookies": [], "respectRobotsTxtFile": False,
            "ignoreSslErrors": False, "ignoreCorsAndCsp": False,
            "waitUntil": ["domcontentloaded"], "pageLoadTimeoutSecs": 20,
            "pageFunctionTimeoutSecs": 10, "preNavigationHooks": "[]",
            "postNavigationHooks": "[]", "pageFunction": PAGE_FUNCTION,
        },
        "owner_budget_usd": "1.00",
        "proposed_run_cap_usd": "0.10",
        "all_in_upper_bound_usd": REVIEWED_GUARD["all_in_upper_bound_usd"] if eligible else None,
        "cost_bound_basis": REVIEWED_GUARD.get("bound_basis") if eligible else None,
        "nominal_compute_only_usd": str(nominal_compute),
        "nominal_compute_is_all_in_bound": False,
        "retention_upper_bound_hours": policy.get("upper_bound_hours") if eligible else None,
        "readiness": {"ready": eligible, "blockers": [] if eligible else list(BLOCKERS)},
        "authentication_preview": "Authorization: Bearer [REDACTED]; environment only after readiness",
        "acceptance_definition": "One validated AA101 record per owned fixture; fixture plus SKU is the unique key.",
        "limitations": [
            "This offline plan is not measured evidence; observations require the separately verified run receipt.",
            "A run cap does not bound storage retention or later export/operation charges.",
            "1024MB times 120 seconds is only a nominal compute calculation; overhead is unresolved.",
            "This is an unexecuted plan; eligibility does not report a run or cleanup. One authorized dispatch only; do not rerun.",
        ],
    }


def validate_build(build):
    if not isinstance(build, str) or not re.fullmatch(
            r"(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]?)\.[1-9][0-9]{0,4}", build):
        raise PolicyError("An immutable public build number is required; tags and arbitrary URLs are rejected.")


def require_readiness(build):
    validate_build(build)
    if REVIEWED_GUARD["ready"] is not True:
        raise PolicyError("Live execution blocked: the reviewed all-in USD 1 cost guard is not justified.")
    if (REVIEWED_GUARD["public_build"] != build or
            not REVIEWED_GUARD["review_reference"]):
        raise PolicyError("Live execution blocked: reviewed build evidence is incomplete.")
    policy = REVIEWED_GUARD["retention_policy"]
    if (not isinstance(policy, dict) or policy.get("mode") not in ("finite_retention", "cleanup") or
            not policy.get("review_reference")):
        raise PolicyError("Live execution blocked: reviewed retention/cleanup policy is incomplete.")
    if quantity(policy.get("upper_bound_hours")) <= 0:
        raise PolicyError("Live execution blocked: retention/cleanup duration must have a known positive bound.")
    if policy["mode"] == "cleanup" and policy.get("cleanup_approved") is not True:
        raise PolicyError("Live execution blocked: deletion in the reviewed cleanup policy requires owner approval.")
    bound = quantity(REVIEWED_GUARD["all_in_upper_bound_usd"])
    if not Decimal("0.10") <= bound <= Decimal("1.00"):
        raise PolicyError("Live execution blocked: reviewed all-in bound is outside the approved budget.")


def execute_live(build, *, opt_in=False, environ=None, transport=None, persist=None, emit=None):
    if opt_in is not True:
        raise PolicyError("Live execution requires explicit opt-in.")
    plan = build_plan(build)
    require_readiness(build)  # Must precede even reading the token environment variable.
    require_cleanup_policy()  # This runner's live path requires the reviewed short cleanup policy.
    environment = os.environ if environ is None else environ
    began = monotonic()
    deadline = began + MAX_WALL_SECONDS
    supplied_deadline = environment.get("APIFY_CALIBRATION_WALL_DEADLINE")
    if supplied_deadline is not None:
        try:
            supplied = float(supplied_deadline)
            if not 0 < supplied < float("inf"): raise ValueError
            deadline = min(deadline, supplied)
        except (ValueError, TypeError):
            raise PolicyError("The job wall deadline is invalid.") from None
    if deadline - monotonic() < MINIMUM_START_SECONDS:
        raise PolicyError("Insufficient job time remains for a run and reserved cleanup; token not read.")
    token = environment.get("APIFY_TOKEN")
    if not isinstance(token, str) or not token or len(token) > 4096 or any(
            ord(character) < 33 or ord(character) > 126 for character in token):
        raise PolicyError("The narrowly supplied token environment variable is missing or invalid.")
    return orchestrate(plan, token, HttpTransport(build, deadline) if transport is None else transport,
                       wall_deadline=deadline, persist=persist_receipt_atomic if persist is None else persist,
                       emit=emit_receipt if emit is None else emit)


def orchestrate(plan, token, transport, *, wall_deadline=None, persist=None, emit=None):
    """One run with bounded reads. A real transport independently enforces readiness."""
    try:
        build = plan["options"]["build"]
        validate_build(build)
        if plan != build_plan(build):
            raise PolicyError("The plan differs from the fixed owned-fixture scope.")
    except (KeyError, TypeError):
        raise PolicyError("The plan is invalid.") from None
    result = {"evidence_type": "transport_receipt_not_an_invoice", "status": "UNKNOWN",
              "wall_budget_exhausted": False, "failure_diagnostic": None,
              "extraction_outcome": "not_attempted", "pre_cleanup_capture": None,
              "pre_cleanup_capture_sha256": None, "pre_cleanup_evidence_verified": False,
              "returned_output_count": None, "accepted_output_count": 0, "records": [],
              "all_in_cost_reconciled": False,
              "meter_refresh": {"state": "preliminary_not_enabled", "capture_wait_seconds": 0,
                                "preliminary": True, "invoice_final": False, "diagnostic": None},
              "receipts": {"run": None, "usage": None, "usage_usd": None, "storage": {}},
              "cleanup": {"absence_confirmed": False, "owner_attention_required": True,
                          "state": "not_attempted", "stores": {}},
              "request_counts": {key: 0 for key in ("start", "poll", "export", "metadata", "delete", "absence")},
              "limitations": ["Run receipts exclude later export, metadata, deletion and absence-read charges.",
                              "Residual storage or ambiguous network outcomes leave total cost unknown; do not rerun."]}
    began = monotonic()
    deadline = began + MAX_WALL_SECONDS
    if wall_deadline is not None: deadline = min(deadline, wall_deadline)

    current_operation, response_context = "start", None

    def request(kind, method, url, payload=None):
        nonlocal current_operation, response_context
        current_operation, response_context = kind, None
        if kind in ("metadata", "delete", "absence"):
            remaining_cleanup = 9 - sum(result["request_counts"][key] for key in ("metadata", "delete", "absence"))
            needed = remaining_cleanup * 10 + 10
        else:
            needed = TIMEOUTS[kind] + (CLEANUP_RESERVE_SECONDS if cleanup_requested else 0)
            if kind == "start" and cleanup_requested: needed = MINIMUM_START_SECONDS
        if monotonic() + needed > deadline:
            result["wall_budget_exhausted"] = True
            raise WallDeadline("Wall deadline reached; request skipped to preserve cleanup time.")
        result["request_counts"][kind] += 1
        reply = safe_request(transport, method, url, payload, token)
        response_context = getattr(transport, "last_response_diagnostic", None)
        return reply

    cleanup_requested = isinstance(REVIEWED_GUARD.get("retention_policy"), dict)
    if cleanup_requested:
        try: require_cleanup_policy()
        except PolicyError:
            raise CalibrationFailure("Cleanup approval/policy is incomplete; no run started.", result) from None
    start_url = API + "/actors/apify~web-scraper/runs?" + urlencode(plan["options"])
    try:
        initial = validate_run(request("start", "POST", start_url, plan["input"]), build)
        run_id = safe_identifier(initial.get("id"))
        run = initial
        result["status"] = run["status"]
        if cleanup_requested:
            verify_initial_references(initial)
            if hasattr(transport, "bind_run"): transport.bind_run(initial)
        for _ in range(POLL_LIMIT):
            if run["status"] in TERMINAL: break
            candidate = validate_run(request("poll", "GET", API + "/actor-runs/" + run_id +
                                             "?waitForFinish=60"), build)
            verify_poll_scope(candidate, initial)
            run = candidate
            result["status"] = run["status"]
    except Exception as error:
        result["failure_diagnostic"] = failure_diagnostic(error, current_operation, response_context)
        result["cleanup"]["state"] = "unknown_run_or_poll_outcome"
        persist_final(result, persist)
        raise CalibrationFailure("Start/polling is ambiguous; owner attention required, no retry or deletion attempted.", result) from None
    if run["status"] not in TERMINAL:
        result["receipts"].update(run_receipts(run))
        result["cleanup"]["state"] = "run_still_active"
        persist_final(result, persist)
        raise CalibrationFailure("Run remains active after bounded polling; owner attention required, no abort or deletion attempted.", result)
    if getattr(transport, "refresh_terminal_meters", False) is True:
        refresh = result["meter_refresh"]
        needed = TERMINAL_METER_WAIT_SECONDS + TIMEOUTS["poll"] + CLEANUP_RESERVE_SECONDS
        if result["request_counts"]["poll"] >= POLL_LIMIT:
            refresh["state"] = "preliminary_no_poll_slot"
        elif monotonic() + needed > min(deadline, getattr(transport, "deadline", deadline)):
            refresh["state"] = "preliminary_insufficient_time"
        else:
            try:
                response_context = None
                transport.meter_wait(TERMINAL_METER_WAIT_SECONDS)
                refresh["capture_wait_seconds"] = TERMINAL_METER_WAIT_SECONDS
                response = request("poll", "GET", API + "/actor-runs/" + run_id + "?waitForFinish=60")
                reject_active_refresh(response, initial)
                candidate = validate_run(response, build)
                verify_poll_scope(candidate, initial, run)
                run = candidate
                refresh.update(state="refreshed_after_wait", preliminary=False)
            except Exception as error:
                diagnostic = failure_diagnostic(error, "poll", response_context)
                if diagnostic["category"] == "latest_run_active":
                    result["historical_terminal_capture"] = {"status": run["status"], "preliminary": True,
                                                              "invoice_final": False, "receipts": run_receipts(run)}
                    result["status"] = diagnostic["run_status"]
                    result["failure_diagnostic"] = diagnostic
                    refresh.update(state="preliminary_latest_active", diagnostic=diagnostic)
                else:
                    refresh.update(state="preliminary_refresh_failed", diagnostic=diagnostic)
    if result["status"] not in TERMINAL:
        result["cleanup"]["state"] = "latest_run_active"
        result["local_elapsed_seconds"] = safe_number(monotonic() - began)
        persist_final(result, persist)
        raise CalibrationFailure("Latest observation reports the original run active; owner attention required, no export or cleanup attempted.", result)
    result["receipts"].update(run_receipts(run))
    failure = None
    try:
        if run["status"] != "SUCCEEDED":
            raise PolicyError("The terminal run did not succeed.")
        dataset_id = safe_identifier(initial.get("defaultDatasetId"))
        query = urlencode({"format": "json", "limit": "2", "fields": ",".join(FIELDS)})
        items = request("export", "GET", API + "/datasets/" + dataset_id + "/items?" + query)
        result["returned_output_count"] = len(items) if isinstance(items, list) else None
        result["records"] = validate_output(items)
        result["accepted_output_count"] = len(result["records"])
        result["extraction_outcome"] = "accepted"
    except Exception:
        failure = "Terminal run or bounded export/extraction validation failed."
        result["extraction_outcome"] = "failed"
    finally:
        if cleanup_requested:
            cleanup_terminal(initial, run, transport, request, result, persist, emit)
        else:
            result["cleanup"]["state"] = "not_authorized"
    result["local_elapsed_seconds"] = safe_number(monotonic() - began)
    if not persist_final(result, persist): failure = "Final sanitized evidence could not be persisted; owner attention required."
    if failure or (cleanup_requested and not result["cleanup"]["absence_confirmed"]):
        raise CalibrationFailure(failure or "Cleanup is incomplete; residual storage and total cost require owner attention.", result)
    return result


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        if not isinstance(value, str) or len(value) > 40: raise ValueError
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None: raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise PolicyError("A required provider timestamp is missing or invalid.") from None


def require_cleanup_policy():
    policy = REVIEWED_GUARD.get("retention_policy")
    if (not isinstance(policy, dict) or policy.get("mode") != "cleanup" or
            policy.get("cleanup_approved") is not True or not policy.get("review_reference") or
            not Decimal("0") < quantity(policy.get("upper_bound_hours")) <= MAX_CLEANUP_HOURS):
        raise PolicyError("The code-defined short-lifetime cleanup policy lacks approval or a valid bound.")
    return policy


def verify_initial_references(initial):
    for field in ("id", "userId", "actId") + tuple(value[0] for value in STORE_FIELDS.values()):
        safe_identifier(initial.get(field))
    if PUBLIC_ACTOR_ID is not None and initial["actId"] != PUBLIC_ACTOR_ID:
        raise DiagnosticError("scope_mismatch", "scope_validation")
    if len({initial[value[0]] for value in STORE_FIELDS.values()}) != 3:
        raise DiagnosticError("scope_mismatch", "scope_validation")
    timestamp(initial.get("startedAt"))


def reject_active_refresh(response, initial):
    """Original ID plus a known active status revokes terminal permission before other validation."""
    data = response.get("data") if isinstance(response, dict) else None
    if isinstance(data, dict) and data.get("id") == initial["id"]:
        status = data.get("status")
        if type(status) is str and status in RUN_STATUSES and status not in TERMINAL:
            raise DiagnosticError("latest_run_active", "run_validation", run_status=status)


def verify_poll_scope(candidate, initial, confirmed_terminal=None):
    fields = ("id", "userId", "actId") + tuple(value[0] for value in STORE_FIELDS.values())
    if (any(candidate.get(field) != initial.get(field) for field in fields) or
            (confirmed_terminal is not None and candidate.get("status") != confirmed_terminal["status"])):
        raise DiagnosticError("scope_mismatch", "scope_validation")


def verify_store(kind, response, initial, terminal):
    data = response.get("data") if isinstance(response, dict) else None
    if (not isinstance(data, dict) or data.get("id") != initial[STORE_FIELDS[kind][0]] or
            data.get("userId") != initial["userId"] or "name" not in data or data["name"] is not None or
            data.get("actRunId") != initial["id"] or data.get("actId") != initial["actId"]):
        raise PolicyError("Storage metadata did not prove the new unnamed owned default scope.")
    started, finished, created = map(timestamp, (initial.get("startedAt"), terminal.get("finishedAt"), data.get("createdAt")))
    tolerance = timedelta(seconds=CREATION_TOLERANCE_SECONDS)
    if finished < started or not started - tolerance <= created <= finished + tolerance:
        raise PolicyError("Storage creation is outside the verified run lifetime.")
    return data


def cleanup_terminal(initial, terminal, transport, request, result, persist, emit):
    metadata, valid = {}, True
    for kind, (_, route) in STORE_FIELDS.items():
        url = API + "/" + route + "/" + initial[STORE_FIELDS[kind][0]]
        try:
            response = request("metadata", "GET", url)
            data = verify_store(kind, response, initial, terminal)
            metadata[kind] = data
            result["receipts"]["storage"][kind] = {"association_verified": True,
                                                  "stats": number_fields(data.get("stats"), STORAGE_STAT_FIELDS)}
        except Exception:
            valid = False
            result["receipts"]["storage"][kind] = {"association_verified": False, "stats": None}
    try:
        policy = require_cleanup_policy()
        deadline = timestamp(initial["startedAt"]) + timedelta(hours=float(quantity(policy["upper_bound_hours"])))
        if utc_now() > deadline or terminal["status"] not in TERMINAL or not valid:
            raise PolicyError("Cleanup metadata, terminal status or lifetime policy could not be proved.")
        if hasattr(transport, "authorize_cleanup"): transport.authorize_cleanup(initial, terminal, metadata)
    except Exception:
        result["cleanup"]["state"] = "scope_or_deadline_unverified"
        return
    capture = {"captured_at": utc_now().isoformat(), "status": result["status"],
               "returned_output_count": result["returned_output_count"],
               "accepted_output_count": result["accepted_output_count"], "records": result["records"],
               "extraction_outcome": result["extraction_outcome"],
               "meter_refresh": result["meter_refresh"],
               "receipts": result["receipts"], "request_counts": dict(result["request_counts"])}
    result["pre_cleanup_capture"] = json.loads(canonical_bytes(capture))
    result["pre_cleanup_capture_sha256"] = digest(capture)
    try:
        result["pre_cleanup_file_sha256"] = save_verified(result, "pre_cleanup", persist)
        result["pre_cleanup_evidence_verified"] = True
        if emit is not None: emit({"phase": "pre_cleanup_verified", "receipt": result})
    except Exception:
        result["cleanup"]["state"] = "evidence_not_durable"
        return
    for kind, (_, route) in STORE_FIELDS.items():
        try:
            reply = request("delete", "DELETE", API + "/" + route + "/" + initial[STORE_FIELDS[kind][0]])
            state = "acknowledged" if reply is None else ("already_absent" if isinstance(reply, MissingStorage) else "unexpected_reply")
        except Exception:
            state = "ambiguous_failure"
        result["cleanup"]["stores"][kind] = {"delete_outcome": state, "absence_confirmed": False}
    for kind, (_, route) in STORE_FIELDS.items():
        try:
            reply = request("absence", "GET", API + "/" + route + "/" + initial[STORE_FIELDS[kind][0]])
            absent = isinstance(reply, MissingStorage)
        except Exception:
            absent = False
        result["cleanup"]["stores"][kind]["absence_confirmed"] = absent
    complete = all(store["absence_confirmed"] for store in result["cleanup"]["stores"].values())
    result["cleanup"].update(absence_confirmed=complete, owner_attention_required=not complete,
                             state="absence_confirmed" if complete else "residual_or_unknown_storage")
    completed = utc_now()
    result["receipts"]["cleanup"] = {"attempts_finished_at": completed.isoformat(),
                                     "since_run_started_seconds": safe_number((completed - timestamp(initial["startedAt"])).total_seconds())}


def safe_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)): return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal("1e18") or len(str(value)) > 48: return None
        return value if type(value) is int else str(number)
    except InvalidOperation:
        return None


def number_fields(value, fields):
    if not isinstance(value, dict): return None
    return {field: safe_number(value.get(field)) for field in fields}


def run_receipts(run):
    events = run.get("chargedEventCounts")
    event_counts = None if not isinstance(events, dict) or len(events) > 64 else [safe_number(value) for value in events.values()]
    def safe_time(value):
        try: return timestamp(value).isoformat()
        except PolicyError: return None
    return {"run": {"build_number": run.get("buildNumber"),
                    "started_at": safe_time(run.get("startedAt")), "finished_at": safe_time(run.get("finishedAt")),
                    "usage_total_usd": safe_number(run.get("usageTotalUsd")),
                    "charged_event_counts_without_labels": event_counts, "stats": number_fields(run.get("stats"), STAT_FIELDS)},
            "usage": number_fields(run.get("usage"), USAGE_FIELDS),
            "usage_usd": number_fields(run.get("usageUsd"), USAGE_FIELDS)}


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def save_verified(result, phase, persist):
    if persist is None: raise PolicyError("Sanitized evidence has no durability callback.")
    snapshot = json.loads(canonical_bytes(result))
    expected = digest(snapshot)
    if persist(snapshot, phase) != expected:
        raise PolicyError("Sanitized evidence persistence did not verify its expected digest.")
    return expected


def persist_final(result, persist):
    if persist is None: return True  # Direct mock-only orchestration can omit persistence when no cleanup is configured.
    try:
        result["final_file_sha256"] = save_verified(result, "final", persist)
        return True
    except Exception:
        result["final_evidence_persistence_failed"] = True
        result["cleanup"]["owner_attention_required"] = True
        return False


def persist_receipt_atomic(receipt, phase):
    """Fixed local sanitized file, atomic replace, file+directory fsync, exact readback/hash verification."""
    target = Path("calibration-receipt.json").resolve()
    data, temporary = canonical_bytes(receipt), None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, prefix=".calibration-receipt-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
        directory = os.open(target.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        saved = target.read_bytes()
        if saved != data or hashlib.sha256(saved).hexdigest() != hashlib.sha256(data).hexdigest():
            raise PolicyError("Local sanitized evidence readback did not verify.")
        return hashlib.sha256(saved).hexdigest()
    except Exception:
        raise PolicyError("Local sanitized evidence durability failed; details are not printed.") from None
    finally:
        if temporary is not None:
            try: temporary.unlink()
            except OSError: pass


def emit_receipt(value):
    print(json.dumps(value, indent=2), flush=True)


def safe_request(transport, method, url, payload, token):
    try:
        return transport.request(method, url, payload, token)
    except HTTPError as error:
        parsed = urlsplit(url)
        if error.code == 404 and parsed.netloc == "api.apify.com" and re.fullmatch(
                r"/v2/(?:datasets|key-value-stores|request-queues)/[A-Za-z0-9]{1,64}", parsed.path) and not parsed.query:
            error.close()
            return MissingStorage()
        error.close()
        raise DiagnosticError("http_error", "response_status", error.code) from None
    except DiagnosticError:
        raise
    except (URLError, OSError):
        raise DiagnosticError("connection_error", "request") from None
    except WallDeadline:
        raise
    except Exception:
        # Even exceptions from HTTP libraries may contain URLs, tokens, headers or full bodies.
        raise DiagnosticError("transport_error", "request") from None


def safe_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{1,64}", value):
        raise DiagnosticError("invalid_identifier", "identifier_validation")
    return value


def numeric_limit_equals(value, expected):
    if type(value) not in (int, float, Decimal): return False
    try:
        number = Decimal(str(value))
        return number.is_finite() and number == Decimal(expected)
    except InvalidOperation:
        return False


def validate_run(response, build):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
        raise DiagnosticError("invalid_response", "run_validation")
    run = response["data"]
    status = run.get("status")
    if type(status) is not str or status not in RUN_STATUSES:
        raise DiagnosticError("invalid_run_status", "run_validation")
    options = run.get("options")
    build_number = run.get("buildNumber")
    pending_build = build_number is None and status not in TERMINAL
    if ((build_number != build and not pending_build) or
            (isinstance(options, dict) and options.get("build") != build)):
        raise DiagnosticError("build_mismatch", "build_validation", run_status=status)
    if (not isinstance(options, dict) or
            type(options.get("memoryMbytes")) is not int or options["memoryMbytes"] != 1024 or
            type(options.get("timeoutSecs")) is not int or options["timeoutSecs"] != 120 or
            not numeric_limit_equals(options.get("maxTotalChargeUsd"), "0.10")):
        raise DiagnosticError("options_mismatch", "options_validation", run_status=status)
    return run


def validate_output(items):
    if not isinstance(items, list) or len(items) != 2:
        raise PolicyError("Export did not contain exactly the two expected fixture records.")
    fixtures, accepted = set(), []
    for item in items:
        if (not isinstance(item, dict) or item.get("fixture") not in FIXTURES or
                item.get("fixture") in fixtures or item.get("sku") != "AA101" or
                item.get("name") != "Desk Lamp" or type(item.get("price_minor")) is not int or
                item["price_minor"] != 3499 or item.get("currency") != "USD"):
            raise PolicyError("Export failed the bounded owned-fixture acceptance contract.")
        fixtures.add(item["fixture"])
        accepted.append({field: item[field] for field in FIELDS})
    return accepted


def storage_cost_usd(dataset_gb, kv_gb, queue_gb, hours):
    """Free/Starter timed storage only, from known GB and hours; no hidden zero defaults."""
    dataset, kv, queue, duration = map(quantity, (dataset_gb, kv_gb, queue_gb, hours))
    with localcontext() as context:
        context.prec = 60
        return duration * ((dataset + kv) * Decimal("0.001") + queue * Decimal("0.004"))


def quantity(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise PolicyError("Known nonnegative decimal strings or integers are required.")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise PolicyError("A supplied quantity is invalid.") from None
    if not result.is_finite() or result < 0 or abs(result.adjusted()) > 24 or len(result.as_tuple().digits) > 28:
        raise PolicyError("A supplied quantity is outside the supported finite precision range.")
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise PolicyError("HTTP redirects are rejected; authorization remains on the fixed API host.")


def read_bounded(response, deadline):
    chunks, total = [], 0
    while total <= RESPONSE_LIMIT:
        if monotonic() >= deadline: raise WallDeadline("Response read exceeded its route deadline.")
        chunk = response.read1(min(65536, RESPONSE_LIMIT + 1 - total))
        if monotonic() > deadline: raise WallDeadline("Response read exceeded its route deadline.")
        if not chunk: break
        chunks.append(chunk)
        total += len(chunk)
    if total > RESPONSE_LIMIT: raise DiagnosticError("response_too_large", "response_read")
    return b"".join(chunks)


class HttpTransport:
    """No redirects or retries, bounded response bytes, fixed API routes, closed readiness gate."""
    def __init__(self, build, wall_deadline=None, *, meter_wait=None, refresh_terminal_meters=True):
        require_readiness(build)
        self.build = build
        self.deadline = monotonic() + MAX_WALL_SECONDS
        if wall_deadline is not None: self.deadline = min(self.deadline, wall_deadline)
        self.initial, self.last_run = None, None
        self.latest_active_status = None
        self.metadata, self.cleanup_urls = {}, set()
        self.start_attempted = False
        self.last_response_diagnostic = None
        self.refresh_terminal_meters = refresh_terminal_meters
        self.meter_wait = sleep if meter_wait is None else meter_wait
        self.seen = {key: set() for key in TIMEOUTS}

    def bind_run(self, initial):
        require_readiness(self.build)
        if self.initial is None or initial != self.initial:
            raise PolicyError("The cleanup scope was not returned by this transport's single start.")
        verify_initial_references(initial)

    def authorize_cleanup(self, initial, terminal, metadata):
        require_readiness(self.build)
        if self.latest_active_status is not None:
            raise PolicyError("An active observation revoked terminal cleanup permission.")
        policy = require_cleanup_policy()
        self.bind_run(initial)
        if terminal != self.last_run or terminal.get("status") not in TERMINAL or set(metadata) != set(STORE_FIELDS):
            raise PolicyError("Cleanup lacks a confirmed terminal run and complete metadata.")
        for kind in STORE_FIELDS:
            if metadata[kind] != self.metadata.get(kind):
                raise PolicyError("Cleanup metadata was not returned by this transport.")
            verify_store(kind, {"data": metadata[kind]}, initial, terminal)
        self.cleanup_deadline = timestamp(initial["startedAt"]) + timedelta(hours=float(quantity(policy["upper_bound_hours"])))
        if utc_now() > self.cleanup_deadline:
            raise PolicyError("The approved short cleanup lifetime has expired.")
        self.cleanup_urls = {API + "/" + route + "/" + initial[field] for field, route in STORE_FIELDS.values()}

    def request(self, method, url, payload, token):
        self.last_response_diagnostic = None
        require_readiness(self.build)
        if self.latest_active_status is not None:
            raise DiagnosticError("latest_run_active", "local_policy", run_status=self.latest_active_status)
        plan = build_plan(self.build)
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        query = dict(pairs)
        start = (method == "POST" and parsed.path == "/v2/actors/apify~web-scraper/runs" and
                 query == plan["options"] and payload == plan["input"] and not self.start_attempted)
        poll = (method == "GET" and re.fullmatch(r"/v2/actor-runs/[A-Za-z0-9]{1,64}", parsed.path) and
                query == {"waitForFinish": "60"} and payload is None and self.initial is not None and
                parsed.path == "/v2/actor-runs/" + self.initial["id"] and len(self.seen["poll"]) < POLL_LIMIT)
        export = (method == "GET" and re.fullmatch(r"/v2/datasets/[A-Za-z0-9]{1,64}/items", parsed.path) and
                  query == {"format": "json", "limit": "2", "fields": ",".join(FIELDS)} and payload is None and
                  self.initial is not None and parsed.path == "/v2/datasets/" + self.initial["defaultDatasetId"] + "/items")
        storage_kind = None
        if self.initial is not None:
            for kind, (field, route) in STORE_FIELDS.items():
                if parsed.path == "/v2/" + route + "/" + self.initial[field]: storage_kind = kind
        storage = storage_kind is not None and not query and payload is None and method in ("GET", "DELETE")
        if (parsed.scheme != "https" or parsed.netloc != "api.apify.com" or parsed.fragment or
                len(pairs) != len(query) or not (start or poll or export or storage)):
            raise PolicyError("HTTP route is outside the fixed calibration scope.")
        kind = "start" if start else "poll" if poll else "export" if export else (
            "delete" if method == "DELETE" else "absence" if url in self.cleanup_urls else "metadata")
        if kind == "delete":
            require_cleanup_policy()
            if url not in self.cleanup_urls or utc_now() > self.cleanup_deadline:
                raise PolicyError("Deletion lacks verified terminal scope or its approved lifetime.")
        if kind != "poll" and url in self.seen[kind]:
            raise PolicyError("Duplicate boundary operation rejected; no retry is permitted.")
        if kind in ("metadata", "delete", "absence"):
            needed = (9 - sum(len(self.seen[key]) for key in ("metadata", "delete", "absence"))) * 10 + 10
        else:
            needed = TIMEOUTS[kind] + CLEANUP_RESERVE_SECONDS
            if kind == "start": needed = MINIMUM_START_SECONDS
        if monotonic() + needed > self.deadline:
            raise WallDeadline("Transport wall deadline reached before another operation.")
        self.seen[kind].add(url if kind != "poll" else str(len(self.seen[kind])))
        if start: self.start_attempted = True
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=body, method=method,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        route_deadline = min(self.deadline, monotonic() + TIMEOUTS[kind])
        status, run_status, stage = None, None, "request"
        try:
            with build_opener(NoRedirect()).open(request, timeout=TIMEOUTS[kind]) as response:
                status = response.getcode()
                stage = "response_status"
                if kind == "delete":
                    if status != 204: raise DiagnosticError("unexpected_http_status", stage)
                    return None
                if status != (201 if start else 200): raise DiagnosticError("unexpected_http_status", stage)
                stage = "response_read"
                data = read_bounded(response, route_deadline)
            stage = "json_decode"
            parsed_response = json.loads(data.decode("utf-8"), parse_float=Decimal)
            if isinstance(parsed_response, dict) and isinstance(parsed_response.get("data"), dict):
                run_status = sanitized_diagnostic({"run_status": parsed_response["data"].get("status")})["run_status"]
            self.last_response_diagnostic = sanitized_diagnostic({"http_status": status, "run_status": run_status})
            stage = "run_validation"
            if start:
                self.initial = validate_run(parsed_response, self.build)
                verify_initial_references(self.initial)
                self.last_run = self.initial
            elif poll:
                if self.last_run["status"] in TERMINAL:
                    try:
                        reject_active_refresh(parsed_response, self.initial)
                    except DiagnosticError as error:
                        self.latest_active_status = error.diagnostic["run_status"]
                        self.cleanup_urls.clear()
                        raise
                candidate = validate_run(parsed_response, self.build)
                verify_poll_scope(candidate, self.initial,
                                  self.last_run if self.last_run["status"] in TERMINAL else None)
                self.last_run = candidate
            elif kind == "metadata" and isinstance(parsed_response, dict) and isinstance(parsed_response.get("data"), dict):
                self.metadata[storage_kind] = parsed_response["data"]
            return parsed_response
        except HTTPError as error:
            if storage and error.code == 404:
                error.close()
                return MissingStorage()
            error.close()
            raise DiagnosticError("http_error", "response_status", error.code) from None
        except DiagnosticError as error:
            data = sanitized_diagnostic(error.diagnostic)
            raise DiagnosticError(data["category"], data["stage"], status, run_status) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DiagnosticError("invalid_json", "json_decode", status) from None
        except WallDeadline:
            raise DiagnosticError("deadline_exceeded", stage, status, run_status) from None
        except (URLError, OSError):
            raise DiagnosticError("connection_error", stage, status, run_status) from None
        except Exception:
            raise DiagnosticError("transport_error", stage, status, run_status) from None


def main(argv=None, *, environ=None, transport=None, persist=None, emit=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true", help="Offline only; this is the default")
    modes.add_argument("--execute", action="store_true", help="Opt in; still blocked by the reviewed cost guard")
    modes.add_argument("--check-readiness", action="store_true", help="Secret-free check; closed guard exits 2")
    parser.add_argument("--build", help="Immutable public Actor build number, never a tag")
    args = parser.parse_args(argv)
    try:
        if args.check_readiness:
            require_readiness(args.build)
            result = {"ready": True}
        elif args.execute:
            result = execute_live(args.build, opt_in=True, environ=environ, transport=transport, persist=persist, emit=emit)
        else:
            result = build_plan(args.build)
        print(json.dumps(result, indent=2))
        return 0
    except CalibrationFailure as error:
        print(json.dumps(error.receipt, indent=2))
        print("Calibration stopped: " + str(error), file=sys.stderr)
        return 2
    except PolicyError as error:
        print("Calibration stopped: " + str(error), file=sys.stderr)
        return 2
    except Exception:
        print("Calibration stopped: unexpected local input or transport error; no response details printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
