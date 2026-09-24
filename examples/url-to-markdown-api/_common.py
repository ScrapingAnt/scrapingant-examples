import json
import os
import sys
import time
from pathlib import Path
import requests

API = "https://api.scrapingant.com/v2"
FIXTURE = "https://scrapingant.github.io/scrapingant-examples/fixtures/markdown-article.html"
PAGES = {
    "fixture": FIXTURE,
    "python-tutorial": "https://docs.python.org/3/tutorial/introduction.html",
    "pandas-read_html": "https://pandas.pydata.org/docs/reference/api/pandas.read_html.html",
    "wikipedia-markdown": "https://en.wikipedia.org/wiki/Markdown",
}
KEY = os.environ.get("SCRAPINGANT_API_KEY", "")
GEN = Path("generated")
GEN.mkdir(exist_ok=True)


def require_key():
    if not KEY:
        print("skipped: SCRAPINGANT_API_KEY is not set")
        sys.exit(0)


def call(endpoint, params, method="GET", timeout=120, **kw):
    """One API call. Returns (status, headers, body_text, seconds)."""
    t = time.perf_counter()
    r = requests.request(method, f"{API}/{endpoint}", params=params, headers={"x-api-key": KEY}, timeout=timeout, **kw)
    return r.status_code, r.headers, r.text, time.perf_counter() - t


def cost(headers):
    return headers.get("Ant-credits-cost")


def page_status(headers):
    return headers.get("Ant-page-status-code")


def cached(name, endpoint, url, browser="true"):
    """Fetch endpoint for url once per run and cache the body under generated/ so later scripts reuse it."""
    f = GEN / f"{name}.{endpoint}.{browser}.txt"
    meta = GEN / f"{name}.{endpoint}.{browser}.json"
    if f.exists() and meta.exists():
        return json.loads(meta.read_text()), f.read_text(encoding="utf-8")
    status, headers, body, secs = call(endpoint, {"url": url, "browser": browser})
    info = {"status": status, "cost": cost(headers), "page_status": page_status(headers), "seconds": round(secs, 2)}
    text = json.loads(body)["markdown"] if endpoint == "markdown" and status == 200 else body
    if endpoint == "markdown" and status == 200 and not text.strip():
        # Observed once on 2026-09-24 (docs.python.org tutorial): HTTP 200, Ant-credits-cost 10, markdown "\n\n". Retry once and record it.
        info["empty_markdown_first_attempt"] = True
        status, headers, body, secs = call(endpoint, {"url": url, "browser": browser})
        info.update({"status": status, "cost": cost(headers), "seconds": round(secs, 2)})
        text = json.loads(body)["markdown"] if status == 200 else body
        print(f"note: {name} returned an empty markdown body on the first attempt (200, charged); retried once")
    f.write_text(text, encoding="utf-8"); meta.write_text(json.dumps(info))
    return info, text
