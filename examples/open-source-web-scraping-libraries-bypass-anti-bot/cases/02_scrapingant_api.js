// The same two signals for a page loaded by the ScrapingAnt API.
// js_snippet runs in the page and writes navigator.webdriver into the HTML we get back.
const snippet = "document.body.dataset.webdriver = String(navigator.webdriver)";
const params = new URLSearchParams({
  url: 'https://httpbin.org/headers',
  'x-api-key': process.env.SCRAPINGANT_API_KEY,
  js_snippet: Buffer.from(snippet).toString('base64'),
});
const response = await fetch(`https://api.scrapingant.com/v2/general?${params}`);
const html = await response.text();

console.log(response.status, response.headers.get('ant-page-status-code'));
console.log('User-Agent:', html.match(/"User-Agent":\s*"([^"]+)"/)[1]);
console.log('navigator.webdriver:', html.match(/data-webdriver="([^"]+)"/)[1]);
