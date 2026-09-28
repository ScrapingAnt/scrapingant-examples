"""Capture browser observations without precomputed pass/fail flags."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from browser_support import browser, environment, fixture_server, source_hashes
from case_contract import EXTRACTION, DIAGNOSTICS
from extraction import CATALOG, project, wait_records
from oracle import has_class_token


def extraction_case(driver, origin, name):
    delayed = name in {'presence_only', 'complete_records_wait'}
    driver.get(origin + '/catalog.html' + ('?delayed=1' if delayed else ''))
    records, error = [], None
    try:
        catalog = driver.find_element(By.ID, 'catalog')
        if name == 'first_scoped':
            records = project([catalog.find_element(By.CSS_SELECTOR, '.product.active')])
        elif name == 'all_scoped_css':
            records = project(catalog.find_elements(By.CSS_SELECTOR, '.product.active'))
        elif name == 'relative_xpath':
            records = project(catalog.find_elements(By.XPATH, ".//article[contains(concat(' ', normalize-space(@class), ' '), ' active ')]"))
        elif name == 'unscoped_css':
            records = project(driver.find_elements(By.CSS_SELECTOR, '.product.active'))
        elif name in {'class_token', 'class_substring_wrong'}:
            rows = catalog.find_elements(By.CLASS_NAME, 'product')
            selected = [row for row in rows if (has_class_token(row.get_dom_attribute('class'), 'active') if name == 'class_token' else 'active' in row.get_dom_attribute('class'))]
            records = project(selected)
        elif name == 'presence_only':
            rows = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located(CATALOG))
            records = project(rows)
        elif name == 'complete_records_wait':
            driver.find_element(By.ID, 'begin').click()
            records = wait_records(driver)
        elif name in {'stale_handle', 'refind_after_replacement'}:
            old = driver.find_elements(*CATALOG)
            driver.find_element(By.ID, 'replace').click()
            WebDriverWait(driver, 5).until(EC.staleness_of(old[0]))
            records = project(old) if name == 'stale_handle' else wait_records(driver)
        elif name == 'iframe_context':
            WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'catalog-frame')))
            try:
                records = wait_records(driver)
            finally:
                driver.switch_to.default_content()
        elif name == 'open_shadow_root':
            root = driver.find_element(By.ID, 'shadow-host').shadow_root
            records = project(root.find_elements(By.CSS_SELECTOR, '.product.active'))
        else:
            raise ValueError('unknown extraction case')
    except WebDriverException as exc:
        # Persist exact exception type, without stack traces containing host paths.
        error = type(exc).__name__
    return {'records': records, 'error': error}


def diagnostic_case(driver, origin, name):
    driver.get(origin + '/catalog.html')
    try:
        if name == 'missing_singular':
            driver.find_element(By.CSS_SELECTOR, '.not-present')
            return {'error': None}
        if name == 'missing_plural':
            return {'count': len(driver.find_elements(By.CSS_SELECTOR, '.not-present'))}
        if name == 'compound_class_name':
            driver.find_elements(By.CLASS_NAME, 'product active')
            return {'error': None}
        if name == 'text_boundaries':
            element = driver.find_element(By.ID, 'text-boundary')
            return {'visible_text': element.text, 'text_content': element.get_property('textContent')}
        if name == 'attribute_property':
            field = driver.find_element(By.ID, 'value-boundary')
            link = driver.find_element(*CATALOG).find_element(By.CSS_SELECTOR, '.title')
            url = urlsplit(link.get_property('href'))
            return {'value_attribute': field.get_dom_attribute('value'), 'value_property': field.get_property('value'),
                    'value_get_attribute': field.get_attribute('value'), 'href_attribute': link.get_dom_attribute('href'),
                    'href_property_is_absolute_loopback': url.scheme == 'http' and url.netloc == urlsplit(origin).netloc and url.path == '/products/cafe'}
    except WebDriverException as exc:
        return {'error': type(exc).__name__}
    raise ValueError('unknown diagnostic')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chrome', 'firefox'], default='chrome')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with fixture_server() as origin, browser(args.browser) as driver:
        packet = {'schema_version': 1, 'rounds': 3, 'environment': environment(driver), 'source_hashes': source_hashes(), 'observations': []}
        for number in (1, 2, 3):
            for name in EXTRACTION:
                packet['observations'].append({'round': number, 'case': name, 'kind': 'extraction', **extraction_case(driver, origin, name)})
            for name in DIAGNOSTICS:
                packet['observations'].append({'round': number, 'case': name, 'kind': 'diagnostic', 'values': diagnostic_case(driver, origin, name)})
            print(f'{args.browser}: captured round {number}/3', flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(packet['environment'], indent=2))


if __name__ == '__main__':
    main()
