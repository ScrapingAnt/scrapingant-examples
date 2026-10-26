const response = await fetch('https://example.com/');
const html = await response.text();
const title = html.match(/<title>(.*?)<\/title>/)[1];
console.log(response.status, title);
