// Supplemental screenshot audit; not part of the canonical repetition matrix.
const fs=require('fs'),path=require('path');
const {chromium}=require('playwright-extra');chromium.use(require('puppeteer-extra-plugin-stealth')());
const root=path.resolve(__dirname,'..'),out=path.join(root,'layout-audit','post-capture-check');fs.mkdirSync(out,{recursive:true});
const extract=new Function('return ('+fs.readFileSync(path.join(root,'scripts/extract.js'),'utf8')+')')();
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
await page.goto('https://www.browserscan.net/bot-detection',{waitUntil:'domcontentloaded',timeout:45000});await new Promise(r=>setTimeout(r,10000));
const result={snapshot:await page.evaluate(extract),layout:await page.evaluate(()=>({innerWidth,outerWidth,scrollX,body:document.body.getBoundingClientRect().toJSON(),documentWidth:document.documentElement.scrollWidth,strong:[...document.querySelectorAll('strong')].filter(x=>x.innerText.includes('Test Results')).map(x=>x.getBoundingClientRect().toJSON())}))};
result.beforeScreenshot=await page.evaluate(extract);
await page.screenshot({path:path.join(out,'extra-stealth-headless-full.png'),fullPage:true});
result.afterScreenshot=await page.evaluate(extract);
fs.writeFileSync(path.join(out,'extra-stealth-headless.json'),JSON.stringify(result,null,2)+'\n');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
