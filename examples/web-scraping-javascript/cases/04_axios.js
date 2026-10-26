import axios from 'axios';
import * as cheerio from 'cheerio';

const { status, data } = await axios.get('https://books.toscrape.com/catalogue/page-2.html', { timeout: 10000 });
const $ = cheerio.load(data);
console.log(status, $('article.product_pod').length, 'books on page 2,', $('li.current').text().trim());
