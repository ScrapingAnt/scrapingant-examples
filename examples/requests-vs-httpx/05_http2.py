"""HTTP/2: who speaks it, and what it changes on the same server (TLS, ALPN h2 + http/1.1).
Without a semaphore the client, not the server, bounds concurrency: httpx DEFAULT_LIMITS max_connections=100 and httpcore's local MAX_CONCURRENT_STREAMS=100."""
import asyncio
import ssl
import subprocess
import sys
import httpx
import requests
from _common import CERT, HTTPS, bench, show

ctx = ssl.create_default_context(cafile=CERT)
print("--- protocol negotiated on GET /get")
r = requests.get(f"{HTTPS}/get", verify=CERT)
print("requests:                 raw.version =", r.raw.version, "| server saw", r.json()["http_version"])
with httpx.Client(verify=ctx) as c:
    print("httpx.Client():           http_version =", c.get(f"{HTTPS}/get").http_version)
with httpx.Client(verify=ctx, http2=True) as c:
    r = c.get(f"{HTTPS}/get")
    print("httpx.Client(http2=True): http_version =", r.http_version, "| server saw", r.json()["http_version"])
with httpx.Client(verify=ctx, http2=True) as c:
    print("httpx.Client(http2=True) against the plain-HTTP port:", c.get("http://127.0.0.1:8080/get").http_version)

print("--- http2=True without the h2 package (subprocess with h2 blocked)")
code = "import sys; sys.modules['h2'] = None\nimport httpx\nhttpx.Client(http2=True)"
p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
print("exit", p.returncode, "|", p.stderr.strip().splitlines()[-1])

N, WORKERS = 200, 20
URL = f"{HTTPS}/delay/0.05"
print(f"--- {N} x GET /delay/0.05 over TLS, AsyncClient + gather with Semaphore({WORKERS}), median of 3 runs")
async def gather(http2, limit=WORKERS):
    sem = asyncio.Semaphore(limit)
    async with httpx.AsyncClient(verify=ctx, http2=http2) as c:
        async def one():
            async with sem:
                return await c.get(URL)
        rs = await asyncio.gather(*(one() for _ in range(N)))
        assert {x.http_version for x in rs} == ({"HTTP/2"} if http2 else {"HTTP/1.1"})
bench("HTTP/1.1 (http2=False)", lambda: asyncio.run(gather(False)), runs=3)
bench("HTTP/2 (http2=True)", lambda: asyncio.run(gather(True)), runs=3)
print(f"--- the same {N} requests with no semaphore (httpx defaults cap in-flight work: 100 connections, or 100 streams on one HTTP/2 connection)")
bench("HTTP/1.1, no semaphore", lambda: asyncio.run(gather(False, N)), runs=3)
bench("HTTP/2, no semaphore", lambda: asyncio.run(gather(True, N)), runs=3)

M = 300
print(f"--- {M} sequential GET /get over TLS on one Client, median of 5 runs")
def seq(http2):
    with httpx.Client(verify=ctx, http2=http2) as c:
        for _ in range(M): c.get(f"{HTTPS}/get")
bench("httpx.Client() HTTP/1.1", lambda: seq(False))
bench("httpx.Client(http2=True)", lambda: seq(True))
print("--- a public server: GitHub Pages fixture")
show("httpx.Client(http2=True) public", lambda: httpx.Client(http2=True).get("https://scrapingant.github.io/scrapingant-examples/fixtures/dynamic-delayed.html").http_version)
