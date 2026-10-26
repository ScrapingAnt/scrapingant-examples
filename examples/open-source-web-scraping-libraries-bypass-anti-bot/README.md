# Anti-bot libraries roundup: status and two headless signals

Evidence for https://scrapingant.com/blog/open-source-web-scraping-libraries-bypass-anti-bot.

- `status.sh` records each library's GitHub status (stars, last push, archived, licence) and its latest PyPI or npm release. Needs an authenticated `gh`.
- `cases/01_playwright_headless.js` opens https://httpbin.org/headers in default headless Playwright Chromium and prints the User-Agent and `navigator.webdriver`.
- `cases/02_scrapingant_api.js` loads the same page through the ScrapingAnt API, with a `js_snippet` that writes `navigator.webdriver` into the page, and prints the same two values. Needs `SCRAPINGANT_API_KEY`.

These are two well-known detection signals, not a test of any anti-bot product.

```bash
npm ci && npx playwright install chromium-headless-shell
SCRAPINGANT_API_KEY=... ./run.sh > expected_output/run.txt
```
