import itertools

import requests

POOL = ["http://127.0.0.1:8901", "http://127.0.0.1:8903", "http://127.0.0.1:8902"]  # 8903 is down
rotation = itertools.cycle(POOL)


def get(url, attempts=3):
    for _ in range(attempts):
        proxy = next(rotation)
        try:
            response = requests.get(url, proxies={"http": proxy, "https": proxy}, timeout=5)
            response.raise_for_status()
            return proxy, response
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout) as error:
            print("skip", proxy, type(error).__name__)
    raise RuntimeError("all attempts failed")


for page in range(1, 5):
    proxy, response = get(f"http://127.0.0.1:8000/page/{page}")
    print(page, proxy, "->", response.json()["via"])
