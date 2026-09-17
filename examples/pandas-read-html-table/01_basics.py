"""Where the HTML comes from: a file, a string (StringIO), a URL. What you get back: a list."""
from io import StringIO
import pandas as pd
from _common import PAGE, URL, show

tables = pd.read_html(PAGE)
print("file:", len(tables), "tables; shapes:", [df.shape for df in tables])
print(tables[0])

html = open(PAGE, encoding="utf-8").read()
show("pd.read_html(html) with a str (pandas 3)", lambda: len(pd.read_html(html)))
show("pd.read_html(StringIO(html))", lambda: len(pd.read_html(StringIO(html))))
with open(PAGE, "rb") as f:
    show("pd.read_html(open(PAGE, 'rb'))", lambda: len(pd.read_html(f)))

show("pd.read_html(URL)", lambda: len(pd.read_html(URL)))
show("pd.read_html('https://' + ...)[1]", lambda: pd.read_html(URL)[1])
