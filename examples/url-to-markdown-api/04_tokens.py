"""Raw HTML (/v2/general) vs Markdown (/v2/markdown) for four pages: bytes and tokens (cl100k_base, o200k_base), same browser=true setting."""
import tiktoken
from _common import PAGES, cached, require_key

require_key()
enc = {n: tiktoken.get_encoding(n) for n in ("cl100k_base", "o200k_base")}
print(f"{'page':<20} {'html bytes':>10} {'md bytes':>9} {'html cl100k':>11} {'md cl100k':>9} {'ratio':>6} {'html o200k':>10} {'md o200k':>8} {'ratio':>6}  cost(html,md)")
for name, url in PAGES.items():
    ih, html = cached(name, "general", url)
    im, md = cached(name, "markdown", url)
    if ih["status"] != 200 or im["status"] != 200:
        print(f"{name:<20} general {ih['status']} markdown {im['status']} (skipped)"); continue
    row = [name, len(html.encode()), len(md.encode())]
    for n in ("cl100k_base", "o200k_base"):
        th, tm = len(enc[n].encode(html, disallowed_special=())), len(enc[n].encode(md, disallowed_special=()))
        row += [th, tm, f"{th / tm:.1f}x"]
    print(f"{row[0]:<20} {row[1]:>10} {row[2]:>9} {row[3]:>11} {row[4]:>9} {row[5]:>6} {row[6]:>10} {row[7]:>8} {row[8]:>6}  {ih['cost']},{im['cost']}")
print("raw HTML = the /v2/general response body for the same URL with browser=true; tokens counted with tiktoken on the exact bytes returned")
