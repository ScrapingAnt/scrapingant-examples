"""Opt-in, one-task SDK experiment on Google's public reCAPTCHA v2 demo
(hCaptcha's public demo for NoneCap, which solves hCaptcha only).

No default/CI caller spends money. Do not loop failed runs to select a success.
SDK request timeouts are supplied by a scoped requests transport patch because
the pinned SDKs omit them. Provider polling and solving remain SDK behavior.
The SIGALRM field records an intended interruption, not a hard process bound;
the measured runs also used an external subprocess timeout of 400 seconds.
"""
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import signal
import time
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
from playwright.sync_api import sync_playwright
from twocaptcha import TwoCaptcha

URL = 'https://www.google.com/recaptcha/api2/demo'
SITEKEY = '6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-'
SPECS = {
    '2captcha': ('2captcha-python', 'TWOCAPTCHA_API_KEY'),
    'anticaptcha': ('anticaptchaofficial', 'ANTICAPTCHA_API_KEY'),
    'nonecap': ('2captcha-python', 'NONECAP_API_KEY'),
}
# NoneCap serves the 2Captcha in.php/res.php protocol, so the same SDK runs it.
SERVERS = {'nonecap': 'api.nonecap.com/compat/2captcha'}
HCAPTCHA_URL = 'https://accounts.hcaptcha.com/demo'
HCAPTCHA_SITEKEY = 'a5f74b19-9e45-40e0-b45d-47ff91b7a6c2'
TARGETS = {
    'recaptcha': {'url': URL, 'sitekey': SITEKEY, 'task_type': 'recaptcha-v2-proxyless',
                  'field': 'g-recaptcha-response', 'submit': '#recaptcha-demo-submit'},
    'hcaptcha': {'url': HCAPTCHA_URL, 'sitekey': HCAPTCHA_SITEKEY, 'task_type': 'hcaptcha-proxyless',
                 'field': 'h-captcha-response', 'submit': '#hcaptcha-demo-submit'},
}
CAPTCHA = {'nonecap': 'hcaptcha'}


def accepted(target, status, url, text):
    if target['field'] == 'h-captcha-response':
        # The demo prints its own siteverify response after the POST.
        return status == 200 and url == target['url'] and re.search(r'"success"\s*:\s*true', text) is not None
    return status == 200 and url == target['url'] and 'Verification Success' in text


def record_cost(result, response):
    # Never serialize the response: it can include tokens, worker IPs or cookies.
    cost = response.get('cost') if isinstance(response, dict) else None
    if cost is not None and re.fullmatch(r'\d+(?:\.\d+)?', str(cost)):
        result['provider_reported_cost_usd'] = str(cost)


def start_task(result):
    if result['task_create_requests']:
        raise RuntimeError('One task per invocation')
    result['task_create_requests'] = 1
    result['task_creation_uncertain'] = True


class MeasuredTwoCaptcha(TwoCaptcha):
    def __init__(self, key, result, server='2captcha.com'):
        super().__init__(key, server=server, recaptchaTimeout=300, pollingInterval=10,
                         extendedResponse=True)
        self.measurement = result

    def send(self, **kwargs):
        start_task(self.measurement)
        task_id = super().send(**kwargs)
        self.measurement.update(paid_tasks_created=1, task_creation_uncertain=False)
        return task_id


class MeasuredAntiCaptcha(recaptchaV2Proxyless):
    def __init__(self, key, result):
        self.set_key(key)
        self.set_verbose(0)
        self.measurement = result

    def create_task(self, post_data):
        start_task(self.measurement)
        created = super().create_task(post_data)
        if created:
            self.measurement.update(paid_tasks_created=1, task_creation_uncertain=False)
        elif self.error_code:
            self.measurement['task_creation_uncertain'] = False
        return created

    def wait_for_result(self, max_seconds=300, current_second=0):
        response = super().wait_for_result(max_seconds, current_second)
        record_cost(self.measurement, response)
        return response


def deadline(*_):
    raise TimeoutError('Experiment deadline')


