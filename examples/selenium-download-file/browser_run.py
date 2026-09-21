import argparse
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from download_helpers import ensure_empty, wait_for_download
from fixture_server import CASES, expected, fixture_server


def run(browser, create_driver, headless, output=None):
    mode = "headless" if headless else "headed"
    with TemporaryDirectory(prefix="selenium-download-") as scratch:
        directory = ensure_empty(output or Path(scratch) / "downloads")
        with fixture_server() as url:
            driver = create_driver(directory, headless)
            try:
                print(f"{browser}/{mode}: browser={driver.capabilities['browserVersion']}")
                if browser == "chrome":
                    version = driver.capabilities["chrome"]["chromedriverVersion"].split()[0]
                else:
                    version = driver.capabilities["moz:geckodriverVersion"]
                print(f"driver={version}")
                driver.get(url)
                for case in CASES:
                    name, size, digest = expected(case)
                    target = directory / name
                    if target.exists():
                        raise FileExistsError(name)
                    WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, case))
                    ).click()
                    result = wait_for_download(target, size, digest)
                    actual = result.read_bytes()
                    print(f"{case}: {name} bytes={len(actual)}/{size} "
                          f"sha256={hashlib.sha256(actual).hexdigest()} verified=True")
                print("verified=3 attempted=3")
                if output:
                    print(f"saved={directory}")
            finally:
                driver.quit()


def main(browser, create_driver):
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--output", type=Path,
                        help="Empty directory to retain downloads; default: temporary")
    args = parser.parse_args()
    run(browser, create_driver, not args.headed, args.output)
