"""Supplemental screenshot audit; not part of the canonical repetition matrix."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'layout-audit';OUT.mkdir(exist_ok=True)
with Stealth().use_sync(sync_playwright()) as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 try:
  context=browser.new_context(viewport={'width':1440,'height':1000})
  page=context.new_page();page.goto('https://www.browserscan.net/bot-detection',wait_until='domcontentloaded',timeout=45000)
  time.sleep(10)
  result={'snapshot':page.evaluate((ROOT/'scripts/extract.js').read_text()),'layout':page.evaluate("""() => ({innerWidth,outerWidth,scrollX,body:document.body.getBoundingClientRect().toJSON(),documentWidth:document.documentElement.scrollWidth,strong:[...document.querySelectorAll('strong')].filter(x=>x.innerText.includes('Test Results')).map(x=>x.getBoundingClientRect().toJSON())})""")}
  page.screenshot(path=str(OUT/'python-stealth-headless-full.png'),full_page=True)
  (OUT/'python-stealth-headless.json').write_text(json.dumps(result,indent=2)+'\n')
 finally:browser.close()
