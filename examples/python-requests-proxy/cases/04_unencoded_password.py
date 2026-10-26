import requests

for password in ["p@ss#w0rd", "p%40ss%23w0rd"]:
    proxy = f"http://lab:{password}@127.0.0.1:8899"
    try:
        response = requests.get("http://127.0.0.1:8000/ip", proxies={"http": proxy}, timeout=10)
        print(password, "->", response.status_code, response.reason)
    except Exception as error:
        print(password, "->", type(error).__name__, str(error)[:80])
