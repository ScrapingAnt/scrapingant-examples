import ssl, urllib.request
from _common import URL, CA, show
show("urllib.request.urlopen(URL)", lambda: urllib.request.urlopen(URL).status)
show("urlopen(URL, context=ssl._create_unverified_context())", lambda: urllib.request.urlopen(URL, context=ssl._create_unverified_context()).status)
show("urlopen(URL, context=ssl.create_default_context(cafile=CA))", lambda: urllib.request.urlopen(URL, context=ssl.create_default_context(cafile=CA)).status)
