"""Picking the table you want: match (text or regex), attrs, index, and what happens when nothing matches."""
import re
import subprocess
import sys
from io import StringIO
import pandas as pd
from _common import PAGE, show

show("match='Ant Farm'", lambda: [df.shape for df in pd.read_html(PAGE, match="Ant Farm")])
show("match='Ant Farm Deluxe'", lambda: [df.shape for df in pd.read_html(PAGE, match="Ant Farm Deluxe")])
show("match=re.compile(r'^Q[1-4]$')", lambda: [df.shape for df in pd.read_html(PAGE, match=re.compile(r"^Q[1-4]$"))])
show("attrs={'id': 'prices'}", lambda: pd.read_html(PAGE, attrs={"id": "prices"})[0])
show("attrs={'class': 'data'}", lambda: [df.shape for df in pd.read_html(PAGE, attrs={"class": "data"})])
show("match='Magnifier', attrs={'class': 'data'}", lambda: [df.shape for df in pd.read_html(PAGE, match="Magnifier", attrs={"class": "data"})])
show("match='Farm Deluxe' (part of one cell)", lambda: [df.shape for df in pd.read_html(PAGE, match="Farm Deluxe")])
show("match='Ant Farm Deluxe manual' (spans two cells)", lambda: [df.shape for df in pd.read_html(PAGE, match="Ant Farm Deluxe manual")])
show("match='no such text'", lambda: pd.read_html(PAGE, match="no such text"))
show("match='no such text', flavor='lxml' (lxml's own message)", lambda: pd.read_html(PAGE, match="no such text", flavor="lxml"))
code = "import sys; sys.modules['bs4'] = None\nimport pandas as pd\npd.read_html('fixtures/tables.html', match='no such text')"
p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
print("match='no such text' with only lxml installed (bs4 blocked):", p.stderr.strip().splitlines()[-1])
show("attrs={'id': 'nope'}", lambda: pd.read_html(PAGE, attrs={"id": "nope"}))
show("pd.read_html('fixtures/no-tables.html')", lambda: pd.read_html("fixtures/no-tables.html"))
SKELETON = "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody></tbody></table>"
show("header-only table (empty tbody, as a JS page skeleton)", lambda: pd.read_html(StringIO(SKELETON))[0].shape)
show("  its columns", lambda: list(pd.read_html(StringIO(SKELETON))[0].columns))
