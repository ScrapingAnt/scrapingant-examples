import urllib3
from _common import URL, CA, show, warn_to_stdout
warn_to_stdout()
show("urllib3.PoolManager().request('GET', URL)", lambda: urllib3.PoolManager().request("GET", URL).status)
show("urllib3.PoolManager(cert_reqs='CERT_NONE')", lambda: urllib3.PoolManager(cert_reqs="CERT_NONE").request("GET", URL).status)
show("urllib3.PoolManager(ca_certs=CA)", lambda: urllib3.PoolManager(ca_certs=CA).request("GET", URL).status)
