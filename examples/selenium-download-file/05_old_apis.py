from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

for name, action in [
    ("Chrome executable_path", lambda: webdriver.Chrome(executable_path="/unused")),
    ("Firefox executable_path", lambda: webdriver.Firefox(executable_path="/unused")),
    ("Firefox firefox_profile", lambda: webdriver.Firefox(firefox_profile=None)),
    ("find_element_by_id", lambda: getattr(WebDriver, "find_element_by_id")),
    ("old window.open snippet", lambda: compile("driver.execute_script('window.open(\n\n, download_url)')", "old-snippet", "exec")),
]:
    try:
        action()
    except (TypeError, AttributeError, SyntaxError) as exc:
        print(f"{name}: {type(exc).__name__}: {str(exc).splitlines()[0]}")
    else:
        raise AssertionError(f"Old API unexpectedly accepted: {name}")
