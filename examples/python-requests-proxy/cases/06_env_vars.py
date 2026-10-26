import os

import requests

os.environ["HTTP_PROXY"] = "http://127.0.0.1:8901"
os.environ["NO_PROXY"] = "localhost"

print(requests.get("http://127.0.0.1:8000/env").json()["via"])  # picked up from HTTP_PROXY
print(requests.get("http://localhost:8000/env").json()["via"])  # NO_PROXY match, goes direct

session = requests.Session()
session.proxies = {"http": "http://127.0.0.1:8902"}
print(session.get("http://127.0.0.1:8000/env").json()["via"])  # environment wins over session.proxies

session.trust_env = False
print(session.get("http://127.0.0.1:8000/env").json()["via"])  # session.proxies used
print(session.get("http://127.0.0.1:8000/env", proxies={"http": "http://127.0.0.1:8901"}).json()["via"])  # per-request wins
