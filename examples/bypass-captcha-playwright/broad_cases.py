"""Fixed public demo fixtures and conservative, typed outcome classification."""
import hashlib
import json
from pathlib import Path
import random
import re

CASES = {
    'recaptcha-v2': {'url': 'https://www.google.com/recaptcha/api2/demo',
                     'sitekey': '6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-',
                     'criterion': 'server-accepted-form'},
    'recaptcha-invisible': {'url': 'https://recaptcha-demo.appspot.com/recaptcha-v2-invisible.php',
                            'sitekey': '6LcmDCcUAAAAAL5QmnMvDFnfPTP4iCUYRk2MwC0-',
                            'criterion': 'server-accepted-form'},
    'recaptcha-v3': {'url': 'https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php',
                     'sitekey': '6LdKlZEpAAAAAAOQjzC2v_d36tWxCl6dWsozdSy9',
                     'action': 'examples/v3scores', 'min_score': 0.5,
                     'criterion': 'server-valid-token-action-hostname-score-at-least-0.5'},
    'geetest-v4': {'url': 'https://2captcha.com/demo/geetest-v4',
                   'sitekey': 'e392e1d7fd421dc63325744d5a2b9c73',
                   'criterion': 'demo-server-verification'},
    'turnstile': {'url': 'https://peet.ws/turnstile-test/non-interactive.html',
                  'sitekey': '0x4AAAAAAABS7vwvV6VFfMcD',
                  'criterion': 'token-delivery-only-no-server-verifier'},
    'image-text': {'url': None, 'criterion': 'case-insensitive-exact-ground-truth'},
}
IMAGE_DIR = Path(__file__).parent / 'fixtures' / 'image-text'


def safe_verification(data):
    """Only typed verification fields; never arbitrary response content."""
    result = {}
    if not isinstance(data, dict):
        return result
    if type(data.get('success')) is bool:
        result['success'] = data['success']
    if data.get('result') in ('success', 'fail'):
        result['result'] = data['result']
    if data.get('status') in ('error', 'success'):
        result['status'] = data['status']
    if isinstance(data.get('code'), str) and re.fullmatch(r'-?\d{1,8}', data['code']):
        result['code'] = data['code']
    if type(data.get('score')) in (int, float) and 0 <= data['score'] <= 1:
        result['score'] = data['score']
    if data.get('action') == 'examples/v3scores':
        result['action'] = data['action']
    if data.get('hostname') in ('recaptcha-demo.appspot.com', '2captcha.com', 'www.google.com'):
        result['hostname'] = data['hostname']
    errors = data.get('error-codes')
    allowed_errors = {'missing-input-response', 'invalid-input-response', 'timeout-or-duplicate',
                      'hostname-mismatch', 'action-mismatch', 'score-threshold-not-met',
                      'challenge-timeout', 'bad-request', 'invalid-input-secret', 'missing-input-secret'}
    if isinstance(errors, list):
        result['error-codes'] = [x for x in errors if isinstance(x, str) and x in allowed_errors]
    return result


def classify_verification(case, status, data):
    if status != 200:
        return False
    if case == 'turnstile':
        return False
    if case == 'geetest-v4':
        return data.get('result') == 'success'
    if case == 'recaptcha-v3':
        return (data.get('success') is True and type(data.get('score')) in (float, int)
                and 0.5 <= data['score'] <= 1 and data.get('action') == 'examples/v3scores'
                and data.get('hostname') == 'recaptcha-demo.appspot.com')
    return data.get('success') is True


def prepare_page(page, case):
    spec = CASES[case]
    # Suppress this demo's automatic native-token verification. The paid token is
    # sent explicitly with browser-context request.get, which does not use routes.
    if case == 'recaptcha-v3':
        page.route('**/recaptcha-v3-verify.php*', lambda route: route.abort())
    response = page.goto(spec['url'], wait_until='domcontentloaded')
    if not response or response.status != 200 or page.url != spec['url']:
        raise ValueError('Fixture navigation changed')
    if case in ('recaptcha-v2', 'recaptcha-invisible', 'turnstile'):
        key = page.locator('[data-sitekey]').first.get_attribute('data-sitekey')
        if key != spec['sitekey']:
            raise ValueError('Fixture sitekey changed')
        if case.startswith('recaptcha'):
            page.locator('[name="g-recaptcha-response"]').first.wait_for(state='attached')
    elif case == 'recaptcha-v3':
        if page.locator(f'script[src*="render={spec["sitekey"]}"]').count() != 1:
            raise ValueError('Fixture sitekey changed')
    elif case == 'geetest-v4':
        page.wait_for_function('''key => performance.getEntriesByType('resource').some(
            x => x.name.includes('gcaptcha4.geetest.com/load?') && x.name.includes(key))''', arg=spec['sitekey'])
    return response.status


