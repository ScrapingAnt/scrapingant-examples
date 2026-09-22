"""Capture a fixture's own DOM output, not properties from an isolated world."""
import json, os
from pathlib import Path

FIXTURE = (Path(__file__).parent / "fixtures/properties.html").resolve().as_uri()

def options():
    opts = {"headless": True}
    if os.environ.get("BROWSER_CHANNEL"):
        opts["channel"] = os.environ["BROWSER_CHANNEL"]
    return opts

def capture(browser, approach):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    try:
        page = context.new_page()
        page.goto(FIXTURE, wait_until="domcontentloaded", timeout=15000)
        value = json.loads(page.locator("#result").inner_text(timeout=15000))
        assert isinstance(value["webdriver"], bool), "Fixture did not expose a boolean webdriver property"
        assert value["viewport"] == [1440, 1000], "Unexpected fixture viewport"
        print(json.dumps({"approach": approach, "browser": browser.version,
                          "webdriver": value["webdriver"], "platform": value["platform"]}, sort_keys=True))
    finally:
        context.close()
