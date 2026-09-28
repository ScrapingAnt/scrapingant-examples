"""Capture real locator observations; evaluate correctness only in summarize.py."""
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path

from playwright.sync_api import Error, TimeoutError, expect, sync_playwright
from extract import PROJECTION, locator_records, wait_for_catalog
from local_server import fixture_server
from oracle import CASE_IDS, DIAGNOSTIC_IDS


def skus(locator):
    return locator.evaluate_all("nodes => nodes.map(node => node.getAttribute('data-sku'))")


def extraction_case(page, case):
    if case == "eager_count_all":
        page.evaluate("window.holdCatalog = true")
        page.get_by_role("button", name="Load catalog", exact=True).click()
        rows = page.locator("#catalog > .product")
        return {"state": page.locator("#catalog").get_attribute("data-state"), "count": rows.count(), "all_length": len(rows.all()), "records": locator_records(rows)}

    wait_for_catalog(page)
    rows = page.locator("#catalog > .product")
    if case == "strict_duplicate":
        target = page.locator("#main .product .title")
        outcome = "no_error"
        try:
            target.inner_text()
        except Error as error:
            if "strict mode violation" not in str(error):
                raise
            outcome = "strict_mode_violation"
        return {"outcome": outcome, "matched_skus": skus(page.locator("#main .product"))}
    if case == "first_masks_decoy":
        return {"records": locator_records(page.locator("#main .product").first)}
    if case == "scoped_records":
        return {"records": locator_records(rows)}
    if case == "locator_reresolution":
        page.evaluate("window.stageArchived()")
        kettle = page.locator('#catalog [data-sku="K-101"]')
        title = kettle.locator(".title")
        before = title.inner_text()
        page.get_by_role("button", name="Replace kettle", exact=True).click()
        expect(page.locator("#catalog")).to_have_attribute("data-state", "replaced")
        return {"before": before, "after": title.inner_text(), "same_dom_node": kettle.evaluate("node => node === window.previousNode"), "records": locator_records(rows)}
    if case == "evaluate_all":
        return {"records": rows.evaluate_all(PROJECTION)}
    if case == "role_records":
        return {"records": locator_records(page.get_by_role("list", name="Catalog", exact=True).get_by_role("listitem"))}
    if case == "text_exact":
        wrong = rows.filter(has=page.locator("#catalog").get_by_text("Café Mug", exact=True))
        # has= starts at each candidate row; ancestor-prefixed inner locators cannot match.
        title = page.get_by_text("Café Mug", exact=True)
        return {"ancestor_prefixed_skus": skus(wrong), "records": locator_records(rows.filter(has=title))}
    if case == "css_attribute":
        return {"records": locator_records(page.locator('#catalog > .product[data-badge="featured"]'))}
    if case == "xpath_records":
        return {"records": locator_records(page.locator('xpath=//ul[@id="catalog"]/li[@class="product"]'))}
    if case == "frame_scope":
        return {"top_document_skus": skus(page.locator("#main .product")), "records": locator_records(page.frame_locator("#catalog-frame").locator(".product"))}
    if case == "shadow_scope":
        shadow_rows = page.locator("#shadow-host .product")
        return {"locator_skus": skus(shadow_rows), "raw_document_skus": page.evaluate("Array.from(document.querySelectorAll('.product'), node => node.dataset.sku)"), "xpath_skus": skus(page.locator('xpath=//*[@id="shadow-host"]//*[@class="product"]')), "records": locator_records(shadow_rows)}
    raise ValueError("unknown extraction case")


def diagnostic_case(page, case, origin):
    wait_for_catalog(page)
    if case == "missing_selector":
        outcome = "found"
        try:
            page.locator("#never-present").inner_text(timeout=150)
        except TimeoutError:
            outcome = "TimeoutError"
        return {"outcome": outcome, "selector": "#never-present"}
    if case == "text_readers":
        title = page.locator('#catalog [data-sku="T-303"] .title')
        return {"inner_text": title.inner_text(), "text_content": title.text_content()}
    if case == "attribute_property":
        kettle = page.locator('#catalog [data-sku="K-101"]')
        return {"attribute_href": kettle.locator(".title").get_attribute("href"), "property_href": kettle.locator(".title").evaluate("node => node.href").replace(origin, "{origin}", 1), "optional_present": kettle.get_attribute("data-badge"), "optional_missing": page.locator('#catalog [data-sku="M-202"]').get_attribute("data-badge")}
    if case == "query_semantics":
        scope = page.locator("#query-examples")
        ids = "nodes => nodes.map(node => node.id)"
        return {"role_visible": scope.get_by_role("button").all_inner_texts(), "role_include_hidden": scope.get_by_role("button", include_hidden=True).all_text_contents(), "text_normalized": scope.get_by_text("Spaced title", exact=True).evaluate_all(ids), "css": scope.locator("button.offer").evaluate_all(ids), "xpath": scope.locator('xpath=.//button[@class="offer"]').evaluate_all(ids)}
    raise ValueError("unknown diagnostic")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium", "firefox"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with fixture_server() as origin, sync_playwright() as playwright:
        options = {"headless": True}
        if args.browser == "chromium":
            options["chromium_sandbox"] = True
        browser = getattr(playwright, args.browser).launch(**options)
        document = {"schema": 1, "environment": {"browser": args.browser, "browser_version": browser.version, "python": platform.python_version(), "playwright": importlib.metadata.version("playwright"), "os": platform.platform(), "architecture": platform.machine()}, "observations": [], "diagnostics": []}
        failures = 0
        try:
            for round_id in (1, 2, 3):
                for kind, cases in (("observations", CASE_IDS), ("diagnostics", DIAGNOSTIC_IDS)):
                    for case in cases:
                        page = browser.new_page()
                        page.set_default_timeout(4000)
                        try:
                            page.goto(origin + "/catalog.html", wait_until="load")
                            observation = extraction_case(page, case) if kind == "observations" else diagnostic_case(page, case, origin)
                        except Exception as error:
                            # Preserve unexpected observations without host paths in browser stacks.
                            observation = {"unexpected_error": type(error).__name__, "message": str(error).splitlines()[0].replace(origin, "{origin}")}
                            failures += 1
                        finally:
                            page.close()
                        document[kind].append({"round": round_id, "case": case, "observation": observation})
                        output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(json.dumps({"browser": args.browser, "round": round_id, "captured": 16, "unexpected_errors_so_far": failures}), flush=True)
        finally:
            browser.close()
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
