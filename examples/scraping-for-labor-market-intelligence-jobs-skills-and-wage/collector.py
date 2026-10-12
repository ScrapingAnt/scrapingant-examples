"""Bounded HTML collector for the owned Northstar fixture's fixed contract.

Replace SourcePolicy and ListingParser for another permitted source after
inspecting its schema. A transport change does not make an adapter universal.
"""
import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.error import HTTPError, URLError

from schema import CONTENT_FIELDS, utc_now, validate_record

MAX_BODY_BYTES = 1_000_000


class CollectionError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Explicitly reject redirects before fetching an unapproved destination.
        return None


def direct_html(url):
    # Ignore inherited proxy settings for the loopback demonstration.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, headers={"User-Agent": "owned-careers-demo/1"}),
                         timeout=30) as response:
            if response.status != 200:
                raise CollectionError(f"http_{response.status}")
            if response.headers.get_content_type() != "text/html":
                raise CollectionError("not_html")
            data = response.read(MAX_BODY_BYTES + 1)
            if len(data) > MAX_BODY_BYTES:
                raise CollectionError("body_limit")
            try:
                return data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise CollectionError("invalid_utf8") from None
    except HTTPError as error:
        raise CollectionError(f"http_{error.code}") from None
    except (URLError, TimeoutError):
        raise CollectionError("transport_failed") from None


@dataclass(frozen=True)
class SourcePolicy:
    start_url: str
    employer: str = "Northstar Demonstration Labs"

    def __post_init__(self):
        parts = urlsplit(self.start_url)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        if (parts.scheme not in ("http", "https") or not parts.netloc or
                parts.username or parts.password or parts.fragment or
                parts.path != "/careers/roles" or len(dict(pairs)) != len(pairs) or
                dict(pairs).get("page") != "1"):
            raise ValueError("start_url must match this fixture's page-1 contract")
        # HTTP is permitted only for the owned loopback example.
        if parts.scheme == "http" and parts.hostname != "127.0.0.1":
            raise ValueError("non-loopback sources must use HTTPS")

    @property
    def origin(self):
        parts = urlsplit(self.start_url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", ""))

    def page_url(self, page):
        parts = urlsplit(self.start_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["page"] = str(page)
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           urlencode(sorted(query.items())), ""))

    def accept_next(self, href, current_url, expected_page):
        candidate = urljoin(current_url, href)
        parts = urlsplit(candidate)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        if parts.username or parts.password or parts.fragment or len(dict(pairs)) != len(pairs):
            return False
        canonical = urlunsplit((parts.scheme, parts.netloc, parts.path,
                                urlencode(sorted(pairs)), ""))
        return canonical == self.page_url(expected_page)

    def record_url(self, value, page_url, job_id, kind):
        candidate = urljoin(page_url, value) if value else ""
        expected = f"{self.origin}/careers/{kind}/{job_id}"
        return candidate if candidate == expected else ""


