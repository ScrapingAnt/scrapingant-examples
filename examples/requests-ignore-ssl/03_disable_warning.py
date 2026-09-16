import requests, urllib3
from _common import URL, show, warn_to_stdout
warn_to_stdout()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
show("after urllib3.disable_warnings(InsecureRequestWarning)", lambda: requests.get(URL, verify=False).status_code)
