"""Negative control: Google's demo must reject a deliberately invalid token."""
import json
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

URL = 'https://www.google.com/recaptcha/api2/demo'


def main():
    start = time.monotonic()
    result = {'method': 'invalid-token-demo-control', 'target': URL,
              'tested_at': datetime.now(timezone.utc).isoformat(),
              'paid_tasks_created': 0, 'test_mode': False,
              'server_accepted': False, 'assertion_passed': False}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                result['browser'] = browser.version
                page = browser.new_page(viewport={'width': 1200, 'height': 850}, locale='en-US')
                page.set_default_timeout(15000)
                page.goto(URL, wait_until='domcontentloaded')
                page.locator('[name="g-recaptcha-response"]').wait_for(state='attached')
                page.locator('[name="g-recaptcha-response"]').evaluate(
                    '(element) => { element.value = "deliberately-invalid-control"; }')
                with page.expect_navigation(wait_until='domcontentloaded') as navigation:
                    page.locator('#recaptcha-demo-submit').click()
                response = navigation.value
                result['submission_status'] = response.status if response else None
                body = page.locator('body').inner_text()
                result['success_message_present'] = 'Verification Success' in body
                result['failure_message_present'] = 'Please verify that you are not a robot.' in body
                result['server_accepted'] = result['success_message_present']
                result['assertion_passed'] = (page.url == URL and result['submission_status'] == 200
                                              and result['failure_message_present']
                                              and not result['success_message_present'])
                page.screenshot(path='screenshots/invalid-token-demo-control.png', timeout=5000)
            finally:
                browser.close()
    except Exception as exc:
        result['error_class'] = type(exc).__name__
    result['elapsed_seconds'] = round(time.monotonic() - start, 2)
    print(json.dumps(result, indent=2))
    return 0 if result['assertion_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
