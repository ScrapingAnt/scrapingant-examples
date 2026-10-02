"""Offline plan by default. Live execution requires a later reviewed cost-guard update."""
import argparse
from decimal import Decimal, InvalidOperation, localcontext
import json
import os
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit
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

# This is source-controlled policy, not a CLI flag, secret, or environment override.
# Enabling it requires a reviewed all-meter bound, pinned build and retention/cleanup policy.
REVIEWED_GUARD = {
    "ready": False,
    "public_build": None,
    "review_reference": None,
    "all_in_upper_bound_usd": None,
    "retention_policy": None,
}
BLOCKERS = (
    "Actual immutable public build and resolved SDK behavior have not been verified.",
    "Retained KV, queue, session/statistics/error metadata bytes have no reviewed upper bound.",
    "Seven-day unnamed expiry is not guaranteed: official latest-ten retention guidance conflicts.",
    "Post-run export/read/transfer volumes and termination accounting are not fully bounded.",
    "Retention duration or cleanup deadline has no reviewed bound; deletion would require separate owner approval.",
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


def build_plan(build=None):
    if build is not None:
        validate_build(build)
    with localcontext() as context:
        context.prec = 28
        nominal_compute = Decimal("120") * Decimal("0.20") / Decimal("3600")
    return {
        "schema_version": 1,
        "evidence_type": "unexecuted_plan",
        "provider_calls_performed": 0,
        "actor": ACTOR,
        "source_checked_on": "2026-10-02",
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
        "all_in_upper_bound_usd": None,
        "nominal_compute_only_usd": str(nominal_compute),
        "nominal_compute_is_all_in_bound": False,
        "retention_upper_bound_hours": None,
        "readiness": {"ready": False, "blockers": list(BLOCKERS)},
        "authentication_preview": "Authorization: Bearer [REDACTED]; environment only after readiness",
        "acceptance_definition": "One validated AA101 record per owned fixture; fixture plus SKU is the unique key.",
        "limitations": [
            "This payload has not been executed and provides no consumption, invoice or savings evidence.",
            "A run cap does not bound storage retention or later export/operation charges.",
            "1024MB times 120 seconds is only a nominal compute calculation; overhead is unresolved.",
            "No build, account ceiling, storage deletion or cleanup has been configured by this package.",
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


def execute_live(build, *, opt_in=False, environ=None, transport=None):
    if opt_in is not True:
        raise PolicyError("Live execution requires explicit opt-in.")
    plan = build_plan(build)
    require_readiness(build)  # Must precede even reading the token environment variable.
    environment = os.environ if environ is None else environ
    token = environment.get("APIFY_TOKEN")
    if not isinstance(token, str) or not token or len(token) > 4096 or any(
            ord(character) < 33 or ord(character) > 126 for character in token):
        raise PolicyError("The narrowly supplied token environment variable is missing or invalid.")
    return orchestrate(plan, token, HttpTransport(build) if transport is None else transport)


def orchestrate(plan, token, transport):
    """One run with bounded reads. A real transport independently enforces readiness."""
    try:
        build = plan["options"]["build"]
        validate_build(build)
        if plan != build_plan(build):
            raise PolicyError("The plan differs from the fixed owned-fixture scope.")
    except (KeyError, TypeError):
        raise PolicyError("The plan is invalid.") from None
    start_url = API + "/actors/apify~web-scraper/runs?" + urlencode(plan["options"])
    run = safe_request(transport, "POST", start_url, plan["input"], token)
    run = validate_run(run, build)
    run_id = safe_identifier(run.get("id"))
    for _ in range(POLL_LIMIT):
        if run["status"] in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            break
        run = validate_run(safe_request(transport, "GET", API + "/actor-runs/" + run_id +
                                       "?waitForFinish=60", None, token), build)
        if safe_identifier(run.get("id")) != run_id:
            raise PolicyError("Run polling returned an inconsistent response.")
    if run["status"] != "SUCCEEDED":
        raise PolicyError("The single run did not report success within the bounded poll count; no restart attempted.")
    dataset_id = safe_identifier(run.get("defaultDatasetId"))
    query = urlencode({"format": "json", "limit": "2", "fields": ",".join(FIELDS)})
    items = safe_request(transport, "GET", API + "/datasets/" + dataset_id + "/items?" + query, None, token)
    accepted = validate_output(items)
    return {
        "evidence_type": "transport_result_not_an_invoice",
        "status": "SUCCEEDED", "returned_output_count": len(items),
        "accepted_output_count": len(accepted), "records": accepted,
        "all_in_cost_reconciled": False,
        "limitations": ["Post-run charges are not reconciled; no account/provider identifiers are exported."],
    }


def safe_request(transport, method, url, payload, token):
    try:
        return transport.request(method, url, payload, token)
    except Exception:
        # Even exceptions from HTTP libraries may contain URLs, tokens, headers or full bodies.
        raise PolicyError("HTTP request failed or returned an invalid response; no automatic retry attempted.") from None


def safe_identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{1,64}", value):
        raise PolicyError("Provider response contains an invalid resource reference.")
    return value


def validate_run(response, build):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
        raise PolicyError("Provider run response is invalid.")
    run = response["data"]
    status = run.get("status")
    if status not in ("READY", "RUNNING", "TIMING-OUT", "ABORTING", "SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
        raise PolicyError("Provider run status is invalid.")
    options = run.get("options")
    if (run.get("buildNumber") != build or not isinstance(options, dict) or
            options.get("build") != build or
            type(options.get("memoryMbytes")) is not int or options["memoryMbytes"] != 1024 or
            type(options.get("timeoutSecs")) is not int or options["timeoutSecs"] != 120 or
            isinstance(options.get("maxTotalChargeUsd"), bool) or
            str(options.get("maxTotalChargeUsd")) not in ("0.1", "0.10")):
        raise PolicyError("Effective run options did not confirm the requested build and limits.")
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


class HttpTransport:
    """No redirects or retries, bounded response bytes, fixed API routes, closed readiness gate."""
    def __init__(self, build):
        require_readiness(build)
        self.build = build

    def request(self, method, url, payload, token):
        require_readiness(self.build)
        plan = build_plan(self.build)
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        query = dict(pairs)
        start = (method == "POST" and parsed.path == "/v2/actors/apify~web-scraper/runs" and
                 query == plan["options"] and payload == plan["input"])
        poll = (method == "GET" and re.fullmatch(r"/v2/actor-runs/[A-Za-z0-9]{1,64}", parsed.path) and
                query == {"waitForFinish": "60"} and payload is None)
        export = (method == "GET" and re.fullmatch(r"/v2/datasets/[A-Za-z0-9]{1,64}/items", parsed.path) and
                  query == {"format": "json", "limit": "2", "fields": ",".join(FIELDS)} and payload is None)
        if (parsed.scheme != "https" or parsed.netloc != "api.apify.com" or parsed.fragment or
                len(pairs) != len(query) or not (start or poll or export)):
            raise PolicyError("HTTP route is outside the fixed calibration scope.")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=body, method=method,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=65) as response:
                data = response.read(RESPONSE_LIMIT + 1)
            if len(data) > RESPONSE_LIMIT:
                raise PolicyError("HTTP response exceeded the bounded local read size.")
            return json.loads(data.decode("utf-8"))
        except Exception:
            raise PolicyError("HTTP transport stopped; response bodies, headers and identifiers are not printed.") from None


def main(argv=None, *, environ=None, transport=None):
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
            result = execute_live(args.build, opt_in=True, environ=environ, transport=transport)
        else:
            result = build_plan(args.build)
        print(json.dumps(result, indent=2))
        return 0
    except PolicyError as error:
        print("Calibration stopped: " + str(error), file=sys.stderr)
        return 2
    except Exception:
        print("Calibration stopped: unexpected local input or transport error; no response details printed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
