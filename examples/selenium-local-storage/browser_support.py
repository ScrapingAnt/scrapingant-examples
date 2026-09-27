"""Fresh Selenium profiles; optional binary/driver overrides are not secret inputs."""
import os
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait


@contextmanager
def browser(kind='chrome'):
    if kind == 'chrome':
        options = webdriver.ChromeOptions()
        for flag in ('--headless=new', '--disable-dev-shm-usage', '--disable-background-networking'):
            options.add_argument(flag)
        if os.getenv('SELENIUM_NO_SANDBOX') == '1':
            options.add_argument('--no-sandbox')
        if os.getenv('CHROME_BINARY'):
            options.binary_location = os.environ['CHROME_BINARY']
        service = ChromeService(executable_path=os.environ['CHROMEDRIVER']) if os.getenv('CHROMEDRIVER') else ChromeService()
        driver = webdriver.Chrome(options=options, service=service)
    elif kind == 'firefox':
        options = webdriver.FirefoxOptions(); options.add_argument('-headless')
        if os.getenv('FIREFOX_BINARY'):
            options.binary_location = os.environ['FIREFOX_BINARY']
        service = FirefoxService(executable_path=os.environ['GECKODRIVER']) if os.getenv('GECKODRIVER') else FirefoxService()
        driver = webdriver.Firefox(options=options, service=service)
    else:
        raise ValueError('unsupported browser')
    driver.set_page_load_timeout(20)
    try:
        yield driver
    finally:
        driver.quit()


def environment(driver):
    caps = driver.capabilities
    return {'browser': caps['browserName'], 'browser_version': caps['browserVersion'],
            'driver_version': caps.get('chrome', {}).get('chromedriverVersion', caps.get('moz:geckodriverVersion'))}


def read_page(driver):
    return driver.execute_script('''return {
      page_path: location.pathname + location.search,
      stored_region: localStorage.getItem('demo_region'),
      session_region: sessionStorage.getItem('demo_region'),
      ready: window.catalog?.ready ?? false,
      rendered_region: window.catalog?.region ?? null,
      request_path: window.catalog?.requestPath ?? null,
      error: window.catalog?.error ?? null,
      records: [...document.querySelectorAll('#products tr')].map(row => ({
        sku: row.dataset.sku,
        currency: row.querySelector('.currency').textContent,
        price_minor: Number(row.querySelector('.price_minor').textContent)
      }))};''')


def wait_catalog(driver, stored_region, rendered_region):
    # Poll storage AND loaded records. Storage alone can change before fetch/render completes.
    from oracle import exact_dataset
    def predicate(current):
        page = read_page(current)
        if page['error']:
            raise RuntimeError(page['error'])
        return page if (page['stored_region'] == stored_region and page['ready']
                        and page['rendered_region'] == rendered_region
                        and exact_dataset(page['records'], rendered_region)) else False
    return WebDriverWait(driver, 10, poll_frequency=0.05).until(predicate)
