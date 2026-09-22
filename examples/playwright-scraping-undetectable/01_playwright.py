from playwright.sync_api import sync_playwright
from common import capture, options

with sync_playwright() as p:
    browser = p.chromium.launch(**options())
    try:
        capture(browser, "plain-chrome")
    finally:
        browser.close()
