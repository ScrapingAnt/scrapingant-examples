"""One fresh browser per approach/mode/repetition; visible detector results only."""
import argparse,contextlib,datetime,importlib.metadata,json,platform,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXTRACT=(ROOT/'scripts/extract.js').read_text()
parser=argparse.ArgumentParser();parser.add_argument('approach');parser.add_argument('mode',choices=['headless','headed']);parser.add_argument('repetition',type=int);args=parser.parse_args()
key=f'{args.approach}-{args.mode}-{args.repetition}'
result={'key':key,'approach':args.approach,'mode':args.mode,'repetition':args.repetition,'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'os':platform.platform(),'python':platform.python_version(),'pages':[]}

@contextlib.contextmanager
def launch():
    headless=args.mode=='headless'
    if args.approach=='camoufox':
        from camoufox.sync_api import Camoufox
        # Fixed actual OS, generated fingerprint otherwise library-default. No proxy/geolocation override.
        with Camoufox(headless=headless,os='macos',browser='152.0.4-beta.30') as browser:
            yield browser
        return
    if args.approach=='patchright':
        from patchright.sync_api import sync_playwright
    else:
        from playwright.sync_api import sync_playwright
    manager=sync_playwright()
    if args.approach=='python-stealth':
        from playwright_stealth import Stealth
        manager=Stealth().use_sync(manager)
    with manager as p:
        kind=p.firefox if args.approach=='firefox-control' else p.chromium
        opts={'headless':headless}
        if args.approach!='firefox-control':opts['channel']='chrome'
        browser=kind.launch(**opts)
        try:yield browser
        finally:browser.close()

try:
    for package in ['playwright','patchright','playwright-stealth','camoufox','browserforge']:
        try:result.setdefault('packages',{})[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    with launch() as browser:
        result['browser_version']=browser.version
        sites=[('local',(ROOT/'fixtures/properties.html').as_uri()),('browserscan','https://www.browserscan.net/bot-detection')]
        if args.repetition==1:sites.append(('sannysoft','https://bot.sannysoft.com/'))
        for site,url in sites:
            item={'site':site,'url':url};start=time.monotonic()
            context=browser.new_context(viewport={'width':1440,'height':1000})
            try:
                page=context.new_page();response=page.goto(url,wait_until='domcontentloaded',timeout=45000)
                item['http_status']=response.status if response else None
                if site=='local':
                    page.locator('#result').wait_for();item['properties']=json.loads(page.locator('#result').inner_text())
                else:
                    # No console listener or DevTools. Fixed snapshots permit checking whether visible results changed.
                    time.sleep(6)
                    item['snapshot_6s']=page.evaluate(EXTRACT)
                    time.sleep(4)
                    item['snapshot_10s']=page.evaluate(EXTRACT)
                    item['screenshot']=f'screenshots/{key}-{site}.png'
                    page.screenshot(path=str(ROOT/item['screenshot']),full_page=False)
                    if site=='browserscan':
                        snap=item['snapshot_10s'];assert snap['verdict'] and len(snap['summary'])==4,'Missing BrowserScan verdict/summary; not a pass'
                    else:assert len(item['snapshot_10s']['rows'])>5,'Missing Sannysoft results; not a pass'
            except Exception as exc:
                item['error']=f'{type(exc).__name__}: {exc}'
            finally:
                item['elapsed_seconds']=round(time.monotonic()-start,3);result['pages'].append(item);context.close()
                print(key,site,'ERROR' if 'error' in item else 'captured',flush=True)
except Exception as exc:
    result['launch_error']=f'{type(exc).__name__}: {exc}';result['traceback']=traceback.format_exc();print(key,result['launch_error'],flush=True)
finally:
    (ROOT/'results'/f'{key}.json').write_text(json.dumps(result,indent=2)+'\n')
