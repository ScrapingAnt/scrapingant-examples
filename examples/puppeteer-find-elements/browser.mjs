import puppeteer from 'puppeteer';
import os from 'node:os';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
const require=createRequire(import.meta.url);
export async function launchBrowser(){
 const disabled=process.env.PUPPETEER_NO_SANDBOX==='1';
 if(disabled&&process.env.CI!=='true') throw Error('Sandbox opt-out requires explicit CI=true');
 return puppeteer.launch({headless:true,args:disabled?['--no-sandbox']:[]});
}
export async function environment(browser){return {node:process.version,puppeteer:require('puppeteer/package.json').version,html_to_text:JSON.parse(readFileSync(new URL('./node_modules/html-to-text/package.json',import.meta.url),'utf8')).version,browser:await browser.version(),os:os.type(),os_release:os.release(),architecture:os.arch(),sandbox_disabled:process.env.PUPPETEER_NO_SANDBOX==='1'};}
// Functions passed to evaluate are self-contained: no Node lexical bindings.
export const projectCard = card => ({sku:card.getAttribute('data-sku'),title:card.querySelector('.title').textContent.trim(),currency:card.querySelector('.price').getAttribute('data-currency'),price:card.querySelector('.price').textContent.trim(),href:card.querySelector('.title').getAttribute('href')});
export const projectCards = cards => cards.map(card=>({sku:card.getAttribute('data-sku'),title:card.querySelector('.title').textContent.trim(),currency:card.querySelector('.price').getAttribute('data-currency'),price:card.querySelector('.price').textContent.trim(),href:card.querySelector('.title').getAttribute('href')}));
export async function populated(page){
 await page.waitForFunction(()=>{
  const cards=[...document.querySelectorAll('#catalog > .card')];
  return cards.length===3&&cards.every(card=>card.querySelector('.title')?.textContent.trim()&&/^\d+\.\d{2}$/.test(card.querySelector('.price')?.textContent.trim()));
 },{timeout:5000});
}
export async function navigate(page,fixture){
 const response=await page.goto(fixture.origin+'/catalog',{waitUntil:'load'});
 if(response.status()!==200)throw Error('Fixture navigation failed');
 return response.status();
}
export async function release(page){await page.evaluate(()=>window.releaseCatalog());await populated(page);}
