import * as cheerio from 'cheerio';

// quotes.toscrape.com/js/ builds its quotes with JavaScript after the page loads
const response = await fetch('https://quotes.toscrape.com/js/');
const $ = cheerio.load(await response.text());
console.log(response.status, $('div.quote').length, 'quotes in the raw HTML');
