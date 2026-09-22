import platform
from camoufox.sync_api import Camoufox
from common import capture

host_os = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}[platform.system()]
with Camoufox(headless=True, os=host_os, browser="152.0.4-beta.30") as browser:
    capture(browser, "camoufox")
