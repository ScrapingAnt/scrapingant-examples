"""Capture full observations for three rounds; query-only controls stay separate by transport."""
import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import selenium
from selenium.common.exceptions import JavascriptException
from browser_support import browser, environment, read_page, wait_catalog
from catalog_fixture import fixture_server
from case_contract import EXTRACTIONS
from local_http import fetch_catalog
from oracle import desired_matches, exact_dataset
from storage_state import (JSON_VALUE, SPECIAL_KEY, SPECIAL_VALUE, get_item, remove_item,
                           restore, set_item, snapshot)


def observation(name, page, event):
    region, stored, session, transport = EXTRACTIONS[name]
    result = {'case': name, 'kind': 'extraction', 'transport': transport,
              'stored_region': page['stored_region'], 'session_region': page['session_region'],
              'rendered_region': page['rendered_region'], 'page_path': page['page_path'], 'request_path': page['request_path'],
              'request_event': event, 'records': page['records'], 'ready': page['ready'],
              'matching_records': desired_matches(page['records']),
              'row_count': len(page['records']), 'expected_records': 4}
    result['assertion_passed'] = (exact_dataset(page['records'], region)
                                  and page['stored_region'] == stored and page['session_region'] == session
                                  and page['ready'] is True and page['rendered_region'] == region
                                  and event['path'] == page['request_path'] and event['region'] == region
                                  and event['status'] == 200 and event['records'] == page['records'])
    return result


def capture(driver, server, name):
    region, stored, _, _ = EXTRACTIONS[name]
    page = wait_catalog(driver, stored, region)
    return observation(name, page, dict(server.events[-1]))


def diagnostic(name, passed, **data):
    return dict(case=name, kind='diagnostic', assertion_passed=passed, **data)


