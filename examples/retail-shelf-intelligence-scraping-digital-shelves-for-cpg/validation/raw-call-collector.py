"""One selected Adagio ProductGroup, with wholly owned structural controls."""
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from html import unescape
import hashlib
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

SOURCE = "https://www.adagio.com/black/earl_grey_lavender_tea.html"
OWNED_SOURCE = "https://scrapingant.github.io/scrapingant-examples/examples/retail-shelf-intelligence-scraping-digital-shelves-for-cpg/fixtures/baseline.html"
MAX_BYTES = 262144
# These two identities are one fixed source shape and its fictional test copy.
CONTRACTS = {
    SOURCE: ("001036", {"001036002":"3oz", "001036004":"16oz"}),
    OWNED_SOURCE: ("000701", {"000701002":"3oz", "000701004":"16oz"}),
}


def utc_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("observation_requires_UTC_seconds")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return value


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_JSON_key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite_JSON_number")


class ProductPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.canonicals, self.blocks, self.parts = [], [], []
        self.in_script = False
        self.duplicate_attributes = False
        self.stack = []
        self.market_tokens = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if len(values) != len(attrs):
            self.duplicate_attributes = True
        if tag == "link" and values.get("rel") == "canonical":
            self.canonicals.append(values.get("href"))
        if tag == "script" and values.get("type") == "application/ld+json":
            self.in_script, self.parts = True, []
        if tag == "meta" and values.get("itemprop") == "addressCountry" and "shippingDestination" in self.stack:
            self.market_tokens.append(values.get("content"))
        if tag not in ("meta", "link", "br", "hr", "img", "input", "source", "wbr", "area", "base", "embed", "param", "col", "track"):
            self.stack.append(values.get("itemprop", ""))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ("meta", "link", "br", "hr", "img", "input", "source", "wbr", "area", "base", "embed", "param", "col", "track"):
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.in_script:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_script:
            self.blocks.append("".join(self.parts))
            self.in_script = False
        if self.stack:
            self.stack.pop()


def decimal_price(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("invalid_price")
    token = str(value)
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,2})?", token):
        raise ValueError("invalid_price")
    try:
        price = Decimal(token)
    except InvalidOperation:
        raise ValueError("invalid_price") from None
    if not price.is_finite() or price > 1000000:
        raise ValueError("invalid_price")
    return format(price, ".2f"), token


def record(product, index, group_id, selected, source, observed_at_utc, market):
    sku = product.get("sku")
    if product.get("@type") != "Product" or sku not in selected:
        raise ValueError("wrong_variant_identity")
    size = product.get("size")
    match = re.fullmatch(r"([1-9]\d{0,3})oz", size or "") if isinstance(size, str) else None
    if not match:
        raise ValueError("invalid_pack_label")
    if size != selected[sku]:
        raise ValueError("pack_identity_changed")
    offer = product.get("offers")
    if not isinstance(offer, dict) or offer.get("@type") != "Offer":
        raise ValueError("invalid_single_variant_offer")
    if offer.get("url") != source:
        raise ValueError("wrong_offer_source")
    price, token = decimal_price(offer.get("price"))
    if offer.get("priceCurrency") != "USD":
        raise ValueError("invalid_currency")
    availability_token = offer.get("availability")
    if availability_token is not None and (not isinstance(availability_token, str) or len(availability_token) > 80):
        raise ValueError("invalid_availability")
    availability = {"http://schema.org/InStock":"in_stock", "https://schema.org/InStock":"in_stock",
                    "http://schema.org/OutOfStock":"out_of_stock", "https://schema.org/OutOfStock":"out_of_stock"}.get(availability_token, "unknown")
    path = f"$.hasVariant[{index}]"
    return {"product_id":group_id, "sku":sku, "variant_id":None,
            "variant":size, "pack_quantity":int(match.group(1)), "pack_unit":"ounce",
            "price":price, "currency":"USD", "availability":availability,
            "observed_at_utc":observed_at_utc, "requested_source_url":source,
            "observed_source_url":offer["url"], "market":market, "market_basis":"page_shipping_destination" if market == "US" else "unspecified",
            "fulfilment":"unselected", "offer_kind":"listed_variant_offer", "purchase_basis":"unspecified",
            "offer_context":"public stated USD offer" if source == SOURCE else "owned fictional USD offer",
            "source_evidence":{"product_path":path, "offer_path":path + ".offers", "pack_label":size,
                               "price_token":token, "availability_token":availability_token}}


