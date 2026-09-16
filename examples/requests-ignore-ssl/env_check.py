"""One default request to the local server; prints the status or the exception. Used by the environment-variable cases."""
import sys, requests
from _common import URL, show
if "--no-trust-env" in sys.argv:
    s = requests.Session(); s.trust_env = False
    show("trust_env=False; s.get(URL)", lambda: s.get(URL).status_code)
else:
    show("requests.get(URL)", lambda: requests.get(URL).status_code)
