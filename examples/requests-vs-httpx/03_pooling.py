"""Sequential requests with and without a session/client, plain HTTP and TLS. N requests, median of 5 runs.
The verify= rows isolate the cost of building an SSL context per call (httpx does it for http:// URLs too)."""
import warnings
warnings.simplefilter("ignore", DeprecationWarning)   # verify=<str> warns once per call in 0.28; shown in 08_migration.py
import httpx
import requests
from _common import CERT, HTTP, HTTPS, bench

N = 300
print(f"--- {N} sequential GET /get, plain HTTP (127.0.0.1:8080), median of 5 runs")
bench("requests.get() x N (no Session)", lambda: [requests.get(f"{HTTP}/get") for _ in range(N)])
def sess():
    with requests.Session() as s:
        for _ in range(N): s.get(f"{HTTP}/get")
bench("requests.Session x N", sess)
bench("httpx.get() x N (no Client)", lambda: [httpx.get(f"{HTTP}/get") for _ in range(N)])
import ssl
ctx = ssl.create_default_context(cafile=CERT)
bench("httpx.get() x N (no Client, verify=ctx)", lambda: [httpx.get(f"{HTTP}/get", verify=ctx) for _ in range(N)])
bench("httpx.get() x N (no Client, verify=False)", lambda: [httpx.get(f"{HTTP}/get", verify=False) for _ in range(N)])
def client():
    with httpx.Client() as c:
        for _ in range(N): c.get(f"{HTTP}/get")
bench("httpx.Client x N", client)

print(f"--- {N} sequential GET /get, TLS (localhost:8443, self-signed, verify=certs/localhost.pem)")
bench("requests.get() x N (no Session)", lambda: [requests.get(f"{HTTPS}/get", verify=CERT) for _ in range(N)])
def sess_tls():
    with requests.Session() as s:
        s.verify = CERT
        for _ in range(N): s.get(f"{HTTPS}/get")
bench("requests.Session x N", sess_tls)
bench("httpx.get() x N (no Client, verify=CERT)", lambda: [httpx.get(f"{HTTPS}/get", verify=CERT) for _ in range(N)])
bench("httpx.get() x N (no Client, verify=ctx)", lambda: [httpx.get(f"{HTTPS}/get", verify=ctx) for _ in range(N)])
def client_tls():
    with httpx.Client(verify=ctx) as c:
        for _ in range(N): c.get(f"{HTTPS}/get")
bench("httpx.Client x N", client_tls)
