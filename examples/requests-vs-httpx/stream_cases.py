"""The four download cases for 06_streaming.py, each run in its own process so peak RSS is per case."""
import resource
import sys
import time
import httpx
import requests

URL = "http://127.0.0.1:8080/bytes/52428800"   # 50 MiB
CHUNK = 1024 * 1024


def requests_buffered():
    r = requests.get(URL)
    return len(r.content)


def requests_streamed():
    n = 0
    with requests.get(URL, stream=True) as r:
        for chunk in r.iter_content(CHUNK):
            n += len(chunk)
    return n


def httpx_buffered():
    r = httpx.get(URL)
    return len(r.content)


def httpx_streamed():
    n = 0
    with httpx.stream("GET", URL) as r:
        for chunk in r.iter_bytes(CHUNK):
            n += len(chunk)
    return n


if __name__ == "__main__":
    t = time.perf_counter()
    n = globals()[sys.argv[1]]()
    print(n, round(time.perf_counter() - t, 3), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
