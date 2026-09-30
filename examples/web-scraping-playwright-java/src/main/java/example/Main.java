package example;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.microsoft.playwright.TimeoutError;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

public final class Main {
  public static void main(String[] args) {
    int status = run(args);
    if (status != 0) System.exit(status);
  }
  static int run(String[] args) {
    if (args.length != 2) { System.err.println("Usage: Main CASE OUTPUT.json"); return 64; }
    Path output = Path.of(args[1]).toAbsolutePath();
    Path temporary = null;
    try (FixtureServer server = new FixtureServer()) {
      var result = CatalogScraper.scrape(server.url(args[0]), 1500);
      String json = new ObjectMapper().writerWithDefaultPrettyPrinter().writeValueAsString(result.products()) + "\n";
      Files.createDirectories(output.getParent());
      temporary = Files.createTempFile(output.getParent(), ".catalog-", ".tmp");
      Files.writeString(temporary, json, StandardCharsets.UTF_8);
      Files.move(temporary, output, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
      System.out.println("case=" + args[0] + " outcome=success records=" + result.products().size());
      System.out.println("browser=" + result.browserVersion());
      System.out.print(json);
      return 0;
    } catch (TimeoutError e) {
      System.err.println("case=" + args[0] + " outcome=timeout"); return 3;
    } catch (CatalogScraper.InvalidCatalog e) {
      System.err.println("case=" + args[0] + " outcome=invalid reason=" + e.getMessage()); return 2;
    } catch (Exception e) {
      System.err.println("outcome=error reason=" + e); return 1;
    } finally {
      if (temporary != null) try { Files.deleteIfExists(temporary); }
      catch (java.io.IOException e) { System.err.println("Temporary-file cleanup failed: " + e); }
    }
  }
}
