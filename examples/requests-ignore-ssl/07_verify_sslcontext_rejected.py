"""The 2024 version of the article passed an ssl.SSLContext as verify=. requests does not accept that."""
import ssl, requests
from _common import URL, CA, show
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
show("requests.get(URL, verify=<SSLContext CERT_NONE>)", lambda: requests.get(URL, verify=ctx).status_code)
ctx2 = ssl.create_default_context(cafile=CA)
show("requests.get(URL, verify=ssl.create_default_context(cafile=CA))", lambda: requests.get(URL, verify=ctx2).status_code)
