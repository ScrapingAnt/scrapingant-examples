"""One paid task through each pinned official SDK; capture metadata only."""
import base64
import json
import os
import re
from contextlib import contextmanager
from unittest.mock import patch

import requests
from twocaptcha import TwoCaptcha
from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
from anticaptchaofficial.recaptchav3proxyless import recaptchaV3Proxyless
from anticaptchaofficial.geetestproxyless import geetestProxyless
from anticaptchaofficial.turnstileproxyless import turnstileProxyless
from anticaptchaofficial.imagecaptcha import imagecaptcha
from paid_demo import start_task, record_cost

ENV = {'2captcha': 'TWOCAPTCHA_API_KEY', 'anticaptcha': 'ANTICAPTCHA_API_KEY'}


@contextmanager
def bounded_transport():
    original = requests.sessions.Session.request
    def request(session, method, url, **kwargs):
        kwargs.update(timeout=(10, 30), allow_redirects=False)
        return original(session, method, url, **kwargs)
    with patch.object(requests.sessions.Session, 'request', request):
        yield


def balance(provider):
    endpoint = 'https://api.2captcha.com' if provider == '2captcha' else 'https://api.anti-captcha.com'
    data = requests.post(endpoint + '/getBalance', json={'clientKey': os.environ[ENV[provider]]},
                         timeout=(10, 20)).json()
    if data.get('errorId') != 0:
        raise ValueError('Balance/authentication error')
    return float(data['balance'])


class MeasuredTwo(TwoCaptcha):
    def __init__(self, key, result, save):
        super().__init__(key, defaultTimeout=300, recaptchaTimeout=300,
                         pollingInterval=10, extendedResponse=True)
        self.result, self.save, self.task_id = result, save, None

    def send(self, **kwargs):
        start_task(self.result)
        self.save()
        task_id = super().send(**kwargs)
        self.task_id = task_id
        self.result.update(paid_tasks_created=1, task_creation_uncertain=False)
        self.save()
        return task_id


class AntiMeasurement:
    def create_task(self, post_data):
        start_task(self.result)
        self.save()
        created = super().create_task(post_data)
        if created:
            self.result.update(paid_tasks_created=1, task_creation_uncertain=False)
        elif self.error_code:
            self.result['task_creation_uncertain'] = False
        self.save()
        return created

    def wait_for_result(self, max_seconds=300, current_second=0):
        # Same nominal 300 polling iterations for all types; outer process timeout
        # is the wall-clock bound. Native provider polling intervals still differ.
        response = super().wait_for_result(300, current_second)
        record_cost(self.result, response)
        return response


def solver_for(provider, case, spec, result, save):
    key = os.environ[ENV[provider]]
    if provider == '2captcha':
        return MeasuredTwo(key, result, save)
    base = {'recaptcha-v2': recaptchaV2Proxyless, 'recaptcha-invisible': recaptchaV2Proxyless,
            'recaptcha-v3': recaptchaV3Proxyless, 'geetest-v4': geetestProxyless,
            'turnstile': turnstileProxyless, 'image-text': imagecaptcha}[case]
    solver = type('MeasuredAnti', (AntiMeasurement, base), {})()
    solver.result, solver.save = result, save
    solver.set_key(key)
    solver.set_verbose(0)
    if case != 'image-text':
        solver.set_website_url(spec['url'])
        if case == 'geetest-v4':
            solver.set_gt_key(spec['sitekey'])
            solver.set_version(4)
        else:
            solver.set_website_key(spec['sitekey'])
    if case == 'recaptcha-invisible':
        solver.set_is_invisible(True)
    if case == 'recaptcha-v3':
        solver.set_min_score(0.5)
        solver.set_page_action(spec['action'])
    return solver


def solve(solver, provider, case, spec, image_bytes=None):
    if provider == 'anticaptcha':
        return (solver.solve_and_return_solution(None, body=image_bytes) if case == 'image-text'
                else solver.solve_and_return_solution())
    if case in ('recaptcha-v2', 'recaptcha-invisible', 'recaptcha-v3'):
        options = {}
        if case == 'recaptcha-invisible':
            options['invisible'] = 1
        if case == 'recaptcha-v3':
            options.update(version='v3', score=0.5, action=spec['action'])
        response = solver.recaptcha(sitekey=spec['sitekey'], url=spec['url'], **options)
    elif case == 'geetest-v4':
        response = solver.geetest_v4(captcha_id=spec['sitekey'], url=spec['url'])
    elif case == 'turnstile':
        response = solver.turnstile(sitekey=spec['sitekey'], url=spec['url'])
    else:
        response = solver.normal(base64.b64encode(image_bytes).decode('ascii'))
    record_cost(solver.result, response)
    answer = response.get('code')
    if case == 'geetest-v4' and isinstance(answer, str):
        answer = json.loads(answer)
    return answer


def extra_cost_receipt(solver, provider, result):
    # Read-only metadata lookup for the already-created v1 SDK task. Unsupported
    # receipts remain unknown; never create a second task to obtain a price.
    if provider != '2captcha' or not solver.task_id:
        return
    try:
        response = requests.post('https://api.2captcha.com/getTaskResult',
            json={'clientKey': solver.API_KEY, 'taskId': int(solver.task_id)}, timeout=(10, 20)).json()
        if response.get('errorId') == 0 and response.get('status') == 'ready':
            record_cost(result, response)
            result['cost_receipt'] = 'api-v2-read-only-existing-task'
        else:
            result['cost_receipt'] = 'unavailable'
    except Exception:
        result['cost_receipt'] = 'request_error'


def safe_error(exc, solver=None):
    code = getattr(solver, 'error_code', '')
    match = re.search(r'\bERROR_[A-Z_]+\b', str(exc))
    if not code and match:
        code = match.group()
    result = {'error_class': type(exc).__name__}
    if isinstance(code, str) and re.fullmatch(r'ERROR_[A-Z_]+', code):
        result['provider_error_code'] = code
    return result
