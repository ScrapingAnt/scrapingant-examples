from selenium import webdriver


def create_driver(download_dir, headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_experimental_option("prefs", {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    })
    return webdriver.Chrome(options=options)


if __name__ == "__main__":
    from browser_run import main
    main("chrome", create_driver)
