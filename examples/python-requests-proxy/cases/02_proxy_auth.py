from urllib.parse import quote

import requests

user, password = "lab", "p@ss#w0rd"
proxy = f"http://{quote(user, safe='')}:{quote(password, safe='')}@127.0.0.1:8899"
proxies = {"http": proxy, "https": proxy}

response = requests.get("http://127.0.0.1:8000/ip", proxies=proxies, timeout=10)
print(proxy)
print(response.status_code, response.json())
