"""Fixed Greenhouse posting adapter. CLI and default demonstrations are offline."""
from datetime import datetime, timezone
import argparse
from email.message import Message
import hashlib
from html.parser import HTMLParser
from html import unescape
import json
from io import BytesIO
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urljoin, urlsplit

ROOT = Path(__file__).resolve().parent
from collector import CollectionError, MAX_BODY_BYTES
import scrapingant_transport as transport

SOURCE_URL = "https://job-boards.greenhouse.io/greenhouse/jobs/8126988?gh_jid=8126988"
HTTP_CANONICAL = "http://job-boards.greenhouse.io/greenhouse/jobs/8126988?gh_jid=8126988"
EMPLOYER = "Greenhouse"
JOB_ID = "8126988"
PARAMETERS = {"url": SOURCE_URL, "browser": "false", "proxy_type": "datacenter",
              "proxy_country": "us", "timeout": "30", "return_page_source": "false"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def utc_stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_stamp(stamp):
    if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
        raise ValueError("invalid observation timestamp")
    datetime.fromisoformat(stamp.replace("Z", "+00:00"))


class SinglePostParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.text_nodes = []
        self.open_nodes = []
        self.canonicals = []
        self.meta = {"og:title": [], "og:description": [], "og:url": []}
        self.forms = []
        self.form_closures = []
        self.html_closed = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in VOID_TAGS:
            self.depth += 1
        kind = "document_title" if tag == "title" else "job_title" if tag == "h1" else None
        if "job__location" in attrs.get("class", "").split():
            kind = "location"
        if kind:
            node = {"kind": kind, "tag": tag, "depth": self.depth, "text": "", "closed": False}
            self.text_nodes.append(node)
            self.open_nodes.append(node)
        if tag == "link" and "canonical" in attrs.get("rel", "").split():
            self.canonicals.append(attrs.get("href", ""))
        if tag == "meta" and attrs.get("property") in self.meta:
            self.meta[attrs["property"]].append(attrs.get("content", ""))
        if tag == "form" and attrs.get("id") == "application-form":
            self.forms.append(attrs)
            self.form_closures.append({"depth": self.depth, "closed": False})

    def handle_data(self, text):
        for node in self.open_nodes:
            node["text"] += text

    def handle_endtag(self, tag):
        if tag == "form":
            for form in self.form_closures:
                if form["depth"] == self.depth:
                    form["closed"] = True
        for node in list(self.open_nodes):
            if node["tag"] == tag and node["depth"] == self.depth:
                node["closed"] = True
                self.open_nodes.remove(node)
        if tag == "html":
            self.html_closed = True
        if tag not in VOID_TAGS:
            self.depth -= 1

    def one_text(self, kind):
        nodes = [node for node in self.text_nodes if node["kind"] == kind]
        if len(nodes) != 1 or not nodes[0]["closed"]:
            raise CollectionError("html_contract")
        value = " ".join(nodes[0]["text"].split())
        if not value:
            raise CollectionError("html_contract")
        return value

    def record(self, observed_utc):
        title, location = self.one_text("job_title"), self.one_text("location")
        document_title = self.one_text("document_title")
        if (not self.html_closed or self.open_nodes or self.depth != 0 or
                document_title != f"Job Application for {title} at {EMPLOYER}" or
                len(self.canonicals) != 1 or self.canonicals[0] not in (SOURCE_URL, HTTP_CANONICAL) or
                self.meta != {"og:title": [title], "og:description": [location], "og:url": [SOURCE_URL]} or
                len(self.forms) != 1 or not self.form_closures[0]["closed"] or self.forms[0].get("method", "").lower() != "get" or
                not self.forms[0].get("action") or
                urljoin(SOURCE_URL, self.forms[0].get("action", "")) != SOURCE_URL):
            raise CollectionError("html_contract")
        return {"jobID": JOB_ID, "title": title, "employer": EMPLOYER, "location": location,
                "sourceURL": SOURCE_URL, "applicationURL": SOURCE_URL,
                "observedUTC": observed_utc, "sourcePostedDate": None}


def collect_one(*, fetch, observed_utc=None):
    if observed_utc is not None:
        validate_stamp(observed_utc)
    counters = {"requested_pages": 1, "fetched_pages": 0, "accepted_pages": 0,
                "unique_records": 0, "failures": 0}
    result = {"source": SOURCE_URL, "employer": EMPLOYER, "complete": False,
              "completeness_scope": "one_selected_posting_page", "board_inventory_complete": False,
              "max_pages": 1, "counters": counters, "records": [], "failures": []}
    try:
        html = fetch(SOURCE_URL)
        counters["fetched_pages"] = 1
        if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_BODY_BYTES:
            raise CollectionError("body_limit")
        stamp = observed_utc or utc_stamp()
        parser = SinglePostParser()
        parser.feed(html)
        parser.close()
        record = parser.record(stamp)
    except CollectionError as error:
        result["failures"] = [{"page": 1, "code": str(error)}]
        counters["failures"] = 1
        return result
    result.update(complete=True, observedUTC=stamp, records=[record],
                  source_metadata={"canonical_url": parser.canonicals[0],
                                   "canonical_scheme_differs": parser.canonicals[0] == HTTP_CANONICAL,
                                   "application_url_semantics": "observed hosted form page; no submission validation"})
    counters.update(accepted_pages=1, unique_records=1)
    return result


class CapturedResponse:
    def __init__(self, status, headers, body):
        self.status, self.headers = status, headers
        self.body = BytesIO(body)

    def read(self, size): return self.body.read(size)
    def __enter__(self): return self
    def __exit__(self, *args): self.body.close()


def contains_credential_echo(value, key):
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    for _ in range(4):
        if key in text:
            return True
        decoded = unescape(text).replace(chr(92) * 2, chr(92))
        decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match[1], 16)), decoded)
        escapes = {'"': '"', '/': '/', 'b': chr(8), 'f': chr(12), 'n': chr(10), 'r': chr(13), 't': chr(9)}
        for escaped, character in escapes.items():
            decoded = decoded.replace(chr(92) + escaped, character)
        if decoded == text:
            break
        text = decoded
    return key in text


