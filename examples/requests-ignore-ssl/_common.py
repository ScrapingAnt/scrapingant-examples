import warnings
URL = "https://localhost:8443/"
IP_URL = "https://127.0.0.1:8443/"
CA = "certs/localhost.pem"
BUNDLE = "certs/bundle.pem"   # certifi's bundle + localhost.pem, built by run.sh
PUBLIC = "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html"

def show(label, fn):
    """Run fn() and print one line: the result, or the exception instead of a traceback, so the script continues."""
    try:
        print(f"{label}: {fn()}")
    except Exception as e:  # noqa: BLE001 - print exactly what the reader would see at the end of the traceback
        mod = type(e).__module__
        name = type(e).__name__ if mod == "builtins" else f"{mod}.{name_of(e)}"
        print(f"{label}: {name}: {str(e)[:400]}")

def name_of(e):
    return type(e).__name__

def warn_to_stdout():
    """Print warnings on stdout, in front of the result they belong to (normally they go to stderr with a file:line prefix)."""
    warnings.showwarning = lambda m, c, f, l, file=None, line=None: print(f"{c.__name__}: {m}")
