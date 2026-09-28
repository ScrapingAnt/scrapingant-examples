"""Extract the complete catalog; a wait re-locates after a stale reference."""
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from oracle import exact_records

CATALOG = (By.CSS_SELECTOR, '#catalog .product.active')


def project(rows):
    result = []
    for row in rows:
        title = row.find_element(By.CSS_SELECTOR, '.title')
        badges = row.find_elements(By.CSS_SELECTOR, '.badge')
        result.append({
            'sku': row.get_dom_attribute('data-sku'),
            'title': title.text,
            'currency': row.find_element(By.CSS_SELECTOR, '.currency').text,
            'price': row.find_element(By.CSS_SELECTOR, '.price').text,
            'href': title.get_dom_attribute('href'),
            'badge': badges[0].text if badges else None,
        })
    return result


def wait_records(driver, locator=CATALOG, timeout=5):
    def complete(current):
        try:
            records = project(current.find_elements(*locator))
            return records if exact_records(records) else False
        except (NoSuchElementException, StaleElementReferenceException):
            return False
    return WebDriverWait(driver, timeout, poll_frequency=0.05).until(complete)