class OneDispatchObserver:
    """Capture receipt/body before the unchanged transport accepts a response."""
    def __init__(self, output_dir, *, delegate):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.delegate = delegate
        self.calls = 0
        self.receipt = {"source_url": SOURCE_URL, "endpoint": transport.ENDPOINT,
                        "parameters": PARAMETERS, "expected_documented_credits": 1,
                        "provider_dispatches": 0, "actual_credits": None,
                        "requests": 0, "actual_receipt_credits": None, "accepted": False,
                        "scope": "one selected published job HTML page; raw only; no board inventory or refresh",
                        "raw_body_retention": "caller-local only; do not commit or redistribute full job/form/tracking HTML"}
        self.save()

    def save(self, key=None):
        encoded = json.dumps(self.receipt, indent=2) + "\n"
        if key and contains_credential_echo(encoded, key):
            raise CollectionError("credential_echo_detected")
        (self.output_dir / "receipt.json").write_text(encoded)

    def open(self, request, timeout):
        parts = urlsplit(request.full_url)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        endpoint = parts._replace(query="", fragment="").geturl()
        key = request.get_header("X-api-key")
        if (self.calls or request.get_method() != "GET" or endpoint != transport.ENDPOINT or
                parts.fragment or len(dict(pairs)) != len(pairs) or dict(pairs) != PARAMETERS or timeout != 35 or
                not isinstance(key, str) or not key):
            raise CollectionError("dispatch_not_allowed")
        self.calls += 1
        self.receipt.update(provider_dispatches=1, requests=1, dispatched_at_utc=datetime.now(timezone.utc).isoformat())
        self.save(key)
        try:
            try:
                response = self.delegate.open(request, timeout=timeout)
            except HTTPError as error:
                response = error
            with response:
                headers = response.headers
                names = {"target_status": "Ant-page-status-code", "credit_receipt": "Ant-credits-cost",
                         "target_content_type": "Ant-original-header-content-type", "outer_content_type": "Content-Type"}
                selected, counts = {}, {}
                sanitized_headers = Message()
                unsafe_header = False
                for field, name in names.items():
                    if hasattr(headers, "get_all"):
                        values = headers.get_all(name, []) or []
                    else:
                        value = headers.get(name)
                        values = [] if value is None else list(value) if isinstance(value, (list, tuple)) else [value]
                    counts[field] = len(values)
                    echoed = any(contains_credential_echo(value, key) for value in values)
                    if echoed:
                        unsafe_header = True
                    selected[field] = values[0] if len(values) == 1 and not echoed and isinstance(values[0], str) else None
                    if selected[field] is not None:
                        sanitized_headers[name] = selected[field]
                credits = selected["credit_receipt"]
                self.receipt.update(http_status=response.status,
                                    **selected,
                                    allowlisted_header_counts=counts,
                                    duplicate_credit_receipt=counts["credit_receipt"] > 1,
                                    actual_credits=int(credits) if credits and re.fullmatch(r"\d+", credits) else None,
                                    actual_receipt_credits=int(credits) if credits and re.fullmatch(r"\d+", credits) else None,
                                    body_retained=False)
                self.save(key)
                body = response.read(MAX_BODY_BYTES + 1)
                unsafe_echo = unsafe_header or contains_credential_echo(body, key)
                self.receipt.update(response_bytes=len(body), response_sha256=hashlib.sha256(body).hexdigest(),
                                    full_body_captured=len(body) <= MAX_BODY_BYTES,
                                    body_hash_scope="full response bytes as received" if len(body) <= MAX_BODY_BYTES else "bounded prefix; full body unavailable",
                                    completed_at_utc=datetime.now(timezone.utc).isoformat())
                if unsafe_echo:
                    self.receipt["error"] = "credential_echo_detected"
                    self.save(key)
                    raise CollectionError("credential_echo_detected")
                (self.output_dir / "response.html").write_bytes(body)
                self.receipt["body_retained"] = True
                self.save(key)
                return CapturedResponse(response.status, sanitized_headers, body)
        except (URLError, TimeoutError, OSError):
            self.receipt.update(error="api_transport_failed", completed_at_utc=datetime.now(timezone.utc).isoformat())
            self.save(key)
            raise CollectionError("api_transport_failed") from None


