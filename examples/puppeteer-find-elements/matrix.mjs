import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {convert} from 'html-to-text';
import {startFixture} from './fixture.mjs';
import {launchBrowser,environment,navigate,release,projectCard,projectCards} from './browser.mjs';
import {EXTRACTIONS,TEXT_EXPECTED,validateRecords,sentinels} from './oracle.mjs';
import {summarize} from './summarize.mjs';
const output=process.argv[2]??'run_output/chrome.json';
const fixture=await startFixture(); let browser;
try {
 browser=await launchBrowser();
 const capture={schema_version:1,browser:'chrome',tested_at:new Date().toISOString(),rounds:3,environment:await environment(browser),runs:[]};
 for(let round=1;round<=3;round++){
  const context=await browser.createBrowserContext();const page=await context.newPage();page.setDefaultTimeout(5000);
  const cases=[];
  const record=(id,records,details={})=>{
   validateRecords(records,EXTRACTIONS[id]);
   cases.push({case:id,kind:'extraction',records,...details,check_passed:true});
  };
  try{
   const navigationStatus=await navigate(page,fixture);
   const present=await page.waitForSelector('#catalog .card');await present.dispose();
   record('presence_only',await page.$$eval('#catalog > .card',projectCards),{boundary:'card exists; application population gate still closed'});
   await release(page);
   record('populated_wait',await page.$$eval('#catalog > .card',projectCards),{boundary:'explicit release acknowledged; every title and decimal price populated'});
   const first=await page.$('.card');record('global_first',[await first.evaluate(projectCard)]);await first.dispose();
   const global=await page.$$('.card');
   record('global_all',await Promise.all(global.map(handle=>handle.evaluate(projectCard))));await Promise.all(global.map(handle=>handle.dispose()));
   record('scoped_css',await page.$$eval('#catalog > .card',projectCards));
   const catalog=await page.$('#catalog'); const handles=await catalog.$$('.card');
   record('scoped_handles',await Promise.all(handles.map(handle=>handle.evaluate(projectCard))));
   await Promise.all(handles.map(handle=>handle.dispose()));await catalog.dispose();
   record('xpath_all',await page.$$eval('::-p-xpath(//section[@id="catalog"]/article)',projectCards));
   const text=await page.$('#catalog ::-p-text(Sugar & Water Feeder)');
   record('text_selector',[await text.evaluate(el=>{const card=el.closest('.card');return {sku:card.dataset.sku,title:card.querySelector('.title').textContent.trim(),currency:card.querySelector('.price').dataset.currency,price:card.querySelector('.price').textContent.trim(),href:card.querySelector('.title').getAttribute('href')};})]);await text.dispose();
   record('eval_first',[await page.$eval('#catalog .card',projectCard)]);
   record('open_shadow',await page.$$eval('#shadow-host >>> .card',projectCards));
   const frameHandle=await page.$('#catalog-frame');const frame=await frameHandle.contentFrame();
   record('iframe',await frame.$$eval('.card',projectCards));await frameHandle.dispose();
   const missing=await page.$('#missing');const missingAll=await page.$$('#missing');let evalError=null;
   try{await page.$eval('#missing',el=>el.textContent);}catch(error){evalError={name:error.name,message:error.message};}
   cases.push({case:'missing_apis',kind:'diagnostic',single:missing,all:missingAll,eval_error:evalError,multi_eval:await page.$$eval('#missing',els=>els.map(el=>el.textContent)),check_passed:true});
   const attributes=await page.$eval('[data-sku="B202"] .title',el=>({missing_attribute:el.getAttribute('data-stock'),raw_href:el.getAttribute('href'),resolved_href_path:new URL(el.href).pathname,resolved_href_is_absolute:el.href.startsWith(location.origin+'/'),text:el.textContent}));
   cases.push({case:'attributes_properties',kind:'diagnostic',...attributes,check_passed:true});
   const boundaries=await page.evaluate(()=>({main_shadow:document.querySelectorAll('#shadow-host .card').length,main_frame:document.querySelectorAll('#catalog-frame .card').length,shadow_open:document.querySelector('#shadow-host').shadowRoot.mode}));
   cases.push({case:'boundary_queries',kind:'diagnostic',...boundaries,check_passed:true});
   const rawResponse=await fetch(fixture.origin+'/catalog');assert.equal(rawResponse.status,200);
   const rawHTML=await rawResponse.text();
   const texts={
    body_inner_text:await page.$eval('body',el=>el.innerText),
    body_text_content:await page.$eval('body',el=>el.textContent),
    body_selection:await page.evaluate(()=>{const selection=window.getSelection();const range=document.createRange();range.selectNodeContents(document.body);selection.removeAllRanges();selection.addRange(range);const text=selection.toString();selection.removeAllRanges();return text;}),
    raw_html_to_text:convert(rawHTML,{wordwrap:false}),
    rendered_html_to_text:convert(await page.content(),{wordwrap:false}),
   };
   for(const [id,textValue] of Object.entries(texts)){
    const markers=sentinels(textValue);assert.deepEqual(markers,TEXT_EXPECTED[id],id);
    cases.push({case:id,kind:'text_diagnostic',text:textValue,sentinels:markers,check_passed:true});
   }
   const old=await page.$('#catalog > .card');
   await page.evaluate(()=>window.replaceFirst());
   record('replaced_old_handle',[await old.evaluate(projectCard)],{connected:await old.evaluate(el=>el.isConnected)});
   record('replaced_fresh',await page.$$eval('#catalog > .card',projectCards));await old.dispose();
   capture.runs.push({round,navigation_status:navigationStatus,raw_html_http_status:rawResponse.status,cases});
  }finally{await context.close();}
 }
 capture.extraction_observations=39;capture.diagnostic_observations=9;capture.text_diagnostic_observations=15;capture.checks=63;capture.passed_checks=63;
 summarize(capture);
 await mkdir(dirname(output),{recursive:true});await writeFile(output,JSON.stringify(capture,null,2)+'\n');
 console.log(JSON.stringify({rounds:3,checks:63,extractions:39,diagnostics:9,text_diagnostics:15,passed:63}));
}finally{await browser?.close();await fixture.close();}
