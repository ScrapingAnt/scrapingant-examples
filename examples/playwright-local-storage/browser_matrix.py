"""Twelve extraction hypotheses and four diagnostics, on loopback only."""
import argparse
import json
import platform
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from playwright.sync_api import sync_playwright
from catalog_fixture import serve_fixture
from spec import JSON_PAYLOAD
from state import init_script, score_records
from summarize import observation_passed, summarize_captures


def now():
    return datetime.now(timezone.utc).isoformat()


def environment(browser):
    return {'python': platform.python_version(), 'platform': platform.system() + ' ' + platform.release(),
            'machine': platform.machine(), 'playwright': version('playwright'), 'browser': browser.version}


@contextmanager
def fresh_context(browser, origins, **kwargs):
    context = browser.new_context(**kwargs)
    context.set_default_timeout(10000)
    allowed = tuple(origin + '/' for origin in origins.values())
    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(allowed) else route.abort())
    try:
        yield context
    finally:
        context.close()


def stored_region(page):
    return page.evaluate("() => localStorage.getItem('region')")


def set_region(page, value):
    page.evaluate("value => localStorage.setItem('region', value)", value)


def extract_rows(page):
    return page.locator('tbody tr').evaluate_all("""rows => rows.map(row => {
        const cells = [...row.querySelectorAll('td')].map(cell => cell.textContent);
        return {sku: cells[0], currency: cells[1], price: cells[2]};
    })""")


def navigate_catalog(page, origin, reload=False, query=''):
    with page.expect_response(lambda response: response.url.startswith(origin + '/api/catalog?')) as pending:
        document = page.reload() if reload else page.goto(origin + '/' + query)
    response = pending.value
    page.wait_for_function("document.documentElement.dataset.ready === 'true'")
    data = response.json()
    return {'mode': 'browser_dom', 'origin': origin, 'page_url': page.url, 'request_url': response.url,
            'page_status': document.status, 'request_status': response.status,
            'response_region': data['region'], 'storage_region': stored_region(page),
            'records': extract_rows(page), 'api_records': data['records']}


def record_extraction(cases, name, observed, origins):
    case = dict(case=name, kind='extraction', captured_at=now(), **observed,
                **score_records(observed['records']))
    case['check_passed'] = observation_passed(case, origins)
    cases.append(case)


def record_diagnostic(cases, name, observed, origins):
    case = dict(case=name, kind='diagnostic', captured_at=now(), observed=observed)
    case['check_passed'] = observation_passed(case, origins)
    cases.append(case)


def extraction_round(browser, origins, cases):
    origin = origins['primary']
    with fresh_context(browser, origins) as context:
        context.add_init_script(script=init_script(origin))
        page = context.new_page()
        record_extraction(cases, 'early_missing_only_seed', navigate_catalog(page, origin), origins)

    with fresh_context(browser, origins) as context:
        page = context.new_page()
        observed = navigate_catalog(page, origin)
        set_region(page, 'eu')
        observed['storage_region'] = stored_region(page)
        observed['records'] = extract_rows(page)  # reread the DOM after the late write
        record_extraction(cases, 'late_write_without_reload', observed, origins)
        record_extraction(cases, 'late_write_then_reload', navigate_catalog(page, origin, reload=True), origins)

    # This source has no initializer: new-page success measures shared storage itself.
    with fresh_context(browser, origins) as source:
        page = source.new_page()
        page.goto(origin + '/blank')
        set_region(page, 'eu')
        snapshot = source.storage_state()
        with fresh_context(browser, origins) as isolated:
            record_extraction(cases, 'fresh_isolated_context',
                              navigate_catalog(isolated.new_page(), origin), origins)
        with fresh_context(browser, origins, storage_state=snapshot) as restored:
            record_extraction(cases, 'storage_state_restore',
                              navigate_catalog(restored.new_page(), origin), origins)
        record_extraction(cases, 'same_context_new_page', navigate_catalog(source.new_page(), origin), origins)
        with fresh_context(browser, origins, storage_state=snapshot) as changed:
            # Same scheme/host; only port differs. State belongs to the original origin.
            record_extraction(cases, 'changed_port_state_miss',
                              navigate_catalog(changed.new_page(), origins['secondary']), origins)

    with fresh_context(browser, origins) as context:
        context.add_init_script(script=init_script(origins['secondary']))
        record_extraction(cases, 'wrong_origin_initializer', navigate_catalog(context.new_page(), origin), origins)

    for missing_only, name in ((True, 'missing_only_preserves_change'),
                               (False, 'unconditional_overwrites_change')):
        with fresh_context(browser, origins) as context:
            context.add_init_script(script=init_script(origin, missing_only=missing_only))
            page = context.new_page()
            navigate_catalog(page, origin)
            set_region(page, 'us')
            record_extraction(cases, name, navigate_catalog(page, origin, reload=True), origins)

    for query, name in (('?region=eu', 'query_only_without_storage'),
                        ('', 'query_missing_without_storage')):
        with fresh_context(browser, origins) as context:
            record_extraction(cases, name, navigate_catalog(context.new_page(), origin, query=query), origins)


