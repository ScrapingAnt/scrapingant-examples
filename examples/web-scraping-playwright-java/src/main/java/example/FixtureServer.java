package example;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

public final class FixtureServer implements AutoCloseable {
  private final HttpServer server;
  public FixtureServer() throws IOException {
    byte[] html = Files.readAllBytes(Path.of("fixtures/catalog.html"));
    server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/catalog", exchange -> {
      exchange.getResponseHeaders().set("Content-Type", "text/html; charset=UTF-8");
      exchange.sendResponseHeaders(200, html.length);
      try (var body = exchange.getResponseBody()) { body.write(html); }
      finally { exchange.close(); }
    });
    server.start();
  }
  public String url(String scenario) {
    if (!Set.of("success", "empty", "missing-field", "timeout", "duplicate", "mismatch").contains(scenario))
      throw new IllegalArgumentException("Unknown fixture case: " + scenario);
    return "http://127.0.0.1:" + port() + "/catalog?case=" + scenario;
  }
  public int port() { return server.getAddress().getPort(); }
  @Override public void close() { server.stop(0); }
}
