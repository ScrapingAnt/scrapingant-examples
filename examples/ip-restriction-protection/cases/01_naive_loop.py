import requests

for i in range(1, 11):
    response = requests.get(f"http://127.0.0.1:8000/item/{i}", timeout=10)
    print(i, response.status_code, response.headers.get("Retry-After"), response.json().get("error"))
