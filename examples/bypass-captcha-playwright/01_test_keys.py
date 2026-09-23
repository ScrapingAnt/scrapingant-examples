"""Real browser widgets and real provider Siteverify; all keys are provider test keys."""
import json, time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from fixture_server import serve

def main():
    rows=[]
    with serve() as root, sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        for provider, mode in [('google','empty'),('google','pass'),('turnstile','pass'),('turnstile','reject'),('turnstile','duplicate')]:
            started=time.monotonic();page=browser.new_page(viewport={'width':1000,'height':700})
            row={'provider':provider,'mode':mode,'browser':browser.version,'tested_at':datetime.now(timezone.utc).isoformat()}
            try:
                page.goto(f'{root}/?provider={provider}&mode={mode if mode != "empty" else "pass"}')
                if mode != 'empty':
                    if provider == 'google':
                        page.frame_locator('iframe[title="reCAPTCHA"]').locator('#recaptcha-anchor').click(timeout=20000)
                    selector='[name="g-recaptcha-response"]' if provider == 'google' else '[name="cf-turnstile-response"]'
                    page.wait_for_function('(s) => document.querySelector(s)?.value.length > 0',arg=selector,timeout=25000)
                with page.expect_response(lambda r: '/verify?' in r.url) as request:
                    page.locator('#submit').click()
                row.update(http_status=request.value.status,result=request.value.json())
                expected=mode=='pass'
                expected_error={'empty':['missing-token'],'reject':['invalid-input-response'],'duplicate':['timeout-or-duplicate']}.get(mode,[])
                actual_error=row['result'].get('verification',{}).get('error-codes',row['result'].get('error_codes',[]))
                row['assertion_passed']=row['result']['accepted'] is expected and not row['result'].get('transport_error') and actual_error==expected_error
                page.screenshot(path=f'screenshots/test-key-{provider}-{mode}.png')
            except Exception as exc:
                row.update(error=type(exc).__name__,detail=str(exc)[:800],assertion_passed=False)
            row['elapsed_seconds']=round(time.monotonic()-started,2);rows.append(row);page.close()
        browser.close()
    print(json.dumps(rows,indent=2))
    return 0 if all(x['assertion_passed'] for x in rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
