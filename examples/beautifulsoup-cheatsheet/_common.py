import pathlib, warnings
PAGE = pathlib.Path("fixtures/page.html").read_text(encoding="utf-8")
BROKEN = pathlib.Path("fixtures/broken.html").read_text(encoding="utf-8")

def show(label, fn):
    """Print the value of fn(), or the exception's type and message instead of a traceback."""
    try:
        print(f"{label}: {fn()!r}")
    except Exception as e:  # noqa: BLE001
        mod = type(e).__module__
        name = type(e).__name__ if mod == "builtins" else f"{mod}.{type(e).__name__}"
        print(f"{label}: {name}: {str(e).splitlines()[0][:200]}")

def warn_to_stdout():
    warnings.simplefilter("always")
    warnings.showwarning = lambda m, c, f, l, file=None, line=None: print(f"warning: {c.__name__}: {m}")
