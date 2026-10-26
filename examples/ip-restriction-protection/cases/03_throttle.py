import time

import requests

MIN_INTERVAL = 2.0  # seconds between requests: 5 per 10 s, the site's limit
last = 0.0
for i in range(1, 9):
    time.sleep(max(0.0, last + MIN_INTERVAL - time.monotonic()))
    last = time.monotonic()
    response = requests.get(f"http://127.0.0.1:8000/item/{i}", timeout=10)
    print(i, response.status_code)
