'use strict';
setTimeout(async()=>{
 const target=document.querySelector('#content-target');const response=await fetch(target.dataset.source,{cache:'no-store'});
 if(!response.ok)throw Error('Owned content fixture failed');
 const payload=await response.json();const parsed=new DOMParser().parseFromString(payload.html,'text/html');
 target.replaceChildren(...parsed.body.childNodes);document.documentElement.dataset.ready='true';
},2000);
