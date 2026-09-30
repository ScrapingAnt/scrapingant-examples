package example;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.net.*;
import static org.junit.jupiter.api.Assertions.*;

class CatalogScraperTest {
  @TempDir Path directory;
  @Test void exactValuesAndSixCaseFailureMatrix() throws Exception {
    // Independently authored expected values, never imported from the fixture or scraper.
    var expected = new ObjectMapper().readTree("""
      [{"id":"mug-001","title":"Café mug ☕","price":12.50,"currency":"EUR"},
       {"id":"book-002","title":"Field notes — Київ","price":8.00,"currency":"EUR"}]
      """);
    String[] cases = {"success", "empty", "missing-field", "timeout", "duplicate", "mismatch"};
    int[] statuses = {0, 0, 2, 3, 2, 2};
    for (int i = 0; i < cases.length; i++) {
      Path output = directory.resolve(cases[i] + ".json");
      var baselineChildren = ProcessHandle.current().descendants().map(ProcessHandle::pid).toList();
      assertEquals(statuses[i], Main.run(new String[]{cases[i], output.toString()}), cases[i]);
      if (i < 2) {
        var parsed = new ObjectMapper().readTree(Files.readString(output, StandardCharsets.UTF_8));
        assertEquals(i == 0 ? expected : new ObjectMapper().readTree("[]"), parsed);
      } else assertFalse(Files.exists(output), "Failed case must not create output");
      var remainingChildren = ProcessHandle.current().descendants()
          .filter(ProcessHandle::isAlive).filter(child -> !baselineChildren.contains(child.pid())).toList();
      assertTrue(remainingChildren.isEmpty(), "Playwright child processes must exit: " + remainingChildren);
      System.out.println("CLEANUP " + cases[i] + " PASS new_live_children=0");
      System.out.println("CONTROL " + cases[i] + " PASS exit=" + statuses[i]);
    }
    System.out.println("CONTROL matrix PASS cases=6/6");
  }
  @Test void failurePreservesExistingOutputWithoutCreatingExtraFiles() throws Exception {
    Path output = directory.resolve("catalog.json");
    Files.writeString(output, "previous complete output", StandardCharsets.UTF_8);
    assertEquals(2, Main.run(new String[]{"missing-field", output.toString()}));
    assertEquals("previous complete output", Files.readString(output));
    try (var files = Files.list(directory)) { assertEquals(1, files.count()); }
  }
  @Test void serverReleasesPortOnClose() throws Exception {
    int port;
    try (FixtureServer server = new FixtureServer()) {
      port = server.port();
      assertEquals(200, ((HttpURLConnection) URI.create(server.url("empty")).toURL().openConnection()).getResponseCode());
    }
    try (var socket = new java.net.ServerSocket()) { socket.bind(new InetSocketAddress("127.0.0.1", port)); }
  }
}
