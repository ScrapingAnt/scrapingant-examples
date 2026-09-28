import http from 'node:http';
import {readFile} from 'node:fs/promises';
export async function startFixture(){
 const catalog=await readFile(new URL('./fixtures/catalog.html',import.meta.url),'utf8');
 const frame=await readFile(new URL('./fixtures/frame.html',import.meta.url),'utf8');
 const server=http.createServer((request,response)=>{
  const path=new URL(request.url,'http://localhost').pathname;
  const body=path==='/catalog'?catalog:path==='/frame'?frame:null;
  response.writeHead(body?200:404,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});
  response.end(body??'Not found');
 });
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 return {origin:`http://127.0.0.1:${server.address().port}`,catalog,
  close:()=>new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()))};
}
