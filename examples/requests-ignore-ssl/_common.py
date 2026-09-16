import sys, warnings
URL = "https://localhost:8443/"
IP_URL = "https://127.0.0.1:8443/"
CA = "certs/localhost.pem"
PUBLIC = "https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html"

def show(label, fn):
    """Run fn(); print the status or the exception type and its first line."""
    try:
        r = fn()
        print(f"{label}: {r}")
    except Exception as e:  # noqa: BLE001 - we want to print exactly what the reader will see
        msg = str(e)
        print(f"{label}: {type(e).__module__}.{type(e).__name__}: {msg[:300]}")

def warn_to_stdout():
    """Print warnings on stdout so they sit next to the result they belong to."""
    warnings.showwarning = lambda m, c, f, l, file=None, line=None: print(f"warning: {c.__name__}: {m}")