def one_round(kind, round_id, server, base, second_server, second_base, run):
    cases = run['cases']
    with browser(kind) as driver:
        env = environment(driver)
        run['environment'] = env
        driver.get('data:text/html,<title>Opaque origin</title>')
        error = driver.execute_script('try { localStorage.setItem("x", "1"); return null; } catch (e) { return e.name; }')
        cases.append(diagnostic('opaque_origin', error == 'SecurityError', error=error))

        driver.get(base+'/catalog')
        cases.append(capture(driver, server, 'empty_startup'))
        driver.get(base+'/blank')
        set_item(driver, 'demo_region', 'eu')
        driver.get(base+'/catalog')
        cases.append(capture(driver, server, 'bootstrap_seed'))

        set_item(driver, SPECIAL_KEY, SPECIAL_VALUE)
        returned = get_item(driver, SPECIAL_KEY)
        cases.append(diagnostic('argument_roundtrip', returned == SPECIAL_VALUE,
                                key=SPECIAL_KEY, value=returned))
        error = None
        try:
            # Deliberately broken, controlled negative example. Never use real input here.
            driver.execute_script("localStorage.setItem('legacy', '"+SPECIAL_VALUE+"');")
        except JavascriptException as exc:
            error = type(exc).__name__
        cases.append(diagnostic('legacy_interpolation_failure', error == 'JavascriptException'
                                and get_item(driver, 'legacy') is None,
                                error=error, legacy_value=get_item(driver, 'legacy')))
        set_item(driver, 'json', json.dumps(JSON_VALUE, ensure_ascii=False))
        decoded = json.loads(get_item(driver, 'json'))
        browser_decoded = driver.execute_script('return JSON.parse(localStorage.getItem(arguments[0]));', 'json')
        cases.append(diagnostic('json_roundtrip', decoded == JSON_VALUE == browser_decoded,
                                python_value=decoded, browser_value=browser_decoded))
        state = snapshot(driver, base)
        # Serialize and deserialize explicitly: the next driver restores this exported JSON.
        state = json.loads(json.dumps(state, ensure_ascii=False))

        driver.get(second_base+'/blank')
        before = snapshot(driver, second_base)
        error = None
        try:
            restore(driver, state, base)
        except ValueError as exc:
            error = type(exc).__name__
        after = snapshot(driver, second_base)
        cases.append(diagnostic('wrong_origin_restore_rejected', error == 'ValueError' and before == after,
                                error=error, unchanged=before == after, before_items=before['items'],
                                after_items=after['items'], source_origin=base, current_origin=second_base))
        driver.get(second_base+'/catalog')
        cases.append(capture(driver, second_server, 'wrong_port'))

        driver.get(base+'/blank')
        driver.execute_script('localStorage.clear(); sessionStorage.clear();')
        driver.get(base+'/catalog')
        wait_catalog(driver, None, 'us')
        set_item(driver, 'demo_region', 'eu')
        cases.append(capture(driver, server, 'late_write_without_reload'))
        driver.refresh()
        cases.append(capture(driver, server, 'reload_after_late_write'))
        set_item(driver, 'keep_me', 'retained')
        remove_item(driver, 'demo_region')
        remaining_region = get_item(driver, 'demo_region')
        retained = get_item(driver, 'keep_me')
        cases.append(diagnostic('crud_selective_removal', remaining_region is None and retained == 'retained',
                                removed_value=remaining_region, retained_value=retained))
        driver.execute_script('sessionStorage.setItem(arguments[0], arguments[1]);', 'demo_region', 'eu')
        driver.refresh()
        cases.append(capture(driver, server, 'session_storage_only'))
        driver.execute_script('sessionStorage.clear();')
        before = driver.execute_script('return window.scheduleEu();')
        cases.append(diagnostic('async_precondition', before == {'storedRegion': None, 'region': 'us', 'stage': 'scheduled'},
                                observed=before))
        cases.append(capture(driver, server, 'delayed_application_update'))

    with browser(kind) as driver:
        driver.get(base+'/catalog')
        cases.append(capture(driver, server, 'fresh_driver_empty'))
        driver.get(base+'/catalog?region=eu')
        cases.append(capture(driver, server, 'query_page_without_storage'))
        driver.get(base+'/blank')
        restored = restore(driver, state, base)
        if restored != 3 or get_item(driver, SPECIAL_KEY) != SPECIAL_VALUE:
            raise AssertionError('snapshot string restoration failed')
        actual_snapshot = snapshot(driver, base)
        cases.append(diagnostic('snapshot_restore_contents', actual_snapshot == state,
                                exported_snapshot=state, restored_snapshot=actual_snapshot))
        driver.get(base+'/catalog')
        cases.append(capture(driver, server, 'manual_snapshot_restore'))

    for name, path in [('query_parameter_only', '/api/catalog?region=eu'),
                       ('query_parameter_missing', '/api/catalog')]:
        # No browser state, cookies or API credentials are copied to this direct request.
        data = fetch_catalog(base+path)
        cases.append(observation(name, dict(stored_region=None, session_region=None, ready=True,
                                             rendered_region=data['region'], page_path=path, request_path=path,
                                             records=data['records']), dict(server.events[-1])))
    return {'round': round_id, 'environment': env, 'cases': cases}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chrome', 'firefox'], default='chrome')
    parser.add_argument('--rounds', type=int, choices=[1, 2, 3], default=3)
    parser.add_argument('--output', type=Path, default=Path('run_output/chrome.json'))
    args = parser.parse_args()
    report = {'schema_version': 1, 'tested_at': datetime.now(timezone.utc).isoformat(),
              'browser': args.browser, 'python': platform.python_version(),
              'selenium': selenium.__version__, 'os': platform.platform(), 'runs': []}
    try:
        with fixture_server() as (server, base), fixture_server() as (second_server, second_base):
            for round_id in range(1, args.rounds+1):
                run = {'round': round_id, 'environment': {}, 'cases': []}
                report['runs'].append(run)
                one_round(args.browser, round_id, server, base, second_server, second_base, run)
    except Exception as exc:
        # Keep completed observations. Do not publish exception text (may contain paths).
        report['failure'] = {'error_type': type(exc).__name__}
    report['assertions'] = sum(len(run['cases']) for run in report['runs'])
    report['passed'] = sum(case['assertion_passed'] for run in report['runs'] for case in run['cases'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'browser': args.browser, 'rounds': args.rounds, 'assertions': report['assertions'],
                      'passed': report['passed'], 'output': str(args.output),
                      'error_type': report.get('failure', {}).get('error_type')}))
    return 0 if 'failure' not in report and report['passed'] == report['assertions'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
