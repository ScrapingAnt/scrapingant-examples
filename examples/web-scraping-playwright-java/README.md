# Playwright Java: owned dynamic catalog evidence

This complete Maven example serves a synthetic catalog on an ephemeral `127.0.0.1` port. JavaScript renders two products after 250 ms, then sets `data-state="ready"` and `data-count`. The scraper waits for that explicit application contract, validates every record and the expected count, and atomically writes UTF-8 JSON only after all validation succeeds.

## Reproduce the tested environment

Docker is required. From this directory:

```sh
docker pull mcr.microsoft.com/playwright/java:v1.63.0-noble
docker run --rm --ipc=host \
  -v "$PWD:/work" -w /work \
  mcr.microsoft.com/playwright/java:v1.63.0-noble ./run.sh
```

These commands were executed on Linux ARM64 through Docker on September 30, 2026. The image supplied OpenJDK **25.0.4**, Maven **3.9.12**, and Chromium **153.0.8010.12**. The POM targets Java **21** bytecode; Java 21 itself was not the tested runtime. The resolved image digest was `sha256:013e2595272806f887d91041fbf26be71dda2f48a805c717cc7de3bbca5339c8`; use `mcr.microsoft.com/playwright/java@sha256:013e2595272806f887d91041fbf26be71dda2f48a805c717cc7de3bbca5339c8` for that exact image reference. Maven dependencies and build plugins are version-pinned in `pom.xml`. Initial Maven dependency resolution needs internet access; the scrape itself only contacts loopback.

`run.sh` compiles the project, runs the independent expected-value tests, records dependencies, builds the runtime classpath, and invokes the real CLI for six scenarios. It exits nonzero if a test or expected CLI outcome fails. Captured stdout, stderr, versions and exit statuses are in `expected_output/`. Generated build products are ignored. The dedicated `playwright-java-evidence.yml` CI workflow runs this container on relevant pull requests, main-branch pushes and a monthly schedule. This Java packet is intentionally outside the Python-oriented general example allowlist.

## Run one scenario

From this directory, this full command compiles and resolves dependencies, then executes the single-scenario CLI in the same container. It was executed and its final stdout/stderr were captured in `expected_output/readme-single.*.txt`:

```sh
docker run --rm --ipc=host \
  -v "$PWD:/work" -w /work \
  mcr.microsoft.com/playwright/java:v1.63.0-noble \
  bash -c './run.sh && java -cp "target/classes:$(cat target/classpath.txt)" example.Main success output/catalog.json > expected_output/readme-single.stdout.txt 2> expected_output/readme-single.stderr.txt'
```

The product JSON is also saved to `output/catalog.json` in the mounted project directory.

A new disposable container has a fresh Maven cache: first run `./run.sh` in that same container. Reusing only the host-mounted classpath file in a new container is insufficient; the captured `fresh-container-without-dependencies.stderr.txt` records that failed diagnostic attempt. The same executable is exercised directly by `run.sh` for each scenario (using fresh temporary output paths). `Main` accepts `CASE OUTPUT.json`. The fixture server stops when the run ends. `CatalogScraper` owns Playwright, browser and context in nested try-with-resources on one thread.

| Case | Expected exit | Outcome |
|---|---:|---|
| `success` | 0 | Two exact product records, including Unicode titles |
| `empty` | 0 | Ready catalog with count zero writes `[]` |
| `missing-field` | 2 | Second product lacks price; no new output |
| `timeout` | 3 | Fixture never sets readiness; no new output |
| `duplicate` | 2 | Duplicate identifier; no new output |
| `mismatch` | 2 | Expected three cards but only two exist; no new output |

Unexpected errors use exit 1; invalid argument count uses exit 64. A failed run preserves an existing output file. The JSON write uses a same-directory temporary file and an atomic replacement; a filesystem without atomic move support returns an error instead of falling back to a potentially partial write. The 1500 ms navigation timeout and 1500 ms readiness timeout are separate operation limits, not a total execution deadline.

## Independent checks and limits

The JUnit oracle spells out both expected products independently of fixture-generation and scraper code, compares the complete JSON tree and cardinality, checks the six expected outcomes, verifies no new output for invalid cases, and checks preservation of a previous output. Each of the six cases also checks that the JVM has no new live descendant processes after the scraper returns. A separate check confirms that the fixture server's port can be bound again after close. These checks cover the observed container process tree and loopback port; they are not a general OS resource-leak proof. Three JUnit tests cover the six-case matrix plus output-preservation and server-port checks.

The fixture promises a stable catalog after readiness. Real sites need their own reliable readiness and completeness contract; counting matching locators does not wait for an entire dynamic list. Price validation here accepts nonnegative two-decimal values, and currency validation checks three uppercase characters; it does not establish a real ISO currency or locale-aware number parser. No external site, credentials, proxy, retries, performance benchmark, or paid API is involved. Original article defects are source-inspection findings, not reproduced compiler diagnostics from this packet.

## Native installation alternative (not executed for this packet)

With JDK 21+ and Maven installed:

```sh
mvn -B -ntp compile
mvn -B -ntp exec:java -Dexec.mainClass=com.microsoft.playwright.CLI -Dexec.args="install --with-deps chromium"
./run.sh
```

The browser install may require OS package privileges. See the official [Java introduction](https://playwright.dev/java/docs/intro), [browser installation](https://playwright.dev/java/docs/browsers), [locators](https://playwright.dev/java/docs/locators), and [threading](https://playwright.dev/java/docs/multithreading) documentation.
