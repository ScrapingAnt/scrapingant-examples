import requests
from _common import URL, show, warn_to_stdout
warn_to_stdout()
show("requests.get(URL, verify=False)", lambda: requests.get(URL, verify=False).status_code)
show("requests.get(URL, verify=False)  # again", lambda: requests.get(URL, verify=False).status_code)
show("requests.get(URL)  # next call, no verify=", lambda: requests.get(URL).status_code)
