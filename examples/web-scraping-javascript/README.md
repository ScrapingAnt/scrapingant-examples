# Web scraping with JavaScript (Node.js): tested snippets

Evidence for https://scrapingant.com/blog/web-scraping-javascript. Each file in `cases/` is a snippet from the article (Node.js 22, ES modules). Targets are the public practice sites example.com, books.toscrape.com and quotes.toscrape.com (`/js/` builds its quotes with JavaScript). Case 08 calls the ScrapingAnt API and runs only with `SCRAPINGANT_API_KEY`.

```bash
npm ci && npx playwright install chromium-headless-shell && npx puppeteer browsers install chrome-headless-shell
SCRAPINGANT_API_KEY=... ./run.sh > expected_output/run.txt
```