def parse_group(group, *, requested_source_url, observed_at_utc, market="unknown"):
    utc_time(observed_at_utc)
    result = {"records":[], "rejected":[], "complete":False}
    contract = CONTRACTS.get(requested_source_url)
    if not contract:
        result["rejected"] = [{"sku":None, "reason":"unexpected_requested_source"}]
        return result
    group_id, selected = contract
    if (not isinstance(group, dict) or group.get("@type") != "ProductGroup" or group.get("productGroupID") != group_id
            or group.get("url") != requested_source_url or not isinstance(group.get("hasVariant"), list) or len(group["hasVariant"]) > 16):
        result["rejected"] = [{"sku":None, "reason":"invalid_product_group"}]
        return result
    products = group["hasVariant"]
    counts = Counter(p.get("sku") for p in products if isinstance(p, dict) and isinstance(p.get("sku"), str))
    for index, product in enumerate(products):
        if not isinstance(product, dict) or not isinstance(product.get("sku"), str) or product.get("sku") not in selected:
            continue  # sample/teabag offers do not enter this selected weight workload
        sku = product["sku"]
        if counts[sku] > 1:
            if not any(r["sku"] == sku for r in result["rejected"]):
                result["rejected"].append({"sku":sku, "reason":"duplicate_or_conflicting_SKU"})
            continue
        try:
            result["records"].append(record(product, index, group_id, selected, requested_source_url, observed_at_utc, market))
        except ValueError as error:
            result["rejected"].append({"sku":sku, "reason":str(error)})
    for sku in selected:
        if sku not in counts:
            result["rejected"].append({"sku":sku, "reason":"missing_selected_SKU"})
    result["records"].sort(key=lambda r: r["sku"])
    result["complete"] = not result["rejected"] and len(result["records"]) == len(selected)
    return result


def parse_page(body, *, requested_source_url, observed_at_utc):
    utc_time(observed_at_utc)
    try:
        if requested_source_url not in CONTRACTS:
            raise ValueError("unexpected_requested_source")
        if not isinstance(body, bytes) or not body or len(body) > MAX_BYTES:
            raise ValueError("empty_or_oversized_body")
        page = ProductPage()
        page.feed(body.decode("utf-8", errors="strict"))
        page.close()
        if page.canonicals != [requested_source_url] or page.in_script or page.duplicate_attributes:
            raise ValueError("invalid_source_envelope")
        groups = []
        for block in page.blocks:
            obj = json.loads(block, object_pairs_hook=unique_keys, parse_float=Decimal, parse_constant=reject_constant)
            if isinstance(obj, dict) and obj.get("@type") == "ProductGroup":
                groups.append(obj)
        if len(groups) != 1:
            raise ValueError("missing_or_ambiguous_ProductGroup")
        market = "US" if page.market_tokens and set(page.market_tokens) == {"US"} else "unknown"
        return parse_group(groups[0], requested_source_url=requested_source_url, observed_at_utc=observed_at_utc, market=market)
    except (ValueError, UnicodeError, RecursionError):
        return {"records":[], "rejected":[{"sku":None, "reason":"invalid_source_HTML_or_JSON"}], "complete":False}


def change_report(previous, current):
    # A comparable observation includes pack, currency and source/offer context.
    # URL alone cannot identify the two selected variants on this source.
    identity_fields = ("requested_source_url", "observed_source_url", "product_id", "sku", "variant", "variant_id",
                       "pack_quantity", "pack_unit", "currency", "market", "market_basis", "fulfilment", "offer_kind",
                       "purchase_basis", "offer_context")
    def indexed(snapshot):
        result = {}
        for value in snapshot["records"]:
            utc_time(value["observed_at_utc"])
            identity = tuple(value[f] for f in identity_fields)
            if identity in result:
                raise ValueError("duplicate_snapshot_identity")
            result[identity] = value
        return result
    before, after = indexed(previous), indexed(current)
    report = {"current_complete":current["complete"], "scope":"two selected offers; no inventory/disappearance inference",
              "changes":[], "unobserved_prior_records":[], "new_observations":[]}
    for identity, old in before.items():
        new = after.get(identity)
        if new is None:
            report["unobserved_prior_records"].append(old)
            continue
        if new["observed_at_utc"] <= old["observed_at_utc"]:
            raise ValueError("new_observation_must_be_later")
        fields = {name:{"before":old[name], "after":new[name]}
                  for name in ("price", "availability") if old[name] != new[name]}
        if fields:
            report["changes"].append({"sku":old["sku"], "variant":old["variant"], "fields":fields})
    report["new_observations"] = [new for identity, new in after.items() if identity not in before]
    return report