class ListingParser(HTMLParser):
    """Parse only the versioned owned HTML contract; fail closed on drift."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.envelopes = []
        self.cards = []
        self.next_links = []
        self.inside = False
        self.card = None
        self.capture = None
        self.capture_tag = None
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "section" and attrs.get("id") == "careers-list":
            self.envelopes.append(attrs)
            self.inside = True
        if not self.inside:
            return
        if tag == "article" and "posting" in classes:
            if self.card is not None:
                self.invalid = True
            self.card = {"jobID": attrs.get("data-job-id", "")}
        if self.card is not None:
            if "job-title" in classes or "job-location" in classes:
                field = "title" if "job-title" in classes else "location"
                if field in self.card:
                    self.invalid = True
                self.card[field] = ""
                self.capture, self.capture_tag = field, tag
            if tag == "a" and "job-source" in classes:
                if "sourceURL" in self.card:
                    self.invalid = True
                self.card["sourceURL"] = attrs.get("href", "")
            if tag == "a" and "job-apply" in classes:
                if "applicationURL" in self.card:
                    self.invalid = True
                self.card["applicationURL"] = attrs.get("href", "")
            if tag == "time" and "job-posted" in classes:
                if "sourcePostedDate" in self.card:
                    self.invalid = True
                self.card["sourcePostedDate"] = attrs.get("datetime", "")
        if tag == "a" and "next" in attrs.get("rel", "").split():
            self.next_links.append(attrs.get("href", ""))

    def handle_data(self, data):
        if self.card is not None and self.capture:
            self.card[self.capture] += data

    def handle_endtag(self, tag):
        if tag == self.capture_tag:
            self.capture = self.capture_tag = None
        if tag == "article" and self.card is not None:
            self.cards.append(self.card)
            self.card = None
        if tag == "section" and self.inside:
            self.inside = False

    def validate_page(self, policy, page, total):
        if self.card is not None or self.inside or self.invalid or len(self.envelopes) != 1:
            raise CollectionError("listing_envelope")
        envelope = self.envelopes[0]
        try:
            declared_page = int(envelope["data-page"])
            declared_total = int(envelope["data-total-pages"])
        except (ValueError, KeyError):
            raise CollectionError("page_metadata") from None
        if (envelope.get("data-schema") != "northstar-jobs-v1" or
                envelope.get("data-employer") != policy.employer or declared_page != page or
                declared_total < 1 or (total is not None and declared_total != total)):
            raise CollectionError("page_metadata")
        status = envelope.get("data-status")
        if not self.cards:
            if status != "empty" or page != 1 or declared_total != 1 or self.next_links:
                raise CollectionError("unconfirmed_empty")
        elif status != "open":
            raise CollectionError("listing_status")
        if page > declared_total or len(self.next_links) != (1 if page < declared_total else 0):
            raise CollectionError("pagination_shape")
        return declared_total


def collect(policy, *, max_pages=3, fetch=direct_html, observed_utc=None):
    if not 1 <= max_pages <= 20:
        raise ValueError("max_pages must be between 1 and 20")
    stamp = observed_utc or utc_now()
    # Validate caller-provided observation timestamps before any acquisition.
    probe = {"jobID": "NS-000", "title": "probe", "employer": policy.employer,
             "location": "probe", "sourceURL": policy.origin + "/careers/jobs/NS-000",
             "applicationURL": policy.origin + "/careers/apply/NS-000",
             "observedUTC": stamp, "sourcePostedDate": None}
    if validate_record(probe):
        raise ValueError("invalid observation timestamp")
    counters = dict(requested_pages=0, fetched_pages=0, accepted_pages=0, cards_seen=0,
                    valid_cards=0, duplicate_cards=0, conflicting_ids=0, rejected_cards=0,
                    unique_records=0)
    records, failures, conflicts, visited = {}, [], set(), set()
    total, page, terminal = None, 1, False
    while page <= max_pages:
        url = policy.page_url(page)
        if url in visited:
            failures.append({"page": page, "code": "pagination_loop"})
            break
        visited.add(url)
        counters["requested_pages"] += 1
        try:
            html = fetch(url)
            counters["fetched_pages"] += 1
            if len(html.encode("utf-8")) > MAX_BODY_BYTES:
                raise CollectionError("body_limit")
            parser = ListingParser()
            parser.feed(html)
            parser.close()
            total = parser.validate_page(policy, page, total)
        except CollectionError as error:
            failures.append({"page": page, "code": str(error)})
            break
        counters["accepted_pages"] += 1
        for index, raw in enumerate(parser.cards, 1):
            counters["cards_seen"] += 1
            job_id = raw.get("jobID", "")
            record = {"jobID": job_id, "title": " ".join(raw.get("title", "").split()),
                      "employer": policy.employer,
                      "location": " ".join(raw.get("location", "").split()),
                      "sourceURL": policy.record_url(raw.get("sourceURL"), url, job_id, "jobs"),
                      "applicationURL": policy.record_url(raw.get("applicationURL"), url, job_id, "apply"),
                      "observedUTC": stamp, "sourcePostedDate": raw.get("sourcePostedDate")}
            errors = validate_record(record)
            if errors:
                counters["rejected_cards"] += 1
                failures.append({"page": page, "card": index, "code": "record_invalid", "fields": errors})
                continue
            counters["valid_cards"] += 1
            if job_id in conflicts:
                continue
            if job_id in records:
                if all(records[job_id][field] == record[field] for field in CONTENT_FIELDS):
                    counters["duplicate_cards"] += 1
                else:
                    conflicts.add(job_id)
                    counters["conflicting_ids"] += 1
                    del records[job_id]
                    failures.append({"page": page, "card": index, "code": "conflicting_id", "jobID": job_id})
            else:
                records[job_id] = record
        if page == total:
            terminal = True
            break
        href = parser.next_links[0]
        candidate = urljoin(url, href)
        if candidate in visited:
            failures.append({"page": page, "code": "pagination_loop"})
            break
        if not policy.accept_next(href, url, page + 1):
            failures.append({"page": page, "code": "next_url_rejected"})
            break
        page += 1
    if not terminal and not failures:
        failures.append({"page": page, "code": "page_budget"})
    counters["unique_records"] = len(records)
    counters["failures"] = len(failures)
    return {"source": policy.start_url, "employer": policy.employer, "observedUTC": stamp,
            "complete": terminal and not failures, "counters": counters,
            "records": [records[key] for key in sorted(records)], "failures": failures}


def refresh(previous, current):
    """Keep prior absent records when current collection cannot prove completeness."""
    if previous["source"] != current["source"] or previous["employer"] != current["employer"]:
        raise ValueError("snapshots must describe the same approved source")
    if type(previous.get("complete")) is not bool or type(current.get("complete")) is not bool:
        raise ValueError("snapshot completeness must be a boolean")
    policy = SourcePolicy(current["source"], employer=current["employer"])
    old = {record["jobID"]: record for record in previous["records"]}
    new = {record["jobID"]: record for record in current["records"]}
    if len(old) != len(previous["records"]) or len(new) != len(current["records"]):
        raise ValueError("duplicate snapshot jobID")
    if any(validate_record(record) for record in list(old.values()) + list(new.values())):
        raise ValueError("invalid snapshot record")
    for record in list(old.values()) + list(new.values()):
        if (record["employer"] != policy.employer or
                not policy.record_url(record["sourceURL"], policy.start_url, record["jobID"], "jobs") or
                not policy.record_url(record["applicationURL"], policy.start_url, record["jobID"], "apply")):
            raise ValueError("snapshot record provenance mismatch")
    changed = [{"jobID": key, "fields": {field: {"before": old[key][field], "after": new[key][field]}
                for field in CONTENT_FIELDS if old[key][field] != new[key][field]}}
               for key in sorted(old.keys() & new.keys())
               if any(old[key][field] != new[key][field] for field in CONTENT_FIELDS)]
    absent = sorted(old.keys() - new.keys())
    merged = dict(new) if current["complete"] else old | new
    return {"added_ids": sorted(new.keys() - old.keys()), "changed": changed,
            "removed_ids": absent if current["complete"] else [],
            "removals_suppressed": not current["complete"],
            "retained_previous_ids": absent if not current["complete"] else [],
            "next_snapshot": {**current, "records": [merged[key] for key in sorted(merged)]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-url", required=True)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--transport", choices=("direct", "scrapingant"), default="direct")
    parser.add_argument("--browser", choices=("false", "true"))
    parser.add_argument("--allow-live-api", action="store_true")
    args = parser.parse_args()
    fetch = direct_html
    if args.transport == "scrapingant":
        if not args.allow_live_api or args.browser is None:
            parser.error("managed retrieval requires --allow-live-api and explicit --browser")
        from scrapingant_transport import managed_html
        fetch = lambda url: managed_html(url, browser=args.browser)
    current = collect(SourcePolicy(args.start_url), max_pages=args.max_pages, fetch=fetch)
    output = refresh(json.loads(args.previous.read_text()), current) if args.previous else current
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if current["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
