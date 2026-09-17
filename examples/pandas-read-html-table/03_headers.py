"""Headers: thead rows, two-row headers (MultiIndex), colspan/rowspan, tables with no thead, header= and index_col= and skiprows=."""
import pandas as pd
from _common import show, table

df = table("two-row-header")
show("two-row thead -> MultiIndex columns", lambda: df)
show("df.columns", lambda: list(df.columns))
df.columns = ["_".join(str(x) for x in col if str(x) != "nan") for col in df.columns]
show("flattened", lambda: df)
show("header=1 (second thead row only)", lambda: table("two-row-header", header=1))
show("spans (rowspan/colspan expanded)", lambda: table("spans"))
show("no thead, td first row: default", lambda: table("no-thead"))
show("no thead, td first row: header=0", lambda: table("no-thead", header=0))
show("simple (th row, no thead): default", lambda: table("simple"))
show("simple: header=None", lambda: table("simple", header=None))
show("simple: index_col=0", lambda: table("simple", index_col=0))
show("simple: skiprows=1", lambda: table("simple", skiprows=1))
show("simple: skiprows=[1]", lambda: table("simple", skiprows=[1]))
show("prices (has thead): skiprows=1", lambda: table("prices", skiprows=1))
