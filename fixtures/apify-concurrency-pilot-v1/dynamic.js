'use strict';
const target=document.querySelector('#target');
async function reveal(){
 const response=await fetch(target.dataset.source,{cache:'no-store'});
 if(!response.ok)throw Error('Owned fixture data failed');
 const row=await response.json();const product=document.createElement('article');product.className='product';
 for(const [key,value] of Object.entries(row))product.dataset[key.replace(/_([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);
 const title=document.createElement('h1');title.textContent=row.name;product.append(title);target.replaceChildren(product);
 document.documentElement.dataset.ready='true';
}
if(target.dataset.mode==='expand'||target.dataset.mode==='load-more')document.querySelector('#reveal').addEventListener('click',()=>reveal());
else setTimeout(reveal,target.dataset.mode.startsWith('delay-')?Number(target.dataset.mode.slice(6)):0);
