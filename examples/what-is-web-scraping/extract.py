"""Extract synthetic product cards from an owned, local HTML file."""
import argparse
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def extract_products(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article.product")
    if not cards:
        raise ValueError("no product cards found")
    records = []
    seen_ids = set()
    for card in cards:
        product_id = (card.get("data-id") or "").strip()
        if not product_id:
            raise ValueError("product card: missing id")
        if product_id in seen_ids:
            raise ValueError(f"{product_id}: duplicate id")
        record = {"id": product_id}
        for field, selector in (("title", "h2"), ("price", ".price")):
            element = card.select_one(selector)
            value = element.get_text(" ", strip=True) if element else ""
            if not value:
                raise ValueError(f"{product_id}: missing {field}")
            record[field] = value
        seen_ids.add(product_id)
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    try:
        records = extract_products(args.html.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
