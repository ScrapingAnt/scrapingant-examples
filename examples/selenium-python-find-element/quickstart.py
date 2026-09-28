"""Complete no-key example: serve, navigate, wait, validate, print and clean up."""
import json
from selenium.webdriver.common.by import By
from browser_support import browser, fixture_server
from extraction import wait_records


def main():
    with fixture_server() as origin, browser() as driver:
        driver.get(origin + '/catalog.html?delayed=1')
        driver.find_element(By.ID, 'begin').click()
        print(json.dumps(wait_records(driver), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
