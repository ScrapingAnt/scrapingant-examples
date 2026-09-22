from playwright.sync_api import sync_playwright
from common import capture, options

with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    try:
        capture(browser, "plain-firefox")
    finally:
        browser.close()
