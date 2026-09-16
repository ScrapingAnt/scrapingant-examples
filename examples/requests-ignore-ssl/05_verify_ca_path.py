import requests
from _common import URL, IP_URL, CA, PUBLIC, show, warn_to_stdout
warn_to_stdout()
show("requests.get(URL, verify='certs/localhost.pem')", lambda: requests.get(URL, verify=CA).status_code)
show("requests.get('https://127.0.0.1:8443/', verify='certs/localhost.pem')", lambda: requests.get(IP_URL, verify=CA).status_code)
show("requests.get(PUBLIC, verify='certs/localhost.pem')  # verify= replaces certifi", lambda: requests.get(PUBLIC, verify=CA).status_code)
