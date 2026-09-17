import pandas as pd

PAGE = "fixtures/tables.html"
BROKEN = "fixtures/broken.html"
URL = "https://scrapingant.github.io/scrapingant-examples/fixtures/html-tables.html"

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 12)


def show(label, fn):
    """Run fn() and print the result, or the exception type and its first line instead of a traceback."""
    try:
        out = fn()
        print(f"{label}:" + ("\n" if "\n" in str(out) else " ") + str(out))
    except Exception as e:  # noqa: BLE001 - print what the reader would see at the end of the traceback
        mod = type(e).__module__
        name = type(e).__name__ if mod == "builtins" else f"{mod}.{type(e).__name__}"
        print(f"{label}: {name}: {str(e).splitlines()[0] if str(e) else ''}")


def table(attrs_id, **kw):
    """The one table with id=attrs_id from the fixture page."""
    return pd.read_html(PAGE, attrs={"id": attrs_id}, **kw)[0]
