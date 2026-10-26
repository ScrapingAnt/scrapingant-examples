import requests

proxies = {"http": "http://127.0.0.1:8899", "https": "http://127.0.0.1:8899"}

# auth= is sent to the website, not to the proxy
response = requests.get("http://127.0.0.1:8000/ip", proxies=proxies, auth=("lab", "p@ss#w0rd"), timeout=10)
print(response.status_code, response.reason)

try:
    requests.get("https://example.com/", proxies=proxies, auth=("lab", "p@ss#w0rd"), timeout=10)
except requests.exceptions.ProxyError as error:
    print("ProxyError:", "Tunnel connection failed" in str(error), "407" in str(error))
