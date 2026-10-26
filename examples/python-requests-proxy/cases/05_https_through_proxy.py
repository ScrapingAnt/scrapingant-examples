from urllib.parse import quote

import requests

proxy = f"http://lab:{quote('p@ss#w0rd', safe='')}@127.0.0.1:8899"

# The "https" key is the scheme of the website. The proxy itself is still http://
response = requests.get("https://example.com/", proxies={"https": proxy}, timeout=15)
print(response.status_code, response.text.split("<title>")[1].split("</title>")[0])
