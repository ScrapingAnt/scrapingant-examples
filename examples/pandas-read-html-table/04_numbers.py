"""Numbers and text: thousands separators, currency, percent, leading zeros, European decimals, NA values, dates, dtypes."""
import pandas as pd
from _common import show, table

df = table("prices")
show("prices: default (thousands=',')", lambda: df)
show("prices: dtypes", lambda: df.dtypes)
show("prices: thousands=None", lambda: table("prices", thousands=None).dtypes)
clean = {"Price": lambda s: float(s.replace("$", "").replace(",", "")), "Share": lambda s: float(s.rstrip("%")) / 100}
show("prices: converters for $ and %", lambda: table("prices", converters=clean))
show("prices: converters dtypes", lambda: table("prices", converters=clean).dtypes)

show("codes: default (leading zeros lost)", lambda: table("codes"))
show("codes: converters={'Code': str, 'Postcode': str}", lambda: table("codes", converters={"Code": str, "Postcode": str}))

show("european: default", lambda: table("european"))
show("european: thousands='.', decimal=','", lambda: table("european", thousands=".", decimal=","))
show("european: + na_values=['n/a']", lambda: table("european", thousands=".", decimal=",", na_values=["n/a"]).dtypes)
show("european: keep_default_na=False, na_values=['n/a']", lambda: table("european", thousands=".", decimal=",", na_values=["n/a"], keep_default_na=False))

show("dates: default dtypes", lambda: table("dates").dtypes)
show("dates: parse_dates=True", lambda: table("dates", parse_dates=True).dtypes)
show("dates: pd.to_datetime after reading", lambda: table("dates").assign(Shipped=lambda d: pd.to_datetime(d["Shipped"])).dtypes)
show("dates: dtype_backend='numpy_nullable'", lambda: table("dates", dtype_backend="numpy_nullable").dtypes)
