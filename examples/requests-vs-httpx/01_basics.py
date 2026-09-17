"""The same GET and POST with both libraries: what the objects look like, where they differ."""
import warnings
import httpx
import requests
from _common import HTTP, show

warnings.simplefilter("always")
warnings.showwarning = lambda m, c, f, l, file=None, line=None: print(f"  {c.__name__}: {m}")

r1 = requests.get(f"{HTTP}/get", params={"q": "ant"})
r2 = httpx.get(f"{HTTP}/get", params={"q": "ant"})
print("--- GET")
print("requests:", r1.status_code, "|", r1.headers["content-type"], "|", r1.json()["http_version"], "|", type(r1.url).__name__, r1.url)
print("httpx:   ", r2.status_code, "|", r2.headers["content-type"], "|", r2.http_version, "|", type(r2.url).__name__, r2.url)
print("requests user-agent:", r1.json()["user_agent"])
print("httpx user-agent:   ", r2.json()["user_agent"])
print("requests r.ok / httpx r.is_success:", r1.ok, r2.is_success)
show("requests r.is_success", lambda: r1.is_success)
show("httpx r.ok", lambda: r2.ok)
print("raise_for_status() returns:", type(r1.raise_for_status()).__name__, "/", type(r2.raise_for_status()).__name__)
print("elapsed types:", type(r1.elapsed).__name__, "/", type(r2.elapsed).__name__)

print("--- POST form, json, raw bytes")
for label, kwargs in [("data=dict", {"data": {"k": "v"}}), ("json=", {"json": {"k": "v"}})]:
    a = requests.post(f"{HTTP}/post", **kwargs).json()
    b = httpx.post(f"{HTTP}/post", **kwargs).json()
    print(f"{label:<10} requests: {a['content_type']!r} {a['body']!r}")
    print(f"{'':<10} httpx:    {b['content_type']!r} {b['body']!r}")
a = requests.post(f"{HTTP}/post", data=b"raw bytes").json()
print(f"{'data=bytes':<10} requests: {a['content_type']!r} {a['body']!r}")
b = httpx.post(f"{HTTP}/post", data=b"raw bytes").json()
print(f"{'':<10} httpx:    {b['content_type']!r} {b['body']!r}   <- deprecated, use content=")
b = httpx.post(f"{HTTP}/post", content=b"raw bytes").json()
print(f"{'content=':<10} httpx:    {b['content_type']!r} {b['body']!r}")

print("--- query params edge cases")
print("requests params={'a': None, 'b': 1}:", requests.get(f"{HTTP}/get", params={"a": None, "b": 1}).json()["query"])
print("httpx    params={'a': None, 'b': 1}:", httpx.get(f"{HTTP}/get", params={"a": None, "b": 1}).json()["query"])
print("requests params=[('k','1'),('k','2')]:", requests.get(f"{HTTP}/get", params=[("k", "1"), ("k", "2")]).json()["query"])
show("httpx    params=[('k','1'),('k','2')]", lambda: httpx.get(f"{HTTP}/get", params=[("k", "1"), ("k", "2")]).json()["query"])
print("httpx    params={'k': ['1','2']}:", httpx.get(f"{HTTP}/get", params={"k": ["1", "2"]}).json()["query"])
print("--- request body on GET")
print("requests.get(json=...):", requests.get(f"{HTTP}/get", json={"k": "v"}).status_code)
show("httpx.get(json=...)", lambda: httpx.get(f"{HTTP}/get", json={"k": "v"}).status_code)
