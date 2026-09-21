"""Expected failures are asserted, not swallowed."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from chrome_download import create_driver as chrome
from firefox_download import create_driver as firefox
from download_helpers import ensure_empty, wait_for_download
from fixture_server import fixture_server, expected


def expect(label, error, callback):
    try:
        callback()
    except error:
        print(f"{label}: {error.__name__} (expected)")
    else:
        raise AssertionError(f"{label}: unexpectedly succeeded")


with TemporaryDirectory() as scratch:
    directory = Path(scratch)
    target = directory / "report.csv"
    body = b"id,name\n1,Ant\n"
    size, digest = len(body), hashlib.sha256(body).hexdigest()
    target.write_bytes(body[:3])
    print(f"naive exists={target.exists()} nonempty_directory={bool(list(directory.iterdir()))} bytes={target.stat().st_size}/{size}")
    expect("truncated", TimeoutError,
           lambda: wait_for_download(target, size, digest, timeout=0.2))
    target.write_bytes(body)
    expect("stale directory", FileExistsError, lambda: ensure_empty(directory))
    target.unlink()
    expect("missing", TimeoutError,
           lambda: wait_for_download(target, size, digest, timeout=0.2))

for browser, factory in (("chrome", chrome), ("firefox", firefox)):
    with TemporaryDirectory() as scratch, fixture_server() as url:
        directory = ensure_empty(scratch)
        driver = factory(directory, True)
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "interrupted"))
            ).click()
            name, size, digest = expected("slow")
            expect(f"{browser} interrupted HTTP body", TimeoutError,
                   lambda: wait_for_download(directory / name, size, digest, timeout=3))
            # Firefox may allocate a random temporary name; record suffixes only.
            print(f"{browser} remaining suffixes={sorted(p.suffix for p in directory.iterdir())}")
        finally:
            driver.quit()
