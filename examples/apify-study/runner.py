"""Two-phase smoke execution. All guards are closed until a separate source review.

Root integration owns plan files, workflow, 0600 temporary state, encryption/upload,
and local decrypt/fsync/readback approval. This module never writes or prints raw
state. A private encrypted receipt contains controlled records and numeric meters,
but no provider identifiers. Public callers must use public_result(), never state.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import copy
import hashlib
import json
import math
import os
import re
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

RUNNER_READY = True
REVIEWED_PLAN_SHA256 = "b0c531f83da2a8206f98cb08401db2d6171a4da187be6e76364a9aa23d0180fd"
REVIEWED_PLAN_FILE_SHA256 = "58042d797c8c0278bb0d6de9c94ac8ab7fd1b8e6ddd556cda094c01a80f6f442"
API = "https://api.apify.com/v2"
OWNED_HOST = "scrapingant.github.io"
OWNED_PATH_PREFIX = "/scrapingant-examples/fixtures/"
TERMINAL = ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED")
ACTIVE = ("READY", "RUNNING", "TIMING-OUT", "ABORTING")
STORES = {"dataset": ("defaultDatasetId", "datasets"),
          "kv": ("defaultKeyValueStoreId", "key-value-stores"),
          "queue": ("defaultRequestQueueId", "request-queues")}
IDENTITY_FIELDS = ("id", "userId", "actId", "defaultDatasetId", "defaultKeyValueStoreId", "defaultRequestQueueId")
OP_LIMITS = {"start": 1, "poll": 3, "settle": 1, "export": 1, "fresh_terminal": 1,
             **{p + "_" + k: 2 if p == "metadata" else 1 for p in ("metadata", "delete", "absence") for k in STORES}}
MAX_CALLS = 20
CAPTURE_WALL_SECONDS = 480
MINIMUM_START_SECONDS = 360
CLEANUP_RESERVE_SECONDS = 100
CLEANUP_WALL_SECONDS = 120
SETTLE_SECONDS = 10
APPROVAL_AGE_SECONDS = 25 * 60
DELETE_AGE_SECONDS = 30 * 60
RESPONSE_LIMIT = 131072
TIMEOUTS = {"start": 30, "poll": 65, "settle": 65, "export": 10, "fresh_terminal": 10,
            **{p + "_" + k: 10 for p in ("metadata", "delete", "absence") for k in STORES}}
USAGE_FIELDS = ("ACTOR_COMPUTE_UNITS", "DATASET_READS", "DATASET_WRITES", "KEY_VALUE_STORE_READS",
                "KEY_VALUE_STORE_WRITES", "KEY_VALUE_STORE_LISTS", "REQUEST_QUEUE_READS",
                "REQUEST_QUEUE_WRITES", "DATA_TRANSFER_INTERNAL_GBYTES", "DATA_TRANSFER_EXTERNAL_GBYTES",
                "PROXY_RESIDENTIAL_TRANSFER_GBYTES", "PROXY_SERPS")
STAT_FIELDS = ("inputBodyLen", "migrationCount", "rebootCount", "restartCount", "resurrectCount",
               "memAvgBytes", "memMaxBytes", "memCurrentBytes", "cpuAvgUsage", "cpuMaxUsage",
               "cpuCurrentUsage", "netRxBytes", "netTxBytes", "durationMillis", "runTimeSecs", "computeUnits")
STORAGE_FIELDS = ("storageBytes", "readCount", "writeCount", "deleteCount", "listCount")
OUTPUT_FIELDS = ("fixture", "case_id", "sku", "name", "price_minor", "currency", "url", "text", "markdown",
                 "duration_ms", "elapsed_ms", "fetch_ms", "parse_ms")
CATEGORIES = ("guard_closed", "opt_in_required", "unreviewed_plan", "invalid_plan", "invalid_cell",
              "budget_exhausted", "deadline_exceeded", "token_unavailable", "invalid_operation", "call_limit",
              "http_error", "connection_error", "transport_error", "unexpected_http_status", "response_too_large",
              "invalid_json", "invalid_response", "invalid_identifier", "invalid_run_status", "build_mismatch",
              "options_mismatch", "scope_mismatch", "latest_run_active", "terminal_unconfirmed", "metadata_invalid",
              "output_invalid", "persistence_failed", "approval_missing", "approval_expired", "state_mismatch",
              "delete_unconfirmed", "absence_unconfirmed")
STAGES = ("policy", "request", "response_status", "response_read", "json_decode", "run_validation",
          "scope_validation", "output_validation", "metadata_validation", "evidence", "approval", "cleanup")


class Fault(Exception):
    """Only fixed enums/numeric HTTP status survive a provider or callback failure."""
    def __init__(self, category, stage="policy", http_status=None):
        self.category = category if category in CATEGORIES else "transport_error"
        self.stage = stage if stage in STAGES else "request"
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        super().__init__(self.category)
    def safe(self):
        return {"category": self.category, "stage": self.stage, "http_status": self.http_status}


class OutputFault(Fault):
    """Bounded projected owned rows are private failure evidence, never exception text."""
    def __init__(self, records):
        super().__init__("output_invalid", "output_validation")
        self.records = records


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise Fault("invalid_plan") from None


def sha(value):
    return hashlib.sha256(value).hexdigest()


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def number(value):
    if type(value) not in (int, float, Decimal) or isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and 0 <= n <= Decimal("1e18") and len(str(value)) <= 96 else None
    except (InvalidOperation, ValueError):
        return None


def numeric_receipt(value):
    n = number(value)
    if n is None:
        return None
    return int(n) if n == n.to_integral_value() else str(n)


def ident(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9]{1,64}", value) is None:
        raise Fault("invalid_identifier", "scope_validation")
    return value


def timestamp(value):
    if not isinstance(value, str) or len(value) > 48:
        raise Fault("invalid_response", "run_validation")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if d.tzinfo is None or d.utcoffset() != timedelta(0):
            raise ValueError()
        return d
    except (ValueError, OverflowError):
        raise Fault("invalid_response", "run_validation") from None


def owned_url(value):
    if not isinstance(value, str) or len(value) > 512:
        return False
    u = urlsplit(value)
    return (u.scheme == "https" and u.netloc == OWNED_HOST and not u.query and not u.fragment
            and u.path.startswith(OWNED_PATH_PREFIX) and not any(s in u.path for s in ("..", "%", "\\")))


def require_guard():
    if RUNNER_READY is not True or not digest(REVIEWED_PLAN_SHA256):
        raise Fault("guard_closed")


def validate_plan(plan):
    if not isinstance(plan, dict) or not digest(REVIEWED_PLAN_SHA256) or sha(canonical(plan)) != REVIEWED_PLAN_SHA256:
        raise Fault("unreviewed_plan")
    if plan.get("schema_version") != 1 or plan.get("stage") != "SMOKE" or plan.get("aggregate_reserved_usd") != "0.84":
        raise Fault("invalid_plan")
    cells = plan.get("cells")
    if not isinstance(cells, list) or len(cells) != 6:
        raise Fault("invalid_plan")
    names, actors = set(), set()
    for spec in cells:
        if not isinstance(spec, dict):
            raise Fault("invalid_cell")
        name = spec.get("cell_id")
        if not isinstance(name, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", name) is None or name in names:
            raise Fault("invalid_cell")
        names.add(name)
        actor = ident(spec.get("actor_id"))
        if actor in actors:
            raise Fault("invalid_cell")
        actors.add(actor)
        build = spec.get("build")
        if not isinstance(build, str) or re.fullmatch(r"[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}", build) is None:
            raise Fault("invalid_cell")
        opts = spec.get("options")
        if not isinstance(opts, dict) or set(opts) != {"build", "memoryMbytes", "timeoutSecs", "maxTotalChargeUsd", "restartOnError"}:
            raise Fault("invalid_cell")
        if (opts["build"] != build or type(opts["memoryMbytes"]) is not int or opts["memoryMbytes"] not in (4096, 8192)
                or type(opts["timeoutSecs"]) is not int or opts["timeoutSecs"] != 120
                or opts["maxTotalChargeUsd"] != "0.12" or opts["restartOnError"] is not False
                or spec.get("ancillary_reserve_usd") != "0.02"):
            raise Fault("invalid_cell")
        if not isinstance(spec.get("input"), dict) or len(canonical(spec["input"])) > 131072:
            raise Fault("invalid_cell")
        out = spec.get("output")
        if not isinstance(out, dict) or type(out.get("max_records")) is not int or out["max_records"] not in (1, 3):
            raise Fault("invalid_cell")
        if type(out.get("max_bytes")) is not int or not 1 <= out["max_bytes"] <= 65536:
            raise Fault("invalid_cell")
        fields = out.get("fields")
        if (not isinstance(fields, list) or not fields or len(set(fields)) != len(fields)
                or any(f not in OUTPUT_FIELDS for f in fields)):
            raise Fault("invalid_cell")
        urls = out.get("allowed_urls")
        if not isinstance(urls, list) or len(urls) != out["max_records"] or len(set(urls)) != len(urls) or not all(owned_url(u) for u in urls):
            raise Fault("invalid_cell")
        expected = out.get("expected_records")
        if expected is not None:
            if (not isinstance(expected, list) or len(expected) != out["max_records"]
                    or any(not isinstance(v, dict) or set(v) - set(fields) for v in expected)
                    or len(canonical(expected)) > out["max_bytes"]):
                raise Fault("invalid_cell")
        else:
            contracts = out.get("content_contracts")
            if isinstance(contracts, list):
                contract_urls = [v.get("url") if isinstance(v, dict) else None for v in contracts]
            elif isinstance(contracts, dict):
                contract_urls = list(contracts)
            else:
                contract_urls = []
            if (len(contract_urls) != len(urls) or set(contract_urls) != set(urls) or "url" not in fields
                    or not (set(fields) & {"text", "markdown"})):
                raise Fault("invalid_cell")
    return plan


def load_reviewed_plan(raw):
    """Root reads the fixed file; both its bytes and canonical dictionary are pinned."""
    if not isinstance(raw, bytes) or len(raw) > 262144 or not digest(REVIEWED_PLAN_FILE_SHA256) or sha(raw) != REVIEWED_PLAN_FILE_SHA256:
        raise Fault("unreviewed_plan")
    try:
        plan = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Fault("invalid_plan") from None
    return validate_plan(plan)


@dataclass(frozen=True, repr=False)
class Cell:
    plan_bytes: bytes
    cell_id: str
    @property
    def spec(self):
        plan = validate_plan(json.loads(self.plan_bytes))
        choices = [c for c in plan["cells"] if c["cell_id"] == self.cell_id]
        if len(choices) != 1:
            raise Fault("invalid_cell")
        return choices[0]
    def __repr__(self):
        return "<reviewed smoke cell>"


def prepare_cell(plan, cell_id):
    validate_plan(plan)
    cell = Cell(canonical(plan), cell_id)
    cell.spec
    return cell


class StudyBudget:
    """Trusted root orchestration shares one ledger; failures never release reserve."""
    def __init__(self, plan):
        validate_plan(plan)
        self.plan_sha256 = sha(canonical(plan))
        self.claimed = set()
        self.reserved_usd = Decimal(0)
    def claim(self, cell):
        if (not isinstance(cell, Cell) or sha(cell.plan_bytes) != self.plan_sha256
                or cell.cell_id in self.claimed or len(self.claimed) >= 6):
            raise Fault("budget_exhausted")
        cell.spec
        with localcontext() as ctx:
            ctx.prec = 50
            amount = self.reserved_usd + Decimal("0.14")
        if amount > Decimal("0.84"):
            raise Fault("budget_exhausted")
        self.claimed.add(cell.cell_id)
        self.reserved_usd = amount


@dataclass(frozen=True, repr=False)
class Reply:
    status: int
    body: object


def empty_counts():
    return {"total": 0, **{k: 0 for k in OP_LIMITS}}


def validate_counts(counts):
    if (not isinstance(counts, dict) or set(counts) != set(empty_counts())
            or any(type(counts[k]) is not int or not 0 <= counts[k] <= OP_LIMITS[k] for k in OP_LIMITS)
            or type(counts["total"]) is not int or counts["total"] != sum(counts[k] for k in OP_LIMITS)
            or counts["total"] > MAX_CALLS):
        raise Fault("state_mismatch")


def consume(counts, operation, mode):
    validate_counts(counts)
    if operation not in OP_LIMITS or (mode == "capture" and (operation.startswith(("delete_", "absence_")) or operation == "fresh_terminal")):
        raise Fault("invalid_operation")
    if mode == "cleanup" and operation not in {"fresh_terminal", *[p + "_" + k for p in ("metadata", "delete", "absence") for k in STORES]}:
        raise Fault("invalid_operation")
    if counts["total"] >= MAX_CALLS or counts[operation] >= OP_LIMITS[operation]:
        raise Fault("call_limit")
    counts["total"] += 1
    counts[operation] += 1


def check_time(clock, deadline, needed=0):
    if not isinstance(deadline, (int, float)) or not math.isfinite(deadline) or deadline - clock() < needed:
        raise Fault("deadline_exceeded")


@dataclass(repr=False)
class PrivateState:
    cell: Cell
    identity: dict = field(default_factory=dict)
    status: str = "UNKNOWN"
    latest_active: bool = False
    evidence: dict = field(default_factory=dict)
    request_counts: dict = field(default_factory=empty_counts)
    plaintext_sha256: str = None
    ciphertext_sha256: str = None
    capture_verified: bool = False
    encrypted_verified: bool = False
    diagnostic: dict = None
    cleanup_state: str = "not_attempted"
    def __repr__(self):
        return "<private smoke state; use public_result for logs>"


def response_data(reply, expected_status):
    if not isinstance(reply, Reply) or type(reply.status) is not int:
        raise Fault("invalid_response", "response_status")
    if reply.status != expected_status:
        raise Fault("unexpected_http_status", "response_status", reply.status)
    if not isinstance(reply.body, dict) or not isinstance(reply.body.get("data"), dict):
        raise Fault("invalid_response", "run_validation", reply.status)
    return reply.body["data"]


def revoke_active(data, state, preserve_approved_evidence=False):
    # This observation precedes all optional/build/scope validation. An active
    # original ID can revoke permission even when every other field is malformed.
    if (isinstance(data, dict) and state.identity and data.get("id") == state.identity.get("id")
            and data.get("status") in ACTIVE and state.status in TERMINAL):
        state.latest_active = True
        if not preserve_approved_evidence:
            state.evidence["historical_terminal_capture"] = copy.deepcopy(state.evidence.get("run"))
            state.evidence["run"] = None
        state.status = data["status"]
        state.capture_verified = False
        raise Fault("latest_run_active", "run_validation")


def validate_run(data, cell, initial=None, required_status=None):
    if not isinstance(data, dict) or data.get("status") not in TERMINAL + ACTIVE:
        raise Fault("invalid_run_status", "run_validation")
    spec = cell.spec
    identity = {k: ident(data.get(k)) for k in IDENTITY_FIELDS}
    if len({identity[k] for k in IDENTITY_FIELDS if k.startswith("default")}) != 3 or identity["actId"] != spec["actor_id"]:
        raise Fault("scope_mismatch", "scope_validation")
    if initial and any(identity[k] != initial[k] for k in IDENTITY_FIELDS):
        raise Fault("scope_mismatch", "scope_validation")
    status = data["status"]
    if required_status is not None and status != required_status:
        raise Fault("scope_mismatch", "scope_validation")
    if data.get("buildNumber") != spec["build"] and not (status in ACTIVE and data.get("buildNumber") is None):
        raise Fault("build_mismatch", "run_validation")
    opts = data.get("options")
    if (not isinstance(opts, dict) or opts.get("build") != spec["build"]
            or type(opts.get("memoryMbytes")) is not int or opts["memoryMbytes"] != spec["options"]["memoryMbytes"]
            or type(opts.get("timeoutSecs")) is not int or opts["timeoutSecs"] != 120
            or number(opts.get("maxTotalChargeUsd")) != Decimal("0.12")
            or ("restartOnError" in opts and opts["restartOnError"] is not False)):
        raise Fault("options_mismatch", "run_validation")
    start = timestamp(data.get("startedAt"))
    if initial and data["startedAt"] != initial["startedAt"]:
        raise Fault("scope_mismatch", "scope_validation")
    finish = None
    if status in TERMINAL:
        finish = timestamp(data.get("finishedAt"))
        if finish < start:
            raise Fault("invalid_response", "run_validation")
        if initial and initial.get("finishedAt") and data["finishedAt"] != initial["finishedAt"]:
            raise Fault("scope_mismatch", "scope_validation")
    identity.update(startedAt=data["startedAt"], finishedAt=data.get("finishedAt") if finish else None,
                    build=spec["build"], options=copy.deepcopy(spec["options"]), status=status)
    return identity


def numeric_fields(value, fields):
    value = value if isinstance(value, dict) else {}
    return {k: numeric_receipt(value.get(k)) for k in fields}


def run_receipt(data, cell):
    events = cell.spec.get("charged_event_fields", [])
    events = events if isinstance(events, list) and len(events) <= 16 else []
    events = [e for e in events if isinstance(e, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", e)]
    return {"status": data["status"], "build": cell.spec["build"], "started_at": data["startedAt"],
            "finished_at": data.get("finishedAt"), "usage_total_usd": numeric_receipt(data.get("usageTotalUsd")),
            "usage": numeric_fields(data.get("usage"), USAGE_FIELDS),
            "usage_usd": numeric_fields(data.get("usageUsd"), USAGE_FIELDS),
            "stats": numeric_fields(data.get("stats"), STAT_FIELDS),
            "charged_event_counts": numeric_fields(data.get("chargedEventCounts"), events),
            "meters_state": "preliminary", "invoice_finality": False}


def scope_commitment(identity):
    return sha(canonical(identity))


def validate_metadata(data, kind, identity):
    if (not isinstance(data, dict) or data.get("id") != identity[STORES[kind][0]]
            or data.get("userId") != identity["userId"] or data.get("actRunId") != identity["id"]
            or data.get("actId") != identity["actId"] or "name" not in data or data["name"] is not None):
        raise Fault("metadata_invalid", "metadata_validation")
    try:
        created = timestamp(data.get("createdAt"))
        start, finish = timestamp(identity["startedAt"]), timestamp(identity["finishedAt"])
    except Fault:
        raise Fault("metadata_invalid", "metadata_validation") from None
    if not start - timedelta(seconds=5) <= created <= finish + timedelta(seconds=5):
        raise Fault("metadata_invalid", "metadata_validation")
    stats = numeric_fields(data.get("stats"), STORAGE_FIELDS)
    if stats["storageBytes"] is None:
        raise Fault("metadata_invalid", "metadata_validation")
    if kind == "dataset":
        count = data.get("itemCount")
        stats["itemCount"] = count if type(count) is int and 0 <= count <= 1000000 else None
    return stats


def validate_output(items, cell):
    out = cell.spec["output"]
    if not isinstance(items, list) or len(items) > out["max_records"] + 1:
        raise OutputFault([])
    projected = []
    invalid = False
    for item in items:
        if not isinstance(item, dict):
            invalid = True
            continue
        v = {k: item[k] for k in out["fields"] if k in item}
        if out.get("url_source") == "metadata.url":
            meta = item.get("metadata")
            v["url"] = meta.get("url") if isinstance(meta, dict) else None
        if out.get("expected_records") is None:
            if v.get("url") not in out["allowed_urls"]:
                invalid = True
                continue
        else:
            key = "case_id" if "case_id" in out["fields"] else "fixture"
            known = {row.get(key) for row in out["expected_records"]}
            if v.get(key) not in known:
                invalid = True
                continue
        valid_row = True
        for k, value in v.items():
            if k in ("duration_ms", "elapsed_ms", "fetch_ms", "parse_ms"):
                if number(value) is None:
                    valid_row = False
                else:
                    v[k] = numeric_receipt(value)
            elif k == "price_minor":
                if type(value) is not int or not 0 <= value <= 100000000:
                    valid_row = False
            elif not isinstance(value, str) or len(value) > out["max_bytes"] or "\x00" in value:
                valid_row = False
        if not valid_row:
            invalid = True
            continue
        if len(canonical(projected + [v])) > out["max_bytes"]:
            invalid = True
            continue
        projected.append(v)
    if invalid or len(items) != out["max_records"] or len(projected) != out["max_records"]:
        raise OutputFault(projected)
    expected = out.get("expected_records")
    if expected is not None:
        # Optional timings never expand the controlled truth contract.
        base = [{k: v for k, v in row.items() if k not in ("duration_ms", "elapsed_ms", "fetch_ms", "parse_ms")} for row in projected]
        if sorted(map(canonical, base)) != sorted(map(canonical, expected)):
            raise OutputFault(projected)
    else:
        urls = [row.get("url") for row in projected]
        if len(set(urls)) != len(urls) or set(urls) != set(out["allowed_urls"]):
            raise OutputFault(projected)
        for row in projected:
            texts = [row.get(k) for k in ("text", "markdown") if k in out["fields"]]
            # Capture checks the controlled shape, URL and text bounds. Exact
            # sentence/table/code acceptance is a separate private study validator.
            if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
                raise OutputFault(projected)
    if len(canonical(projected)) > out["max_bytes"]:
        raise OutputFault(projected)
    return projected


class Session:
    def __init__(self, transport, state, mode, clock, deadline):
        self.transport, self.state, self.mode, self.clock, self.deadline = transport, state, mode, clock, deadline
    def call(self, operation):
        timeout = TIMEOUTS.get(operation, 10)
        reserve = CLEANUP_RESERVE_SECONDS if self.mode == "capture" else 0
        check_time(self.clock, self.deadline, timeout + reserve)
        consume(self.state.request_counts, operation, self.mode)
        try:
            result = self.transport.request(operation, self.state.identity or None, timeout)
            if operation in ("poll", "settle", "fresh_terminal") and isinstance(result, Reply) and result.status == 200:
                raw = result.body.get("data") if isinstance(result.body, dict) else None
                revoke_active(raw, self.state, preserve_approved_evidence=self.mode == "cleanup")
            check_time(self.clock, self.deadline, reserve)
            return result
        except Fault as exc:
            if exc.category == "latest_run_active":
                self.state.latest_active = True
                self.state.capture_verified = False
                if self.mode == "capture" and self.state.evidence.get("run") is not None:
                    self.state.evidence["historical_terminal_capture"] = self.state.evidence["run"]
                    self.state.evidence["run"] = None
                status = getattr(self.transport, "latest_active_status", None)
                if status in ACTIVE:
                    self.state.status = status
            raise
        except Exception:
            raise Fault("transport_error", "request") from None


def record_fault(state, fault):
    state.diagnostic = fault.safe()


def persist_capture(state, callback):
    state.evidence.update(status=state.status, latest_active=state.latest_active,
                          request_counts=copy.deepcopy(state.request_counts), diagnostic=state.diagnostic,
                          scope_association_sha256=scope_commitment(state.identity) if state.identity else None)
    payload = canonical(state.evidence)
    state.plaintext_sha256 = sha(payload)
    try:
        receipt = callback(payload) if callable(callback) else None
        if (not isinstance(receipt, dict) or receipt.get("plaintext_sha256") != state.plaintext_sha256
                or not digest(receipt.get("ciphertext_sha256")) or receipt.get("remote_file_readback_verified") is not True):
            raise Fault("persistence_failed", "evidence")
        state.ciphertext_sha256 = receipt["ciphertext_sha256"]
        state.encrypted_verified = True
    except Exception:
        state.encrypted_verified = False
        record_fault(state, Fault("persistence_failed", "evidence"))
    return state


def run_until_capture(transport, cell, persist_encrypted, *, budget, clock=monotonic,
                      utcnow=lambda: datetime.now(timezone.utc), wait=sleep, deadline=None):
    require_guard()
    if not isinstance(cell, Cell):
        raise Fault("invalid_cell")
    cell.spec
    if not callable(persist_encrypted):
        raise Fault("persistence_failed", "evidence")
    deadline = min(deadline, clock() + CAPTURE_WALL_SECONDS) if deadline is not None else clock() + CAPTURE_WALL_SECONDS
    check_time(clock, deadline, MINIMUM_START_SECONDS)
    if not isinstance(budget, StudyBudget):
        raise Fault("budget_exhausted")
    budget.claim(cell)  # A start attempt consumes the full per-cell reserve.
    state = PrivateState(cell)
    state.evidence = {"schema_version": 1, "stage": "SMOKE", "cell_id": cell.cell_id,
                      "actor_id": cell.spec["actor_id"], "invoice_finality": False, "all_in_cost_reconciled": False,
                      "run": None, "records": [], "extraction_state": "not_attempted", "storage": {},
                      "owner_association_verified": False, "captured_at": None}
    session = Session(transport, state, "capture", clock, deadline)
    try:
        reply = session.call("start")
        data = response_data(reply, 201)
        try:
            state.identity = validate_run(data, cell)
        except Fault as exc:
            raise Fault(exc.category, exc.stage, reply.status) from None
        state.status = data["status"]
        transport.bind_run(state.identity)
        while state.status in ACTIVE and state.request_counts["poll"] < 3:
            reply = session.call("poll")
            data = response_data(reply, 200)
            try:
                updated = validate_run(data, cell, state.identity)
            except Fault as exc:
                raise Fault(exc.category, exc.stage, reply.status) from None
            state.identity.update(updated)
            state.status = data["status"]
            transport.bind_run(state.identity)
        if state.status in ACTIVE:
            state.latest_active = True
            raise Fault("terminal_unconfirmed", "run_validation")
        state.evidence["run"] = run_receipt(data, cell)
        if (getattr(transport, "enable_terminal_settling", False) is True
                and state.request_counts["poll"] < 4 and deadline - clock() >= SETTLE_SECONDS + 65 + 40 + CLEANUP_RESERVE_SECONDS):
            try:
                wait(SETTLE_SECONDS)
                reply = session.call("settle")
                fresh = response_data(reply, 200)
                updated = validate_run(fresh, cell, state.identity, state.status)
                state.identity.update(updated)
                data = fresh
                state.evidence["run"] = run_receipt(data, cell)
            except Fault as exc:
                if state.latest_active:
                    raise
                record_fault(state, exc)
        if state.status == "SUCCEEDED":
            try:
                reply = session.call("export")
                if not isinstance(reply, Reply) or reply.status != 200:
                    raise Fault("unexpected_http_status", "response_status", getattr(reply, "status", None))
                state.evidence["records"] = validate_output(reply.body, cell)
                state.evidence["extraction_state"] = "accepted"
            except Fault as exc:
                state.evidence["extraction_state"] = "invalid"
                if isinstance(exc, OutputFault):
                    state.evidence["records"] = exc.records
                record_fault(state, exc)
        else:
            state.evidence["extraction_state"] = "terminal_failure"
        all_verified = True
        for kind in STORES:
            try:
                reply = session.call("metadata_" + kind)
                meta = response_data(reply, 200)
                state.evidence["storage"][kind] = validate_metadata(meta, kind, state.identity)
            except Fault as exc:
                all_verified = False
                record_fault(state, exc)
        state.capture_verified = all_verified
        state.evidence["owner_association_verified"] = all_verified
        count = state.evidence["storage"].get("dataset", {}).get("itemCount")
        matches = count == len(state.evidence["records"]) if count is not None else None
        state.evidence["dataset_item_count_matches_capture"] = matches
        if matches is False and state.evidence["extraction_state"] == "accepted":
            state.evidence["extraction_state"] = "invalid"
            record_fault(state, Fault("output_invalid", "output_validation"))
    except Fault as exc:
        record_fault(state, exc)
    except Exception:
        record_fault(state, Fault("transport_error", "request"))
    state.evidence["captured_at"] = utcnow().isoformat()
    return persist_capture(state, persist_encrypted)


def public_result(state):
    spec = state.cell.spec
    diagnostic = state.diagnostic if isinstance(state.diagnostic, dict) else None
    diagnostic = Fault(diagnostic.get("category"), diagnostic.get("stage"), diagnostic.get("http_status")).safe() if diagnostic else None
    counts = {k: state.request_counts.get(k) if type(state.request_counts.get(k)) is int and 0 <= state.request_counts[k] <= MAX_CALLS else None
              for k in empty_counts()}
    return {"cell_id": state.cell.cell_id, "actor_id": spec["actor_id"],
            "status": state.status if state.status in TERMINAL + ACTIVE else "UNKNOWN",
            "stage": "SMOKE", "request_counts": counts,
            "ciphertext_sha256": state.ciphertext_sha256 if digest(state.ciphertext_sha256) else None,
            "diagnostic": diagnostic, "cleanup_state": state.cleanup_state if state.cleanup_state in ("not_attempted", "blocked", "residual", "complete") else "blocked",
            "owner_attention_required": bool(state.latest_active or not state.capture_verified or not state.encrypted_verified
                                              or state.cleanup_state in ("blocked", "residual"))}


def cleanup_verified_capture(transport, state, approved_sha, *, verify_local_approval=None,
                             clock=monotonic, utcnow=lambda: datetime.now(timezone.utc), deadline=None):
    # This result is PRIVATE: root encrypts scalar meters/timestamps after cleanup.
    # Public logs must project fixed state/diagnostic/counts only.
    phase_started = clock()
    result = {"cleanup_state": "blocked", "owner_attention_required": True, "stores": {}, "diagnostic": None,
              "refreshed_run": None, "refreshed_storage": {}, "cleaned_at": None, "cleanup_elapsed_seconds": None}
    try:
        deadline = min(deadline, clock() + CLEANUP_WALL_SECONDS) if deadline is not None else clock() + CLEANUP_WALL_SECONDS
        require_guard()
        if (not isinstance(state, PrivateState) or not state.capture_verified or not state.encrypted_verified
                or state.latest_active or state.cleanup_state != "not_attempted"):
            raise Fault("state_mismatch", "approval")
        state.cell.spec
        validate_counts(state.request_counts)
        if (state.status not in TERMINAL or state.evidence.get("status") != state.status
                or state.evidence.get("scope_association_sha256") != scope_commitment(state.identity)
                or sha(canonical(state.evidence)) != state.plaintext_sha256):
            raise Fault("state_mismatch", "approval")
        if (not isinstance(approved_sha, dict) or set(approved_sha) != {"plaintext_sha256", "ciphertext_sha256", "scope_approved"}
                or approved_sha.get("plaintext_sha256") != state.plaintext_sha256
                or approved_sha.get("ciphertext_sha256") != state.ciphertext_sha256 or approved_sha.get("scope_approved") is not True
                or not callable(verify_local_approval)):
            raise Fault("approval_missing", "approval")
        try:
            verified = verify_local_approval(state.plaintext_sha256, state.ciphertext_sha256, copy.deepcopy(approved_sha))
        except Exception:
            verified = False
        if verified is not True:
            raise Fault("approval_missing", "approval")
        finish = timestamp(state.identity["finishedAt"])
        age = (utcnow() - finish).total_seconds()
        if not 0 <= age <= APPROVAL_AGE_SECONDS:
            raise Fault("approval_expired", "approval")
        check_time(clock, deadline, CLEANUP_RESERVE_SECONDS)
        session = Session(transport, state, "cleanup", clock, deadline)
        # Fresh terminal confirmation has no waitForFinish and cannot fall back to
        # earlier terminal evidence if this request or validation fails.
        reply = session.call("fresh_terminal")
        fresh = response_data(reply, 200)
        validate_run(fresh, state.cell, state.identity, state.status)
        result["refreshed_run"] = run_receipt(fresh, state.cell)
        all_verified = True
        for kind in STORES:
            try:
                reply = session.call("metadata_" + kind)
                result["refreshed_storage"][kind] = validate_metadata(response_data(reply, 200), kind, state.identity)
            except Fault as exc:
                all_verified = False
                result["diagnostic"] = exc.safe()
        if not all_verified:
            raise Fault("metadata_invalid", "metadata_validation")
        transport.authorize_cleanup(state.identity)
        for kind in STORES:
            try:
                age = (utcnow() - finish).total_seconds()
                if not 0 <= age <= DELETE_AGE_SECONDS:
                    raise Fault("approval_expired", "cleanup")
                reply = session.call("delete_" + kind)
                if not isinstance(reply, Reply) or reply.status != 204:
                    raise Fault("delete_unconfirmed", "cleanup", getattr(reply, "status", None))
                reply = session.call("absence_" + kind)
                if not isinstance(reply, Reply) or reply.status != 404 or reply.body is not None:
                    raise Fault("absence_unconfirmed", "cleanup", getattr(reply, "status", None))
                result["stores"][kind] = "absent"
            except Fault as exc:
                result["stores"][kind] = exc.category if exc.category in ("delete_unconfirmed", "absence_unconfirmed") else "unknown"
                result["diagnostic"] = exc.safe()
        result["cleanup_state"] = "complete" if all(result["stores"].get(k) == "absent" for k in STORES) else "residual"
        result["owner_attention_required"] = result["cleanup_state"] != "complete"
    except Fault as exc:
        result["diagnostic"] = exc.safe()
    except Exception:
        result["diagnostic"] = Fault("transport_error", "cleanup").safe()
    if isinstance(state, PrivateState):
        state.cleanup_state = result["cleanup_state"]
    result["cleaned_at"] = utcnow().isoformat()
    result["cleanup_elapsed_seconds"] = max(0, clock() - phase_started)
    return result


PRIVATE_STATE_KEYS = ("schema_version", "plan_sha256", "cell_id", "identity", "status", "latest_active", "evidence",
                      "request_counts", "plaintext_sha256", "ciphertext_sha256", "capture_verified", "encrypted_verified",
                      "diagnostic", "cleanup_state")


def private_state_bytes(state):
    """RAW private identifiers: root writes these bytes ONLY to 0600 RUNNER_TEMP.

    Never log, upload, commit or pass these bytes to the evidence encryption callback.
    There is no filesystem write in this module and no pickle serialization.
    """
    if not isinstance(state, PrivateState):
        raise Fault("state_mismatch")
    data = {"schema_version": 1, "plan_sha256": sha(state.cell.plan_bytes), "cell_id": state.cell.cell_id,
            **{k: copy.deepcopy(getattr(state, k)) for k in PRIVATE_STATE_KEYS if k not in ("schema_version", "plan_sha256", "cell_id")}}
    raw = canonical(data)
    if len(raw) > 262144:
        raise Fault("state_mismatch")
    restore_private_state(raw, json.loads(state.cell.plan_bytes))
    return raw


def serialize_private_state(state):
    """Root-facing name for the bounded raw-state handoff; never an artifact."""
    return private_state_bytes(state)


def restore_private_state(raw, plan):
    """Verify the exact frozen scope/receipt/counts before creating cleanup transport."""
    try:
        if not isinstance(raw, bytes) or len(raw) > 262144:
            raise Fault("state_mismatch")
        def unique(pairs):
            d = {}
            for k, v in pairs:
                if k in d:
                    raise ValueError()
                d[k] = v
            return d
        def reject(value):
            raise ValueError()
        data = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
        if not isinstance(data, dict) or set(data) != set(PRIVATE_STATE_KEYS) or data["schema_version"] != 1:
            raise Fault("state_mismatch")
        cell = prepare_cell(plan, data["cell_id"])
        if data["plan_sha256"] != sha(cell.plan_bytes):
            raise Fault("state_mismatch")
        validate_counts(data["request_counts"])
        if (data["status"] not in TERMINAL + ACTIVE + ("UNKNOWN",)
                or data["cleanup_state"] not in ("not_attempted", "blocked", "residual", "complete")
                or any(type(data[k]) is not bool for k in ("latest_active", "capture_verified", "encrypted_verified"))
                or not digest(data["plaintext_sha256"]) or not isinstance(data["evidence"], dict)
                or sha(canonical(data["evidence"])) != data["plaintext_sha256"]
                or (data["encrypted_verified"] and not digest(data["ciphertext_sha256"]))):
            raise Fault("state_mismatch")
        diagnostic = data["diagnostic"]
        if diagnostic is not None:
            if not isinstance(diagnostic, dict) or set(diagnostic) != {"category", "stage", "http_status"}:
                raise Fault("state_mismatch")
            if diagnostic != Fault(diagnostic.get("category"), diagnostic.get("stage"), diagnostic.get("http_status")).safe():
                raise Fault("state_mismatch")
        identity = data["identity"]
        if not isinstance(identity, dict):
            raise Fault("state_mismatch")
        if identity:
            required = set(IDENTITY_FIELDS) | {"startedAt", "finishedAt", "build", "options", "status"}
            if set(identity) != required or identity["options"] != cell.spec["options"] or identity["build"] != cell.spec["build"]:
                raise Fault("state_mismatch")
            api_copy = copy.deepcopy(identity)
            api_copy["buildNumber"] = identity["build"]
            api_copy["options"]["maxTotalChargeUsd"] = Decimal("0.12")
            validate_run(api_copy, cell)
        ev = data["evidence"]
        if (ev.get("scope_association_sha256") != (scope_commitment(identity) if identity else None)
                or ev.get("cell_id") != cell.cell_id or ev.get("actor_id") != cell.spec["actor_id"]
                or (data["cleanup_state"] == "not_attempted" and ev.get("request_counts") != data["request_counts"])):
            raise Fault("state_mismatch")
        if data["capture_verified"]:
            if (not identity or data["latest_active"] or data["status"] not in TERMINAL
                    or identity["status"] != data["status"] or ev.get("status") != data["status"]
                    or ev.get("owner_association_verified") is not True
                    or not isinstance(ev.get("storage"), dict) or set(ev["storage"]) != set(STORES)):
                raise Fault("state_mismatch")
        state = PrivateState(cell)
        for key in PRIVATE_STATE_KEYS:
            if key not in ("schema_version", "plan_sha256", "cell_id"):
                setattr(state, key, copy.deepcopy(data[key]))
        return state
    except Fault:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeDecodeError, RecursionError):
        raise Fault("state_mismatch") from None


def execute(plan, cell_id, *, opt_in=False, environ=None, persist_encrypted=None, budget=None,
            transport_factory=None, clock=monotonic, utcnow=lambda: datetime.now(timezone.utc), wait=sleep, deadline=None):
    require_guard()
    if opt_in is not True:
        raise Fault("opt_in_required")
    cell = prepare_cell(plan, cell_id)
    deadline = min(deadline, clock() + CAPTURE_WALL_SECONDS) if deadline is not None else clock() + CAPTURE_WALL_SECONDS
    check_time(clock, deadline, MINIMUM_START_SECONDS)
    if not isinstance(budget, StudyBudget) or budget.plan_sha256 != sha(cell.plan_bytes) or cell_id in budget.claimed:
        raise Fault("budget_exhausted")
    if not callable(persist_encrypted):
        raise Fault("persistence_failed", "evidence")
    env = os.environ if environ is None else environ
    token = env.get("APIFY_TOKEN")
    if not isinstance(token, str) or not 1 <= len(token) <= 512 or any(c.isspace() for c in token):
        raise Fault("token_unavailable")
    factory = HttpTransport if transport_factory is None else transport_factory
    transport = factory(cell, token, clock=clock, deadline=deadline)
    return run_until_capture(transport, cell, persist_encrypted, budget=budget, clock=clock, utcnow=utcnow,
                             wait=wait, deadline=deadline)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpTransport:
    """Fixed-host/header-auth transport. Root creates cleanup mode from 0600 state.

    No arbitrary routes, redirects, retries, aborts, run deletion or enumeration.
    Every attempted request consumes a slot even on ambiguous network failure.
    """
    enable_terminal_settling = True
    def __init__(self, cell, token, *, mode="capture", identity=None, request_counts=None,
                 opener=None, clock=monotonic, deadline=None):
        require_guard()
        if not isinstance(cell, Cell) or mode not in ("capture", "cleanup"):
            raise Fault("invalid_cell")
        self.cell, self.spec, self.mode = cell, cell.spec, mode
        if not isinstance(token, str) or not 1 <= len(token) <= 512 or any(c.isspace() for c in token):
            raise Fault("token_unavailable")
        self._token = token
        self.clock = clock
        cap = CAPTURE_WALL_SECONDS if mode == "capture" else CLEANUP_WALL_SECONDS
        self.deadline = min(deadline, clock() + cap) if deadline is not None else clock() + cap
        self.counts = copy.deepcopy(request_counts) if request_counts is not None else empty_counts()
        validate_counts(self.counts)
        self.identity = {}
        self.latest_active = False
        self.latest_active_status = None
        self.cleanup_authorized = False
        self._open = opener if opener is not None else build_opener(NoRedirect()).open
        if identity is not None:
            self.bind_run(identity)
        if mode == "cleanup" and not self.identity:
            raise Fault("state_mismatch")
    def __repr__(self):
        return "<fixed smoke transport>"
    def bind_run(self, identity):
        if not isinstance(identity, dict) or identity.get("actId") != self.spec["actor_id"] or identity.get("build") != self.spec["build"]:
            raise Fault("scope_mismatch", "scope_validation")
        for k in IDENTITY_FIELDS:
            ident(identity.get(k))
        if self.identity and any(identity[k] != self.identity[k] for k in IDENTITY_FIELDS):
            raise Fault("scope_mismatch", "scope_validation")
        self.identity = copy.deepcopy(identity)
    def authorize_cleanup(self, identity):
        self.bind_run(identity)
        if self.mode != "cleanup" or self.latest_active or self.identity.get("status") not in TERMINAL:
            raise Fault("latest_run_active" if self.latest_active else "state_mismatch", "cleanup")
        self.cleanup_authorized = True
    def request(self, operation, identity, timeout):
        require_guard()
        if self.latest_active:
            raise Fault("latest_run_active", "run_validation")
        if operation not in TIMEOUTS or timeout != TIMEOUTS[operation]:
            raise Fault("invalid_operation")
        if operation != "start":
            if not self.identity or identity != self.identity:
                raise Fault("scope_mismatch", "scope_validation")
        if operation.startswith(("delete_", "absence_")) and not self.cleanup_authorized:
            raise Fault("approval_missing", "cleanup")
        consume(self.counts, operation, self.mode)
        check_time(self.clock, self.deadline, timeout)
        route_deadline = min(self.deadline, self.clock() + timeout)
        method, payload = "GET", None
        if operation == "start":
            opts = self.spec["options"]
            query = {"build": self.spec["build"], "memory": opts["memoryMbytes"], "timeout": 120,
                     "maxTotalChargeUsd": "0.12", "restartOnError": "false"}
            url = API + "/acts/" + self.spec["actor_id"] + "/runs?" + urlencode(query)
            method, payload = "POST", canonical(self.spec["input"])
        elif operation in ("poll", "settle", "fresh_terminal"):
            url = API + "/actor-runs/" + self.identity["id"]
            if operation != "fresh_terminal":
                url += "?waitForFinish=60"
        elif operation == "export":
            fields = list(self.spec["output"]["fields"])
            if self.spec["output"].get("url_source") == "metadata.url":
                fields = [f for f in fields if f != "url"] + ["metadata"]
            query = {"format": "json", "clean": "true", "limit": self.spec["output"]["max_records"] + 1,
                     "fields": ",".join(fields)}
            url = API + "/datasets/" + self.identity["defaultDatasetId"] + "/items?" + urlencode(query)
        else:
            prefix, kind = operation.split("_", 1)
            field_name, route = STORES[kind]
            url = API + "/" + route + "/" + self.identity[field_name]
            if prefix == "delete":
                method = "DELETE"
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "api.apify.com" or parsed.username or parsed.password:
            raise Fault("invalid_operation")
        req = Request(url, data=payload, method=method,
                      headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"})
        response = None
        status = None
        def route_time(stage):
            try:
                check_time(self.clock, route_deadline)
            except Fault:
                raise Fault("deadline_exceeded", stage, status) from None
        try:
            route_time("request")
            response = self._open(req, timeout=timeout)
            status = response.status
            route_time("response_status")
            if type(status) is not int or not 100 <= status <= 599:
                raise Fault("unexpected_http_status", "response_status")
            if operation.startswith("delete_"):
                if status != 204:
                    raise Fault("delete_unconfirmed", "cleanup", status)
                return Reply(204, None)
            if operation.startswith("absence_") and status == 404:
                return Reply(404, None)
            expected = 201 if operation == "start" else 200
            if status != expected:
                raise Fault("unexpected_http_status", "response_status", status)
            body = bytearray()
            while True:
                route_time("response_read")
                chunk = response.read1(min(8192, RESPONSE_LIMIT + 1 - len(body)))
                route_time("response_read")
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > RESPONSE_LIMIT:
                    raise Fault("response_too_large", "response_read", status)
            route_time("json_decode")
            def reject_constant(value):
                raise ValueError()
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError()
                    result[key] = value
                return result
            try:
                decoded = json.loads(body.decode("utf-8"), parse_float=Decimal, parse_constant=reject_constant,
                                     object_pairs_hook=unique_pairs)
            except (ValueError, UnicodeDecodeError, RecursionError):
                raise Fault("invalid_json", "json_decode", status) from None
            # An already decoded same-ID active observation revokes permission
            # before a late deadline or any build/options/scope validation.
            if operation in ("poll", "settle", "fresh_terminal") and self.identity.get("status") in TERMINAL:
                data = decoded.get("data") if isinstance(decoded, dict) else None
                if isinstance(data, dict) and data.get("id") == self.identity["id"] and data.get("status") in ACTIVE:
                    self.latest_active = True
                    self.latest_active_status = data["status"]
                    self.cleanup_authorized = False
                    raise Fault("latest_run_active", "run_validation", status)
            route_time("json_decode")
            return Reply(status, decoded)
        except HTTPError as exc:
            code = exc.code if type(exc.code) is int else None
            exc.close()
            status = code
            route_time("response_status")
            if operation.startswith("absence_") and code == 404:
                return Reply(404, None)
            raise Fault("http_error", "response_status", code) from None
        except (URLError, TimeoutError, OSError):
            raise Fault("connection_error", "request", status) from None
        except Fault:
            raise
        except Exception:
            raise Fault("transport_error", "request", status) from None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
