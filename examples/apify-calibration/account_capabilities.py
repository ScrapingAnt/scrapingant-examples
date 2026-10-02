"""Closed, read-only account-capability probe; offline preparation only."""
import argparse
from decimal import Decimal, InvalidOperation, localcontext
import json
import os
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

# Review must change source before a separately approved read; no environment override.
CAPABILITIES_READY = False  # Closed immediately after the one reviewed two-GET observation.
# The limits schema says Gbytes, without defining its relation to scheduled memory Mbytes.
# None is deliberate. A later source review may approve an explicit 1000 or 1024 mapping.
REVIEWED_MBYTES_PER_GBYTE = None
CONSERVATIVE_MBYTES_PER_GBYTE = 1000  # Minimum of the decimal/binary candidate conventions; an inference.
URLS = ("https://api.apify.com/v2/users/me", "https://api.apify.com/v2/users/me/limits")
RESPONSE_LIMIT = 131072
ROUTE_SECONDS, WALL_SECONDS = 10, 30
PUBLIC_PLAN_LABELS = ("FREE", "STARTER", "SCALE", "BUSINESS")
TECHNICAL_FIELDS = ("maxActorMemoryGbytes", "maxConcurrentActorJobs", "actorMemoryGbytes", "activeActorJobCount")
CATEGORIES = ("guard_closed", "opt_in_required", "invalid_arguments", "authentication_rejected", "route_rejected",
              "http_error", "redirect_refused", "unexpected_status", "invalid_json", "response_too_large",
              "deadline_exceeded", "connection_error", "transport_error")


class ProbeError(Exception):
    def __init__(self, category, status=None):
        super().__init__("Account capability probe stopped; only sanitized diagnostics are retained.")
        self.category = category if type(category) is str and category in CATEGORIES else "transport_error"
        self.status = status if type(status) is int and 100 <= status <= 599 else None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def project(user, account):
    """Private technical allowlist only; extra provider fields never enter the returned receipt."""
    user, account = object_field(user, "data"), object_field(account, "data")
    features = object_field(user, "effectivePlatformFeatures")
    paying = boolean(user.get("isPaying"))
    enabled = {name: boolean(object_field(features, name).get("isEnabled")) for name in ("ACTORS", "STORAGE")}
    tier = object_field(user, "plan").get("tier")
    tier = tier if type(tier) is str and tier in PUBLIC_PLAN_LABELS else None
    maximum, current = object_field(account, "limits"), object_field(account, "current")
    technical = {"maxActorMemoryGbytes": number(maximum.get("maxActorMemoryGbytes")),
                 "maxConcurrentActorJobs": number(maximum.get("maxConcurrentActorJobs"), integer=True),
                 "actorMemoryGbytes": number(current.get("actorMemoryGbytes")),
                 "activeActorJobCount": number(current.get("activeActorJobCount"), integer=True)}
    memory = difference(technical["maxActorMemoryGbytes"], technical["actorMemoryGbytes"])
    jobs = difference(technical["maxConcurrentActorJobs"], technical["activeActorJobCount"])
    complete = paying is not None and all(value is not None for value in (*enabled.values(), *technical.values()))
    conversion = REVIEWED_MBYTES_PER_GBYTE
    conversion = conversion if type(conversion) is int and conversion in (1000, 1024) else None
    feasible = {"one_job_at_memoryMbytes_8192": None, "one_job_at_memoryMbytes_32768": None}
    if complete and conversion is not None:
        with localcontext() as context:
            context.prec = 400
            for field, target in zip(feasible, (8192, 32768)):
                feasible[field] = all(enabled.values()) and jobs >= 1 and memory >= Decimal(target) / conversion
    conservative = {"one_job_at_memoryMbytes_4096": None, "one_job_at_memoryMbytes_8192": None,
                    "one_job_at_memoryMbytes_32768": None}
    if complete:
        with localcontext() as context:
            context.prec = 400
            for field, target in zip(conservative, (4096, 8192, 32768)):
                conservative[field] = all(enabled.values()) and jobs >= 1 and memory >= Decimal(target) / CONSERVATIVE_MBYTES_PER_GBYTE
    return {"evidence_type": "private_account_capability_snapshot", "paying": paying, "plan_tier": tier,
            "features": enabled, "technical": {field: json_number(value) for field, value in technical.items()},
            "headroom": {"actorMemoryGbytes": json_number(memory), "concurrentActorJobs": json_number(jobs)},
            "schema_complete": complete, "execution_ready": False,
            "memory_conversion_Mbytes_per_Gbyte": conversion, "feasibility": feasible,
            "conservative_feasibility": conservative,
            "limitations": ["Private technical snapshot; do not publish raw account limits or current allocations.",
                            "Combined memory and job headroom are not a per-run allocation limit or reservation.",
                            "No spend, balance, invoice, run authorization or study budget is verified."]}


