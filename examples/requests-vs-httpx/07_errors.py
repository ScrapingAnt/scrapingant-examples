"""Exceptions side by side, and what 'retries' means in each library (server request counter)."""
import time
import httpx
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from _common import HTTP, show, stats

def cls(e):
    mod = type(e).__module__
    return f"{mod}.{type(e).__name__}" if mod != "builtins" else type(e).__name__

def catch(fn):
    try:
        fn(); return "no exception"
    except Exception as e:  # noqa: BLE001
        bases = [b.__name__ for b in type(e).__mro__[1:] if b.__module__ in ("requests.exceptions", "httpx") and b.__name__ != "Exception"]
        return f"{cls(e)}  (bases: {' > '.join(bases)})"

print("--- the same failures")
cases = [
    ("404 + raise_for_status()", lambda: requests.get(f"{HTTP}/status/404").raise_for_status(), lambda: httpx.get(f"{HTTP}/status/404").raise_for_status()),
    ("connection refused (port 1)", lambda: requests.get("http://127.0.0.1:1/", timeout=2), lambda: httpx.get("http://127.0.0.1:1/")),
    ("read timeout (/delay/2, timeout=0.5)", lambda: requests.get(f"{HTTP}/delay/2", timeout=0.5), lambda: httpx.get(f"{HTTP}/delay/2", timeout=0.5)),
    ("unknown host", lambda: requests.get("http://nonexistent.invalid/", timeout=2), lambda: httpx.get("http://nonexistent.invalid/")),
    ("bad URL", lambda: requests.get("not a url"), lambda: httpx.get("not a url")),
]
for label, a, b in cases:
    print(f"{label}\n  requests: {catch(a)}\n  httpx:    {catch(b)}")
print("top-level bases: requests.exceptions.RequestException / httpx.HTTPError; both raise_for_status errors carry .response")

print("--- retries against GET /status/503 (server counts requests)")
stats(reset=True)
s = requests.Session()
s.mount("http://", HTTPAdapter(max_retries=Retry(total=3, status_forcelist=[503], backoff_factor=0)))
show("requests + urllib3 Retry(total=3, status_forcelist=[503])", lambda: s.get(f"{HTTP}/status/503").status_code)
print("  server saw", stats()["requests"], "requests")
stats(reset=True)
show("httpx.HTTPTransport(retries=3)", lambda: httpx.Client(transport=httpx.HTTPTransport(retries=3)).get(f"{HTTP}/status/503").status_code)
print("  server saw", stats()["requests"], "requests")
print("--- retries against connection refused (port 1)")
t = time.perf_counter()
show("httpx.HTTPTransport(retries=3)", lambda: httpx.Client(transport=httpx.HTTPTransport(retries=3)).get("http://127.0.0.1:1/"))
print(f"  gave up after {time.perf_counter() - t:.1f} s (backoff between attempts)")
t = time.perf_counter()
s = requests.Session(); s.mount("http://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.5)))
show("requests Retry(total=3, backoff_factor=0.5)", lambda: s.get("http://127.0.0.1:1/", timeout=2))
print(f"  gave up after {time.perf_counter() - t:.1f} s")
