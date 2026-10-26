import * as cheerio from 'cheerio';

const response = await fetch('https://books.toscrape.com/');
const $ = cheerio.load(await response.text());

const books = $('article.product_pod').map((_, el) => ({
  title: $(el).find('h3 a').attr('title'),
  price: $(el).find('p.price_color').text(),
})).get();

console.log(books.length, 'books');
console.log(books.slice(0, 3));