def object_field(value, field):
    item = value.get(field) if isinstance(value, dict) else None
    return item if isinstance(item, dict) else {}


def boolean(value):
    return value if type(value) is bool else None


def number(value, *, integer=False):
    if integer:
        return value if type(value) is int and 0 <= value <= 1000000 else None
    if type(value) not in (int, float, Decimal) or len(str(value)) > 48: return None
    try:
        numeric = Decimal(str(value))
        if not numeric.is_finite() or not 0 <= numeric <= 1048576: return None
        if numeric and float(numeric) == 0: return None
        return numeric if numeric else Decimal(0)
    except (InvalidOperation, ValueError, OverflowError):
        return None


def difference(maximum, current):
    if maximum is None or current is None: return None
    with localcontext() as context:
        context.prec = 400  # Accepted magnitudes/representations fit; preserve tiny capacity shortfalls.
        return maximum - current


def json_number(value):
    if value is None: return None
    return int(value) if value == int(value) else float(value)


def probe(transport):
    """Private in-memory projection. Only public_result may cross the CLI/execution boundary."""
    result = {**project(None, None), "outcome": "read_failed", "requests_attempted": 0, "reads": []}
    responses = []
    for stage, url in zip(("identity", "limits"), URLS):
        result["requests_attempted"] += 1
        try:
            responses.append(transport.get(url))
            result["reads"].append({"stage": stage, "http_status": 200, "category": "ok"})
        except Exception as error:
            safe = error if isinstance(error, ProbeError) else ProbeError("transport_error")
            result["reads"].append({"stage": stage, "http_status": safe.status, "category": safe.category})
            return result
    projected = project(*responses)
    return {**result, **projected, "outcome": "complete" if projected["schema_complete"] else "incomplete_schema"}


def public_result(private):
    """Construct a fresh public allowlist; never forward raw account capacity values or messages."""
    tier, outcome = private.get("plan_tier"), private.get("outcome")
    features, capacity = object_field(private, "features"), object_field(private, "conservative_feasibility")
    reads = []
    for item in private.get("reads", [])[:2]:
        item = item if isinstance(item, dict) else {}
        stage, category, status = (item.get(key) for key in ("stage", "category", "http_status"))
        reads.append({"stage": stage if stage in ("identity", "limits") else None,
                      "category": category if category in CATEGORIES + ("ok",) else "transport_error",
                      "http_status": status if type(status) is int and 100 <= status <= 599 else None})
    attempts = private.get("requests_attempted")
    return {"evidence_type": "public_derived_account_capabilities", "paying": boolean(private.get("paying")),
            "starter_plan_confirmed": (tier == 'STARTER') if type(tier) is str and tier in PUBLIC_PLAN_LABELS else None,
            "features": {name: boolean(features.get(name)) for name in ("ACTORS", "STORAGE")},
            "schema_complete": boolean(private.get("schema_complete")), "execution_ready": False,
            "memory_unit_mapping": "unverified", "conservative_conversion_Mbytes_per_Gbyte": CONSERVATIVE_MBYTES_PER_GBYTE,
            "feasibility": {field: boolean(capacity.get(field)) for field in
                            ("one_job_at_memoryMbytes_4096", "one_job_at_memoryMbytes_8192", "one_job_at_memoryMbytes_32768")},
            "outcome": outcome if outcome in CATEGORIES + ("complete", "incomplete_schema", "read_failed", "unexecuted_plan") else "read_failed",
            "requests_attempted": attempts if type(attempts) is int and 0 <= attempts <= 2 else None,
            "reads": reads,
            "limitations": ["Only derived states are public; raw account capacity values stay in memory.",
                            "1000 Mbytes/Gbyte is a conservative inference for the 1000/1024 candidate conventions; API units remain unverified.",
                            "Combined account capacity does not prove a per-run limit, reservation, spend or run authorization."]}