def verify_oracle(actual, expected):
    if actual != expected:
        raise ValueError("literal_field_oracle_mismatch")


def cost_summary(receipt, count):
    credits = receipt["actual_receipt_credits"]
    return {"actual_receipt_credits":credits, "unknown_charge_requests":int(receipt["credit_receipt_state"] == "unknown"),
            "accepted_records":count, "credits_per_accepted_record":format(Decimal(credits) / count, ".2f") if credits is not None and count else None}


def collection(acquisition, *, source, observed_at_utc):
    result = parse_page(acquisition["body"], requested_source_url=source, observed_at_utc=observed_at_utc) if acquisition["usable"] else {
        "records":[], "rejected":[{"sku":None,"reason":"acquisition_failed"}], "complete":False}
    result["acquisition"] = acquisition["receipt"]
    result["cost"] = cost_summary(acquisition["receipt"], len(result["records"]))
    return result


def replay_projection(path):
    """Replay the minimal saved facts; this does not reconstruct original HTML."""
    from pathlib import Path
    raw = Path(path).read_bytes()
    projection = json.loads(raw, object_pairs_hook=unique_keys)
    facts = projection["records"]
    if len(facts) != 2 or any(f["source_url"] != SOURCE for f in facts):
        raise ValueError("invalid_field_projection")
    group = {"@type":"ProductGroup","productGroupID":"001036","url":SOURCE,"hasVariant":[
        {"@type":"Product","sku":f["sku"],"size":f["size_literal"],"offers":{
            "@type":"Offer","url":f["source_url"],"price":f["price_decimal"],
            "priceCurrency":f["currency"],"availability":f["availability_literal"]}}
        for f in facts]}
    at = datetime.fromisoformat(facts[0]["observed_at_utc"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    market = "US" if all(f["market"] == "US" and f["market_basis"] == "page microdata shippingDestination.addressCountry=US" for f in facts) else "unknown"
    result = parse_group(group, requested_source_url=SOURCE, observed_at_utc=at, market=market)
    for i, value in enumerate(result["records"]):
        value["source_evidence"]["product_path"] = f"projection.records[{i}]"
        value["source_evidence"]["offer_path"] = f"projection.records[{i}].price_decimal"
    result["acquisition"] = {"transport":"field_projection_replay","api_http_status":None,
        "target_http_status":None,"actual_receipt_credits":None,"credit_receipt_state":"not_applicable",
        "projection_sha256":hashlib.sha256(raw).hexdigest(),"source_body_sha256":facts[0]["source_sha256"],
        "scope":"saved minimal facts; full HTML withheld; original body hash cannot be regenerated from this projection"}
    result["cost"] = cost_summary(result["acquisition"], len(result["records"]))
    return result


def main(argv=None):
    import argparse
    import os
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("replay", help="Local owned/source HTML; no network")
    replay.add_argument("html", type=Path)
    replay.add_argument("--source", choices=("owned", "adagio"), default="owned")
    replay.add_argument("--observed-at", required=True, help="UTC observation/capture time, not a source date")
    projection = commands.add_parser("projection", help="Local minimal factual projection; no network")
    projection.add_argument("file", type=Path)
    commands.add_parser("direct", help="OPTIONAL: one direct HTTP request to the fixed Adagio page")
    managed = commands.add_parser("managed", help="OPTIONAL PAID: one request to the fixed Adagio page")
    managed.add_argument("--browser", choices=("false", "true"), default="false")
    args = parser.parse_args(argv)
    try:
        if args.command == "projection":
            result = replay_projection(args.file)
        elif args.command == "replay":
            with args.html.open("rb") as handle:
                body = handle.read(MAX_BYTES + 1)
            result = parse_page(body, requested_source_url=OWNED_SOURCE if args.source == "owned" else SOURCE, observed_at_utc=args.observed_at)
            result["acquisition"] = {"transport":"offline_replay","api_http_status":None,"target_http_status":None,
                "actual_receipt_credits":None,"credit_receipt_state":"not_applicable","body_sha256":hashlib.sha256(body).hexdigest(),
                "scope":"locally replayed bytes; no fresh HTTP observation"}
            result["cost"] = cost_summary(result["acquisition"], len(result["records"]))
        else:
            acquisition = acquire(SOURCE, managed=True, browser=args.browser == "true", key=os.environ.get("SCRAPINGANT_API_KEY")) if args.command == "managed" else acquire(SOURCE)
            from datetime import timezone
            at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = collection(acquisition, source=SOURCE, observed_at_utc=at)
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"complete":False,"error":"invalid_input_or_missing_credential"}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["complete"] else 1


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def header(headers, name):
    values = headers.get_all(name, [])
    return values[0].strip() if len(values) == 1 else None


def secret_echo(body, key):
    if not key:
        return False
    text = body.decode("utf-8", errors="replace")
    for _ in range(3):
        if key in text:
            return True
        text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), unescape(unquote(text)))
    return key in text


