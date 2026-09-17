"""N requests to /delay/0.05 (the server sleeps 50 ms per request): sequential, threads, asyncio. Median of 3 runs."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import httpx
import requests
from requests.adapters import HTTPAdapter
from _common import HTTP, bench

class Count(logging.Handler):
    n = 0; last = ""
    def emit(self, record):
        if "pool is full" in record.getMessage(): self.n += 1; self.last = record.getMessage()
counter = Count(); logging.getLogger("urllib3").addHandler(counter); logging.getLogger("urllib3").setLevel(logging.WARNING)

N, WORKERS = 200, 20
URL = f"{HTTP}/delay/0.05"
print(f"--- {N} x GET /delay/0.05, plain HTTP, concurrency {WORKERS} where applicable, median of 3 runs")

def sequential():
    with requests.Session() as s:
        for _ in range(N): s.get(URL)
bench("requests.Session, sequential", sequential, runs=3)

def threads_requests():
    with requests.Session() as s, ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(lambda _: s.get(URL), range(N)))
bench(f"requests.Session + {WORKERS} threads", threads_requests, runs=3)
print(f"  urllib3 logged '{counter.last}' {counter.n} times over 3 runs")

def threads_requests_sized():
    with requests.Session() as s, ThreadPoolExecutor(WORKERS) as pool:
        s.mount("http://", HTTPAdapter(pool_maxsize=WORKERS))
        list(pool.map(lambda _: s.get(URL), range(N)))
counter.n = 0
bench(f"requests.Session + {WORKERS} threads, pool_maxsize={WORKERS}", threads_requests_sized, runs=3)
print(f"  urllib3 'pool is full' warnings: {counter.n}")

def threads_httpx():
    with httpx.Client() as c, ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(lambda _: c.get(URL), range(N)))
bench(f"httpx.Client + {WORKERS} threads", threads_httpx, runs=3)

async def gather(limit, **kw):
    sem = asyncio.Semaphore(limit)
    async with httpx.AsyncClient(**kw) as c:
        async def one():
            async with sem:
                return await c.get(URL)
        await asyncio.gather(*(one() for _ in range(N)))
bench(f"httpx.AsyncClient + gather, Semaphore({WORKERS})", lambda: asyncio.run(gather(WORKERS)), runs=3)
bench("httpx.AsyncClient + gather, no semaphore", lambda: asyncio.run(gather(N)), runs=3)
bench(f"httpx.AsyncClient(limits=Limits({WORKERS}, {WORKERS})), no semaphore", lambda: asyncio.run(gather(N, limits=httpx.Limits(max_connections=WORKERS, max_keepalive_connections=WORKERS))), runs=3)
from httpx._config import DEFAULT_LIMITS
print("httpx default client limits:", DEFAULT_LIMITS)
print("requests/urllib3 default pool: pool_connections=10, pool_maxsize=10 (HTTPAdapter defaults)")
