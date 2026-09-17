"""What breaks when requests code is run against httpx 0.28: the real errors and warnings."""
import warnings
import httpx
import requests
from _common import CERT, HTTP, HTTPS, show

warnings.simplefilter("always")
warnings.showwarning = lambda m, c, f, l, file=None, line=None: print(f"  {c.__name__}: {m}")

print("--- arguments that do not exist or were removed")
show("httpx.get(url, allow_redirects=True)", lambda: httpx.get(f"{HTTP}/get", allow_redirects=True).status_code)
show("httpx.Client(proxies={...})  (removed in 0.28)", lambda: httpx.Client(proxies={"http://": "http://127.0.0.1:3128"}))
show("httpx.Client(proxy='http://127.0.0.1:3128')", lambda: type(httpx.Client(proxy="http://127.0.0.1:3128")).__name__)
show("httpx.Client(mounts={'http://': httpx.HTTPTransport(proxy='http://127.0.0.1:3128')})", lambda: type(httpx.Client(mounts={"http://": httpx.HTTPTransport(proxy="http://127.0.0.1:3128")})).__name__)
show("requests.Session().proxies = {'http': ...}", lambda: requests.Session().proxies.update({"http": "http://127.0.0.1:3128"}) or "ok")
show("httpx.Client(app=...)  (removed in 0.28)", lambda: httpx.Client(app=object()))
print("--- deprecated in 0.28 (still works, warns)")
show("httpx.get(url, verify='certs/localhost.pem')", lambda: httpx.get(f"{HTTPS}/get", verify=CERT).status_code)
show("httpx.get(url, cert=(...))", lambda: httpx.get(f"{HTTPS}/get", verify=CERT, cert=("certs/localhost.pem", "certs/localhost-key.pem")).status_code)
show("httpx.post(url, data=b'raw')", lambda: httpx.post(f"{HTTP}/post", data=b"raw").status_code)
c = httpx.Client()
show("client.post(url, cookies={...}) on a Client", lambda: c.post(f"{HTTP}/post", cookies={"a": "b"}).status_code)
print("--- attributes with different names")
r = requests.get(f"{HTTP}/get"); h = httpx.get(f"{HTTP}/get")
show("requests r.reason / httpx r.reason_phrase", lambda: f"{hasattr(r, 'reason')} / {hasattr(h, 'reason_phrase')}")
show("httpx r.reason", lambda: h.reason)
show("requests r.raw / httpx r.raw", lambda: f"{type(r.raw).__name__} / {type(h.raw).__name__}")
show("httpx r.iter_content", lambda: h.iter_content)
show("requests r.next / httpx r.next_request", lambda: f"{r.next} / {h.next_request}")
show("str(httpx r.url) == requests r.url", lambda: str(h.url) == r.url)
show("requests.Session().mount / httpx.Client().mounts", lambda: f"{callable(requests.Session().mount)} / {type(httpx.Client()._mounts).__name__}")
with httpx.stream("GET", f"{HTTP}/get") as s:
    show("httpx elapsed inside stream block", lambda: s.elapsed)
show("httpx elapsed after the block", lambda: s.elapsed)
