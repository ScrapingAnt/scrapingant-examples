import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto('https://quotes.toscrape.com/js/');

const quotes = await page.locator('div.quote').evaluateAll((nodes) =>
  nodes.map((q) => ({ text: q.querySelector('.text').textContent, author: q.querySelector('.author').textContent })),
);
console.log(quotes.length, 'quotes');
console.log(quotes[0]);
await browser.close();
