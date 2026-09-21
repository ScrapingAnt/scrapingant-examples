# Approved primary sources (accessed 2026-09-21)

- https://pypi.org/pypi/selenium/json — version 4.49.0, requires Python >=3.10. Reproduction uses Python 3.12.11.
- https://www.selenium.dev/documentation/selenium_manager/ — fallback driver discovery/download/cache, automated Firefox provisioning and browser version labels. Initial resolution needs network access; manager caches downloaded artifacts.
- https://developer.chrome.com/docs/chromedriver/capabilities — use full download paths; choose a nonspecial directory; ChromeDriver does not wait for download completion and early quit can terminate a transfer.
- https://www.selenium.dev/documentation/webdriver/waits/ — explicit waits poll a specified condition; the packet waits for clickability, separately from checking the filesystem.
- https://www.selenium.dev/documentation/test_practices/discouraged/file_downloads/ — use Selenium to obtain a link/cookies, then an HTTP library when browser download behavior is not the objective. Do not broaden this into a claim that all newer browser event APIs lack download events.
- https://www.selenium.dev/documentation/webdriver/troubleshooting/upgrade_to_selenium_4/ — supported migration patterns; exact failures are captured against 4.49.0 in 05_old_apis.txt.
- https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_firefox/selenium.webdriver.firefox.options.html — Firefox Options.set_preference API. Preference combinations and PDF attachment saving are measured by this packet, not claimed universally.
- https://searchfox.org/firefox-main/source/browser/app/profile/firefox.js — browser.download.useDownloadDir and browser.download.folderList source defaults. Article explains the tested custom-directory combination without inferring that every MIME preference is necessary in every Firefox version.

Product boundary: no paid API was used and no binary-file retrieval capability is claimed for ScrapingAnt. The optional page-acquisition next step links to https://docs.scrapingant.com/request-response-format without making additional product capability claims.
