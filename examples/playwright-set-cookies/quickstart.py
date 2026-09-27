"""Complete, no-secret example: save, restore, extract, and explicitly query API."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

from browser_matrix import api_records, browser_records, environment
from catalog_fixture import serve_catalog
from state import region_params, score_records


def main():
    with serve_catalog() as fixture, TemporaryDirectory(prefix='synthetic-playwright-state-') as temporary:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                source = browser.new_context()
                # Only this synthetic fixture recognizes this made-up session value.
                source.add_cookies([{'name': 'demo_session', 'value': 'member-v1',
                                     'url': fixture.origin, 'httpOnly': True}])
                page = source.new_page()
                page.goto(fixture.origin + '/catalog')
                page.evaluate("localStorage.setItem('region', 'EU')")
                state_file = Path(temporary) / 'state.json'
                state = source.storage_state(path=state_file)
                source.close()

                context = browser.new_context(storage_state=state_file)
                try:
                    browser_result = browser_records(context.new_page(), fixture.origin)
                    api_result = api_records(context.request, fixture.origin, region_params(state, fixture.origin))
                    result = {
                        'environment': environment(browser),
                        'browser': {**browser_result, **score_records(browser_result['records'])},
                        'api': {**api_result, **score_records(api_result['records'])},
                        'saved_cookie_names': [cookie['name'] for cookie in state['cookies']],
                        'saved_region': region_params(state, fixture.origin)['region'],
                    }
                    assert result['browser']['exact_match'] and result['api']['exact_match']
                finally:
                    context.close()
            finally:
                browser.close()
    result['temporary_state_file_removed'] = not state_file.exists()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.dumps(main(), indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data)
    print(data, end='')
