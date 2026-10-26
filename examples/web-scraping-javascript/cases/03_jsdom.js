import { JSDOM } from 'jsdom';

const response = await fetch('https://books.toscrape.com/');
const { document } = new JSDOM(await response.text()).window;

const prices = [...document.querySelectorAll('p.price_color')].map((p) => p.textContent);
console.log(prices.length, 'prices, first three:', prices.slice(0, 3).join(' '));
