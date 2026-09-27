"""Measure extracted records, not just cookie insertion or HTTP success."""
import argparse
import json
import os
import platform
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import InvalidCookieDomainException
from selenium.webdriver.common.by import By

from catalog_fixture import fixture_server
from cookie_state import save_snapshot, restore_snapshot

# Explicit independent oracle: do not generate this from the fixture price table.
EXPECTED = [
    {'sku': 'SKU-1', 'currency': 'EUR', 'price_minor': 800},
    {'sku': 'SKU-2', 'currency': 'EUR', 'price_minor': 1600},
    {'sku': 'SKU-3', 'currency': 'EUR', 'price_minor': 2400},
    {'sku': 'SKU-4', 'currency': 'EUR', 'price_minor': 3200},
]


def matching_records(records):
    def keys(rows):
        return Counter((r['sku'], r['currency'], r['price_minor']) for r in rows)
    return sum((keys(records) & keys(EXPECTED)).values())


@contextmanager
def browser(kind):
    if kind == 'chrome':
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1100,800')
        if os.getenv('CHROME_BINARY'): options.binary_location = os.environ['CHROME_BINARY']
        factory = webdriver.Chrome
    else:
        options = webdriver.FirefoxOptions(); options.add_argument('-headless')
        if os.getenv('FIREFOX_VERSION'): options.browser_version = os.environ['FIREFOX_VERSION']
        if os.getenv('FIREFOX_BINARY'): options.binary_location = os.environ['FIREFOX_BINARY']
        factory = webdriver.Firefox
    # Only the self-authored localhost HTTPS fixture is visited by this runner.
    options.accept_insecure_certs = True
    driver = factory(options=options)
    driver.set_page_load_timeout(30)
    try: yield driver
    finally: driver.quit()


def extract(driver, server, base, name, expected_matches, **extra):
    driver.get(base+'/catalog/')
    records = [
        {'sku': row.get_attribute('data-sku'),
         'currency': row.find_element(By.CSS_SELECTOR, '.currency').text,
         'price_minor': int(row.find_element(By.CSS_SELECTOR, '.price').text)}
        for row in driver.find_elements(By.CSS_SELECTOR, '#products tr')
    ]
    matched = matching_records(records)
    result = {'case': name, 'kind': 'extraction', 'target_status': server.events[-1]['status'],
              'row_count': len(records), 'matching_records': matched, 'expected_records': len(EXPECTED),
              'records': records, 'tier': driver.find_element(By.ID, 'tier').text, **extra}
    result['assertion_passed'] = len(records) == 4 and matched == expected_matches
    return result


def one_round(kind, round_id, server, base, tmp):
    results = []
    snapshot = Path(tmp)/'cookies.json'
    with browser(kind) as driver:
        caps = driver.capabilities
        environment = {'browser': caps['browserName'], 'browser_version': caps['browserVersion'],
                       'driver_version': caps.get('chrome', {}).get('chromedriverVersion', caps.get('moz:geckodriverVersion'))}
        driver.get('about:blank')
        error = None
        try: driver.add_cookie({'name': 'demo_region', 'value': 'eu'})
        except InvalidCookieDomainException as exc: error = type(exc).__name__
        results.append({'case': 'about_blank', 'kind': 'diagnostic', 'error': error,
                        'assertion_passed': error == 'InvalidCookieDomainException'})
        results.append(extract(driver, server, base, 'anonymous', 0))
        driver.get(base+'/seed')
        results.append(extract(driver, server, base, 'server_seeded', 4))
        cookie_names = sorted(c['name'] for c in driver.get_cookies())
        js_names = sorted(v.split('=', 1)[0].strip() for v in driver.execute_script('return document.cookie').split(';') if v.strip())
        results.append({'case': 'httponly_visibility', 'kind': 'diagnostic',
                        'webdriver_names': cookie_names, 'javascript_names': js_names,
                        'assertion_passed': 'demo_session' in cookie_names and 'demo_session' not in js_names})
        save_snapshot(driver, snapshot, base)
        stored = json.loads(snapshot.read_text())
        driver.save_screenshot(str(Path(tmp)/'member-eur.png'))
        error = None
        try: driver.add_cookie({'name': 'demo_region', 'value': 'eu', 'domain': 'unrelated.example'})
        except InvalidCookieDomainException as exc: error = type(exc).__name__
        results.append({'case': 'wrong_domain', 'kind': 'diagnostic', 'error': error,
                        'assertion_passed': error == 'InvalidCookieDomainException'})

    with browser(kind) as driver:
        driver.get(base+'/blank')
        stats = restore_snapshot(driver, snapshot, base)
        results.append(extract(driver, server, base, 'full_restore_fresh_browser', 4, restore=stats))

        def altered(cookies):
            driver.get(base+'/blank'); driver.delete_all_cookies()
            server.session_active = True
            snapshot.write_text(json.dumps(dict(stored, cookies=cookies)))
            return restore_snapshot(driver, snapshot, base)

        altered([c for c in stored['cookies'] if c['name'] == 'demo_session'])
        results.append(extract(driver, server, base, 'auth_cookie_only', 0))
        altered([c for c in stored['cookies'] if not c.get('httpOnly')])
        results.append(extract(driver, server, base, 'javascript_visible_only', 0))
        altered([dict(c, path='/admin/') if c['name'] == 'demo_session' else c for c in stored['cookies']])
        results.append(extract(driver, server, base, 'wrong_session_path', 0))
        stats = altered([dict(c, expiry=int(time.time())-60) if c['name'] == 'demo_session' else c for c in stored['cookies']])
        results.append(extract(driver, server, base, 'expired_session_filtered', 0, restore=stats))
        altered(stored['cookies']); server.session_active = False
        results.append(extract(driver, server, base, 'server_revoked_session', 0,
                               cookie_still_in_browser=driver.get_cookie('demo_session') is not None))
        altered(stored['cookies']); driver.delete_cookie('demo_session')
        results.append(extract(driver, server, base, 'deleted_session', 0))
        driver.delete_all_cookies()
        results.append({'case': 'delete_all', 'kind': 'diagnostic',
                        'remaining_cookie_count': len(driver.get_cookies()), 'assertion_passed': driver.get_cookies() == []})
    return {'round': round_id, 'environment': environment, 'cases': results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chrome', 'firefox'], default='chrome')
    parser.add_argument('--rounds', type=int, choices=range(1, 11), default=3)
    parser.add_argument('--output', type=Path, default=Path('run_output/chrome.json'))
    args = parser.parse_args()
    import selenium
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'browser': args.browser,
              'python': platform.python_version(), 'selenium': selenium.__version__,
              'os': platform.platform(), 'expected_member_eur': EXPECTED, 'runs': []}
    with fixture_server() as (server, base), tempfile.TemporaryDirectory(prefix='cookie-state-') as tmp:
        for i in range(1, args.rounds+1):
            report['runs'].append(one_round(args.browser, i, server, base, tmp))
    report['assertions'] = sum(len(run['cases']) for run in report['runs'])
    report['passed'] = sum(c['assertion_passed'] for run in report['runs'] for c in run['cases'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'browser': args.browser, 'rounds': args.rounds, 'assertions': report['assertions'],
                      'passed': report['passed'], 'output': str(args.output)}))
    return 0 if report['passed'] == report['assertions'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
