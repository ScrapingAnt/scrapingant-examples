"""The fixed cost behind 03_pooling.py's httpx.get() row: building an SSL context, and constructing an httpx transport, in ms."""
import ssl
import statistics
import time
import certifi
import httpx
from _common import CERT

def ms(fn, runs=50):
    t = []
    for _ in range(runs):
        s = time.perf_counter(); fn(); t.append((time.perf_counter() - s) * 1000)
    return f"median {statistics.median(t):6.2f} ms  min {min(t):6.2f} ms  (n={runs})"

print("ssl.create_default_context(cafile=certifi.where())   ", ms(lambda: ssl.create_default_context(cafile=certifi.where())))
print("ssl.create_default_context(cafile=CERT) (one cert)   ", ms(lambda: ssl.create_default_context(cafile=CERT)))
print("httpx.HTTPTransport() (default verify=True)          ", ms(lambda: httpx.HTTPTransport()))
ctx = ssl.create_default_context(cafile=CERT)
print("httpx.HTTPTransport(verify=ctx)                      ", ms(lambda: httpx.HTTPTransport(verify=ctx)))
print("httpx.HTTPTransport(verify=False)                    ", ms(lambda: httpx.HTTPTransport(verify=False)))
print("requests.Session()                                   ", ms(lambda: __import__("requests").Session()))
