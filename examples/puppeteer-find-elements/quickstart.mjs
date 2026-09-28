// Run after npm ci. Starts only this packet's self-authored local HTTP fixture.
import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {startFixture} from './fixture.mjs';
import {launchBrowser} from './browser.mjs';
import {validateRecords} from './oracle.mjs';
const fixture=await startFixture();let browser;
try{
 browser=await launchBrowser();const page=await browser.newPage();
 const response=await page.goto(fixture.origin+'/catalog',{waitUntil:'load'});assert.equal(response.status(),200);
 await page.evaluate(()=>window.releaseCatalog()); // Fixture handshake; a real site loads its own data.
 await page.waitForFunction(()=>{
  const rows=[...document.querySelectorAll('#catalog > .card')];
  return rows.length===3&&rows.every(row=>row.querySelector('.title')?.textContent.trim()&&/^\d+\.\d{2}$/.test(row.querySelector('.price')?.textContent.trim()));
 },{timeout:5000});
 const records=await page.$$eval('#catalog > .card',cards=>cards.map(card=>({
  sku:card.dataset.sku,title:card.querySelector('.title').textContent.trim(),currency:card.querySelector('.price').dataset.currency,
  price:card.querySelector('.price').textContent.trim(),href:card.querySelector('.title').getAttribute('href'),
 })));
 validateRecords(records);const result={records};console.log(JSON.stringify(result,null,2));
 const output=process.argv[2]??'run_output/quickstart.json';await mkdir(dirname(output),{recursive:true});await writeFile(output,JSON.stringify(result,null,2)+'\n');
}finally{await browser?.close();await fixture.close();}
