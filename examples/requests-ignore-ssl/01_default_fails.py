import requests
from _common import URL, show
show("requests.get(URL)", lambda: requests.get(URL).status_code)