class AccountTransport:
    def __init__(self, token, *, opener=None):
        require_guard()
        validate_token(token)
        self._token, self._calls = token, 0
        self._deadline = monotonic() + WALL_SECONDS
        self._opener = build_opener(NoRedirect()) if opener is None else opener

    def get(self, url):
        require_guard()
        if self._calls >= 2 or url != URLS[self._calls]: raise ProbeError("route_rejected")
        remaining = self._deadline - monotonic()
        if remaining <= 0: raise ProbeError("deadline_exceeded")
        self._calls += 1  # An ambiguous or failed attempt consumes its slot; never retry.
        deadline = min(self._deadline, monotonic() + ROUTE_SECONDS)
        request = Request(url, method="GET", headers={"Authorization": "Bearer " + self._token,
                          "Accept": "application/json", "Accept-Encoding": "identity"})
        status = None
        try:
            with self._opener.open(request, timeout=min(ROUTE_SECONDS, remaining)) as response:
                status = response.status
                if type(status) is not int or status != 200: raise ProbeError("unexpected_status", status)
                raw = bytearray()
                reader = getattr(response, "read1", response.read)
                while True:
                    if monotonic() >= deadline: raise ProbeError("deadline_exceeded", status)
                    chunk = reader(min(8192, RESPONSE_LIMIT + 1 - len(raw)))
                    if monotonic() > deadline: raise ProbeError("deadline_exceeded", status)
                    if not chunk: break
                    raw.extend(chunk)
                    if len(raw) > RESPONSE_LIMIT: raise ProbeError("response_too_large", status)
            try:
                parsed = json.loads(raw.decode("utf-8"), parse_float=Decimal, parse_constant=reject_constant,
                                    object_pairs_hook=unique_object)
                if monotonic() > deadline: raise ProbeError("deadline_exceeded", status)
                return parsed
            except (ValueError, UnicodeError, RecursionError):
                raise ProbeError("invalid_json", status) from None
        except HTTPError as error:
            status = error.code
            error.close()  # No raw error-body reads, messages, headers or URLs.
            category = "redirect_refused" if type(status) is int and 300 <= status <= 399 else "http_error"
            raise ProbeError(category, status) from None
        except ProbeError:
            raise
        except (URLError, OSError):
            raise ProbeError("connection_error", status) from None
        except Exception:
            raise ProbeError("transport_error", status) from None


def reject_constant(value):
    raise ValueError


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError
        result[key] = value
    return result


def require_guard():
    if CAPABILITIES_READY is not True: raise ProbeError("guard_closed")


def validate_token(token):
    if type(token) is not str or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ProbeError("authentication_rejected")


def execute(*, opt_in=False, environ=None, transport=None):
    if opt_in is not True: raise ProbeError("opt_in_required")
    require_guard()
    try: token = (os.environ if environ is None else environ).get("APIFY_TOKEN")
    except Exception: raise ProbeError("authentication_rejected") from None
    validate_token(token)
    return public_result(probe(AccountTransport(token) if transport is None else transport))


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ProbeError("invalid_arguments")


def main(argv=None, *, environ=None):
    parser = SafeParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--execute", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.execute:
            result = execute(opt_in=True, environ=environ)
            code = 0 if result["outcome"] == "complete" else 2
        else:
            result = public_result({**project(None, None), "outcome": "unexecuted_plan", "requests_attempted": 0, "reads": []})
            result.update(maximum_requests=2, methods=["GET"], routes=["/users/me", "/users/me/limits"],
                          guard_ready=CAPABILITIES_READY is True)
            code = 0
    except Exception as error:
        safe = error if isinstance(error, ProbeError) else ProbeError("transport_error")
        result, code = public_result({**project(None, None), "outcome": safe.category, "requests_attempted": 0, "reads": []}), 2
    print(json.dumps(result, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
