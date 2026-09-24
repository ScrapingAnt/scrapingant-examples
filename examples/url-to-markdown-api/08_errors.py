"""What failures look like: wrong key, invalid url, unreachable host, a target that returns 404, a selector that never appears."""
import json
from _common import call, require_key, KEY
import requests

require_key()
def show(label, status, headers, body):
    try:
        detail = json.loads(body).get("detail")
    except Exception:  # noqa: BLE001
        detail = body[:120]
    print(f"{label}\n  status {status} | Ant-credits-cost {headers.get('Ant-credits-cost')} | Ant-page-status-code {headers.get('Ant-page-status-code')} | detail: {detail}")

r = requests.get("https://api.scrapingant.com/v2/markdown", params={"url": "https://example.com"}, headers={"x-api-key": "wrong-key"}, timeout=60)
show("wrong API key", r.status_code, r.headers, r.text)
s, h, b, _ = call("markdown", {"url": "not-a-url"}); show("url=not-a-url", s, h, b)
s, h, b, _ = call("markdown", {"url": "https://nonexistent-host.invalid/page"}); show("unreachable host", s, h, b)
s, h, b, _ = call("markdown", {"url": "https://scrapingant.github.io/scrapingant-examples/fixtures/does-not-exist.html"}); show("target returns 404 (GitHub Pages)", s, h, b)
if s == 200:
    print("  markdown of the 404 page, first line:", json.loads(b)["markdown"].splitlines()[0][:80])
s, h, b, _ = call("markdown", {"url": "https://scrapingant.github.io/scrapingant-examples/fixtures/markdown-article.html", "wait_for_selector": "#never-appears", "timeout": "5"}); show("wait_for_selector never appears, timeout=5", s, h, b)
