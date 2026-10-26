import requests  # pip install "requests[socks]"

proxy = "socks5h://lab:secret@127.0.0.1:1080"  # socks5h: the proxy resolves hostnames
response = requests.get("http://localhost:8000/socks", proxies={"http": proxy, "https": proxy}, timeout=10)
print(response.status_code, response.json())
