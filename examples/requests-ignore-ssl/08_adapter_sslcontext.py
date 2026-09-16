"""The supported way to use a custom SSLContext: an HTTPAdapter mounted for one host prefix."""
import ssl, requests
from requests.adapters import HTTPAdapter
from _common import URL, IP_URL, CA, PUBLIC, show, warn_to_stdout
warn_to_stdout()

class SSLContextAdapter(HTTPAdapter):
    def __init__(self, ssl_context, **kw):
        self.ssl_context = ssl_context
        super().__init__(**kw)
    def init_poolmanager(self, *a, **kw):
        kw["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*a, **kw)

# 1. trust one CA and keep hostname checking, for one host only
ctx = ssl.create_default_context(cafile=CA)
s = requests.Session()
s.mount("https://localhost:8443", SSLContextAdapter(ctx))
show("adapter(cafile=CA) mounted on https://localhost:8443; s.get(URL)", lambda: s.get(URL).status_code)
show("same session; s.get(PUBLIC) (default adapter, still verified)", lambda: s.get(PUBLIC).status_code)
show("same session; s.get('https://127.0.0.1:8443/') (not mounted -> default verification)", lambda: s.get(IP_URL).status_code)

# 2. a CERT_NONE context does NOT switch verification off: requests re-applies cert_reqs=CERT_REQUIRED
insecure = ssl.create_default_context()
insecure.check_hostname = False
insecure.verify_mode = ssl.CERT_NONE
s2 = requests.Session()
s2.mount("https://127.0.0.1:8443", SSLContextAdapter(insecure))
show("adapter(CERT_NONE) mounted on https://127.0.0.1:8443; s2.get(IP_URL)", lambda: s2.get(IP_URL).status_code)

# 3. what does switch it off for one host only: an adapter that forces verify=False
class NoVerifyAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
        kwargs["verify"] = False
        return super().send(request, **kwargs)

s3 = requests.Session()
s3.mount("https://127.0.0.1:8443", NoVerifyAdapter())
show("NoVerifyAdapter mounted on https://127.0.0.1:8443; s3.get(IP_URL)", lambda: s3.get(IP_URL).status_code)
show("same session; s3.get(URL) (localhost not mounted -> still verified)", lambda: s3.get(URL).status_code)
