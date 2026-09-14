"""Playwright (sync API), Chromium."""
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from _fixtures import LOCAL

with sync_playwright() as p:
    browser = p.chromium.launch()
    print(f"playwright chromium {browser.version}")
    page = browser.new_page()

    page.goto(LOCAL["domcontentloaded"].as_uri())
    soup = BeautifulSoup(page.content(), "html.parser")
    print(f"domcontentloaded: {soup.find(id='test').get_text()}")

    page.goto(LOCAL["delayed"].as_uri())
    soup = BeautifulSoup(page.content(), "html.parser")
    print(f"delayed, read immediately: {soup.find(id='test').get_text()}")
    page.wait_for_selector("#loaded", timeout=10_000)
    soup = BeautifulSoup(page.content(), "html.parser")
    print(f"delayed, after waiting for #loaded: {soup.find(id='test').get_text()}")

    browser.close()
