"""Selenium 4: no manual chromedriver download, Selenium Manager resolves the driver."""
import selenium
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from _fixtures import LOCAL

opts = Options()
opts.add_argument("--headless=new")
driver = webdriver.Chrome(options=opts)  # Selenium Manager finds/downloads a matching chromedriver
print(f"selenium {selenium.__version__}, chrome {driver.capabilities['browserVersion']}")

driver.get(LOCAL["domcontentloaded"].as_uri())
soup = BeautifulSoup(driver.page_source, "html.parser")
print(f"domcontentloaded: {soup.find(id='test').get_text()}")

driver.get(LOCAL["delayed"].as_uri())
soup = BeautifulSoup(driver.page_source, "html.parser")
print(f"delayed, read immediately: {soup.find(id='test').get_text()}")
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "loaded")))
soup = BeautifulSoup(driver.page_source, "html.parser")
print(f"delayed, after waiting for #loaded: {soup.find(id='test').get_text()}")

driver.quit()
