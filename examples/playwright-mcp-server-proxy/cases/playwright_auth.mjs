import { chromium } from 'playwright';

const browser = await chromium.launch({
  proxy: { server: 'http://127.0.0.1:8899', username: 'lab', password: 'p@ss#w0rd' },
});
const page = await browser.newPage();
const response = await page.goto('http://httpbin.org/headers');
const headers = JSON.parse(await page.innerText('body')).headers;
console.log(response.status(), 'X-Lab-Proxy:', headers['X-Lab-Proxy']);
await browser.close();
