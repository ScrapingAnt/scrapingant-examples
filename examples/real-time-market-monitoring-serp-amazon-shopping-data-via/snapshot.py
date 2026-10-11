"""Owned-fixture adapter and conservative bounded-window diff; no network."""
import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class Node:
    def __init__(self, tag, attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
        self.duplicate_attributes = len(attrs) != len(self.attrs)

    def all(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.all()

    def text(self):
        return "".join(c.text() if isinstance(c, Node) else c for c in self.children).strip()


class Tree(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]
        self.malformed = False

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        if len(self.stack) > 1 and self.stack[-1].tag == tag:
            self.stack.pop()
        else:
            self.malformed = True

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def integer(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_snapshot(html):
    """Parse this packet's annotated HTML, not arbitrary live Amazon HTML.

    An independent production adapter must derive/validate the envelope and end
    signal from its actual permitted source; do not inject a fake completion tag.
    """
    tree = Tree()
    tree.feed(html)
    tree.close()
    nodes = list(tree.root.all())
    roots = [n for n in nodes if n.attrs.get("data-snapshot") == "amazon-shaped-v1"]
    if len(roots) != 1:
        raise ValueError("expected one owned-fixture snapshot envelope")
    root = roots[0]
    context = {key: root.attrs.get("data-" + key.replace("_", "-")) for key in
               ("query", "marketplace", "currency", "source_url", "observed_utc")}
    issues = []
    if any(node.duplicate_attributes for node in nodes):
        issues.append("duplicate_attributes")
    if any(not context[k] for k in context):
        issues.append("missing_provenance")
    try:
        time = datetime.fromisoformat(context["observed_utc"].replace("Z", "+00:00"))
        if not context["observed_utc"].endswith("Z") or time.utcoffset().total_seconds() != 0:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        issues.append("invalid_observed_utc")
    source = urlsplit(context["source_url"] or "")
    if source.scheme not in ("http", "https") or not source.hostname:
        issues.append("invalid_source_url")
    if not re.fullmatch(r"[A-Z]{3}", context["currency"] or ""):
        issues.append("invalid_currency")
    page = integer(root.attrs.get("data-page"))
    expected = integer(root.attrs.get("data-expected-count"))
    if page != 1:
        issues.append("unexpected_page")
    if expected is None or expected < 1:
        issues.append("invalid_expected_count")
    if root.attrs.get("data-capture-status") != "ok":
        issues.append("capture_not_ok")
    if root.attrs.get("data-complete") != "true":
        issues.append("declared_incomplete")
    local = list(root.all())
    cards = [n for n in local if n.attrs.get("data-component-type") == "s-search-result"]
    records = []
    for position, card in enumerate(cards, 1):
        descendants = list(card.all())
        asin = card.attrs.get("data-asin", "").strip() or None
        if asin is not None and not re.fullmatch(r"[A-Z0-9]{10}", asin):
            asin = None
        if asin is None:
            issues.append("missing_or_invalid_asin")
        titles = [n.text() for n in descendants if n.tag == "h2"]
        title = titles[0] or None if len(titles) == 1 else None
        labels = [n.text().strip().lower() for n in descendants if n.attrs.get("data-role") == "placement-label"]
        # "Organic" is an explicit annotation in owned fixtures. Missing a real
        # sponsored label is NOT evidence of organic placement.
        status = {("sponsored",): "sponsored", ("organic",): "organic"}.get(tuple(labels), "unknown")
        prices = [n for n in descendants if "a-offscreen" in n.attrs.get("class", "").split()]
        price = None
        if len(prices) == 1:
            raw = prices[0].text()
            currency = prices[0].attrs.get("data-currency")
            match = re.fullmatch(r"\$([0-9]+(?:\.[0-9]{2})?)", raw)
            if match and currency == "USD" and context["currency"] == "USD":
                try:
                    price = str(Decimal(match.group(1)).quantize(Decimal("0.01")))
                except InvalidOperation:
                    pass
        records.append({**context, "asin": asin, "observed_position": position,
                        "sponsored_status": status, "title": title, "price": price})
    if len(records) != expected:
        issues.append("count_mismatch")
    ends = [n for n in local if n.attrs.get("id") == "snapshot-end"]
    if len(ends) != 1:
        issues.append("missing_or_duplicate_end_signal")
    elif integer(ends[0].attrs.get("data-count")) != expected or integer(ends[0].attrs.get("data-page")) != page:
        issues.append("end_signal_mismatch")
    elif cards and local.index(ends[0]) < max(local.index(n) for n in cards):
        issues.append("premature_end_signal")
    if tree.malformed or len(tree.stack) != 1:
        issues.append("malformed_or_truncated_html")
    issues = sorted(set(issues))
    return {"context": context, "page": page, "expected_count": expected,
            "complete": not issues, "issues": issues, "records": records}


def compare(before, after):
    """Report observations only; never infer market delisting or organic rank."""
    reasons = []
    if not before["complete"]:
        reasons.append("baseline_incomplete")
    if not after["complete"]:
        reasons.append("current_incomplete")
    for key in ("query", "marketplace", "currency", "source_url"):
        if before["context"][key] != after["context"][key]:
            reasons.append("mismatch_" + key)
    if before["page"] != after["page"] or before["expected_count"] != after["expected_count"]:
        reasons.append("mismatch_window")
    try:
        if datetime.fromisoformat(after["context"]["observed_utc"].replace("Z", "+00:00")) <= datetime.fromisoformat(before["context"]["observed_utc"].replace("Z", "+00:00")):
            reasons.append("non_increasing_observation_time")
    except (TypeError, ValueError, AttributeError):
        reasons.append("invalid_observation_time")
    if reasons:
        return {"status": "suppressed", "reasons": reasons, "changes": [], "ambiguous_placements": []}
    groups = []
    for snapshot in (before, after):
        group = defaultdict(list)
        for record in snapshot["records"]:
            group[(record["asin"], record["sponsored_status"])].append(record)
        groups.append(group)
    old, new = groups
    changes, ambiguous = [], []
    for key in sorted(set(old) | set(new)):
        ident = {"asin": key[0], "sponsored_status": key[1]}
        if len(old[key]) > 1 or len(new[key]) > 1:
            ambiguous.append({**ident, "before_count": len(old[key]), "after_count": len(new[key])})
            continue
        if not old[key] or not new[key]:
            changes.append({**ident, "kind": "newly_observed_in_window" if not old[key] else "not_observed_in_window"})
            continue
        b, a = old[key][0], new[key][0]
        if b["observed_position"] != a["observed_position"]:
            changes.append({**ident, "kind": "observed_position_change", "before": b["observed_position"], "after": a["observed_position"]})
        if b["price"] is not None and a["price"] is not None and b["price"] != a["price"]:
            changes.append({**ident, "kind": "observed_price_change", "before": b["price"], "after": a["price"], "currency": a["currency"]})
    return {"status": "compared", "reasons": [], "changes": changes, "ambiguous_placements": ambiguous}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", nargs="?", type=Path)
    args = parser.parse_args()
    before = parse_snapshot(args.before.read_text())
    result = compare(before, parse_snapshot(args.after.read_text())) if args.after else before
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
