"""One bounded attempt against Google's official public demo; no paid image API."""
import argparse,json,time,signal
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright
from playwright_recaptcha import recaptchav2

URL='https://www.google.com/recaptcha/api2/demo'
def deadline(*_): raise TimeoutError('Whole experiment exceeded 90 seconds')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');parser.add_argument('--headed',action='store_true');parser.add_argument('--repeat',type=int,default=1);parser.add_argument('--attempts',type=int,default=1);args=parser.parse_args()
    method='plain-checkbox' if args.baseline else 'playwright-recaptcha-audio'
    label=f'{method}-{"headed" if args.headed else "headless"}-{args.repeat}'
    result={'method':method,'test_mode':False,'target':URL,'headed':args.headed,'repeat':args.repeat,'attempt_budget':args.attempts,'tested_at':datetime.now(timezone.utc).isoformat(),'server_accepted':False}
    start=time.monotonic();signal.signal(signal.SIGALRM,deadline);signal.alarm(90)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=not args.headed)
        result['browser']=browser.version;page=browser.new_page(viewport={'width':1200,'height':850},locale='en-US');page.set_default_timeout(15000)
        try:
            result['navigation_status']=page.goto(URL,wait_until='domcontentloaded').status
            if args.baseline:
                page.frame_locator('iframe[title="reCAPTCHA"]').locator('#recaptcha-anchor').click()
                page.wait_for_timeout(3000)
                token=page.locator('[name="g-recaptcha-response"]').input_value()
            else:
                with recaptchav2.SyncSolver(page,attempts=args.attempts) as solver:
                    token=solver.solve_recaptcha(wait=True,wait_timeout=15,image_challenge=False)
            result['token_length']=len(token)
            if token:
                with page.expect_navigation(wait_until='domcontentloaded') as navigation:
                    page.locator('#recaptcha-demo-submit').click()
                result['submission_status']=navigation.value.status if navigation.value else None
                result['server_accepted']='Verification Success' in page.locator('body').inner_text()
        except Exception as exc:
            result.update(error=type(exc).__name__,detail=str(exc)[:900])
        finally:
            signal.alarm(0)
            try:
                result['visible_text']=page.locator('body').inner_text(timeout=3000)[:1400]
                result['challenge_text']=[f.locator('body').inner_text(timeout=1000)[:700] for f in page.frames if 'bframe' in f.url]
                page.screenshot(path=f'screenshots/{label}.png',timeout=5000)
            except Exception as exc: result['capture_error']=type(exc).__name__
            browser.close()
    result['elapsed_seconds']=round(time.monotonic()-start,2)
    print(json.dumps(result,indent=2))
    return 0 if result['server_accepted'] else 1

if __name__=='__main__': raise SystemExit(main())
