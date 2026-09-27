"""Measure cookie/state boundaries against a loopback catalog, without secrets."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

from catalog_fixture import serve_catalog
from state import region_params, score_records


# These are hypotheses asserted against observations, not fabricated results.
EXPECTED_MATCHES = {
    'fresh_browser': 0,
    'cookie_before_navigation': 4,
    'server_seeded_browser': 4,
    'full_storage_state_restore': 4,
    'cookies_only_restore': 0,
    'shared_api_explicit_region': 4,
    'shared_api_missing_region': 0,
    'isolated_api_no_handoff': 0,
    'isolated_api_state_handoff': 4,
    'other_browser_context': 0,
    'api_set_cookie_changes_browser': 0,
    'wrong_cookie_path': 0,
}


def environment(browser):
    return {
        'python': platform.python_version(),
        'os': platform.system(), 'os_release': platform.release(),
        'macos_version': platform.mac_ver()[0] or None,
        'architecture': platform.machine(),
        'packages': {name: importlib.metadata.version(name)
                     for name in ('playwright', 'greenlet', 'pyee', 'typing_extensions')},
        'browser_version': browser.version,
    }


def browser_records(page, origin):
    with page.expect_response(lambda response: '/api/catalog?' in response.url) as pending:
        navigation = page.goto(origin + '/catalog')
    response = pending.value
    page.wait_for_selector('body[data-ready="yes"]')
    rows = page.locator('tbody tr').evaluate_all("""rows => rows.map(row => {
      const cells = [...row.querySelectorAll('td')].map(cell => cell.textContent);
      return {sku: cells[0], currency: cells[1], price: cells[2]};
    })""")
    payload = response.json()
    return {
        'transport': 'browser_dom', 'navigation_status': navigation.status,
        'target_status': response.status, 'audience': payload['audience'],
        'region': payload['region'], 'records': rows,
    }


def api_records(context, origin, params=None):
    response = context.get(origin + '/api/catalog', params=params)
    try:
        payload = response.json()
        return {
            'transport': 'api_json', 'target_status': response.status,
            'audience': payload['audience'], 'region': payload['region'],
            'records': payload['records'],
        }
    finally:
        response.dispose()


def extraction(case, observation):
    result = {'case': case, 'kind': 'extraction', **observation,
              **score_records(observation['records'])}
    result['expected_matching_records'] = EXPECTED_MATCHES[case]
    result['check_passed'] = (
        result['target_status'] == 200 and result['row_count'] == 4
        and result['matching_records'] == EXPECTED_MATCHES[case]
        and result['exact_match'] == (EXPECTED_MATCHES[case] == 4)
    )
    return result


def diagnostic(case, passed, **details):
    return {'case': case, 'kind': 'diagnostic', 'check_passed': bool(passed), **details}


def add_demo_state(context, origin, path='/'):
    context.add_cookies([{
        'name': 'demo_session', 'value': 'member-v1',
        'domain': '127.0.0.1', 'path': path,
        'httpOnly': True, 'secure': False, 'sameSite': 'Lax',
    }])
    context.add_init_script("if (location.origin === " + json.dumps(origin) +
                            ") localStorage.setItem('region', 'EU');")


def one_round(playwright, browser, fixture, number):
    cases = []
    origin = fixture.origin
    with ExitStack() as stack:
        def new_context(**kwargs):
            context = browser.new_context(**kwargs)
            stack.callback(context.close)
            context.set_default_timeout(15000)
            return context

        def new_api(**kwargs):
            context = playwright.request.new_context(**kwargs)
            stack.callback(context.dispose)
            return context

        fresh = new_context()
        cases.append(extraction('fresh_browser', browser_records(fresh.new_page(), origin)))

        early = new_context()
        early_page = early.new_page()
        hits_before = fixture.hit_count('/catalog')
        add_demo_state(early, origin)
        early_cookies = early.cookies(origin)
        cases.append(diagnostic(
            'cookie_inserted_before_first_navigation',
            early_page.url == 'about:blank' and fixture.hit_count('/catalog') == hits_before
            and any(c['name'] == 'demo_session' for c in early_cookies),
            page_url=early_page.url, fixture_navigation_delta=fixture.hit_count('/catalog') - hits_before,
            cookie_names=[c['name'] for c in early_cookies],
        ))
        cases.append(extraction('cookie_before_navigation', browser_records(early_page, origin)))

        seeded = new_context()
        seeded_page = seeded.new_page()
        seeded_page.goto(origin + '/seed')
        cases.append(extraction('server_seeded_browser', browser_records(seeded_page, origin)))
        js_cookie = seeded_page.evaluate('document.cookie')
        browser_cookie = seeded.cookies(origin)
        cases.append(diagnostic(
            'httponly_visible_to_context_not_document',
            any(c['name'] == 'demo_session' and c['httpOnly'] for c in browser_cookie)
            and 'demo_session=' not in js_cookie,
            context_cookie_names=[c['name'] for c in browser_cookie],
            context_cookie_http_only={c['name']: c['httpOnly'] for c in browser_cookie},
            document_cookie=js_cookie,
        ))

        with TemporaryDirectory(prefix='synthetic-playwright-state-') as temporary:
            state_file = Path(temporary) / 'state.json'
            snapshot = seeded.storage_state(path=state_file)
            restored = new_context(storage_state=state_file)
            cases.append(extraction('full_storage_state_restore', browser_records(restored.new_page(), origin)))
            cookies_only = new_context()
            cookies_only.add_cookies(snapshot['cookies'])
            cases.append(extraction('cookies_only_restore', browser_records(cookies_only.new_page(), origin)))
            params = region_params(snapshot, origin)
            cases.append(extraction('shared_api_explicit_region', api_records(seeded.request, origin, params)))
            cases.append(extraction('shared_api_missing_region', api_records(seeded.request, origin)))
            isolated = new_api()
            cases.append(extraction('isolated_api_no_handoff', api_records(isolated, origin, params)))
            handed_off = new_api(storage_state=state_file)
            cases.append(extraction('isolated_api_state_handoff', api_records(handed_off, origin, params)))

        other = new_context()
        other_page = other.new_page()
        cases.append(extraction('other_browser_context', browser_records(other_page, origin)))
        mutation = other.request.get(origin + '/session/guest')
        mutation.dispose()
        other_cookie = {c['name']: c['value'] for c in other.cookies(origin)}
        seeded_cookie = {c['name']: c['value'] for c in seeded.cookies(origin)}
        cases.append(diagnostic(
            'context_mutation_remains_isolated',
            other_cookie.get('demo_session') == 'guest-v1'
            and seeded_cookie.get('demo_session') == 'member-v1',
            other_session=other_cookie.get('demo_session'), seeded_session=seeded_cookie.get('demo_session'),
        ))
        mutation = seeded.request.get(origin + '/session/guest')
        mutation.dispose()
        cases.append(extraction('api_set_cookie_changes_browser', browser_records(seeded_page, origin)))

        wrong_path = new_context()
        add_demo_state(wrong_path, origin, path='/admin')
        cases.append(extraction('wrong_cookie_path', browser_records(wrong_path.new_page(), origin)))

        for mode, expected_hits in [('normal', 1), ('fetch_then_continue', 2), ('fetch_then_fulfill', 1)]:
            context = new_context()
            page = context.new_page()
            if mode != 'normal':
                def route_handler(route):
                    response = route.fetch()
                    try:
                        if mode == 'fetch_then_continue':
                            route.continue_()
                        else:
                            route.fulfill(response=response)
                    finally:
                        response.dispose()
                page.route('**/diagnostic/ping', route_handler)
            before = fixture.hit_count('/diagnostic/ping')
            response = page.goto(origin + '/diagnostic/ping')
            observed_hits = fixture.hit_count('/diagnostic/ping') - before
            cases.append(diagnostic(
                'route_' + mode,
                response.status == 200 and observed_hits == expected_hits,
                target_status=response.status, server_hits=observed_hits,
                expected_server_hits=expected_hits, navigations=1,
            ))
    return {'round': number, 'cases': cases}


def run(browser_name, rounds):
    with serve_catalog() as fixture, sync_playwright() as playwright:
        browser = getattr(playwright, browser_name).launch(headless=True)
        try:
            result = {
                'tested_at': datetime.now(timezone.utc).isoformat(),
                'browser': browser_name, 'environment': environment(browser),
                'fixture': 'self-authored HTTP loopback catalog; synthetic state only',
                'records_per_extraction': 4,
                'runs': [one_round(playwright, browser, fixture, n) for n in range(1, rounds + 1)],
            }
        finally:
            browser.close()
    cases = [case for run in result['runs'] for case in run['cases']]
    result['checks'] = len(cases)
    result['passed_checks'] = sum(case['check_passed'] for case in cases)
    result['extraction_observations'] = sum(case['kind'] == 'extraction' for case in cases)
    result['diagnostic_observations'] = sum(case['kind'] == 'diagnostic' for case in cases)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chromium', 'firefox'], default='chromium')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error('--rounds must be positive')
    result = run(args.browser, args.rounds)
    serialized = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized)
    else:
        print(serialized, end='')
    print(json.dumps({k: result[k] for k in ('browser', 'checks', 'passed_checks', 'extraction_observations', 'diagnostic_observations')}))
    raise SystemExit(0 if result['checks'] == result['passed_checks'] else 1)
