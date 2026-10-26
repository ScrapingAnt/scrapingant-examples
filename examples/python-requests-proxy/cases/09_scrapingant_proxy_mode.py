import os

import requests
import urllib3

urllib3.disable_warnings()  # proxy mode re-signs HTTPS, so certificate checks are off for this proxy only

API_KEY = os.environ["SCRAPINGANT_API_KEY"]
proxy = f"http://scrapingant&browser=false&proxy_country=FR:{API_KEY}@proxy.scrapingant.com:8080"
proxies = {"http": proxy, "https": proxy}

exit_ips = set()
for _ in range(5):
    response = requests.get("https://ipinfo.io/json", proxies=proxies, verify=False, timeout=60)
    exit_ip = response.json()
    exit_ips.add(exit_ip["ip"])
    print(response.status_code, exit_ip["country"], exit_ip["city"])
print(len(exit_ips), "different exit IPs in 5 requests")
