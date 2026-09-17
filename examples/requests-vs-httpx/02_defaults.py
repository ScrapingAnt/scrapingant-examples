"""Two defaults that differ: redirects and timeouts."""
import time
import httpx
import requests
from _common import HTTP, show

print("--- redirects: GET /redirect/2 -> /redirect/1 -> /get")
r = requests.get(f"{HTTP}/redirect/2")
print("requests default:", r.status_code, "history:", [h.status_code for h in r.history], "final:", r.url)
r = httpx.get(f"{HTTP}/redirect/2")
print("httpx default:   ", r.status_code, "history:", [h.status_code for h in r.history], "next_request:", r.next_request.url if r.next_request else None)
r = httpx.get(f"{HTTP}/redirect/2", follow_redirects=True)
print("httpx follow_redirects=True:", r.status_code, "history:", [h.status_code for h in r.history], "final:", r.url)
r = requests.get(f"{HTTP}/redirect/2", allow_redirects=False)
print("requests allow_redirects=False:", r.status_code, "next:", r.next.url)

print("--- timeouts: GET /delay/6 (server sleeps 6 s)")
t = time.perf_counter()
show("requests default (no timeout)", lambda: f"{requests.get(f'{HTTP}/delay/6').status_code} after {time.perf_counter() - t:.1f} s")
t = time.perf_counter()
show("httpx default (5 s)", lambda: httpx.get(f"{HTTP}/delay/6").status_code)
print(f"  raised after {time.perf_counter() - t:.1f} s")
show("requests timeout=1", lambda: requests.get(f"{HTTP}/delay/6", timeout=1).status_code)
show("httpx timeout=1", lambda: httpx.get(f"{HTTP}/delay/6", timeout=1).status_code)
show("httpx timeout=None", lambda: f"{httpx.get(f'{HTTP}/delay/6', timeout=None).status_code}")
print("httpx.Timeout(10.0, connect=60.0):", httpx.Timeout(10.0, connect=60.0))
print("requests timeout=(connect, read) is a tuple: (3.05, 27)")
