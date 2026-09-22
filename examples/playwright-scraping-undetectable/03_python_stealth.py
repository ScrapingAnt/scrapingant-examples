from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from common import capture, options

with Stealth().use_sync(sync_playwright()) as p:
    browser = p.chromium.launch(**options())
    try:
        capture(browser, "python-stealth")
    finally:
        browser.close()
