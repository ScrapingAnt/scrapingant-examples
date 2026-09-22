() => {
 const labels=['Webdriver','User-Agent','CDP','Navigator'];
 const summary=Array.from(document.querySelectorAll('li')).filter(e=>labels.includes(e.innerText.trim())).map(e=>{
   const label=e.querySelector('div');
   return {label:e.innerText.trim(),class:label?.className,color:label?getComputedStyle(label).color:null};
 });
 const title=Array.from(document.querySelectorAll('strong')).find(e=>e.textContent.trim()==='Test Results:');
 const verdict=title?.parentElement.innerText.trim()||null;
 const rows=Array.from(document.querySelectorAll('tr')).map(e=>({text:e.innerText.trim(),cells:Array.from(e.querySelectorAll('td,th')).map(c=>({text:c.innerText.trim(),class:c.className,color:getComputedStyle(c).color,background:getComputedStyle(c).backgroundColor}))}));
 return {title:document.title,url:location.href,verdict,summary,rows,fixture:document.querySelector('#result')?.textContent||null};
}
