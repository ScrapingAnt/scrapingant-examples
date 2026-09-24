"""What the conversion keeps and removes, checked on the fixture's Markdown; then the same conversion run locally with the pinned libraries and compared."""
import re
import html2text
from bs4 import BeautifulSoup
from _common import FIXTURE, cached, require_key

require_key()
info, md = cached("fixture", "markdown", FIXTURE)
_, html = cached("fixture", "general", FIXTURE)
lines = md.splitlines()
checks = [
    ("navigation link text present", "Reviews" in md and "Pricing" in md),
    ("cookie banner text present", "COOKIE-SENTINEL-2b8e" in md),
    ("aside (sponsored) text present", "ASIDE-SENTINEL-5d6f" in md),
    ("footer text present", "FOOTER-SENTINEL-4a2c" in md),
    ("script body absent", "SCRIPT-SENTINEL-7f3a" not in md),
    ("noscript text absent", "NOSCRIPT-SENTINEL-9c1d" not in md),
    ("h1 as '# '", any(l.startswith("# Ant Farm Deluxe review") for l in lines)),
    ("h2 as '## '", any(l.startswith("## ") for l in lines)),
    ("inline link kept as [text](href)", re.search(r"\[harvester ant care\s+guide\]\(/guides/harvester-ants\)", md) is not None),
    ("table as pipe rows", any("---|---" in l for l in lines)),
    ("image kept as ![alt](src)", "![Ant Farm Deluxe with two chambers and a magnifier](" in md),
    ("code block indented 4 spaces, no fence", any(l.startswith("    def feed(day):") for l in lines) and "```" not in md),
    ("blockquote as '> '", any(l.startswith("> Tunnels") for l in lines)),
]
for label, ok in checks:
    print(f"{'ok ' if ok else 'NO '} {label}")
print("lines:", len(lines), "| characters:", len(md), "| lines over 78 chars:", sum(1 for l in lines if len(l) > 78), "(html2text wraps at 78 where it can break)")

soup = BeautifulSoup(html, "html.parser")
for tag in soup(["script", "noscript"]):
    tag.decompose()
h = html2text.HTML2Text()
h.ignore_links = False
local = h.handle(str(soup))
print("local html2text 2020.1.16 on the /v2/general HTML == API markdown:", local == md)
if local != md:
    import difflib
    d = list(difflib.unified_diff(local.splitlines(), md.splitlines(), "local", "api", lineterm="", n=0))
    print("\n".join(d[:20]))
