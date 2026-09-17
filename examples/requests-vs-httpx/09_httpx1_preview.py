"""Install the httpx 1.0 pre-release into a scratch directory and run the 0.28 calls from this packet against it."""
import os
import subprocess
import sys

VERSION = os.environ.get("HTTPX_PRE", "1.0.dev6")
target = os.path.abspath(f"generated/httpx-{VERSION}")
if not os.path.isdir(target):
    cmd = ["uv", "pip", "install", "--quiet", "--target", target, f"httpx=={VERSION}"]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--target", target, f"httpx=={VERSION}"], check=True)
code = r'''
import sys, os
sys.path = [p for p in sys.path if "site-packages" not in p and ".venv" not in p]
sys.path.insert(0, TARGET)
import httpx
print("httpx", httpx.__version__, "from", os.path.relpath(os.path.dirname(httpx.__file__), os.getcwd()))
def show(label, fn):
    try: print(f"{label}: {fn()}")
    except Exception as e: print(f"{label}: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
URL = "http://127.0.0.1:8080/get"
show("httpx.get(URL).status_code", lambda: httpx.get(URL).status_code)
show("httpx.get(URL).json()['http_version']", lambda: httpx.get(URL).json()["http_version"])
show("httpx.Client()", lambda: type(httpx.Client()).__name__)
show("with httpx.Client() as c: c.get(URL)", lambda: (lambda c: c.get(URL).status_code)(httpx.Client()))
show("httpx.AsyncClient", lambda: httpx.AsyncClient.__name__)
show("httpx.Client(http2=True)", lambda: type(httpx.Client(http2=True)).__name__)
show("httpx.get(URL, follow_redirects=True)", lambda: httpx.get(URL, follow_redirects=True).status_code)
show("httpx.get(URL, timeout=5)", lambda: httpx.get(URL, timeout=5).status_code)
show("httpx.get('http://127.0.0.1:8080/redirect/1') default", lambda: httpx.get("http://127.0.0.1:8080/redirect/1").status_code)
show("httpx.post(URL.replace('get','post'), json={'k': 'v'})", lambda: httpx.post(URL.replace("get", "post"), json={"k": "v"}).json()["body"])
show("httpx.post(..., data={'k': 'v'})", lambda: httpx.post(URL.replace("get", "post"), data={"k": "v"}).json()["body"])
show("httpx.stream('GET', URL)", lambda: (lambda s: s.__enter__().status_code)(httpx.stream("GET", URL)))
show("httpx.Timeout", lambda: httpx.Timeout.__name__)
show("httpx.HTTPTransport", lambda: httpx.HTTPTransport.__name__)
show("httpx.Response(200, content=b'x').status_code", lambda: httpx.Response(200, content=b"x").status_code)
show("hasattr(httpx, 'run') (server)", lambda: hasattr(httpx, "run"))
names = sorted(n for n in dir(httpx) if not n.startswith("_") and not n.islower())
print(f"public names ({len(names)}):", ", ".join(names))
'''.replace("TARGET", repr(target))
p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
print(p.stdout, end=""); print(p.stderr.strip().splitlines()[-1] if p.returncode else "", end="")
