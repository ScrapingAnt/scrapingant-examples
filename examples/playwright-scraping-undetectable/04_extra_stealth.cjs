const { chromium } = require('playwright-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const { capture } = require('./common.cjs');

chromium.use(StealthPlugin());
capture(chromium, 'extra-stealth').catch(error => {
  console.error(error); process.exitCode = 1;
});