def record_oracle_matches(records):
    expected = json.loads((ROOT / "fixtures/greenhouse-single-post-expected-record.json").read_text())
    if len(records) != 1:
        return False
    return ({field: value for field, value in records[0].items() if field != "observedUTC"} ==
            {field: value for field, value in expected.items() if field != "observedUTC"})


def managed_collection(observer, *, observed_utc=None):
    def fetch(url):
        try:
            html = transport.managed_html(url, browser="false", opener=observer)
        except (KeyError, ValueError):
            raise CollectionError("managed_preflight_failed") from None
        if observer.receipt.get("credit_receipt") != "1":
            raise CollectionError("credit_receipt_unaccepted")
        return html
    result = collect_one(fetch=fetch, observed_utc=observed_utc)
    result["semantic_oracle_matches"] = record_oracle_matches(result["records"])
    observer.receipt["accepted"] = bool(result["complete"] and observer.calls == 1 and
                                        observer.receipt.get("actual_receipt_credits") == 1 and
                                        result["semantic_oracle_matches"])
    observer.save()
    return result


def verify_source(path):
    contract = json.loads((ROOT / "greenhouse-single-post-contract.json").read_text())
    expected = json.loads((ROOT / "fixtures/greenhouse-single-post-expected-record.json").read_text())
    with Path(path).open("rb") as source:
        body = source.read(MAX_BODY_BYTES + 1)
    digest = hashlib.sha256(body).hexdigest()
    matched = (len(body) == contract["full_source_HTML"]["bytes"] and
               digest == contract["full_source_HTML"]["sha256"])
    if len(body) <= MAX_BODY_BYTES:
        try:
            html = body.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            result = {"source": SOURCE_URL, "complete": False, "records": [],
                      "completeness_scope": "one_selected_posting_page", "board_inventory_complete": False,
                      "failures": [{"code": "invalid_utf8"}]}
        else:
            result = collect_one(fetch=lambda url: html, observed_utc=expected["observedUTC"])
    else:
        result = {"source": SOURCE_URL, "complete": False, "records": [],
                  "completeness_scope": "one_selected_posting_page", "board_inventory_complete": False,
                  "failures": [{"code": "body_limit"}]}
    oracle_matches = record_oracle_matches(result["records"])
    result["semantic_preflight"] = {"accepted": result["complete"] and oracle_matches,
                                    "matches_frozen_full_body": matched, "literal_oracle_matches": oracle_matches,
                                    "matches_frozen_byte_count": len(body) == contract["full_source_HTML"]["bytes"],
                                    "input_bytes": len(body), "input_sha256": digest,
                                    "input_hash_scope": "full local input bytes" if len(body) <= MAX_BODY_BYTES else "bounded prefix; full file exceeds body limit",
                                    "hash_acceptance_policy": "diagnostic only; exact semantic contract and literal record oracle determine acceptance",
                                    "observedUTC_semantics": "offline oracle timestamp; acquisition metadata is separately recorded"}
    result["execution"] = {"mode": "frozen_local_source_verification", "provider_dispatches": 0, "network_requests": 0}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-source", type=Path, help="Validate a local HTML file; no network or provider dispatch")
    args = parser.parse_args()
    if args.verify_source:
        result = verify_source(args.verify_source)
        print(json.dumps(result, indent=2))
        return 0 if result["semantic_preflight"]["accepted"] else 2
    body = (ROOT / "fixtures/greenhouse-single-post.html").read_text()
    result = collect_one(fetch=lambda url: body, observed_utc="2026-10-12T08:26:43Z")
    result["execution"] = {"mode": "owned_source_shaped_fixture", "provider_dispatches": 0}
    print(json.dumps(result, indent=2))
    return 0 if result["complete"] and record_oracle_matches(result["records"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
