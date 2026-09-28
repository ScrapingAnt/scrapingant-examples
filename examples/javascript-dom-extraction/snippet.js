// The runner inserts JSON configuration. The body is a ScrapingAnt js_snippet.
const config = __CONFIG__;
let result;
try {
  if (config.mode === "delayed") {
    const deadline = Date.now() + 4000;
    while (!document.querySelector("#loaded") && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    if (!document.querySelector("#loaded")) throw new Error("NOT_READY");
    // Deliberate awaited DOM change: verifies completion, not API latency.
    await new Promise(resolve => setTimeout(resolve, 50));
    result = {version: 1, ok: true, data: {
      text: document.querySelector("#test").textContent.trim(), awaited: true
    }};
  } else {
    const rows = [...document.querySelectorAll(config.selector)];
    if (!rows.length) throw new Error("ELEMENT_MISSING");
    const records = rows.map(row => {
      const cells = [...row.querySelectorAll("td")].map(cell => cell.textContent.trim());
      if (cells.length !== 4 || cells.some(value => !value)) throw new Error("FIELDS_MISSING");
      return {product: cells[0], price: cells[1], units: cells[2], share: cells[3]};
    });
    // Synthetic transport probe, separate from the real catalog extraction.
    const probe = document.createElement("span");
    probe.textContent = config.probe;
    document.body.append(probe);
    result = {version: 1, ok: true, data: {records, transport_probe: probe.textContent}};
    probe.remove();
  }
} catch (error) {
  const allowed = ["NOT_READY", "ELEMENT_MISSING", "FIELDS_MISSING"];
  const code = allowed.includes(error.message) ? error.message : "EXTRACTION_FAILED";
  result = {version: 1, ok: false, error: {code}};
}
const carrier = document.createElement("script");
carrier.id = config.marker;
carrier.type = "application/json";
// Script data is raw text: escape less-than, not HTML entities.
carrier.textContent = JSON.stringify(result).replace(/</g, "\\u003c");
document.body.append(carrier);