def run(provider, trial):
    package, variable = SPECS[provider]
    target = TARGETS[CAPTCHA.get(provider, 'recaptcha')]
    result = {
        'provider': provider, 'package': package, 'version': metadata.version(package),
        'trial': trial, 'tested_at': datetime.now(timezone.utc).isoformat(),
        'target': target['url'], 'test_mode': False, 'headed': False,
        'task_type': target['task_type'], 'task_budget': 1,
        'task_create_requests': 0, 'paid_tasks_created': 0,
        'task_creation_uncertain': False, 'server_acceptance_tested': False,
        'server_accepted': False, 'token_length': 0,
        'provider_reported_cost_usd': None, 'whole_run_deadline_seconds': 360,
        'http_timeout_seconds': {'connect': 10, 'read': 30},
    }
    start = time.monotonic()
    key = os.environ.get(variable)
    if not key:
        result.update(outcome='unavailable', reason='missing_credential')
        return result, 2
    solver = (MeasuredAntiCaptcha(key, result) if provider == 'anticaptcha'
              else MeasuredTwoCaptcha(key, result, SERVERS.get(provider, '2captcha.com')))
    original_request = requests.sessions.Session.request

    def timed_request(session, method, url, **kwargs):
        kwargs['timeout'] = (10, 30)
        kwargs['allow_redirects'] = False
        return original_request(session, method, url, **kwargs)

    previous_handler = signal.signal(signal.SIGALRM, deadline)
    signal.alarm(360)
    stage = 'balance_preflight'
    try:
        with patch.object(requests.sessions.Session, 'request', timed_request):
            balance = solver.get_balance() if provider == 'anticaptcha' else solver.balance()
            if balance <= 0:
                result.update(outcome='unavailable', reason='no_positive_balance_or_api_error')
                return result, 2
            stage = 'browser_setup'
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                try:
                    result['browser'] = browser.version
                    page = browser.new_page(viewport={'width': 1200, 'height': 850}, locale='en-US')
                    page.set_default_timeout(15000)
                    navigation = page.goto(target['url'], wait_until='domcontentloaded')
                    result['navigation_status'] = navigation.status if navigation else None
                    actual_key = page.locator('[data-sitekey]').get_attribute('data-sitekey')
                    if actual_key != target['sitekey'] or page.url != target['url']:
                        raise ValueError('Demo changed; stop before creating a task')
                    field = page.locator('[name="%s"]' % target['field'])
                    field.wait_for(state='attached')
                    stage = 'provider_solve'
                    solve_start = time.monotonic()
                    try:
                        if provider == '2captcha':
                            response = solver.recaptcha(sitekey=SITEKEY, url=URL)
                            record_cost(result, response)
                            token = response.get('code')
                        elif provider == 'nonecap':
                            response = solver.hcaptcha(sitekey=HCAPTCHA_SITEKEY, url=HCAPTCHA_URL)
                            record_cost(result, response)
                            token = response.get('code')
                        else:
                            solver.set_website_url(URL)
                            solver.set_website_key(SITEKEY)
                            token = solver.solve_and_return_solution()
                    finally:
                        result['provider_elapsed_seconds'] = round(time.monotonic() - solve_start, 2)
                    if not isinstance(token, str) or not token:
                        raise ValueError('Provider returned no token')
                    result['token_length'] = len(token)
                    stage = 'form_submission'
                    field.evaluate('(element, token) => { element.value = token; }', token)
                    with page.expect_navigation(wait_until='domcontentloaded') as navigation:
                        page.locator(target['submit']).click()
                    submission = navigation.value
                    result['submission_status'] = submission.status if submission else None
                    result['server_acceptance_tested'] = True
                    # Read the new document after submission, not the checkbox state.
                    result['server_accepted'] = accepted(
                        target, result['submission_status'], page.url, page.locator('body').inner_text())
                    result['outcome'] = 'accepted' if result['server_accepted'] else 'not_accepted'
                    Path('screenshots').mkdir(exist_ok=True)
                    try:
                        page.screenshot(path=f'screenshots/{provider}-paid-{trial}.png', timeout=5000)
                    except Exception as exc:
                        result['screenshot_error'] = type(exc).__name__
                finally:
                    browser.close()
    except Exception as exc:
        result.update(outcome='error', error_stage=stage, error_class=type(exc).__name__)
        # Exception messages can contain keys, task IDs or token-bearing URLs.
        # Retain only a provider error code, never the raw message/response.
        code = getattr(solver, 'error_code', '')
        match = re.search(r'\bERROR_[A-Z_]+\b', str(exc))
        if not code and match:
            code = match.group()
        if re.fullmatch(r'ERROR_[A-Z_]+', code):
            result['provider_error_code'] = code
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
        result['elapsed_seconds'] = round(time.monotonic() - start, 2)
    return result, 0 if result['server_accepted'] else 1


def cli(provider):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Spend funds on at most ONE task')
    parser.add_argument('--trial', type=int, choices=(1, 2), default=1, help='Capture label, not a retry count')
    args = parser.parse_args()
    if not args.live:
        from provider_preflight import main
        return main(provider)
    result, status = run(provider, args.trial)
    print(json.dumps(result, indent=2))
    return status
