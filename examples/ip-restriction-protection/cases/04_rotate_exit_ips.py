import itertools

import requests

PROXIES = itertools.cycle(["http://127.0.0.1:8901", "http://127.0.0.1:8902"])

for i in range(1, 11):
    proxy = next(PROXIES)
    response = requests.get(f"http://127.0.0.1:8000/item/{i}", proxies={"http": proxy, "https": proxy}, timeout=10)
    print(i, response.status_code, "seen as", response.json()["client"])
