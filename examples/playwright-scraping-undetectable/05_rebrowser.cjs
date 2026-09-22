const { chromium } = require('rebrowser-playwright');
const { capture } = require('./common.cjs');

capture(chromium, 'rebrowser').catch(error => {
  console.error(error); process.exitCode = 1;
});
