"""Hidden rows (displayed_only) and nested tables."""
from io import StringIO
import pandas as pd
from _common import PAGE, show, table

show("hidden: default (displayed_only=True)", lambda: table("hidden"))
show("hidden: displayed_only=False", lambda: table("hidden", displayed_only=False))
HIDDEN_WAYS = """<style>.gone { display: none }</style>
<table><thead><tr><th>Row</th><th>How hidden</th></tr></thead><tbody>
<tr><td>1</td><td>visible</td></tr>
<tr style="display:none"><td>2</td><td>inline display:none</td></tr>
<tr style="DISPLAY: NONE"><td>3</td><td>inline, upper case</td></tr>
<tr class="gone"><td>4</td><td>class + stylesheet</td></tr>
<tr hidden><td>5</td><td>hidden attribute</td></tr>
<tr style="visibility:hidden"><td>6</td><td>visibility:hidden</td></tr>
</tbody></table>"""
for flavor in ("lxml", "bs4"):
    show(f"six ways to hide a row, flavor={flavor!r}, displayed_only=True", lambda: pd.read_html(StringIO(HIDDEN_WAYS), flavor=flavor)[0])
show("nested: attrs id=outer", lambda: table("outer"))
show("nested: attrs id=inner", lambda: table("inner"))
show("nested: match='Bin' returns both", lambda: [df.shape for df in pd.read_html(PAGE, match="Bin")])
