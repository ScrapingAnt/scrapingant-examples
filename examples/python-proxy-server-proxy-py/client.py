"""Usage: python client.py [http|https]; start `python lab.py serve` first."""
import sys
import requests

scheme = sys.argv[1] if len(sys.argv) > 1 else 'http'
if scheme not in {'http', 'https'}:
    raise SystemExit('Use http or https')
url = f'{scheme}://localhost:{8443 if scheme == "https" else 8000}/reader-client'
proxies = {'http': 'http://127.0.0.1:8899', 'https': 'http://127.0.0.1:8899'}
with requests.Session() as session:
    session.trust_env = False
    response = session.get(url, proxies=proxies, timeout=5, verify='generated/ca.pem')
    response.raise_for_status()
    print(response.status_code)
    print(response.text, end='')
