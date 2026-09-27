"""Complete no-key example; all HTTP traffic goes to an ephemeral local fixture."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from catalog_fixture import serve_fixture
from state import init_script, score_records
from browser_matrix import environment, fresh_context, navigate_catalog, now


def run():
    with serve_fixture() as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with fresh_context(browser, {'primary': origin}) as context:
                context.add_init_script(script=init_script(origin))
                page = context.new_page()
                observed = navigate_catalog(page, origin)
                result = {'captured_at': now(), 'environment': environment(browser),
                          **observed, **score_records(observed['records'])}
                if not result['exact_match']:
                    raise AssertionError('Catalog differs from four literal expected records')
                return result
        finally:
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run()
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')
