"""Removing navigation, cookie banner, aside and footer in the browser before conversion, with js_snippet (needs browser=true)."""
import base64
import re
from _common import FIXTURE, call, require_key
import json

require_key()
snippet = "document.querySelectorAll('nav, footer, .cookie, aside').forEach(e => e.remove());"
s, h, b, secs = call("markdown", {"url": FIXTURE, "js_snippet": base64.b64encode(snippet.encode()).decode()})
print("js_snippet:", snippet)
print("status", s, "| Ant-credits-cost", h.get("Ant-credits-cost"))
md = json.loads(b)["markdown"]
for label, ok in [("navigation gone", "Reviews" not in md), ("cookie banner gone", "COOKIE-SENTINEL" not in md), ("aside gone", "ASIDE-SENTINEL" not in md), ("footer gone", "FOOTER-SENTINEL" not in md), ("article kept", "# Ant Farm Deluxe review" in md and re.search(r"harvester ant care\s+guide", md) is not None)]:
    print(f"{'ok ' if ok else 'NO '} {label}")
print("characters:", len(md), "| first lines:"); print("\n".join(md.splitlines()[:6]))
