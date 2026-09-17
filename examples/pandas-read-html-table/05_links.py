"""extract_links: keep the href next to the cell text."""
import pandas as pd
from _common import show, table

show("links: default", lambda: table("links"))
show("links: extract_links='body'", lambda: table("links", extract_links="body"))
df = table("links", extract_links="all")
show("links: extract_links='all'", lambda: df)
show("columns", lambda: list(df.columns))
show("hrefs of the Docs column", lambda: df[("Docs", None)].str[1].tolist())
