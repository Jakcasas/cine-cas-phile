import http from 'node:http';
import {readFileSync,existsSync,statSync} from 'node:fs';
import path from 'node:path';
import {handler} from '../netlify/functions/api.mjs';
const root=path.resolve('dist/netlify');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wasm':'application/wasm','.svg':'image/svg+xml','.png':'image/png','.ttf':'font/ttf'};
http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    if(url.pathname.startsWith('/api/')){let body='';for await(const data of req){body+=data;if(body.length>1_000_000){res.writeHead(413);res.end();return;}}
      const result=await handler({path:url.pathname,httpMethod:req.method,queryStringParameters:Object.fromEntries(url.searchParams),body});res.writeHead(result.statusCode,result.headers);res.end(result.body);return;}
    let file=path.resolve(root,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
    if(url.pathname==='/vision-check.html')file=path.resolve('runtime/netlify-check.html');
    if(url.pathname==='/scene-example.png')file=path.resolve('runtime/scene-example.png');
    const allowed=file.startsWith(root+path.sep)||file===path.resolve('runtime/netlify-check.html')||file===path.resolve('runtime/scene-example.png');
    if(!allowed||!existsSync(file)||!statSync(file).isFile()){res.writeHead(404);res.end('Not found');return;}
    const bytes=readFileSync(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Content-Length':bytes.length});res.end(bytes);
  }catch(error){res.writeHead(500);res.end(error.message);}
}).listen(8001,'127.0.0.1',()=>console.log('Netlify preview http://127.0.0.1:8001'));
