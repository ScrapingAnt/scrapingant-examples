// Credential-free integration probe: discovery is separate from solving.
const {chromium} = require('playwright-extra');
const RecaptchaPlugin = require('puppeteer-extra-plugin-recaptcha');
const fs = require('node:fs');
chromium.use(RecaptchaPlugin());
(async () => {
  const started=Date.now();
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1200,height:850},locale:'en-US'});
  const result={method:'playwright-extra-recaptcha',version:'3.6.8',target:'https://www.google.com/recaptcha/api2/demo',browser:browser.version(),tested_at:new Date().toISOString(),paid_solve_attempted:false,server_accepted:false};
  try {
    const nav=await page.goto(result.target,{waitUntil:'domcontentloaded'});
    result.navigation_status=nav.status();
    await page.frameLocator('iframe[title="reCAPTCHA"]').locator('#recaptcha-anchor').waitFor({timeout:20000});
    const discovery=await page.findRecaptchas();
    result.discovered=discovery.captchas.map(c=>({vendor:c._vendor,sitekey:c.sitekey,type:c.type,hasResponseElement:c.hasResponseElement}));
    result.discovery_error=discovery.error || null;
    const solved=await page.solveRecaptchas();
    result.solve_error=solved.error || null;
    result.solution_count=solved.solutions.length;
    result.solved_count=solved.solved.length;
    result.expected_missing_provider_error=String(solved.error).includes('Please provide a solution provider');
    result.token_length=await page.locator('[name="g-recaptcha-response"]').inputValue().then(x=>x.length);
    await page.screenshot({path:'screenshots/extra-discovery.png'});
  } catch(e) {result.error=e.name;result.detail=e.message.slice(0,700);}
  finally {await browser.close();}
  result.elapsed_seconds=(Date.now()-started)/1000;
  console.log(JSON.stringify(result,null,2));
  process.exitCode=result.discovered?.length===1 && result.expected_missing_provider_error ? 0 : 1;
})();
