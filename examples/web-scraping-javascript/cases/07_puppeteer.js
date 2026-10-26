import puppeteer from 'puppeteer';

const browser = await puppeteer.launch();
const page = await browser.newPage();
await page.goto('https://quotes.toscrape.com/js/');
await page.waitForSelector('div.quote');

const authors = await page.$$eval('div.quote .author', (nodes) => nodes.map((n) => n.textContent));
console.log(authors.length, 'quotes, first authors:', authors.slice(0, 3).join(', '));
await browser.close();
