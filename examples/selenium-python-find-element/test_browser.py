"""A real-browser regression forcing replacement between locate and projection."""
import unittest
from contextlib import ExitStack

from selenium.webdriver.common.by import By
from browser_support import browser, fixture_server
from extraction import wait_records
from test_packet import RECORDS


class BrowserRegression(unittest.TestCase):
    def test_stale_during_projection_requeries_locator(self):
        with ExitStack() as stack:
            origin = stack.enter_context(fixture_server())
            driver = stack.enter_context(browser())
            driver.get(origin + '/catalog.html')

            class ReplaceFirstSearch:
                # A scheduling adapter around real WebElements: no fake exceptions.
                def __init__(self):
                    self.searches = 0

                def find_elements(self, by, value):
                    rows = driver.find_elements(by, value)
                    self.searches += 1
                    if self.searches == 1:
                        driver.find_element(By.ID, 'replace').click()
                    return rows

            search = ReplaceFirstSearch()
            self.assertEqual(wait_records(search), RECORDS)
            self.assertEqual(search.searches, 2)


if __name__ == '__main__':
    unittest.main()
