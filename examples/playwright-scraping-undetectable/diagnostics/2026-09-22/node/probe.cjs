const fs=require('fs');const path=require('path');const {pathToFileURL}=require('url');
const root=path.resolve(__dirname,'..');const [approach,mode,repString]=process.argv.slice(2);const rep=Number(repString);const key=`${approach}-${mode}-${rep}`;
const result={key,approach,mode,repetition:rep,timestamp:new Date().toISOString(),node:process.version,pages:[]};
// Compile our own shared extractor as a function: Node treats a string as an expression, not a callback.
const extract=new Function('return ('+fs.readFileSync(path.join(root,'scripts/extract.js'),'utf8')+')')();
(async()=>{
 let browser;
 try{
  let chromium;
  if(approach==='extra-stealth'){
   chromium=require('playwright-extra').chromium;
   chromium.use(require('puppeteer-extra-plugin-stealth')());
  }else chromium=require('rebrowser-playwright').chromium;
  browser=await chromium.launch({channel:'chrome',headless:mode==='headless'});
  result.browser_version=browser.version();
  const sites=[['local',pathToFileURL(path.join(root,'fixtures/properties.html')).href],['browserscan','https://www.browserscan.net/bot-detection']];
  if(rep===1)sites.push(['sannysoft','https://bot.sannysoft.com/']);
  for(const [site,url] of sites){
   const item={site,url};const start=Date.now();const context=await browser.newContext({viewport:{width:1440,height:1000}});
   try{
    const page=await context.newPage();const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});item.http_status=response?.status()??null;
    if(site==='local')item.properties=JSON.parse(await page.locator('#result').innerText());
    else{
     await new Promise(r=>setTimeout(r,6000));item.snapshot_6s=await page.evaluate(extract);
     await new Promise(r=>setTimeout(r,4000));item.snapshot_10s=await page.evaluate(extract);
     item.screenshot=`screenshots/${key}-${site}.png`;await page.screenshot({path:path.join(root,item.screenshot),fullPage:false});
     if(site==='browserscan'&&(!item.snapshot_10s.verdict||item.snapshot_10s.summary.length!==4))throw new Error('Missing BrowserScan results; not a pass');
     if(site==='sannysoft'&&item.snapshot_10s.rows.length<6)throw new Error('Missing Sannysoft table; not a pass');
    }
   }catch(e){item.error=String(e)}finally{item.elapsed_seconds=(Date.now()-start)/1000;result.pages.push(item);await context.close();console.log(key,site,item.error?'ERROR':'captured');}
  }
 }catch(e){result.launch_error=String(e);console.log(key,result.launch_error)}finally{if(browser)await browser.close();fs.writeFileSync(path.join(root,'results',`${key}.json`),JSON.stringify(result,null,2)+'\n');}
})();
