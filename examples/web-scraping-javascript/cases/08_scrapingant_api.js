import * as cheerio from 'cheerio';

const params = new URLSearchParams({
  url: 'https://quotes.toscrape.com/js/',
  'x-api-key': process.env.SCRAPINGANT_API_KEY,
}); // browser=true is the default: the page renders in headless Chrome
const response = await fetch(`https://api.scrapingant.com/v2/general?${params}`);
const $ = cheerio.load(await response.text());

console.log(response.status, response.headers.get('ant-page-status-code'), $('div.quote').length, 'quotes');
console.log($('div.quote .author').first().text(), '|', $('div.quote .text').first().text().slice(0, 50));
