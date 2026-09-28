"""Complete local browser lifecycle: fixture, readiness, projection, literal validation."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from extract import PROJECTION, wait_for_catalog
from local_server import fixture_server
from oracle import CATALOG, validate_records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    with fixture_server() as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            page = browser.new_page()
            page.goto(origin + "/catalog.html", wait_until="load")
            wait_for_catalog(page)
            records = page.locator("#catalog > .product").evaluate_all(PROJECTION)
            validate_records(records, CATALOG)
        finally:
            browser.close()
    output = json.dumps(records, indent=2, ensure_ascii=False) + "\n"
    print(output, end="")
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
