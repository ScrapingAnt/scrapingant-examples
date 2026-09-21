from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from urllib.error import HTTPError
from download_helpers import wait_for_download
from fixture_server import fixture_server, expected

with fixture_server() as url, TemporaryDirectory() as scratch:
    name, size, digest = expected("csv")
    target = Path(scratch) / name
    with urlopen(url + "/download/csv", timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status {response.status}")
        target.write_bytes(response.read())
    wait_for_download(target, size, digest)
    print(f"HTTP: {name} bytes={size} sha256={digest} verified=True")
    print(target.read_text(), end="")
    try:
        urlopen(url + "/missing", timeout=10)
    except HTTPError as exc:
        assert exc.code == 404
        print("missing URL: HTTPError 404 (expected)")
    else:
        raise AssertionError("Expected HTTP 404")
