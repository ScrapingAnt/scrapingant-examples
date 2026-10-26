import { chromium } from 'playwright';

const browser = await chromium.launch(); // headless by default
const page = await browser.newPage();
await page.goto('https://httpbin.org/headers');

const userAgent = JSON.parse(await page.innerText('body')).headers['User-Agent'];
console.log('User-Agent:', userAgent);
console.log('navigator.webdriver:', await page.evaluate(() => navigator.webdriver));
await browser.close();
