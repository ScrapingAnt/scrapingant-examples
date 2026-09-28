"""Ephemeral browser profiles and a server bound only to loopback."""
import hashlib
import os
import platform
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

ROOT = Path(__file__).resolve().parent


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@contextmanager
def fixture_server():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'fixtures')))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


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
        options = webdriver.FirefoxOptions()
        options.add_argument('-headless')
        if os.getenv('FIREFOX_BINARY'):
            options.binary_location = os.environ['FIREFOX_BINARY']
        service = FirefoxService(executable_path=os.environ['GECKODRIVER']) if os.getenv('GECKODRIVER') else FirefoxService()
        driver = webdriver.Firefox(options=options, service=service)
    else:
        raise ValueError('unsupported browser')
    try:
        driver.set_page_load_timeout(20)
        driver.implicitly_wait(0)
        yield driver
    finally:
        driver.quit()


def environment(driver):
    caps = driver.capabilities
    driver_version = caps.get('chrome', {}).get('chromedriverVersion', caps.get('moz:geckodriverVersion'))
    return {'browser': caps['browserName'], 'browser_version': caps['browserVersion'],
            'driver_version': driver_version.split(' ')[0] if driver_version else None,
            'python': platform.python_version(), 'selenium': selenium.__version__,
            'os': platform.system(), 'os_release': platform.release(), 'architecture': platform.machine()}


def source_hashes():
    paths = list(ROOT.glob('*.py')) + list(ROOT.glob('requirements*.txt')) + [ROOT / 'run.sh'] + list((ROOT / 'fixtures').glob('*.html'))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}
