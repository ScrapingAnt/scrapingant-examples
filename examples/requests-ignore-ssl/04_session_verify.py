import requests, urllib3
from _common import URL, show
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
s = requests.Session()
s.verify = False
show("session.verify=False; s.get(URL)", lambda: s.get(URL).status_code)
show("session.verify=False; s.get(URL + 'index.html')", lambda: s.get(URL + "index.html").status_code)
show("session.verify=False; s.get(URL, verify=True)", lambda: s.get(URL, verify=True).status_code)
