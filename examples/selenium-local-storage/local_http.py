"""Direct fixture reads ignore ambient proxy variables and accept loopback URLs only."""
import json
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


def fetch_catalog(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.port is None
            or parsed.username or parsed.password or parsed.path != '/api/catalog' or parsed.fragment):
        raise ValueError('only the loopback catalog endpoint is allowed')
    opener = build_opener(ProxyHandler({}))
    with opener.open(url, timeout=10) as response:
        return json.load(response)