def diagnostic_round(browser, origins, cases):
    origin = origins['primary']
    with fresh_context(browser, origins) as context:
        page = context.new_page()
        page.goto(origin + '/blank')
        observed = page.evaluate('''value => {
            localStorage.setItem('preferences', JSON.stringify(value));
            const raw = localStorage.getItem('preferences');
            return {input: value, raw, parsed: JSON.parse(raw), stored_type: typeof raw};
        }''', JSON_PAYLOAD)
        record_diagnostic(cases, 'json_argument_round_trip', observed, origins)

    with fresh_context(browser, origins) as context:
        page = context.new_page()
        page.goto(origin + '/blank')
        observed = page.evaluate('''() => {
            const initial = localStorage.getItem('demo');
            localStorage.setItem('demo', 'first');
            const after_set = localStorage.getItem('demo');
            localStorage.setItem('demo', 'second');
            const after_update = localStorage.getItem('demo');
            localStorage.removeItem('demo');
            const after_remove = localStorage.getItem('demo');
            localStorage.setItem('one', '1'); localStorage.setItem('two', '2');
            const count_before_clear = localStorage.length;
            localStorage.clear();
            return {initial, after_set, after_update, after_remove,
                    count_before_clear, count_after_clear: localStorage.length};
        }''')
        record_diagnostic(cases, 'storage_crud', observed, origins)

    with fresh_context(browser, origins) as context:
        page = context.new_page()
        page.goto(origin + '/blank')
        page.evaluate("() => {localStorage.setItem('region', 'eu'); sessionStorage.setItem('tab', 'tab-only');}")
        snapshot = context.storage_state()
        original = page.evaluate("() => ({local: localStorage.getItem('region'), session: sessionStorage.getItem('tab')})")
        other = context.new_page()  # no opener, unlike a window.open() copy
        other.goto(origin + '/blank')
        sibling = other.evaluate("() => ({local: localStorage.getItem('region'), session: sessionStorage.getItem('tab')})")
        with fresh_context(browser, origins, storage_state=snapshot) as restored:
            restored_page = restored.new_page()
            restored_page.goto(origin + '/blank')
            restored_values = restored_page.evaluate("() => ({local: localStorage.getItem('region'), session: sessionStorage.getItem('tab')})")
        record_diagnostic(cases, 'session_storage_not_restored', {
            'original_local': original['local'], 'original_session': original['session'],
            'new_page_local': sibling['local'], 'new_page_session': sibling['session'],
            'restored_local': restored_values['local'], 'restored_session': restored_values['session'],
            'snapshot': snapshot}, origins)

    with fresh_context(browser, origins) as context:
        writer, reader = context.new_page(), context.new_page()
        for page in (writer, reader):
            page.goto(origin + '/blank')
            page.evaluate('''() => {
                window.storageEvents = [];
                addEventListener('storage', event => window.storageEvents.push({key: event.key,
                    oldValue: event.oldValue, newValue: event.newValue,
                    storageArea: event.storageArea === localStorage ? 'localStorage' : 'other'}));
            }''')
        set_region(writer, 'eu')
        reader.wait_for_function('window.storageEvents.length === 1')
        record_diagnostic(cases, 'storage_event_other_page', {
            'writer_events': writer.evaluate('window.storageEvents'),
            'reader_events': reader.evaluate('window.storageEvents'),
            'writer_value': stored_region(writer), 'reader_value': stored_region(reader)}, origins)


def run(browser_name, output):
    data = {'schema_version': 1, 'browser': browser_name, 'started_at': now(), 'rounds': 3, 'runs': []}
    try:
        with serve_fixture() as first, serve_fixture() as second, sync_playwright() as playwright:
            origins = {'primary': first, 'secondary': second}
            data['fixture_origins'] = origins
            browser = getattr(playwright, browser_name).launch(headless=True)
            try:
                data['environment'] = environment(browser)
                for number in range(1, 4):
                    cases = []
                    data['runs'].append({'round': number, 'cases': cases})
                    extraction_round(browser, origins, cases)
                    diagnostic_round(browser, origins, cases)
            finally:
                browser.close()
        data['completed_at'] = now()
        summary = summarize_captures([data], [browser_name])
        if summary['checks'] != summary['passed_checks']:
            raise AssertionError('Observed behavior did not match a predeclared hypothesis')
    except Exception as error:
        data['completed_at'] = now()
        data['error_type'] = type(error).__name__
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'browser': browser_name, 'checks': summary['checks'],
                      'passed_checks': summary['passed_checks']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chromium', 'firefox'], default='chromium')
    parser.add_argument('--output', type=Path, default=Path('run_output/chromium.json'))
    args = parser.parse_args()
    run(args.browser, args.output)
