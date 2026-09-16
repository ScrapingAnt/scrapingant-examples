import certifi, requests
from _common import PUBLIC, show
show("requests.get(PUBLIC)  # valid public certificate, default verify=True", lambda: requests.get(PUBLIC).status_code)
print(f"certifi.where() = .../site-packages/{certifi.where().split('/site-packages/')[-1]}")
print(f"certifi version = {certifi.__version__}")
