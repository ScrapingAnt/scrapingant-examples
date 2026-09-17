import json
import statistics
import time
import urllib.request

HTTP = "http://127.0.0.1:8080"
HTTPS = "https://localhost:8443"
CERT = "certs/localhost.pem"


def show(label, fn):
    """Run fn() and print one line: the value, or the exception type and its first line instead of a traceback."""
    try:
        print(f"{label}: {fn()}")
    except Exception as e:  # noqa: BLE001 - print what the reader would see at the end of the traceback
        mod = type(e).__module__
        name = type(e).__name__ if mod == "builtins" else f"{mod}.{type(e).__name__}"
        print(f"{label}: {name}: {str(e).splitlines()[0] if str(e) else ''}")


def stats(reset=False):
    """Read (or reset) the server's counters over urllib, so the packet's own clients are not disturbed."""
    with urllib.request.urlopen(f"{HTTP}/stats/reset" if reset else f"{HTTP}/stats") as r:
        return json.load(r)


def bench(label, fn, runs=5, n=None):
    """Time fn() `runs` times; print median and min seconds and the TCP connections the server saw opened in the last run."""
    times = []
    for _ in range(runs):
        stats(reset=True)
        t = time.perf_counter(); fn(); times.append(time.perf_counter() - t)
    s = stats()
    print(f"{label:<52} median {statistics.median(times):6.3f} s  min {min(times):6.3f} s  conns opened {s['connections']:>3}  requests {s['requests']:>4}")
    return statistics.median(times)
