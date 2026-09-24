// The same request from TypeScript (run with: node --experimental-strip-types 03_request_node.ts).
const key = process.env.SCRAPINGANT_API_KEY;
if (!key) { console.log("skipped: SCRAPINGANT_API_KEY is not set"); process.exit(0); }
const url = "https://scrapingant.github.io/scrapingant-examples/fixtures/markdown-article.html";

const res = await fetch(
  "https://api.scrapingant.com/v2/markdown?" + new URLSearchParams({ url }),
  { headers: { "x-api-key": key } },
);
const { url: finalUrl, markdown } = (await res.json()) as { url: string; markdown: string };
console.log("status:", res.status, "| Ant-credits-cost:", res.headers.get("ant-credits-cost"), "| Ant-page-status-code:", res.headers.get("ant-page-status-code"));
console.log("url:", finalUrl);
console.log("markdown characters:", markdown.length);
console.log(markdown.split("\n").slice(0, 8).join("\n"));
