import time

import requests


def get(url, max_tries=5):
    for attempt in range(max_tries):
        response = requests.get(url, timeout=10)
        if response.status_code != 429:
            return response
        wait = int(response.headers.get("Retry-After", 2 ** attempt))
        print(f"  429 on {url}, waiting {wait}s")
        time.sleep(wait)
    return response


for i in range(1, 9):
    response = get(f"http://127.0.0.1:8000/item/{i}")
    print(i, response.status_code)
