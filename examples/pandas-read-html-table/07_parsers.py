"""flavor: lxml vs bs4/html5lib on broken markup; missing parser errors; wall time on a generated 20,000-row table."""
import statistics
import subprocess
import sys
import time
from io import StringIO
import pandas as pd
from _common import BROKEN, show

for flavor in ("lxml", "bs4", "html5lib"):
    show(f"broken.html flavor={flavor!r}", lambda: pd.read_html(BROKEN, flavor=flavor)[0])
show("broken.html flavor=None (default: lxml, fallback bs4)", lambda: pd.read_html(BROKEN)[0].shape)

print("--- flavor with the library missing (subprocess, module blocked)")
for mod, flavor in (("lxml", "lxml"), ("bs4", "bs4"), ("html5lib", "bs4")):
    code = f"import sys; sys.modules[{mod!r}] = None\nimport pandas as pd\npd.read_html({BROKEN!r}, flavor={flavor!r})"
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    print(f"{mod} blocked, flavor={flavor!r}: exit {p.returncode} | {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else 'ok'}")

N = 20_000
rows = "\n".join(f"<tr><td>{i}</td><td>Item {i}</td><td>{i * 3 % 1000},{i % 1000:03d}</td><td>{i % 7}</td><td>x{i}</td><td>{i % 2 == 0}</td></tr>" for i in range(N))
html = f"<table><thead><tr><th>id</th><th>name</th><th>amount</th><th>bucket</th><th>tag</th><th>flag</th></tr></thead><tbody>{rows}</tbody></table>"
print(f"--- generated table: {N} rows x 6 cols, {len(html) / 1e6:.1f} MB of HTML, median of 5 runs")
for flavor in ("lxml", "bs4"):
    t = []
    for _ in range(5):
        s = time.perf_counter(); df = pd.read_html(StringIO(html), flavor=flavor)[0]; t.append(time.perf_counter() - s)
    print(f"flavor={flavor!r:<10} median {statistics.median(t):6.2f} s  min {min(t):6.2f} s  shape {df.shape}  dtypes {dict(df.dtypes.astype(str))}")
