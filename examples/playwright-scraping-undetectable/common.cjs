const path = require('node:path');
const { pathToFileURL } = require('node:url');
exports.capture = async (chromium, approach) => {
  const opts = { headless: true };
  if (process.env.BROWSER_CHANNEL) opts.channel = process.env.BROWSER_CHANNEL;
  const browser = await chromium.launch(opts);
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    await page.goto(pathToFileURL(path.join(__dirname, 'fixtures/properties.html')).href,
      { waitUntil: 'domcontentloaded', timeout: 15000 });
    const value = JSON.parse(await page.locator('#result').innerText({ timeout: 15000 }));
    if (typeof value.webdriver !== 'boolean' || JSON.stringify(value.viewport) !== '[1440,1000]')
      throw new Error('Invalid fixture capture');
    console.log(JSON.stringify({ approach, browser: browser.version(),
      webdriver: value.webdriver, platform: value.platform }));
  } finally { await browser.close(); }
};
