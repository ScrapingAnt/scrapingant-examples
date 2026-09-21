from selenium import webdriver


def create_driver(download_dir, headless=True):
    options = webdriver.FirefoxOptions()
    options.browser_version = "stable"
    if headless:
        options.add_argument("-headless")
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.dir", str(download_dir))
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk",
                           "text/csv,application/octet-stream,application/pdf")
    options.set_preference("pdfjs.disabled", True)
    return webdriver.Firefox(options=options)


if __name__ == "__main__":
    from browser_run import main
    main("firefox", create_driver)