def verify_solution(page, case, solution):
    spec = CASES[case]
    if case == 'turnstile':
        return {'server_acceptance_tested': False, 'server_accepted': None,
                'verification': {}, 'submission_status': None}
    if case in ('recaptcha-v2', 'recaptcha-invisible'):
        # The invisible demo can render two response fields during initialization.
        # Both represent this page's checked sitekey; fill all before native submit.
        page.locator('[name="g-recaptcha-response"]').evaluate_all(
            '(elements, value) => elements.forEach(e => { e.value = value; })', solution)
        with page.expect_navigation(wait_until='domcontentloaded') as pending:
            if case == 'recaptcha-v2':
                page.locator('#recaptcha-demo-submit').click()
            else:
                page.evaluate('document.getElementById("demo-form").submit()')
        response = pending.value
        status = response.status if response else None
        headings = page.locator('h2').all_text_contents()
        success = ('Verification Success' in page.locator('body').inner_text()
                   if case == 'recaptcha-v2' else 'Success!' in headings)
        success = success and page.url == spec['url']
        body = page.locator('body').inner_text()
        errors = [x for x in ('invalid-input-response', 'timeout-or-duplicate', 'hostname-mismatch') if x in body]
        data = {'success': success, 'error-codes': errors}
    elif case == 'recaptcha-v3':
        response = page.request.get('https://recaptcha-demo.appspot.com/recaptcha-v3-verify.php',
                                    params={'action': spec['action'], 'token': solution}, timeout=20000)
        status, data = response.status, response.json()
    else:
        required = ('captcha_id', 'lot_number', 'pass_token', 'gen_time', 'captcha_output')
        if not isinstance(solution, dict) or not all(k in solution for k in required):
            raise ValueError('Incomplete GeeTest response')
        payload = {k: solution[k] for k in required}
        response = page.request.post('https://2captcha.com/api/v1/captcha-demo/gee-test-v4/verify',
                                     data=payload, timeout=20000)
        status, data = response.status, response.json()
    data = safe_verification(data)
    rejection = (('Please verify that you are not a robot.' in body) if case == 'recaptcha-v2'
                 else ('Something went wrong' in headings) if case == 'recaptcha-invisible'
                 else data.get('success') is False if case == 'recaptcha-v3'
                 else data.get('result') == 'fail' or data.get('status') == 'error')
    return {'server_acceptance_tested': True, 'server_accepted': classify_verification(case, status, data),
            'rejection_observed': rejection, 'verification': data, 'submission_status': status}


def image_fixture(trial):
    rows = json.loads((IMAGE_DIR / 'manifest.json').read_text())['images']
    return rows[trial - 1]


def make_images():
    """Distinct synthetic OCR controls, not a production CAPTCHA dataset."""
    from playwright.sync_api import sync_playwright
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260923)
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 300, 'height': 100}, device_scale_factor=1)
        for trial in range(1, 101):
            answer = ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            shapes = ['<rect width="300" height="100" fill="#faf8f2"/>']
            for _ in range(6):
                shapes.append(f'<path d="M0 {rng.randrange(100)} Q150 {rng.randrange(100)} 300 {rng.randrange(100)}" stroke="#a2adb8" stroke-width="1" fill="none"/>')
            for i, letter in enumerate(answer):
                x, y, angle = 28 + i * 43, rng.randrange(56, 73), rng.randrange(-13, 14)
                shapes.append(f'<text x="{x}" y="{y}" transform="rotate({angle} {x} {y})" font-family="monospace" font-size="42" font-weight="bold" fill="#253342">{letter}</text>')
            svg = '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100">' + ''.join(shapes) + '</svg>'
            page.set_content('<style>body{margin:0}</style>' + svg)
            path = IMAGE_DIR / f'{trial:02}.png'
            rendered = page.screenshot()
            if path.exists():
                if path.read_bytes() != rendered:
                    raise ValueError('Existing image differs; refusing to replace a measured fixture')
            else:
                path.write_bytes(rendered)
            records.append({'trial': trial, 'file': path.name, 'answer': answer,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        version = browser.version
        browser.close()
    (IMAGE_DIR / 'manifest.json').write_text(json.dumps({'scope': 'Synthetic OCR fixtures; case-insensitive exact answer',
        'seed': 20260923, 'renderer': 'Playwright Chromium ' + version, 'images': records}, indent=2) + '\n')


if __name__ == '__main__':
    make_images()