def acquire(url, *, managed=False, browser=False, key=None, send=None, clock=None):
    """One attempt only. send is an offline boundary delegate used by tests."""
    split = urlsplit(url)
    if split.scheme not in ("http", "https") or not split.netloc or split.username or split.password or split.fragment:
        raise ValueError("invalid_request_URL")
    if managed and (not isinstance(key, str) or not key.strip()):
        raise ValueError("managed_mode_requires_key")
    if key and secret_echo(url.encode(), key):
        raise ValueError("credential_in_target_URL")
    clock = clock or time.monotonic
    started = clock()
    receipt = {"transport":"managed" if managed else "direct", "requested_source_url":url,
               "api_http_status":None, "target_http_status":None, "target_media_type":None,
               "actual_receipt_credits":None, "credit_receipt_state":"unknown" if managed else "not_applicable",
               "body_bytes":None, "body_sha256":None, "error":None}
    result = {"usable":False, "body":b"", "receipt":receipt}
    endpoint = "https://api.scrapingant.com/v2/general"
    request_url = endpoint + "?" + urlencode({"url":url, "browser":"true" if browser else "false",
                  "proxy_type":"datacenter", "proxy_country":"us", "return_page_source":"false", "timeout":"30"}) if managed else url
    request = Request(request_url, headers={"x-api-key":key, "Accept":"text/html"} if managed else {"Accept":"text/html"})
    # Ignore ambient proxies, including on loopback. No redirect/retry handler.
    send = send or build_opener(ProxyHandler({}), NoRedirect()).open
    response = None
    try:
        try:
            response = send(request, timeout=30)
        except HTTPError as error:
            response = error
        status = response.status
        if managed:
            receipt["api_http_status"] = status
            target = header(response.headers, "Ant-page-status-code")
            receipt["target_http_status"] = int(target) if target and re.fullmatch(r"[1-5]\d\d", target) else None
            media = header(response.headers, "Ant-original-header-content-type")
            credits = header(response.headers, "Ant-credits-cost")
            if credits and re.fullmatch(r"\d{1,9}", credits):
                receipt["actual_receipt_credits"] = int(credits)
                receipt["credit_receipt_state"] = "known"
        else:
            receipt["target_http_status"] = status
            media = header(response.headers, "Content-Type")
        if media and secret_echo(media.encode(), key):
            receipt["error"] = "credential_echo"
            return result
        receipt["target_media_type"] = media.split(";", 1)[0].strip().lower() if media else None
        if response.geturl() != request_url:
            receipt["error"] = "unexpected_response_URL"
            return result
        chunks, size = [], 0
        while True:
            if clock() - started > 30:
                receipt["error"] = "read_deadline"
                return result
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if clock() - started > 30:
                receipt["error"] = "read_deadline"
                return result
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                receipt["error"] = "oversized_body"
                return result
        body = b"".join(chunks)
        if secret_echo(body, key):
            receipt["error"] = "credential_echo"
            return result
        receipt["body_bytes"] = len(body)
        receipt["body_sha256"] = hashlib.sha256(body).hexdigest()
        if status != 200:
            receipt["error"] = "API_HTTP_failure" if managed else "target_HTTP_failure"
        elif receipt["target_http_status"] != 200:
            receipt["error"] = "missing_or_unsuccessful_target_status"
        elif receipt["target_media_type"] not in ("text/html", "application/xhtml+xml"):
            receipt["error"] = "missing_or_non_HTML_target_media"
        elif not body:
            receipt["error"] = "empty_body"
        else:
            result.update(usable=True, body=body)
    except (OSError, ValueError, TypeError, AttributeError):
        receipt["error"] = "transport_failure"
    finally:
        if response is not None:
            response.close()
    return result


if __name__ == "__main__":
    import sys
    sys.exit(main())
