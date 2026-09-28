import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {convert} from 'html-to-text';
import {startFixture} from './fixture.mjs';
import {launchBrowser} from './browser.mjs';
import {TEXT_EXPECTED,sentinels} from './oracle.mjs';
const fixture=await startFixture();let browser;
try{
 browser=await launchBrowser();const page=await browser.newPage();
 await page.goto(fixture.origin+'/catalog',{waitUntil:'load'});
 await page.evaluate(()=>window.releaseCatalog());
 await page.waitForFunction(()=>document.querySelector('#catalog')?.dataset.ready==='yes',{timeout:5000});
 const rawResponse=await fetch(fixture.origin+'/catalog');assert.equal(rawResponse.status,200);
 const rawHTML=await rawResponse.text();
 const texts={
  body_inner_text:await page.$eval('body',body=>body.innerText),
  body_text_content:await page.$eval('body',body=>body.textContent),
  body_selection:await page.evaluate(()=>{
   const selection=window.getSelection();const range=document.createRange();range.selectNodeContents(document.body);
   selection.removeAllRanges();selection.addRange(range);const text=selection.toString();selection.removeAllRanges();return text;
  }),
  raw_html_to_text:convert(rawHTML,{wordwrap:false}),
  rendered_html_to_text:convert(await page.content(),{wordwrap:false}),
 };
 const result=Object.fromEntries(Object.entries(texts).map(([method,text])=>{const markers=sentinels(text);assert.deepEqual(markers,TEXT_EXPECTED[method]);return [method,{text,sentinels:markers}];}));
 console.log(JSON.stringify(result,null,2));const output=process.argv[2]??'run_output/text-quickstart.json';await mkdir(dirname(output),{recursive:true});await writeFile(output,JSON.stringify(result,null,2)+'\n');
}finally{await browser?.close();await fixture.close();}
