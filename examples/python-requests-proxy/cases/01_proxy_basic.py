import requests

proxy = "http://127.0.0.1:8901"
proxies = {"http": proxy, "https": proxy}

response = requests.get("http://127.0.0.1:8000/ip", proxies=proxies, timeout=10)
print(response.status_code, response.json())
