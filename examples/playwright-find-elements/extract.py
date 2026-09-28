"""Reader-facing extraction helpers. Locators and browser JS remain distinct."""
from playwright.sync_api import expect


def wait_for_catalog(page):
    page.get_by_role("button", name="Load catalog", exact=True).click()
    # This signal belongs to the fixture application, and means all three rows were installed.
    expect(page.locator('#catalog[data-state="ready"]')).to_have_count(1)
    expect(page.locator("#catalog")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#catalog > .product")).to_have_count(3)


def locator_records(rows):
    return [{
        "sku": row.get_attribute("data-sku"),
        "title": row.locator(".title").inner_text().strip(),
        "currency": row.locator(".price").get_attribute("data-currency"),
        "price": row.locator(".price").inner_text().strip(),
        "href": row.locator(".title").get_attribute("href"),
    } for row in rows.all()]


PROJECTION = """rows => rows.map(row => ({
    sku: row.getAttribute('data-sku'),
    title: row.querySelector('.title').innerText.trim(),
    currency: row.querySelector('.price').getAttribute('data-currency'),
    price: row.querySelector('.price').innerText.trim(),
    href: row.querySelector('.title').getAttribute('href')
}))"""
