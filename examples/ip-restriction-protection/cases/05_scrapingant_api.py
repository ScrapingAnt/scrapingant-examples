import os

import requests

seen = set()
for i in range(1, 6):
    response = requests.get(
        "https://api.scrapingant.com/v2/general",
        params={
            "url": "https://ipinfo.io/json",
            "x-api-key": os.environ["SCRAPINGANT_API_KEY"],
            "browser": "false",
            "proxy_type": "residential",
            "proxy_country": "US",
        },
        timeout=60,
    )
    exit_ip = response.json()
    seen.add(exit_ip["ip"])
    print(i, response.headers["Ant-Page-Status-Code"], exit_ip["country"], exit_ip["region"])
print(len(seen), "different exit IPs in 5 requests")
