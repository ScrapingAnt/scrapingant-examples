"""Parse + find_all on a generated page, one subprocess per parser, best of 5, CPU seconds (process_time) so background load matters less."""
import os, subprocess, sys
N = 20_000
PATH = "generated/large.html"
if not os.path.exists(PATH):
    with open(PATH, "w", encoding="utf-8") as f:
        f.write("<html><body><div id='list'>\n")
        for i in range(N):
            f.write(f'<div class="product" data-sku="S{i}"><h2><a href="/p/{i}">Item {i}</a></h2><p class="price">${i % 100}.{i % 10}0</p><ul class="tags"><li>a</li><li>b</li></ul></div>\n')
        f.write("</div></body></html>\n")
size_mb = os.path.getsize(PATH) / 1e6
CASES = {
    "BeautifulSoup html.parser": "from bs4 import BeautifulSoup; s=BeautifulSoup(open(P,'rb').read(),'html.parser'); n=len(s.find_all('p', class_='price'))",
    "BeautifulSoup lxml":        "from bs4 import BeautifulSoup; s=BeautifulSoup(open(P,'rb').read(),'lxml'); n=len(s.find_all('p', class_='price'))",
    "BeautifulSoup html5lib":    "from bs4 import BeautifulSoup; s=BeautifulSoup(open(P,'rb').read(),'html5lib'); n=len(s.find_all('p', class_='price'))",
    "BeautifulSoup lxml + select": "from bs4 import BeautifulSoup; s=BeautifulSoup(open(P,'rb').read(),'lxml'); n=len(s.select('p.price'))",
    "lxml.html + xpath (no bs4)": "import lxml.html; doc=lxml.html.parse(P); n=len(doc.xpath('//p[@class=\"price\"]'))",
}
print(f"file: {PATH}, {size_mb:.1f} MB, {N:,} products; task: parse and collect every p.price; CPU seconds, best of 5 runs, one subprocess per case")
print(f"{'case':30} {'cpu s':>8} {'count':>7}")
for name, code in CASES.items():
    best = None
    for _ in range(5):
        prog = f"import time\nP={PATH!r}\nt=time.process_time()\n{code}\nprint(n, round(time.process_time()-t, 2))"
        out = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, timeout=900)
        if out.returncode: print(f"{name:30} failed: {out.stderr.strip().splitlines()[-1][:80]}"); break
        n, secs = out.stdout.split(); best = min(best, float(secs)) if best is not None else float(secs)
    else:
        print(f"{name:30} {best:8.2f} {int(n):7d}")
