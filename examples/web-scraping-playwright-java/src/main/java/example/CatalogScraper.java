package example;

import com.microsoft.playwright.*;
import com.microsoft.playwright.options.WaitForSelectorState;
import java.math.BigDecimal;
import java.util.*;

public final class CatalogScraper {
  public record Product(String id, String title, BigDecimal price, String currency) {}
  public record Result(List<Product> products, String browserVersion) {}
  public static final class InvalidCatalog extends RuntimeException {
    public InvalidCatalog(String message) { super(message); }
  }
  public static Result scrape(String url, double timeoutMs) {
    // All Playwright calls stay on this thread; each scope closes on success or failure.
    try (Playwright playwright = Playwright.create();
         Browser browser = playwright.chromium().launch();
         BrowserContext context = browser.newContext()) {
      Page page = context.newPage();
      page.navigate(url, new Page.NavigateOptions().setTimeout(timeoutMs));
      Locator catalog = page.locator("#catalog[data-state='ready']");
      catalog.waitFor(new Locator.WaitForOptions().setState(WaitForSelectorState.ATTACHED).setTimeout(timeoutMs));
      String expectedText = catalog.getAttribute("data-count");
      if (expectedText == null || !expectedText.matches("[0-9]+"))
        throw new InvalidCatalog("Invalid expected count");
      int expected;
      try { expected = Integer.parseInt(expectedText); }
      catch (NumberFormatException e) { throw new InvalidCatalog("Invalid expected count"); }
      Locator cards = catalog.locator(".product");
      int actual = cards.count(); // Readiness, not count(), establishes list completeness.
      if (actual != expected) throw new InvalidCatalog("Count mismatch: expected " + expected + ", found " + actual);
      Set<String> ids = new HashSet<>();
      List<Product> products = new ArrayList<>();
      for (int i = 0; i < actual; i++) {
        Locator card = cards.nth(i);
        String id = required(card.getAttribute("data-id"), "id");
        String title = field(card, ".title", "title");
        String priceText = field(card, ".price", "price");
        String currency = required(card.getAttribute("data-currency"), "currency");
        if (!ids.add(id)) throw new InvalidCatalog("Duplicate id: " + id);
        if (!priceText.matches("[0-9]+\\.[0-9]{2}")) throw new InvalidCatalog("Invalid price: " + priceText);
        if (!currency.matches("[A-Z]{3}")) throw new InvalidCatalog("Invalid currency: " + currency);
        products.add(new Product(id, title, new BigDecimal(priceText), currency));
      }
      return new Result(List.copyOf(products), browser.version());
    }
  }
  private static String field(Locator card, String selector, String name) {
    Locator value = card.locator(selector);
    if (value.count() != 1) throw new InvalidCatalog("Missing or repeated field: " + name);
    return required(value.textContent(), name);
  }
  private static String required(String value, String name) {
    if (value == null || value.isBlank()) throw new InvalidCatalog("Missing field: " + name);
    return value.strip();
  }
}
